# Stock Analysis Bot (Telegram + OpenClaw)

## 1) Local setup

```bash
cd /Users/qinzimu/Documents/Playground
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
```

Edit `.env` and set:

```env
TELEGRAM_BOT_TOKEN=your_real_bot_token
```

## 2) Test the analysis CLI first

```bash
source .venv/bin/activate
python stock_agent.py AAPL
```

## 3) Run Telegram bot directly

```bash
source .venv/bin/activate
python bot.py
```

Then in Telegram:

```text
/start
/analyze 600519
/risk 000001
/compare 600519 000858
/watch 0700
/unwatch 0700
/list
/scan
```

`/scan` 会快速返回你关注列表里（最多 8 个标的）的简版评分结果。
代码支持自动识别并补后缀，如 `600519 -> 600519.SS`、`000001 -> 000001.SZ`、`0700 -> 0700.HK`。
分析结果包含板块维度：所属板块、板块强度(涨跌幅)、板块主力资金流向。

## 4) OpenClaw integration (command mode)

Use this script as the command OpenClaw executes:

```bash
/Users/qinzimu/Documents/Playground/openclaw_stock_command.sh {{ticker}}
```

Recommended routing in OpenClaw:

1. Trigger pattern: `/analyze <ticker>`
2. Extract `<ticker>` as variable `ticker`
3. Execute command above
4. Send command stdout back to Telegram chat

If your OpenClaw uses regex, a typical pattern is:

```regex
^/analyze\s+([A-Za-z.\-]+)$
```

Map capture group 1 to `ticker`.

## Notes

- This is technical analysis only and is not investment advice.
- Data source is `yfinance`; some tickers or markets may be delayed/missing.
- If you want watchlist pushes (`/watch`) later, add a scheduler job in OpenClaw or a cron task.
