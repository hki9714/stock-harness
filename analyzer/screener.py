"""
정기 종목 스크리닝 엔진 (09:00 / 12:00 / 15:00 KST)

흐름:
  시가총액 상위 100개 종목 조회 (KOSPI)
  → 30일 OHLCV + 기술 분석 점수화
  → 점수 상위 10개를 메모리 캐시에 저장
  → /api/dashboard/screening 에서 캐시 즉시 반환
"""
import asyncio
import json
import logging
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional

from crawler.stock_crawler import fetch_stock_snapshot
from analyzer.signal_engine import score_snapshot

logger = logging.getLogger(__name__)

# ── 메모리 캐시 ────────────────────────────────────────────────
_cache: dict = {
    "results":       [],
    "updated_at":    None,   # "HH:MM" 형태
    "total_scanned": 0,
    "running":       False,
}

_CONCURRENCY = 10            # 동시 종목 조회 제한 (KRX API 부하 방지)
_TOP_N       = 10            # 최종 선별 종목 수
_UNIVERSE    = 100           # 시가총액 상위 N개를 대상으로 스크리닝

# 마지막 성공한 시가총액 순위를 영속 저장 (장외 시간 재사용)
_UNIVERSE_CACHE = Path(__file__).parent / "data" / "kospi_universe.json"

# KRX API 전체 실패 시 최후 수단 하드코딩 목록
_KOSPI_FALLBACK_CODES = [
    "005930", "000660", "207940", "005380", "000270",  # 삼성전자 SK하이닉스 삼성바이오 현대차 기아
    "068270", "373220", "005490", "051910", "006400",  # 셀트리온 LG에너지솔루션 POSCO홀딩스 LG화학 삼성SDI
    "028260", "012330", "066570", "003550", "086790",  # 삼성물산 현대모비스 LG전자 LG 하나금융지주
    "105560", "055550", "316140", "032830", "009540",  # KB금융 신한지주 우리금융지주 삼성생명 HD한국조선해양
    "329180", "010950", "034020", "096770", "034730",  # HD현대중공업 S-Oil 두산에너빌리티 SK이노베이션 SK
    "017670", "030200", "015760", "011070", "003670",  # SK텔레콤 KT 한국전력 LG이노텍 포스코퓨처엠
    "247540", "086520", "035720", "035420", "267250",  # 에코프로비엠 에코프로 카카오 NAVER HD현대
    "042660", "010130", "009150", "021240", "012450",  # 한화오션 고려아연 삼성전기 코웨이 한화에어로스페이스
    "259960", "323410", "138040", "000810", "078930",  # 크래프톤 카카오뱅크 메리츠금융지주 삼성화재 GS
    "011200", "051600", "064350", "009830", "004020",  # HMM 한전KPS 현대로템 한화솔루션 현대제철
    "090430", "051900", "003490", "000720", "047810",  # 아모레퍼시픽 LG생활건강 대한항공 현대건설 한국항공우주
    "241560", "302440", "377300", "352820", "036570",  # 두산밥캣 SK바이오사이언스 카카오페이 하이브 엔씨소프트
    "000100", "006800", "016360", "032640", "024110",  # 유한양행 미래에셋증권 삼성증권 LG유플러스 기업은행
    "003600", "004370", "097950", "010140", "011780",  # SK케미칼 농심 CJ제일제당 삼성중공업 금호석유
    "000080", "161390", "069960", "180640", "001450",  # 하이트진로 한국타이어 현대백화점 한진칼 현대해상
    "005830", "082640", "175330", "071050", "005940",  # DB손해보험 DB하이텍 JB금융지주 한국금융지주 NH투자증권
    "006360", "028050", "000150", "086280", "036460",  # GS건설 삼성엔지니어링 두산 현대글로비스 한국가스공사
    "251270", "035900", "041510", "122870", "030000",  # 넷마블 JYP엔터 SM엔터 YG엔터 제일기획
    "000370", "001040", "002380", "004800", "139130",  # 한화손해보험 CJ KCC 효성 DGB금융지주
    "033780", "009420", "000210", "011790", "064960",  # KT&G 한올바이오파마 DL SKC S&T모티브
]


def get_cache() -> dict:
    return _cache


def _save_universe(codes: list[str], names: dict[str, str] | None = None) -> None:
    """시가총액 기준 종목 순서 + 이름을 파일에 저장 (장 마감 후 재사용)"""
    try:
        _UNIVERSE_CACHE.parent.mkdir(parents=True, exist_ok=True)
        _UNIVERSE_CACHE.write_text(
            json.dumps({
                "codes": codes,
                "names": names or {},
                "saved_at": datetime.now().strftime("%Y-%m-%d %H:%M"),
            }, ensure_ascii=False),
            encoding="utf-8",
        )
    except Exception as e:
        logger.warning(f"[스크리너] 유니버스 저장 실패: {e}")


def _load_universe(n: int) -> tuple[list[str], dict[str, str]]:
    """마지막으로 저장된 시가총액 순 목록 + 이름 로드"""
    try:
        if _UNIVERSE_CACHE.exists():
            data = json.loads(_UNIVERSE_CACHE.read_text(encoding="utf-8"))
            saved_at = data.get("saved_at", "")
            codes = data.get("codes", [])[:n]
            names = data.get("names", {})
            if codes:
                logger.info(f"[스크리너] 방법3 성공: 마지막 거래일 캐시 ({saved_at}, {len(codes)}개)")
                return codes, names
    except Exception as e:
        logger.warning(f"[스크리너] 유니버스 로드 실패: {e}")
    return [], {}


