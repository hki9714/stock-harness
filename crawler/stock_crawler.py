import asyncio
from datetime import datetime, timedelta
from typing import Optional
import pandas as pd

# pykrx는 동기 라이브러리이므로 executor로 비동기 처리
from pykrx import stock as krx


def _fetch_ohlcv_sync(code: str, days: int = 10) -> Optional[pd.DataFrame]:
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
        return krx.get_market_ticker_name(code)
    except Exception:
        return code


async def fetch_stock_snapshot(code: str) -> Optional[dict]:
    """
    종목 스냅샷 비동기 조회
    반환: {name, price, prev_close, volume, avg_volume_5d, change_pct, volume_ratio}
    """
    loop = asyncio.get_event_loop()

    df = await loop.run_in_executor(None, _fetch_ohlcv_sync, code, 7)
    name = await loop.run_in_executor(None, _fetch_name_sync, code)

    if df is None or len(df) < 2:
        return None

    today = df.iloc[-1]
    prev = df.iloc[-2]

    price = float(today["종가"])
    prev_close = float(prev["종가"])
    volume = int(today["거래량"])
    avg_volume_5d = float(df["거래량"].iloc[-6:-1].mean())  # 직전 5일 평균

    change_pct = ((price - prev_close) / prev_close) * 100
    volume_ratio = volume / avg_volume_5d if avg_volume_5d > 0 else 0

    return {
        "code": code,
        "name": name,
        "price": price,
        "prev_close": prev_close,
        "volume": volume,
        "avg_volume_5d": avg_volume_5d,
        "change_pct": round(change_pct, 2),
        "volume_ratio": round(volume_ratio, 2),
    }


async def fetch_all_snapshots(codes: list) -> list:
    """여러 종목 동시 조회"""
    tasks = [fetch_stock_snapshot(code) for code in codes]
    results = await asyncio.gather(*tasks, return_exceptions=True)
    return [r for r in results if isinstance(r, dict)]
