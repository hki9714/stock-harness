"""
텔레그램 알림 봇
- 거래량 급등 알림
- 매수 시그널 알림 ("이건 사야돼!")
- /watch, /unwatch, /status 커맨드 지원
"""
import asyncio
import logging
from datetime import datetime
from typing import Set

from telegram import Update, Bot
from telegram.ext import (
    Application,
    CommandHandler,
    ContextTypes,
)
from telegram.constants import ParseMode

from models.config import settings
from models.signal import VolumeAlert, BuySignal

logger = logging.getLogger(__name__)

# 감시 중인 종목 (런타임 동적 추가/제거)
_watch_set: Set[str] = set(settings.watch_codes)
_bot: Bot = None


# ──────────────────────────────────────────
# 메시지 포맷터
# ──────────────────────────────────────────

def format_volume_alert(alert: VolumeAlert) -> str:
    direction = "📈" if alert.change_pct >= 0 else "📉"
    sign = "+" if alert.change_pct >= 0 else ""
    return (
        f"🔥 *거래량 급등 알림*\n"
        f"━━━━━━━━━━━━━━━\n"
        f"종목: *{alert.name}* ({alert.code})\n"
        f"현재가: {alert.price:,.0f}원  {direction} {sign}{alert.change_pct:.1f}%\n"
        f"거래량: {alert.volume:,}주\n"
        f"평균 대비: *{alert.volume_ratio:.1f}배*\n"
        f"⏰ {alert.timestamp.strftime('%H:%M')}"
    )


def format_buy_signal(signal: BuySignal) -> str:
    conditions = []
    if signal.volume_surge:
        conditions.append(f"✅ 거래량 급등 ({signal.volume_ratio:.1f}배) + 주가 상승")
    if signal.price_surge:
        conditions.append(f"✅ 전일 대비 +{signal.change_pct:.1f}% 급등")
    if signal.sentiment_surge:
        conditions.append(f"✅ 토론 긍정 감성 급증 ({signal.positive_ratio*100:.0f}%)")

    condition_text = "\n".join(conditions)

    sample_text = ""
    if signal.sample_titles:
        titles = "\n".join(f"  • {t[:30]}" for t in signal.sample_titles[:3])
        sample_text = f"\n\n💬 *토론 인기글*\n{titles}"

    return (
        f"🚨 *이건 사야돼\\!* 매수 시그널\n"
        f"━━━━━━━━━━━━━━━\n"
        f"종목: *{signal.name}* ({signal.code})\n"
        f"현재가: *{signal.price:,.0f}원*  \\+{signal.change_pct:.1f}%\n\n"
        f"*충족 조건 ({signal.score}/3)*\n"
        f"{condition_text}"
        f"{sample_text}\n\n"
        f"⚠️ 투자 판단은 본인 책임입니다\n"
        f"⏰ {signal.timestamp.strftime('%H:%M')}"
    )


# ──────────────────────────────────────────
# 알림 발송 함수 (스케줄러에서 호출)
# ──────────────────────────────────────────

async def send_volume_alert(alert: VolumeAlert):
    bot = Bot(token=settings.telegram_bot_token)
    await bot.send_message(
        chat_id=settings.telegram_chat_id,
        text=format_volume_alert(alert),
        parse_mode=ParseMode.MARKDOWN,
    )
    logger.info(f"[텔레그램] 거래량 급등 알림 발송: {alert.name}")


async def send_buy_signal(signal: BuySignal):
    bot = Bot(token=settings.telegram_bot_token)
    await bot.send_message(
        chat_id=settings.telegram_chat_id,
        text=format_buy_signal(signal),
        parse_mode=ParseMode.MARKDOWN_V2,
    )
    logger.info(f"[텔레그램] 매수 시그널 발송: {signal.name}")


async def send_text(message: str):
    """일반 텍스트 메시지"""
    bot = Bot(token=settings.telegram_bot_token)
    await bot.send_message(
        chat_id=settings.telegram_chat_id,
        text=message,
    )


# ──────────────────────────────────────────
# 봇 커맨드 핸들러
# ──────────────────────────────────────────

async def cmd_watch(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    """/watch 005930  → 종목 감시 추가"""
    if not ctx.args:
        await update.message.reply_text("사용법: /watch 종목코드\n예: /watch 005930")
        return
    code = ctx.args[0].strip()
    _watch_set.add(code)
    await update.message.reply_text(f"✅ {code} 감시 추가됨\n현재 감시: {', '.join(sorted(_watch_set))}")


async def cmd_unwatch(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    """/unwatch 005930  → 종목 감시 제거"""
    if not ctx.args:
        await update.message.reply_text("사용법: /unwatch 종목코드")
        return
    code = ctx.args[0].strip()
    _watch_set.discard(code)
    await update.message.reply_text(f"🗑 {code} 감시 제거됨\n현재 감시: {', '.join(sorted(_watch_set))}")


async def cmd_status(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    """/status  → 현재 감시 종목 + 설정 확인"""
    watch_list = ", ".join(sorted(_watch_set)) or "없음"
    msg = (
        f"📊 *감시 현황*\n"
        f"종목: {watch_list}\n\n"
        f"*임계값 설정*\n"
        f"거래량 급등: {settings.volume_surge_ratio}배\n"
        f"주가 급등: {settings.price_surge_pct}%\n"
        f"긍정 감성: {settings.sentiment_positive_threshold*100:.0f}%\n"
        f"체크 주기: {settings.check_interval_minutes}분"
    )
    await update.message.reply_text(msg, parse_mode=ParseMode.MARKDOWN)


async def cmd_help(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "📌 *명령어 목록*\n"
        "/watch [코드] - 종목 감시 추가\n"
        "/unwatch [코드] - 종목 감시 제거\n"
        "/status - 현재 감시 현황\n"
        "/help - 도움말",
        parse_mode=ParseMode.MARKDOWN,
    )


def get_watch_set() -> Set[str]:
    return _watch_set


# ──────────────────────────────────────────
# 봇 앱 빌더 (main.py에서 호출)
# ──────────────────────────────────────────

def build_application() -> Application:
    app = (
        Application.builder()
        .token(settings.telegram_bot_token)
        .build()
    )
    app.add_handler(CommandHandler("watch", cmd_watch))
    app.add_handler(CommandHandler("unwatch", cmd_unwatch))
    app.add_handler(CommandHandler("status", cmd_status))
    app.add_handler(CommandHandler("help", cmd_help))
    return app
