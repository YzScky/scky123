from __future__ import annotations

import argparse
import re
from dataclasses import dataclass
from typing import List

import pandas as pd
import yfinance as yf


@dataclass
class AnalysisResult:
    symbol: str
    latest_price: float
    ma20: float
    ma60: float
    rsi14: float
    return_5d: float
    return_20d: float
    vol_20d: float
    support_20d: float
    resistance_20d: float
    trend_score: int
    momentum_score: int
    risk_score: int
    total_score: int
    confidence: int
    stance: str
    summary: str
    risks: List[str]


def _compute_rsi(close: pd.Series, period: int = 14) -> pd.Series:
    delta = close.diff()
    gain = delta.clip(lower=0)
    loss = -delta.clip(upper=0)
    avg_gain = gain.ewm(alpha=1 / period, min_periods=period, adjust=False).mean()
    avg_loss = loss.ewm(alpha=1 / period, min_periods=period, adjust=False).mean()
    rs = avg_gain / avg_loss.replace(0, pd.NA)
    rsi = 100 - (100 / (1 + rs))
    return rsi.fillna(50)


def _clip_score(value: float) -> int:
    return int(max(0, min(100, round(value))))


def normalize_symbol(raw: str) -> str:
    value = raw.strip().upper()
    if not value:
        raise ValueError("股票代码为空。")

    # sh600519 / sz000001
    if value.startswith("SH") and len(value) == 8 and value[2:].isdigit():
        value = f"{value[2:]}.SS"
    elif value.startswith("SZ") and len(value) == 8 and value[2:].isdigit():
        value = f"{value[2:]}.SZ"

    # 600519.SH -> 600519.SS (yfinance convention)
    if value.endswith(".SH"):
        value = value[:-3] + ".SS"

    # 6-digit mainland code without suffix
    if re.fullmatch(r"\d{6}", value):
        if value[0] in {"6", "9"}:
            value = f"{value}.SS"
        elif value[0] in {"0", "2", "3"}:
            value = f"{value}.SZ"
        elif value[0] in {"4", "8"}:
            value = f"{value}.BJ"
        else:
            raise ValueError("无法识别该A股代码，请使用如 600519 或 000001。")

    # 4/5-digit Hong Kong code without suffix
    if re.fullmatch(r"\d{4,5}", value):
        value = f"{value.zfill(4)}.HK"

    if not re.fullmatch(r"[A-Z0-9.\-]{1,12}", value):
        raise ValueError("股票代码格式不合法。示例: 600519, 000001, 0700, AAPL")
    return value


def analyze_stock(symbol: str) -> AnalysisResult:
    symbol = normalize_symbol(symbol)

    df = yf.Ticker(symbol).history(period="1y", interval="1d", auto_adjust=True)
    if df.empty or "Close" not in df:
        raise ValueError(f"没有拿到 {symbol} 的行情数据。")
    if len(df) < 90:
        raise ValueError(f"{symbol} 数据不足（需要至少 90 个交易日）。")

    close = df["Close"].dropna()
    returns = close.pct_change()
    rsi = _compute_rsi(close, 14)

    latest_price = float(close.iloc[-1])
    ma20 = float(close.rolling(20).mean().iloc[-1])
    ma60 = float(close.rolling(60).mean().iloc[-1])
    rsi14 = float(rsi.iloc[-1])
    return_5d = float((close.iloc[-1] / close.iloc[-6]) - 1)
    return_20d = float((close.iloc[-1] / close.iloc[-21]) - 1)
    vol_20d = float(returns.tail(20).std() * (252**0.5))
    support_20d = float(close.tail(20).min())
    resistance_20d = float(close.tail(20).max())

    if latest_price > ma20 > ma60:
        trend_score = 82
        trend_text = "多头趋势"
    elif latest_price < ma20 < ma60:
        trend_score = 24
        trend_text = "空头趋势"
    elif latest_price > ma60:
        trend_score = 64
        trend_text = "中期偏强"
    else:
        trend_score = 40
        trend_text = "中期偏弱"

    momentum_raw = 50 + (return_20d * 220) + (return_5d * 120)
    if 45 <= rsi14 <= 60:
        momentum_raw += 5
    if rsi14 >= 75 or rsi14 <= 25:
        momentum_raw -= 8
    momentum_score = _clip_score(momentum_raw)

    risk_raw = 30 + (vol_20d * 120)
    if latest_price < ma60:
        risk_raw += 10
    if abs(return_5d) > 0.08:
        risk_raw += 8
    if rsi14 > 75 or rsi14 < 25:
        risk_raw += 8
    risk_score = _clip_score(risk_raw)

    total_score = _clip_score(
        (0.45 * trend_score) + (0.35 * momentum_score) + (0.20 * (100 - risk_score))
    )

    disagreement = abs(trend_score - momentum_score)
    confidence = _clip_score(72 - (disagreement * 0.35) - (risk_score * 0.18))
    confidence = max(confidence, 35)

    if total_score >= 65:
        stance = "看多"
    elif total_score <= 35:
        stance = "看空"
    else:
        stance = "中性"

    risks: List[str] = []
    if risk_score >= 70:
        risks.append("波动偏高，仓位应控制")
    if latest_price < ma60:
        risks.append("价格在 MA60 下方，中期压力较大")
    if rsi14 >= 75:
        risks.append("RSI 过热，短线回撤风险上升")
    if rsi14 <= 25:
        risks.append("RSI 过冷，走势可能继续弱势")
    if abs(return_5d) > 0.08:
        risks.append("近5日振幅过大，短线不稳定")
    if not risks:
        risks.append("当前风险可控，仍需设置止损")

    summary = f"{trend_text}，20日动量{(return_20d * 100):+.2f}%，风险分 {risk_score}/100。"

    return AnalysisResult(
        symbol=symbol,
        latest_price=latest_price,
        ma20=ma20,
        ma60=ma60,
        rsi14=rsi14,
        return_5d=return_5d,
        return_20d=return_20d,
        vol_20d=vol_20d,
        support_20d=support_20d,
        resistance_20d=resistance_20d,
        trend_score=trend_score,
        momentum_score=momentum_score,
        risk_score=risk_score,
        total_score=total_score,
        confidence=confidence,
        stance=stance,
        summary=summary,
        risks=risks,
    )


