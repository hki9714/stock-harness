"""
APScheduler 기반 주기 실행 잡
- 장중(09:00~15:30)에만 실행
- 중복 알림 방지: 동일 종목 동일 신호는 1시간 내 재발송 안 함
"""
import asyncio
import logging
from datetime import datetime, timedelta
from typing import Dict, Set

from models.config import settings
from analyzer.signal_engine import check_all
from analyzer.screener import run_screening, get_cache
from bot.telegram_bot import (
    send_volume_alert, send_buy_signal, send_price_drop_alert,
    send_screening_alert, send_text, get_watch_set,
)

logger = logging.getLogger(__name__)

# 중복 알림 방지 캐시 {종목코드: 마지막 알림 시각}
_volume_sent: Dict[str, datetime] = {}
_buy_sent:    Dict[str, datetime] = {}
_drop_sent:   Dict[str, datetime] = {}
COOLDOWN_MINUTES = 60  # 동일 시그널 재발송 대기 시간


def _is_market_hours() -> bool:
    """KST 기준 장중 여부 (09:00 ~ 15:30, 평일)"""
    now = datetime.now()
    if now.weekday() >= 5:  # 토/일
        return False
    market_open = now.replace(hour=9, minute=0, second=0, microsecond=0)
    market_close = now.replace(hour=15, minute=30, second=0, microsecond=0)
    return market_open <= now <= market_close


def _can_send(cache: Dict[str, datetime], code: str) -> bool:
    """쿨다운 체크"""
    if code not in cache:
        return True
    elapsed = datetime.now() - cache[code]
    return elapsed > timedelta(minutes=COOLDOWN_MINUTES)


async def run_check_job():
    """스케줄러가 주기적으로 호출하는 메인 잡"""
    if not _is_market_hours():
        logger.debug("장 외 시간, 스킵")
        return

    codes = list(get_watch_set())
    if not codes:
        return

    logger.info(f"[스케줄러] 종목 체크 시작: {codes}")

    try:
        volume_alerts, buy_signals, price_drop_alerts = await check_all(codes)
    except Exception as e:
        logger.error(f"[스케줄러] check_all 실패: {e}")
        return

    # 거래량 급등 알림 발송
    for alert in volume_alerts:
        if _can_send(_volume_sent, alert.code):
            try:
                await send_volume_alert(alert)
                _volume_sent[alert.code] = datetime.now()
            except Exception as e:
                logger.error(f"[텔레그램] 거래량 알림 발송 실패 {alert.code}: {e}")

    # 매수 시그널 알림 발송
    for signal in buy_signals:
        if _can_send(_buy_sent, signal.code):
            try:
                await send_buy_signal(signal)
                _buy_sent[signal.code] = datetime.now()
            except Exception as e:
                logger.error(f"[텔레그램] 매수 시그널 발송 실패 {signal.code}: {e}")

    # 당일 시가 대비 급락 알림 발송
    for alert in price_drop_alerts:
        if _can_send(_drop_sent, alert.code):
            try:
                await send_price_drop_alert(alert)
                _drop_sent[alert.code] = datetime.now()
            except Exception as e:
                logger.error(f"[텔레그램] 급락 알림 발송 실패 {alert.code}: {e}")

    logger.info(
        f"[스케줄러] 완료 - 거래량알림: {len(volume_alerts)}건, "
        f"매수시그널: {len(buy_signals)}건, 급락알림: {len(price_drop_alerts)}건"
    )


async def refresh_open():
    """9:00 — 스크리닝 캐시 갱신 + 감시 종목 체크를 동시 실행 (데이터 새로고침 전용)"""
    logger.info("[스케줄러] 9시 데이터 갱신 시작 (스크리닝 + 감시 종목)")
    await asyncio.gather(
        run_screening(),
        run_check_job(),
    )
    logger.info("[스케줄러] 9시 데이터 갱신 완료")


async def send_screening_notify():
    """9:10 — 갱신된 스크리닝 캐시를 텔레그램으로 발송"""
    cache = get_cache()
    if cache["results"]:
        try:
            await send_screening_alert(cache["results"], cache["total_scanned"])
        except Exception as e:
            logger.error(f"[텔레그램] 스크리닝 결과 발송 실패: {e}")
    else:
        logger.warning("[스케줄러] 9:10 알림 스킵 — 스크리닝 캐시 없음")
