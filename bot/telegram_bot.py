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
from models.signal import VolumeAlert, BuySignal, PriceDropAlert

logger = logging.getLogger(__name__)

# 감시 중인 종목 (런타임 동적 추가/제거)
_watch_set: Set[str] = set(settings.watch_codes)
_bot: Bot = None


# ──────────────────────────────────────────
# 메시지 포맷터
# ──────────────────────────────────────────

def _esc(text) -> str:
    """MarkdownV2 특수문자 이스케이프"""
    special = r'_*[]()~`>#+-=|{}.!'
    return ''.join(f'\\{c}' if c in special else c for c in str(text))


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
    # ── 기본 조건 ──────────────────────────────────────────────
    conditions = []
    if signal.volume_surge:
        conditions.append(f"✅ 거래량 급등 \\({_esc(f'{signal.volume_ratio:.1f}')}배\\) \\+ 주가 상승")
    if signal.price_surge:
        conditions.append(f"✅ 전일 대비 \\+{_esc(f'{signal.change_pct:.1f}')}% 급등")
    if signal.sentiment_surge:
        conditions.append(f"✅ 토론 긍정 감성 급증 \\({_esc(f'{signal.positive_ratio*100:.0f}')}%\\)")

    # ── 기술적 분석 조건 ───────────────────────────────────────
    tech = []
    if signal.golden_cross:
        tech.append("📊 골든크로스 \\(MA5↑MA20\\)")
    if signal.ma_uptrend:
        tech.append("📈 정배열 \\(MA5\\>MA10\\>MA20\\)")
    if signal.long_bull:
        tech.append("🕯 장대양봉 \\(58% 상승 지속\\)")
    if signal.resistance_break:
        tech.append(f"🔓 20일 고점 돌파 \\({_esc(f'{signal.high_20d:,.0f}')}원\\)")
    if signal.volume_breakout:
        tech.append("💥 거래량 수렴 후 급증 \\(쐐기/삼각형 돌파\\)")

    condition_text = "\n".join(conditions)
    tech_text = ""
    if tech:
        tech_text = "\n\n*기술적 분석 신호*\n" + "\n".join(tech)

    # ── MA 수치 표시 ───────────────────────────────────────────
    ma_text = ""
    if signal.ma5 and signal.ma20:
        ma_text = f"\nMA5: {signal.ma5:,.0f}원 / MA20: {signal.ma20:,.0f}원"

    sample_text = ""
    if signal.sample_titles:
        titles = "\n".join(f"  • {_esc(t[:30])}" for t in signal.sample_titles[:3])
        sample_text = f"\n\n💬 *토론 인기글*\n{titles}"

    total = signal.score + signal.technical_score
    return (
        f"🚨 *이건 사야돼\\!* 매수 시그널\n"
        f"━━━━━━━━━━━━━━━\n"
        f"종목: *{_esc(signal.name)}* \\({_esc(signal.code)}\\)\n"
        f"현재가: *{_esc(f'{signal.price:,.0f}')}원*  \\+{_esc(f'{signal.change_pct:.1f}')}%"
        f"{_esc(ma_text)}\n\n"
        f"*충족 조건 \\({signal.score}/3\\) \\| 기술점수 {signal.technical_score}/5*\n"
        f"{condition_text}"
        f"{tech_text}"
        f"{sample_text}\n\n"
        f"⚠️ 투자 판단은 본인 책임입니다\n"
        f"⏰ {signal.timestamp.strftime('%H:%M')}"
    )


def format_price_drop_alert(alert: PriceDropAlert) -> str:
    return (
        f"🔻 *급락 알림*\n"
        f"━━━━━━━━━━━━━━━\n"
        f"종목: *{_esc(alert.name)}* \\({_esc(alert.code)}\\)\n"
        f"현재가: *{_esc(f'{alert.price:,.0f}')}원*\n"
        f"시가: {_esc(f'{alert.open_price:,.0f}')}원\n"
        f"시가 대비: *{_esc(f'{alert.drop_pct:.1f}')}%*\n\n"
        f"⚠️ 투자 판단은 본인 책임입니다\n"
        f"⏰ {alert.timestamp.strftime('%H:%M')}"
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


async def send_price_drop_alert(alert: PriceDropAlert):
    bot = Bot(token=settings.telegram_bot_token)
    await bot.send_message(
        chat_id=settings.telegram_chat_id,
        text=format_price_drop_alert(alert),
        parse_mode=ParseMode.MARKDOWN_V2,
    )
    logger.info(f"[텔레그램] 급락 알림 발송: {alert.name}")


_SCREENING_SIGNAL_LABELS = {
    "volume_surge":     "거래량급등",
    "price_surge":      "주가급등",
    "golden_cross":     "골든크로스",
    "ma_uptrend":       "정배열",
    "long_bull":        "장대양봉",
    "resistance_break": "저항돌파",
    "volume_breakout":  "거래량돌파",
}


def format_screening_alert(results: list, total_scanned: int) -> str:
    from datetime import timedelta
    # pykrx는 일봉 EOD 데이터 — 9시 실행 시 당일 봉이 아직 없으므로
    # df.iloc[-1]은 항상 가장 최근 거래일(전일) 종가 기준
    ref_date = (datetime.now() - timedelta(days=1)).strftime("%m/%d")

    lines = [
        "📊 *장 시작 스크리닝 결과*",
        _esc(f"KOSPI 시총 상위 {total_scanned}개 분석 완료 (전일 {ref_date} 종가 기준)"),
        "━━━━━━━━━━━━━━━",
        "",
    ]
    for i, item in enumerate(results, 1):
        name  = item.get("name", item["code"])
        if not isinstance(name, str):
            name = item["code"]
        code  = item["code"]
        score = item.get("total_score", 0)
        chg   = item.get("change_pct", 0)   # 전일 대비 전전일 변동률
        vol_r = item.get("volume_ratio", 0)
        price = item.get("price", 0)         # 전일 종가
        arrow = "▲" if chg >= 0 else "▼"
        sign  = "+" if chg >= 0 else ""

        sigs = [label for key, label in _SCREENING_SIGNAL_LABELS.items() if item.get(key)]
        sig_text = " · ".join(sigs) if sigs else "–"

        lines.append(
            f"{i}\\. *{_esc(name)}* \\({_esc(code)}\\) ★{score}/7\n"
            f"   전일종가 {_esc(f'{price:,.0f}')}원 \\| {_esc(arrow)} {_esc(sign + f'{chg:.1f}')}% \\| 거래량 {_esc(f'{vol_r:.1f}')}배\n"
            f"   {_esc(sig_text)}"
        )

    lines.append(f"\n⏰ {_esc(datetime.now().strftime('%H:%M'))}")
    return "\n".join(lines)


async def send_screening_alert(results: list, total_scanned: int):
    bot = Bot(token=settings.telegram_bot_token)
    await bot.send_message(
        chat_id=settings.telegram_chat_id,
        text=format_screening_alert(results, total_scanned),
        parse_mode=ParseMode.MARKDOWN_V2,
    )
    logger.info(f"[텔레그램] 장 시작 스크리닝 결과 발송: {len(results)}개 종목")


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
