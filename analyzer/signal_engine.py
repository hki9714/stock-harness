"""
시그널 판단 엔진
- 거래량 급등 알림: volume_ratio >= threshold (단독)
- 매수 시그널: 거래량급등 + 주가5%+ + 토론긍정급증 (AND 3조건)
"""
from datetime import datetime
from typing import Optional, Tuple

from models.config import settings
from models.signal import BuySignal, VolumeAlert, StockSnapshot, SentimentSnapshot
from crawler.stock_crawler import fetch_stock_snapshot
from crawler.naver_crawler import fetch_discussion_posts
from analyzer.sentiment import analyze_posts


async def check_stock(code: str) -> Tuple[Optional[VolumeAlert], Optional[BuySignal]]:
    """
    단일 종목 전체 시그널 체크
    반환: (volume_alert, buy_signal)
    - volume_alert: 거래량 급등 시 반환 (매수 시그널과 무관하게)
    - buy_signal: 3조건 충족 시 반환
    """
    # 1. 주가/거래량 데이터
    snap = await fetch_stock_snapshot(code)
    if snap is None:
        return None, None

    volume_surge = snap["volume_ratio"] >= settings.volume_surge_ratio
    price_surge = snap["change_pct"] >= settings.price_surge_pct
    price_up = snap["change_pct"] > 0  # 주가 상승 동반 여부

    # 거래량 급등 + 주가 상승 동반 조건
    volume_with_price = volume_surge and price_up

    # 거래량 급등 단독 알림 객체 (매수 시그널과 별도)
    volume_alert = None
    if volume_surge:
        volume_alert = VolumeAlert(
            code=snap["code"],
            name=snap["name"],
            price=snap["price"],
            change_pct=snap["change_pct"],
            volume_ratio=snap["volume_ratio"],
            volume=snap["volume"],
        )

    # 2. 감성 분석 (거래량 급등 또는 주가 급등 시에만 실행 → API 절약)
    sentiment_surge = False
    positive_ratio = 0.0
    positive_count = 0
    sample_titles = []

    if volume_surge or price_surge:
        posts = await fetch_discussion_posts(code, pages=3, hours_back=1)
        positive_ratio, positive_count, total_count = analyze_posts(posts)
        sample_titles = [p["title"] for p in posts[:3]]

        sentiment_surge = (
            positive_ratio >= settings.sentiment_positive_threshold
            and positive_count >= settings.sentiment_surge_count
        )

    # 3. 매수 시그널 조합 판단
    signal = BuySignal(
        code=snap["code"],
        name=snap["name"],
        score=sum([volume_with_price, price_surge, sentiment_surge]),
        volume_surge=volume_with_price,
        price_surge=price_surge,
        sentiment_surge=sentiment_surge,
        price=snap["price"],
        change_pct=snap["change_pct"],
        volume_ratio=snap["volume_ratio"],
        positive_ratio=positive_ratio,
        sample_titles=sample_titles,
    )

    buy_signal = signal if signal.is_buy else None
    return volume_alert, buy_signal


async def check_all(codes: list) -> Tuple[list, list]:
    """전체 감시 종목 체크, 중복 알림 방지는 호출자가 관리"""
    import asyncio
    results = await asyncio.gather(
        *[check_stock(code) for code in codes],
        return_exceptions=True,
    )

    volume_alerts, buy_signals = [], []
    for r in results:
        if isinstance(r, Exception):
            continue
        va, bs = r
        if va:
            volume_alerts.append(va)
        if bs:
            buy_signals.append(bs)

    return volume_alerts, buy_signals
