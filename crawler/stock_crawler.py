import asyncio
from datetime import datetime, timedelta
from typing import Optional
import pandas as pd

# pykrx는 동기 라이브러리이므로 executor로 비동기 처리
from pykrx import stock as krx


def _fetch_ohlcv_sync(code: str, days: int = 30) -> Optional[pd.DataFrame]:
    """동기 방식으로 OHLCV 조회 (executor 내부 실행용)"""
    end = datetime.today().strftime("%Y%m%d")
    start = (datetime.today() - timedelta(days=days * 2)).strftime("%Y%m%d")  # 공휴일 여유분
    try:
        df = krx.get_market_ohlcv_by_date(start, end, code)
        return df.tail(days) if not df.empty else None
    except Exception as e:
        print(f"[OHLCV 조회 실패] {code}: {e}")
        return None


def _fetch_name_sync(code: str) -> str:
    try:
        result = krx.get_market_ticker_name(code)
        # 장외 시간에 예외 없이 {} 또는 None 반환하는 pykrx 버그 방어
        if isinstance(result, str) and result:
            return result
        return code
    except Exception:
        return code


async def fetch_stock_snapshot(code: str) -> Optional[dict]:
    """
    종목 스냅샷 비동기 조회 (30일 데이터 기반 기술적 분석 포함)
    반환: 기본 OHLCV + 이동평균선 + 지지/저항 + 거래량 추세
    """
    loop = asyncio.get_event_loop()

    df = await loop.run_in_executor(None, _fetch_ohlcv_sync, code, 30)
    name = await loop.run_in_executor(None, _fetch_name_sync, code)

    if df is None or len(df) < 5:
        return None

    today = df.iloc[-1]
    prev = df.iloc[-2]

    price       = float(today["종가"])
    open_price  = float(today["시가"])
    high        = float(today["고가"])
    low         = float(today["저가"])
    prev_close  = float(prev["종가"])
    volume      = int(today["거래량"])

    # 직전 5일 평균 거래량 (오늘 제외)
    avg_volume_5d = float(df["거래량"].iloc[-6:-1].mean())

    change_pct          = ((price - prev_close) / prev_close) * 100
    change_from_open_pct = ((price - open_price) / open_price) * 100
    volume_ratio        = volume / avg_volume_5d if avg_volume_5d > 0 else 0

    # ── 이동평균선 (MA5, MA10, MA20) ──────────────────────────────
    closes      = df["종가"].astype(float)
    ma5         = float(closes.iloc[-5:].mean())   if len(closes) >= 5  else price
    ma10        = float(closes.iloc[-10:].mean())  if len(closes) >= 10 else price
    ma20        = float(closes.iloc[-20:].mean())  if len(closes) >= 20 else price
    # 전일 MA (크로스 탐지용)
    prev_ma5    = float(closes.iloc[-6:-1].mean()) if len(closes) >= 6  else ma5
    prev_ma20   = float(closes.iloc[-21:-1].mean()) if len(closes) >= 21 else ma20

    # ── 지지/저항 기준 (20일 고/저가) ─────────────────────────────
    high_20d    = float(df["고가"].iloc[-20:].max())  if len(df) >= 20 else high
    low_20d     = float(df["저가"].iloc[-20:].min())  if len(df) >= 20 else low

    # ── 거래량 수렴 추세 (직전 5거래일, 오늘 제외) ─────────────────
    volume_5d_trend = df["거래량"].iloc[-6:-1].tolist()

    return {
        "code":               code,
        "name":               name,
        "price":              price,
        "open_price":         open_price,
        "high":               high,
        "low":                low,
        "prev_close":         prev_close,
        "volume":             volume,
        "avg_volume_5d":      avg_volume_5d,
        "change_pct":         round(change_pct, 2),
        "change_from_open_pct": round(change_from_open_pct, 2),
        "volume_ratio":       round(volume_ratio, 2),
        # 이동평균
        "ma5":                round(ma5, 0),
        "ma10":               round(ma10, 0),
        "ma20":               round(ma20, 0),
        "prev_ma5":           round(prev_ma5, 0),
        "prev_ma20":          round(prev_ma20, 0),
        # 지지/저항
        "high_20d":           high_20d,
        "low_20d":            low_20d,
        # 거래량 추세
        "volume_5d_trend":    volume_5d_trend,
    }


async def fetch_all_snapshots(codes: list) -> list:
    """여러 종목 동시 조회"""
    tasks = [fetch_stock_snapshot(code) for code in codes]
    results = await asyncio.gather(*tasks, return_exceptions=True)
    return [r for r in results if isinstance(r, dict)]
