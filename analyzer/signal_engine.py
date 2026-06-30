"""
시그널 판단 엔진 (기술적 분석 강화)

이미지 기반 분석 기준:
  이미지00/01 - 패턴 확률: 상승깃발 80%, 역삼각형 65%, 쌍봉 100% 매도
  이미지02    - 매수/대기/매도 패턴 분류
  이미지03/13 - 지지선/저항선: 2회 이상 반등 지점, 저항 돌파 → 매수
  이미지04/10 - 이동평균선: 골든크로스(MA5↑MA20) → 매수, 데드크로스 → 매도
  이미지06/15 - 쐐기/삼각형: 거래량 수렴 후 급증 = 돌파 신호
  이미지11    - 캔들 지속률: 장대양봉 58%, 장대음봉 33%
  이미지14    - 돌파 후 조정: 조정 형태로 진짜/가짜 돌파 판별

매수 시그널:
  필수: 거래량 급등(3x) + 주가 상승
  보조: 감성 급증 OR 기술적 조건 2개 이상 충족
"""
from datetime import datetime
from typing import Optional, Tuple

from models.config import settings
from models.signal import BuySignal, VolumeAlert, PriceDropAlert, StockSnapshot, SentimentSnapshot
from crawler.stock_crawler import fetch_stock_snapshot
from crawler.naver_crawler import fetch_discussion_posts
from analyzer.sentiment import analyze_posts


# ──────────────────────────────────────────────────────────────
# 기술적 분석 보조 함수 (이미지 기반)
# ──────────────────────────────────────────────────────────────

def _analyze_candle(snap: dict) -> dict:
    """
    캔들 패턴 분석 (이미지07~09, 11)
    장대양봉: 몸통 비율 70%+, 등락률 2%+ → 58% 상승 지속 확률
    장대음봉: 반대 조건 → 33% 지속 (매도 신호)
    """
    price      = snap["price"]
    open_price = snap["open_price"]
    high       = snap.get("high", price)
    low        = snap.get("low", price)

    body       = abs(price - open_price)
    total_range = high - low if high != low else body or 1
    body_ratio  = body / total_range

    long_bull = (
        price > open_price
        and body_ratio >= 0.7
        and snap["change_pct"] >= 2.0
    )
    long_bear = (
        price < open_price
        and body_ratio >= 0.7
        and snap["change_pct"] <= -2.0
    )

    return {"long_bull": long_bull, "long_bear": long_bear}


def _analyze_ma(snap: dict) -> dict:
    """
    이동평균선 분석 (이미지04, 10)
    골든크로스: MA5가 MA20을 상향 돌파 → 매수 (일봉 기준)
    데드크로스: MA5가 MA20을 하향 돌파 → 매도
    정배열(MA5>MA10>MA20): 강세장 구조
    """
    ma5      = snap.get("ma5", 0)
    ma10     = snap.get("ma10", 0)
    ma20     = snap.get("ma20", 0)
    prev_ma5  = snap.get("prev_ma5", 0)
    prev_ma20 = snap.get("prev_ma20", 0)

    golden_cross  = prev_ma5 <= prev_ma20 and ma5 > ma20
    dead_cross    = prev_ma5 >= prev_ma20 and ma5 < ma20
    ma_uptrend    = ma5 > ma10 > ma20 > 0   # 정배열
    ma_downtrend  = ma5 < ma10 < ma20       # 역배열

    return {
        "golden_cross":  golden_cross,
        "dead_cross":    dead_cross,
        "ma_uptrend":    ma_uptrend,
        "ma_downtrend":  ma_downtrend,
    }


def _analyze_volume_pattern(snap: dict) -> dict:
    """
    거래량 패턴 분석 (이미지06, 15)
    쐐기형/삼각형 돌파: 직전 3~5일 거래량이 줄다가 오늘 급증 = 돌파 신호
    '쐐기 패턴은 거래량이 줄며 수렴하다가 돌파 시 거래량이 증가'
    """
    trend = snap.get("volume_5d_trend", [])
    today_vol = snap["volume"]
    avg_5d    = snap["avg_volume_5d"]

    breakout_surge = False
    if len(trend) >= 3 and avg_5d > 0:
        # 직전 3일 이상 거래량 감소 추세 확인
        recent = trend[-3:]
        is_converging = all(recent[i] >= recent[i + 1] for i in range(len(recent) - 1))
        # 오늘 거래량이 평균의 2배 이상 (돌파)
        breakout_surge = is_converging and today_vol >= avg_5d * 2.0

    return {"breakout_surge": breakout_surge}


def _analyze_support_resistance(snap: dict) -> dict:
    """
    지지/저항 분석 (이미지03, 13)
    저항선 돌파: 20일 고가의 98% 이상 → 저항 돌파 후 지지 전환 매수 신호
    지지선 이탈: 20일 저가의 102% 이하 → 지지 붕괴, 급락 위험
    '수평선의 요령: 2번 이상 반등하는 곳에 선을 긋다'
    """
    price    = snap["price"]
    high_20d = snap.get("high_20d", price)
    low_20d  = snap.get("low_20d", price)

    resistance_break = high_20d > 0 and price >= high_20d * 0.98
    support_break    = low_20d > 0  and price <= low_20d * 1.02

    return {
        "resistance_break": resistance_break,
        "support_break":    support_break,
    }


# ──────────────────────────────────────────────────────────────
# 공용 점수화 함수 (스크리너에서도 사용)
# ──────────────────────────────────────────────────────────────