def format_report(result: AnalysisResult) -> str:
    return (
        f"【{result.symbol} 分析】\n"
        "仅供参考，不构成投资建议。\n\n"
        f"结论: {result.stance} | 评分 {result.total_score}/100 | 置信度 {result.confidence}%\n"
        f"趋势/动量/风险: {result.trend_score}/{result.momentum_score}/{result.risk_score}\n\n"
        f"最新价: {result.latest_price:.2f}\n"
        f"MA20 / MA60: {result.ma20:.2f} / {result.ma60:.2f}\n"
        f"RSI(14): {result.rsi14:.1f}\n"
        f"近5日 / 20日: {result.return_5d * 100:+.2f}% / {result.return_20d * 100:+.2f}%\n"
        f"20日年化波动估计: {result.vol_20d * 100:.2f}%\n"
        f"关键位(20日): 支撑 {result.support_20d:.2f} | 阻力 {result.resistance_20d:.2f}\n\n"
        f"摘要: {result.summary}\n"
        f"风险提示: {'；'.join(result.risks[:3])}"
    )


def format_risk_report(result: AnalysisResult) -> str:
    return (
        f"【{result.symbol} 风险报告】\n"
        "仅供参考，不构成投资建议。\n\n"
        f"风险评分: {result.risk_score}/100 (越高风险越高)\n"
        f"波动率(20日年化): {result.vol_20d * 100:.2f}%\n"
        f"RSI(14): {result.rsi14:.1f}\n"
        f"近5日涨跌: {result.return_5d * 100:+.2f}%\n"
        f"MA60位置: {'上方' if result.latest_price >= result.ma60 else '下方'}\n"
        f"风险要点: {'；'.join(result.risks[:4])}"
    )


def format_compare_report(left: AnalysisResult, right: AnalysisResult) -> str:
    winner = left if left.total_score >= right.total_score else right
    return (
        f"【对比 {left.symbol} vs {right.symbol}】\n"
        "仅供参考，不构成投资建议。\n\n"
        f"{left.symbol}: 评分 {left.total_score} | 结论 {left.stance} | 风险 {left.risk_score}\n"
        f"{right.symbol}: 评分 {right.total_score} | 结论 {right.stance} | 风险 {right.risk_score}\n\n"
        f"相对更优: {winner.symbol}\n"
        f"{left.symbol} 摘要: {left.summary}\n"
        f"{right.symbol} 摘要: {right.summary}"
    )


def _main() -> None:
    parser = argparse.ArgumentParser(description="股票分析 CLI")
    parser.add_argument("symbol", help="股票代码，如 AAPL")
    args = parser.parse_args()

    result = analyze_stock(args.symbol)
    print(format_report(result))


if __name__ == "__main__":
    _main()
