import asyncio
import logging
from datetime import datetime, timedelta
from typing import Optional
import pandas as pd

# pykrx는 동기 라이브러리이므로 executor로 비동기 처리
from pykrx import stock as krx

logger = logging.getLogger(__name__)

# screener에서 FDR로 사전 확보한 이름을 캐싱 (KRX 개별 name API 호출 절감)
_name_cache: dict = {}
_fdr_loaded:  bool = False  # FDR 전종목 폴백 1회 로드 플래그


def populate_name_cache(names: dict) -> None:
    """screener가 FDR에서 얻은 {code: name} 딕셔너리를 전역 캐시에 주입"""
    _name_cache.update(names)


def _load_fdr_names() -> None:
    """FDR 전종목 리스트로 이름 캐시 보충 (ETF 등 pykrx 미지원 종목 대비, 1회만 실행)"""
    global _fdr_loaded
    if _fdr_loaded:
        return
    _fdr_loaded = True  # 실패해도 재시도 방지
    try:
        import FinanceDataReader as fdr
        for market in ("KOSPI", "KOSDAQ"):
            df = fdr.StockListing(market)
            if df is None or df.empty or "Code" not in df.columns or "Name" not in df.columns:
                continue
            for _, row in df.iterrows():
                c = str(row["Code"]).strip().zfill(6)
                n = str(row["Name"]).strip()
                if len(c) == 6 and n and c not in _name_cache:
                    _name_cache[c] = n
        logger.debug("[stock_crawler] FDR 이름 캐시 보충 완료 (%d종목)", len(_name_cache))
    except Exception as e:
        logger.warning("[stock_crawler] FDR 이름 캐시 로드 실패: %s", e)


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


def _fetch_name_from_naver(code: str) -> Optional[str]:
    """Naver Finance 페이지 제목에서 종목명 추출 (ETF 포함 모든 종목 커버)"""
    try:
        import requests
        from bs4 import BeautifulSoup
        url = f"https://finance.naver.com/item/main.naver?code={code}"
        resp = requests.get(url, headers={"User-Agent": "Mozilla/5.0"}, timeout=4)
        if resp.status_code == 200:
            soup = BeautifulSoup(resp.text, "html.parser")
            title_tag = soup.find("title")
            if title_tag and " : " in title_tag.text:
                name = title_tag.text.split(" : ")[0].strip()
                if name and name != code:
                    return name
    except Exception:
        pass
    return None


def _fetch_name_sync(code: str) -> str:
    if code in _name_cache:
        return _name_cache[code]

    # 1차: pykrx (장중에는 일반 주식·ETF 모두 정상 동작)
    try:
        result = krx.get_market_ticker_name(code)
        # 장외 시간에 pykrx가 {} 또는 None 반환하는 버그 방어
        if isinstance(result, str) and result:
            _name_cache[code] = result
            return result
    except Exception:
        pass

    # 2차: FDR 전종목 리스트 (일반 주식 보완, 장외 시간 대응)
    _load_fdr_names()
    if code in _name_cache:
        return _name_cache[code]

    # 3차: Naver Finance 페이지 (ETF·기타 특수 종목 최종 수단)
    name = _fetch_name_from_naver(code)
    if name:
        _name_cache[code] = name
        logger.debug("[stock_crawler] Naver Finance에서 이름 조회: %s → %s", code, name)
        return name

    return code


async def fetch_stock_snapshot(code: str, name: Optional[str] = None) -> Optional[dict]:
    """
    종목 스냅샷 비동기 조회 (30일 데이터 기반 기술적 분석 포함)
    반환: 기본 OHLCV + 이동평균선 + 지지/저항 + 거래량 추세
    name이 제공되면 KRX name API 호출을 생략한다.
    """
    loop = asyncio.get_event_loop()

    df = await loop.run_in_executor(None, _fetch_ohlcv_sync, code, 30)
    if name is None:
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