def score_snapshot(snap: dict) -> dict:
    """
    스냅샷 기술적 분석 점수화.
    signal_engine.check_stock 과 screener 양쪽에서 공용으로 사용.
    반환: 각 조건 bool + total_score(0~7)
    """
    candle = _analyze_candle(snap)
    ma     = _analyze_ma(snap)
    vol_pt = _analyze_volume_pattern(snap)
    sr     = _analyze_support_resistance(snap)

    volume_surge = (
        snap["volume_ratio"] >= settings.volume_surge_ratio
        and snap["change_pct"] > 0
    )
    price_surge = snap["change_pct"] >= settings.price_surge_pct

    total_score = sum([
        volume_surge,
        price_surge,
        ma["golden_cross"],
        ma["ma_uptrend"],
        candle["long_bull"],
        sr["resistance_break"],
        vol_pt["breakout_surge"],
    ])

    return {
        "volume_surge":     volume_surge,
        "price_surge":      price_surge,
        "golden_cross":     ma["golden_cross"],
        "dead_cross":       ma["dead_cross"],
        "ma_uptrend":       ma["ma_uptrend"],
        "long_bull":        candle["long_bull"],
        "long_bear":        candle["long_bear"],
        "resistance_break": sr["resistance_break"],
        "support_break":    sr["support_break"],
        "volume_breakout":  vol_pt["breakout_surge"],
        "total_score":      total_score,
    }


# ──────────────────────────────────────────────────────────────
# 메인 시그널 판단
# ──────────────────────────────────────────────────────────────

async def check_stock(code: str) -> Tuple[Optional[VolumeAlert], Optional[BuySignal], Optional[PriceDropAlert]]:
    """
    단일 종목 전체 시그널 체크
    반환: (volume_alert, buy_signal, price_drop_alert)
    """
    snap = await fetch_stock_snapshot(code)
    if snap is None:
        return None, None, None

    # ── 기본 조건 ──────────────────────────────────────────────
    volume_surge = snap["volume_ratio"] >= settings.volume_surge_ratio
    price_surge  = snap["change_pct"] >= settings.price_surge_pct
    price_up     = snap["change_pct"] > 0
    volume_with_price = volume_surge and price_up

    # ── 기술적 분석 ────────────────────────────────────────────
    candle = _analyze_candle(snap)
    ma     = _analyze_ma(snap)
    vol_pt = _analyze_volume_pattern(snap)
    sr     = _analyze_support_resistance(snap)

    technical_score = sum([
        ma["golden_cross"],
        ma["ma_uptrend"],
        candle["long_bull"],
        sr["resistance_break"],
        vol_pt["breakout_surge"],
    ])

    # ── 거래량 급등 단독 알림 ──────────────────────────────────
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

    # ── 당일 시가 대비 급락 알림 ───────────────────────────────
    price_drop_alert = None
    if snap["change_from_open_pct"] <= -settings.price_drop_pct:
        price_drop_alert = PriceDropAlert(
            code=snap["code"],
            name=snap["name"],
            price=snap["price"],
            open_price=snap["open_price"],
            drop_pct=snap["change_from_open_pct"],
        )

    # ── 감성 분석 (거래량 또는 주가 급등 시에만 실행) ─────────
    sentiment_surge  = False
    positive_ratio   = 0.0
    positive_count   = 0
    sample_titles    = []

    if volume_surge or price_surge:
        posts = await fetch_discussion_posts(code, pages=3, hours_back=1)
        positive_ratio, positive_count, total_count = analyze_posts(posts)
        sample_titles = [p["title"] for p in posts[:3]]

        sentiment_surge = (
            positive_ratio >= settings.sentiment_positive_threshold
            and positive_count >= settings.sentiment_surge_count
        )

    # ── 종합 매수 시그널 ───────────────────────────────────────
    signal = BuySignal(
        code=snap["code"],
        name=snap["name"],
        score=sum([volume_with_price, price_surge, sentiment_surge]),
        # 기본 조건
        volume_surge=volume_with_price,
        price_surge=price_surge,
        sentiment_surge=sentiment_surge,
        # 기술적 분석
        golden_cross=ma["golden_cross"],
        dead_cross=ma["dead_cross"],
        ma_uptrend=ma["ma_uptrend"],
        long_bull=candle["long_bull"],
        long_bear=candle["long_bear"],
        resistance_break=sr["resistance_break"],
        volume_breakout=vol_pt["breakout_surge"],
        technical_score=technical_score,
        # 수치
        price=snap["price"],
        change_pct=snap["change_pct"],
        volume_ratio=snap["volume_ratio"],
        positive_ratio=positive_ratio,
        ma5=snap.get("ma5", 0),
        ma20=snap.get("ma20", 0),
        high_20d=snap.get("high_20d", 0),
        sample_titles=sample_titles,
    )

    buy_signal = signal if signal.is_buy else None
    return volume_alert, buy_signal, price_drop_alert


async def check_all(codes: list) -> Tuple[list, list, list]:
    """전체 감시 종목 체크, 중복 알림 방지는 호출자가 관리"""
    import asyncio
    results = await asyncio.gather(
        *[check_stock(code) for code in codes],
        return_exceptions=True,
    )

    volume_alerts, buy_signals, price_drop_alerts = [], [], []
    for r in results:
        if isinstance(r, Exception):
            continue
        va, bs, pda = r
        if va:
            volume_alerts.append(va)
        if bs:
            buy_signals.append(bs)
        if pda:
            price_drop_alerts.append(pda)

    return volume_alerts, buy_signals, price_drop_alerts
