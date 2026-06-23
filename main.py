"""
주식 분석 하네스 - 메인 진입점
FastAPI + APScheduler + Telegram Bot 통합 실행
"""
import asyncio
import logging
import os
import sys
from contextlib import asynccontextmanager

import httpx
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.interval import IntervalTrigger

from models.config import settings
from scheduler.job import run_check_job
from bot.telegram_bot import build_application, send_text
from utils.git_watcher import start_watcher

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler("logs/harness.log", encoding="utf-8"),
    ],
)
logger = logging.getLogger(__name__)

scheduler = AsyncIOScheduler(timezone="Asia/Seoul")
tg_app = build_application()


@asynccontextmanager
async def lifespan(app: FastAPI):
    os.makedirs("logs", exist_ok=True)

    scheduler.add_job(
        run_check_job,
        trigger=IntervalTrigger(minutes=settings.check_interval_minutes),
        id="stock_check",
        replace_existing=True,
        max_instances=1,
    )
    scheduler.start()
    logger.info(f"스케줄러 시작 - {settings.check_interval_minutes}분 간격")

    await tg_app.initialize()
    await tg_app.start()
    logger.info("텔레그램 봇 시작")

    git_watcher = start_watcher(delay=10.0)
    app.state.git_watcher = git_watcher

    try:
        await send_text(
            f"🟢 주식 분석 하네스 시작\n"
            f"감시 종목: {', '.join(settings.watch_codes)}\n"
            f"체크 주기: {settings.check_interval_minutes}분\n"
            f"거래량 임계: {settings.volume_surge_ratio}배\n"
            f"주가 임계: {settings.price_surge_pct}%+"
        )
    except Exception as e:
        logger.warning(f"시작 알림 발송 실패: {e}")

    yield

    scheduler.shutdown(wait=False)
    await tg_app.stop()
    await tg_app.shutdown()
    logger.info("종료 완료")


app = FastAPI(title="Stock Analysis Harness", lifespan=lifespan)

# CORS (Nginx가 처리하지만 직접 접근 대비)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


# ──────────────────────────────────────────
# 기본 엔드포인트
# ──────────────────────────────────────────

@app.get("/health")
async def health():
    return {"status": "ok", "scheduler_running": scheduler.running}


@app.post("/check/now")
async def trigger_check():
    asyncio.create_task(run_check_job())
    return {"message": "체크 시작됨"}


@app.get("/watch")
async def get_watchlist():
    from bot.telegram_bot import get_watch_set
    return {"codes": sorted(get_watch_set())}


@app.post("/watch/{code}")
async def add_watch(code: str):
    from bot.telegram_bot import get_watch_set
    get_watch_set().add(code)
    return {"codes": sorted(get_watch_set())}


@app.delete("/watch/{code}")
async def remove_watch(code: str):
    from bot.telegram_bot import get_watch_set
    get_watch_set().discard(code)
    return {"codes": sorted(get_watch_set())}


# ──────────────────────────────────────────
# Claude API 프록시 (브라우저 CORS 우회)
# ──────────────────────────────────────────

ANTHROPIC_API_URL = "https://api.anthropic.com/v1/messages"
ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY", "")


@app.post("/api/chat")
async def proxy_claude(request: Request):
    """
    Dev Console → 이 엔드포인트 → Anthropic API
    브라우저 CORS 문제 없이 Claude API 호출 가능
    """
    body = await request.body()

    headers = {
        "Content-Type": "application/json",
        "x-api-key": ANTHROPIC_API_KEY,
        "anthropic-version": "2023-06-01",
    }

    try:
        async with httpx.AsyncClient(timeout=60.0) as client:
            resp = await client.post(
                ANTHROPIC_API_URL,
                content=body,
                headers=headers,
            )
        return JSONResponse(
            content=resp.json(),
            status_code=resp.status_code,
        )
    except Exception as e:
        logger.error(f"[Claude 프록시] 오류: {e}")
        return JSONResponse(
            content={"error": {"message": str(e)}},
            status_code=500,
        )


@app.get("/api/settings")
async def get_ai_settings():
    """현재 AI 설정 반환 (서버 측 기본값)"""
    return {
        "default_provider": "claude",
        "default_model": "claude-sonnet-4-6",
        "anthropic_api_configured": bool(ANTHROPIC_API_KEY),
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=False)
