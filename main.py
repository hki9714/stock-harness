"""
주식 분석 하네스 - 메인 진입점
FastAPI + APScheduler + Telegram Bot 통합 실행
"""
import asyncio
import logging
import os
import pathlib
import shutil
import subprocess
import sys
import time
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, RedirectResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.interval import IntervalTrigger
from apscheduler.triggers.cron import CronTrigger

from models.config import settings
from scheduler.job import run_check_job, refresh_open, send_screening_notify
from bot.telegram_bot import build_application, send_text
from utils.git_watcher import start_watcher
from api.dashboard import router as dashboard_router
from analyzer.screener import run_screening

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler("logs/harness.log", encoding="utf-8"),
    ],
)
logger = logging.getLogger(__name__)

# pykrx 내부 logging.info(args, kwargs) 버그로 인한 "--- Logging error ---" 노이즈 억제
logging.raiseExceptions = False

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

    # 9:00 — 스크리닝 캐시 + 감시 종목 동시 갱신 (알림 없음)
    scheduler.add_job(
        refresh_open,
        trigger=CronTrigger(hour=9, minute=0, timezone="Asia/Seoul"),
        id="stock_refresh_open",
        replace_existing=True,
        max_instances=1,
    )
    # 9:10 — 갱신된 데이터로 텔레그램 발송
    scheduler.add_job(
        send_screening_notify,
        trigger=CronTrigger(hour=9, minute=10, timezone="Asia/Seoul"),
        id="stock_screening_notify",
        replace_existing=True,
        max_instances=1,
    )
    # 12시, 15시: 스크리닝만 (캐시 갱신)
    scheduler.add_job(
        run_screening,
        trigger=CronTrigger(hour="12,15", minute=0, timezone="Asia/Seoul"),
        id="stock_screening_mid",
        replace_existing=True,
        max_instances=1,
    )

    scheduler.start()
    logger.info(f"스케줄러 시작 - 시그널 체크 {settings.check_interval_minutes}분 / 데이터갱신 09:00 / 알림 09:10 / 스크리닝 12·15시")

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

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# 대시보드 API 라우터 등록
app.include_router(dashboard_router)


# ──────────────────────────────────────────
# 기본 엔드포인트
# ──────────────────────────────────────────

@app.get("/.well-known/appspecific/com.chrome.devtools.json")
async def chrome_devtools():
    return JSONResponse({})


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
# Claude Code CLI 프록시
# ──────────────────────────────────────────

def _find_claude() -> str | None:
    return shutil.which("claude")


def _build_system_prompt() -> str:
    root = pathlib.Path(__file__).parent
    lines = [
        '당신은 "Stock Harness" Python 주식 분석 프로젝트의 전담 개발 AI입니다.',
        '한국어로 응답하세요.',
        '코드 수정 시 반드시 ```python:파일경로``` 형식으로 파일명을 명시하세요.',
        '',
        '=== 프로젝트 핵심 파일 ===',
    ]
    # 토큰 초과 방지: 가장 중요한 파일만 포함
    key_files = [
        'CLAUDE.md',
        'analyzer/signal_engine.py',
        'models/config.py',
    ]
    for rel in key_files:
        p = root / rel
        if p.exists():
            lines.append(f'\n[{rel}]\n{p.read_text(encoding="utf-8")}')
    return '\n'.join(lines)


def _decode_stderr(b: bytes) -> str:
    """Windows CP949 / UTF-8 모두 처리"""
    for enc in ("utf-8", "cp949", "euc-kr"):
        try:
            return b.decode(enc)
        except UnicodeDecodeError:
            continue
    return b.decode("utf-8", errors="replace")