def _fetch_top_codes_sync(n: int = _UNIVERSE) -> tuple[list[str], dict[str, str]]:
    """
    KOSPI 상위 n개 종목 코드 + 이름 반환 (동기, executor 내부 실행)
    반환: (codes, {code: name})  — names가 있으면 개별 name API 호출 생략 가능

    방법1: FinanceDataReader  — 시가총액 정렬 + 이름 포함 (장중/직후 주력)
    방법2: KOSPI 200 구성종목 — pykrx 인덱스 엔드포인트 (이름 없음)
    방법3: kospi_universe.json — 마지막 거래일 캐시 (장외 주력)
    방법4: 하드코딩 목록      — 캐시 파일 없을 때 최후 수단
    """
    from pykrx import stock as krx

    # 방법1: FinanceDataReader — Name 컬럼도 함께 제공
    try:
        import FinanceDataReader as fdr
        df = fdr.StockListing("KOSPI")
        if df is not None and not df.empty and "Marcap" in df.columns:
            df_top = df.sort_values("Marcap", ascending=False).head(n)
            codes  = df_top["Code"].tolist()
            names  = dict(zip(df_top["Code"], df_top["Name"])) if "Name" in df_top.columns else {}
            logger.info(f"[스크리너] 방법1 성공: FDR 시가총액 기준 ({len(codes)}개, 이름 {len(names)}개) → 캐시 저장")
            _save_universe(codes, names)
            return codes, names
    except Exception as e:
        logger.warning(f"[스크리너] 방법1 실패 → 방법2 시도 ({type(e).__name__}: {e})")

    # 방법2: KOSPI 200 구성종목 (이름 없음)
    for delta in range(0, 6):
        d = (datetime.today() - timedelta(days=delta)).strftime("%Y%m%d")
        try:
            tickers = krx.get_index_portfolio_deposit_file("1028", d)
            if tickers is not None and len(tickers) > 10:
                logger.info(f"[스크리너] 방법2 성공: KOSPI 200 구성종목 ({d}, {len(tickers)}개)")
                return list(tickers[:n]), {}
        except Exception:
            continue

    # 방법3: 마지막 거래일 캐시 (이름 포함)
    logger.warning("[스크리너] 방법1·2 실패 → 방법3: 캐시 파일 시도")
    cached_codes, cached_names = _load_universe(n)
    if cached_codes:
        return cached_codes, cached_names

    # 방법4: 하드코딩 목록 (이름 없음)
    logger.warning("[스크리너] 방법1·2·3 모두 실패 → 방법4: 하드코딩 목록 사용")
    return _KOSPI_FALLBACK_CODES[:n], {}


async def run_screening(top_n: int = _TOP_N) -> dict:
    """
    스크리닝 실행 (APScheduler 09:00/12:00/15:00 에서 호출).
    이미 실행 중이면 스킵. 결과를 _cache 에 저장하고 반환.
    """
    if _cache["running"]:
        logger.info("[스크리너] 이미 실행 중 — 스킵")
        return _cache

    _cache["running"] = True
    logger.info("[스크리너] 시작")
    start = datetime.now()

    try:
        loop = asyncio.get_event_loop()

        # 1. 시가총액 상위 종목 목록 + 이름 (이름이 있으면 개별 name API 호출 생략)
        codes, names_dict = await loop.run_in_executor(None, _fetch_top_codes_sync, _UNIVERSE)
        if not codes:
            logger.error("[스크리너] 종목 목록 조회 실패")
            return _cache
        logger.info(f"[스크리너] {len(codes)}개 종목 분석 시작 (사전 이름 {len(names_dict)}개 확보)")

        # 확보한 이름을 크롤러 전역 캐시에 주입 → 감시 종목 조회 시에도 재활용
        if names_dict:
            from crawler.stock_crawler import populate_name_cache
            populate_name_cache(names_dict)

        # 2. 동시 제한 + 스냅샷 조회 (종목별 타임아웃 + 완료 즉시 캐시 갱신)
        sem = asyncio.Semaphore(_CONCURRENCY)
        _STOCK_TIMEOUT = 12.0  # 종목 1개 최대 대기 (초) — 초과 시 스킵

        async def _fetch_one(code: str) -> Optional[dict]:
            async with sem:
                try:
                    return await asyncio.wait_for(
                        fetch_stock_snapshot(code, name=names_dict.get(code)),
                        timeout=_STOCK_TIMEOUT,
                    )
                except asyncio.TimeoutError:
                    logger.warning(f"[스크리너] {code} 타임아웃 ({_STOCK_TIMEOUT}s) — 스킵")
                    return None

        scored_live: list = []  # 완료된 종목 누적 (실시간 정렬용)

        tasks = [asyncio.create_task(_fetch_one(c)) for c in codes]
        for coro in asyncio.as_completed(tasks):
            snap = await coro
            if not isinstance(snap, dict):
                continue
            try:
                analysis = score_snapshot(snap)
                scored_live.append({**snap, **analysis})
            except Exception as e:
                logger.debug(f"[스크리너] {snap.get('code')} 점수 계산 실패: {e}")

            # 완료된 종목만으로 상위 top_n 정렬 → 프론트 폴링 때마다 중간 결과 노출
            scored_live.sort(
                key=lambda x: (x.get("total_score", 0), x.get("volume_ratio", 0)),
                reverse=True,
            )
            _cache["results"]       = scored_live[:top_n]
            _cache["total_scanned"] = len(scored_live)

        _cache["updated_at"] = datetime.now().strftime("%Y-%m-%d %H:%M")
        elapsed = (datetime.now() - start).seconds
        logger.info(
            f"[스크리너] 완료: {len(scored_live)}개 분석 → 상위 {len(_cache['results'])}개 선별 ({elapsed}s)"
        )

    except Exception as e:
        logger.exception("[스크리너] 오류: %s", str(e))
    finally:
        _cache["running"] = False

    return _cache
