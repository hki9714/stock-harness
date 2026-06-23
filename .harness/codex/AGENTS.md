# Stock Harness — Codex / ChatGPT Agent Guide

This file provides project context for OpenAI Codex or ChatGPT-based agents.

---

## Project Overview

**Stock Harness** is a Korean stock market monitoring system that detects
volume surges and buy signals, then sends alerts via Telegram.

- **Runtime**: FastAPI + Uvicorn (no separate WAS needed)
- **Scheduler**: APScheduler (market hours 09:00~15:30 KST, 30min interval)
- **Data**: pykrx (stock prices), Naver Finance discussion crawling
- **AI Analysis**: KR-FinBert-SC sentiment analysis (keyword fallback included)
- **Alerts**: python-telegram-bot
- **Dev Console**: ui/dev_console.html (AI API integrated)
- **Git**: Auto-commit on file change via watchdog

---

## Project Structure

```
stock-harness/
├── main.py                    # FastAPI entrypoint
├── config.yaml                # User config (excluded from Git)
├── setup/bootstrap.py         # Auto setup (local/server runtime)
├── models/config.py           # pydantic-settings env vars
├── models/signal.py           # BuySignal, VolumeAlert, StockSnapshot
├── crawler/stock_crawler.py   # pykrx async fetcher
├── crawler/naver_crawler.py   # Naver discussion crawler
├── analyzer/sentiment.py      # KR-FinBert sentiment analysis
├── analyzer/signal_engine.py  # 3-condition AND buy signal logic
├── scheduler/job.py           # APScheduler job, 60min cooldown
├── bot/telegram_bot.py        # Telegram alerts + commands
├── utils/git_watcher.py       # watchdog auto Git commit
└── ui/dev_console.html        # AI-integrated dev console
```

---

## Buy Signal Logic

```
Condition 1: Volume surge (3x 5-day avg) + price rising
Condition 2: Price up +5% vs previous close
Condition 3: Naver discussion 65%+ positive AND 20+ posts/hour

→ ALL 3 = BUY signal → Telegram
→ Condition 1 only = Volume alert → Telegram
```

---

## Key Rules

- Config source of truth: `config.yaml` → `.env` → `models/config.py`
- Do not edit `.env` directly; regenerate via `python setup/bootstrap.py`
- Async throughout; pykrx runs in executor (sync library)
- New features go in `analyzer/` or `crawler/`

---

## Pending Features

- [ ] Auto stock screening (top N by market cap, KOSPI200)
- [ ] FastAPI static file serving for dev_console.html
- [ ] Financial statement analysis (OpenDartReader)
- [ ] Technical indicators (Golden Cross, RSI)
- [ ] React web dashboard