@app.post("/api/chat")
async def proxy_claude(request: Request):
    try:
        body     = await request.json()
        messages = body.get("messages", [])
        model    = body.get("model", settings.default_model)

        # 서버 사이드 시스템 프롬프트 + 대화 내역 조합
        parts = [_build_system_prompt()]
        for msg in messages:
            prefix  = "Human" if msg["role"] == "user" else "Assistant"
            content = msg["content"] if isinstance(msg["content"], str) else ""
            parts.append(f"{prefix}: {content}")
        prompt = "\n\n".join(parts)

        claude_bin = _find_claude()
        if not claude_bin:
            return JSONResponse(
                {"error": {"message": "Claude Code CLI가 설치되어 있지 않습니다. `npm i -g @anthropic-ai/claude-code` 로 설치하세요."}},
                status_code=500,
            )

        async def generate():
            import tempfile
            import threading
            from queue import Queue

            q: Queue = Queue()
            _DONE = object()

            def _run():
                try:
                    proc = subprocess.Popen(
                        [claude_bin, "-p", "--model", model],
                        stdin=subprocess.PIPE,   # 커맨드라인 길이 제한 우회
                        stdout=subprocess.PIPE,
                        stderr=subprocess.PIPE,
                        cwd=tempfile.gettempdir(),  # CLAUDE.md 자동 탐색 방지
                    )
                    proc.stdin.write(prompt.encode("utf-8"))
                    proc.stdin.close()
                    while True:
                        chunk = proc.stdout.read(128)
                        if not chunk:
                            break
                        q.put(chunk)
                    proc.wait()
                    if proc.returncode != 0:
                        err = _decode_stderr(proc.stderr.read()).strip()
                        if err:
                            logger.error(f"[Claude CLI] {err}")
                            q.put(f"\n[오류: {err}]".encode("utf-8"))
                except Exception as ex:
                    logger.error(f"[Claude CLI 스레드] {ex}")
                    q.put(f"\n[예외: {ex}]".encode("utf-8"))
                finally:
                    q.put(_DONE)

            threading.Thread(target=_run, daemon=True).start()

            import codecs
            utf8 = codecs.getincrementaldecoder("utf-8")(errors="replace")

            loop = asyncio.get_event_loop()
            while True:
                try:
                    chunk = await asyncio.wait_for(
                        loop.run_in_executor(None, q.get),
                        timeout=120.0,
                    )
                except asyncio.TimeoutError:
                    tail = utf8.decode(b"", final=True)
                    if tail:
                        yield tail
                    yield "\n\n[응답 시간 초과 (120초)]"
                    break
                if chunk is _DONE:
                    tail = utf8.decode(b"", final=True)
                    if tail:
                        yield tail
                    break
                if isinstance(chunk, bytes):
                    decoded = utf8.decode(chunk)
                    if decoded:
                        yield decoded
                else:
                    yield chunk

        return StreamingResponse(generate(), media_type="text/plain; charset=utf-8")

    except Exception as e:
        logger.error(f"[Claude CLI] 예외: {e}")
        return JSONResponse({"error": {"message": str(e)}}, status_code=500)


@app.get("/api/settings")
async def get_ai_settings():
    return {
        "default_provider":    settings.default_provider,
        "default_model":       settings.default_model,
        "claude_cli_path":     _find_claude(),
        "claude_cli_ready":    bool(_find_claude()),
    }


# ──────────────────────────────────────────
# 정적 파일 서빙
# 반드시 API 엔드포인트 등록 후 마지막에 위치해야 함
# ──────────────────────────────────────────

DASH_DIR    = pathlib.Path(__file__).parent / "static" / "dashboard"
CONSOLE_DIR = pathlib.Path(__file__).parent / "static" / "console"


@app.get("/")
async def root():
    return RedirectResponse("/dashboard")


# React 대시보드 (빌드 완료 후 자동 활성화)
if DASH_DIR.exists():
    app.mount("/dashboard", StaticFiles(directory=str(DASH_DIR), html=True), name="dashboard")

# Dev Console 단독 페이지
if CONSOLE_DIR.exists():
    app.mount("/devconsole", StaticFiles(directory=str(CONSOLE_DIR), html=True), name="console")


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=False)