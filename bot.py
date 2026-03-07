from __future__ import annotations

import asyncio
import json
import logging
import os
import time
from pathlib import Path
from typing import Dict, List, Tuple

from dotenv import load_dotenv
from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes

from stock_agent import (
    analyze_stock,
    format_compare_report,
    format_report,
    format_risk_report,
    normalize_symbol,
)

logging.basicConfig(
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger(__name__)

CACHE_TTL_SECONDS = 120
WATCHLIST_FILE = Path(__file__).resolve().parent / "watchlists.json"

# symbol -> (timestamp, analysis_result)
analysis_cache: Dict[str, Tuple[float, object]] = {}
cache_lock = asyncio.Lock()
watchlist_lock = asyncio.Lock()


def _load_watchlists_sync() -> Dict[str, List[str]]:
    if not WATCHLIST_FILE.exists():
        return {}
    try:
        data = json.loads(WATCHLIST_FILE.read_text(encoding="utf-8"))
    except Exception:
        return {}
    if not isinstance(data, dict):
        return {}

    clean: Dict[str, List[str]] = {}
    for chat_id, symbols in data.items():
        if isinstance(symbols, list):
            clean[chat_id] = [str(s).upper() for s in symbols if isinstance(s, str)]
    return clean


def _save_watchlists_sync(data: Dict[str, List[str]]) -> None:
    WATCHLIST_FILE.write_text(
        json.dumps(data, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


async def _analyze_cached(symbol: str):
    now = time.time()
    async with cache_lock:
        cached = analysis_cache.get(symbol)
        if cached and (now - cached[0]) <= CACHE_TTL_SECONDS:
            return cached[1]

    result = await asyncio.to_thread(analyze_stock, symbol)
    async with cache_lock:
        analysis_cache[symbol] = (time.time(), result)
    return result


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.message.reply_text(
        "指令示例:\n"
        "/analyze 600519\n"
        "/risk 000001\n"
        "/compare 600519 000858\n\n"
        "/watch 0700\n"
        "/unwatch 0700\n"
        "/list\n"
        "/scan\n\n"
        "代码支持: 600519 / 000001 / 0700 / AAPL（会自动补交易所后缀）\n"
        "说明: 仅供参考，不构成投资建议。"
    )


async def analyze(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not context.args:
        await update.message.reply_text("用法: /analyze 股票代码，例如 /analyze TSLA")
        return

    try:
        symbol = normalize_symbol(context.args[0])
        await update.message.reply_text(f"正在分析 {symbol} ...")
        result = await _analyze_cached(symbol)
        await update.message.reply_text(format_report(result))
    except Exception as exc:
        logger.exception("Analyze failed")
        await update.message.reply_text(f"分析失败: {exc}")


async def risk(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not context.args:
        await update.message.reply_text("用法: /risk 股票代码，例如 /risk TSLA")
        return

    try:
        symbol = normalize_symbol(context.args[0])
        await update.message.reply_text(f"正在生成 {symbol} 风险报告 ...")
        result = await _analyze_cached(symbol)
        await update.message.reply_text(format_risk_report(result))
    except Exception as exc:
        logger.exception("Risk failed")
        await update.message.reply_text(f"风险报告失败: {exc}")


async def compare(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if len(context.args) < 2:
        await update.message.reply_text(
            "用法: /compare 股票1 股票2，例如 /compare AAPL MSFT"
        )
        return

    try:
        left = normalize_symbol(context.args[0])
        right = normalize_symbol(context.args[1])
        await update.message.reply_text(f"正在对比 {left} 和 {right} ...")
        left_result, right_result = await asyncio.gather(
            _analyze_cached(left),
            _analyze_cached(right),
        )
        await update.message.reply_text(format_compare_report(left_result, right_result))
    except Exception as exc:
        logger.exception("Compare failed")
        await update.message.reply_text(f"对比失败: {exc}")


async def watch(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not context.args:
        await update.message.reply_text("用法: /watch 股票代码，例如 /watch NVDA")
        return

    try:
        symbol = normalize_symbol(context.args[0])
        chat_id = str(update.effective_chat.id)
        async with watchlist_lock:
            data = _load_watchlists_sync()
            symbols = set(data.get(chat_id, []))
            symbols.add(symbol)
            data[chat_id] = sorted(symbols)
            _save_watchlists_sync(data)
        await update.message.reply_text(f"已加入关注: {symbol}")
    except Exception as exc:
        logger.exception("Watch failed")
        await update.message.reply_text(f"设置关注失败: {exc}")


async def unwatch(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not context.args:
        await update.message.reply_text("用法: /unwatch 股票代码，例如 /unwatch NVDA")
        return

    try:
        symbol = normalize_symbol(context.args[0])
        chat_id = str(update.effective_chat.id)
        async with watchlist_lock:
            data = _load_watchlists_sync()
            symbols = set(data.get(chat_id, []))
            if symbol in symbols:
                symbols.remove(symbol)
            data[chat_id] = sorted(symbols)
            _save_watchlists_sync(data)
        await update.message.reply_text(f"已取消关注: {symbol}")
    except Exception as exc:
        logger.exception("Unwatch failed")
        await update.message.reply_text(f"取消关注失败: {exc}")


async def list_watch(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    try:
        chat_id = str(update.effective_chat.id)
        async with watchlist_lock:
            data = _load_watchlists_sync()
            symbols = data.get(chat_id, [])
        if not symbols:
            await update.message.reply_text("当前没有关注标的。可用 /watch TSLA 添加。")
            return
        await update.message.reply_text("关注列表:\n" + "\n".join(f"- {s}" for s in symbols))
    except Exception as exc:
        logger.exception("List watch failed")
        await update.message.reply_text(f"读取关注列表失败: {exc}")


async def scan_watch(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    try:
        chat_id = str(update.effective_chat.id)
        async with watchlist_lock:
            data = _load_watchlists_sync()
            symbols = data.get(chat_id, [])
        if not symbols:
            await update.message.reply_text("当前没有关注标的。可用 /watch TSLA 添加。")
            return

        symbols = symbols[:8]
        await update.message.reply_text(
            f"正在扫描关注列表（{len(symbols)}个）: {', '.join(symbols)}"
        )

        results = await asyncio.gather(
            *[_analyze_cached(s) for s in symbols], return_exceptions=True
        )
        lines = ["【关注扫描】仅供参考，不构成投资建议。", ""]
        for symbol, result in zip(symbols, results):
            if isinstance(result, Exception):
                lines.append(f"{symbol}: 失败 ({result})")
            else:
                lines.append(
                    f"{symbol}: {result.stance} | 评分 {result.total_score} | 风险 {result.risk_score}"
                )
        await update.message.reply_text("\n".join(lines))
    except Exception as exc:
        logger.exception("Scan watch failed")
        await update.message.reply_text(f"扫描失败: {exc}")


def main() -> None:
    load_dotenv()
    token = os.getenv("TELEGRAM_BOT_TOKEN", "").strip()
    if not token:
        raise RuntimeError("未设置 TELEGRAM_BOT_TOKEN。请先配置 .env。")

    app = Application.builder().token(token).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("analyze", analyze))
    app.add_handler(CommandHandler("risk", risk))
    app.add_handler(CommandHandler("compare", compare))
    app.add_handler(CommandHandler("watch", watch))
    app.add_handler(CommandHandler("unwatch", unwatch))
    app.add_handler(CommandHandler("list", list_watch))
    app.add_handler(CommandHandler("scan", scan_watch))
    app.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main()
