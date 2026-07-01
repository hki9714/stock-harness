"""
대시보드 API 라우터
GET /api/dashboard/chart/{code}           - 차트 데이터 (OHLCV + 이동평균 + RSI)
GET /api/dashboard/financial/{code}       - 재무제표 (PER, PBR, ROE 등)
GET /api/dashboard/sentiment/{code}       - 감성 분석 (네이버 토론)
GET /api/dashboard/screening              - 종목 스크리닝
GET /api/dashboard/watchlist              - 감시 종목 전체 현황
GET /api/dashboard/backtest/{code}        - 백테스트 (단순보유 / 시그널진입)
"""
import asyncio
import logging
from datetime import datetime, timedelta
from typing import Optional

from fastapi import APIRouter

from crawler.stock_crawler import fetch_stock_snapshot, fetch_all_snapshots
from crawler.naver_crawler import fetch_discussion_posts, fetch_fundamentals
from analyzer.sentiment import analyze_posts
from bot.telegram_bot import get_watch_set
from models.config import settings

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/dashboard", tags=["dashboard"])


# ──────────────────────────────────────────
# 차트 데이터
# ──────────────────────────────────────────

@router.get("/chart/{code}")
async def get_chart(code: str, days: int = 60):
    """OHLCV + 이동평균(5/20/60일) + RSI(14) 반환"""
    try:
        loop = asyncio.get_event_loop()

        def _fetch():
            from pykrx import stock as krx
            from datetime import datetime, timedelta
            end   = datetime.today().strftime("%Y%m%d")
            start = (datetime.today() - timedelta(days=days * 2)).strftime("%Y%m%d")
            df    = krx.get_market_ohlcv_by_date(start, end, code)
            _n    = krx.get_market_ticker_name(code)
            name  = _n if isinstance(_n, str) and _n else code
            return df.tail(days), name

        df, name = await loop.run_in_executor(None, _fetch)
        if df is None or df.empty:
            return {"error": "데이터 없음"}

        # OHLCV
        candles = []
        for date, row in df.iterrows():
            candles.append({
                "time":  date.strftime("%Y-%m-%d"),
                "open":  int(row["시가"]),
                "high":  int(row["고가"]),
                "low":   int(row["저가"]),
                "close": int(row["종가"]),
                "volume": int(row["거래량"]),
            })

        # 이동평균
        closes = df["종가"]
        ma5  = closes.rolling(5).mean().fillna(0)
        ma20 = closes.rolling(20).mean().fillna(0)
        ma60 = closes.rolling(60).mean().fillna(0)

        def ma_series(series):
            return [
                {"time": date.strftime("%Y-%m-%d"), "value": round(float(v), 0)}
                for date, v in zip(df.index, series) if v > 0
            ]

        # RSI(14)
        delta  = closes.diff()
        gain   = delta.clip(lower=0).rolling(14).mean()
        loss   = (-delta.clip(upper=0)).rolling(14).mean()
        rs     = gain / loss.replace(0, 1)
        rsi    = (100 - 100 / (1 + rs)).fillna(50)
        rsi_series = [
            {"time": date.strftime("%Y-%m-%d"), "value": round(float(v), 2)}
            for date, v in zip(df.index, rsi)
        ]

        return {
            "code":    code,
            "name":    name,
            "candles": candles,
            "ma5":     ma_series(ma5),
            "ma20":    ma_series(ma20),
            "ma60":    ma_series(ma60),
            "rsi":     rsi_series,
        }

    except Exception as e:
        logger.error(f"[차트 API] {code}: {e}")
        return {"error": str(e)}


# ──────────────────────────────────────────
# 재무제표
# ──────────────────────────────────────────

@router.get("/financial/{code}")
async def get_financial(code: str):
    """PER, PBR, ROE, EPS, 시가총액 반환 (네이버 증권 크롤링)

    KRX 전종목 통계 API(get_market_fundamental_by_ticker 등)가 로그인 세션을
    요구하도록 바뀌어 항상 실패하므로, 네이버 증권 종목 페이지를 크롤링한다.
    """
    try:
        loop = asyncio.get_event_loop()

        def _get_name():
            from pykrx import stock as krx
            _n = krx.get_market_ticker_name(code)
            return _n if isinstance(_n, str) and _n else code

        name = await loop.run_in_executor(None, _get_name)
        data = await fetch_fundamentals(code)

        if data is None:
            return {"error": "재무 데이터 없음"}

        return {"code": code, "name": name, **data}

    except Exception as e:
        logger.error(f"[재무 API] {code}: {e}")
        return {"error": str(e)}


# ──────────────────────────────────────────
# 감성 분석
# ──────────────────────────────────────────

@router.get("/sentiment/{code}")
async def get_sentiment(code: str, hours: int = 6):
    """네이버 토론 감성 분석 결과 반환"""
    try:
        # hours에 비례해 페이지 수 결정 (페이지당 ~20건, early-exit 있으므로 과다 요청 방지됨)
        pages = min(hours * 3, 25)
        posts = await fetch_discussion_posts(code, pages=pages, hours_back=hours)
        positive_ratio, positive_count, total_count = analyze_posts(posts)

        # 12시간 이상은 날짜 포함 표시
        dt_fmt = "%m/%d %H:%M" if hours >= 12 else "%H:%M"

        return {
            "code":           code,
            "hours":          hours,
            "total_count":    total_count,
            "positive_count": positive_count,
            "negative_count": total_count - positive_count,
            "positive_ratio": positive_ratio,
            "sentiment":      "긍정" if positive_ratio >= 0.6 else "부정" if positive_ratio < 0.4 else "중립",
            "recent_posts":   [
                {"title": p["title"], "datetime": p["datetime"].strftime(dt_fmt)}
                for p in posts[:100]
            ],
        }

    except Exception as e:
        logger.error(f"[감성 API] {code}: {e}")
        return {"error": str(e)}


# ──────────────────────────────────────────
# 종목 스크리닝 (캐시 기반, 09:00/12:00/15:00 갱신)
# ──────────────────────────────────────────

@router.get("/screening")
async def get_screening():
    """
    정기 스크리닝 캐시 반환 (즉시 응답).
    데이터는 09:00 / 12:00 / 15:00 스케줄러가 갱신.
    캐시가 비어있으면 즉시 실행(최초 1회).
    """
    try:
        from analyzer.screener import get_cache, run_screening
        cache = get_cache()

        if not cache["results"] and not cache["running"]:
            # 최초 요청 시 백그라운드 실행
            asyncio.create_task(run_screening())
            return {
                "screened":       [],
                "updated_at":     None,
                "total_scanned":  0,
                "running":        True,
                "message":        "첫 스크리닝 실행 중입니다. 잠시 후 새로고침하세요.",
            }

        return {
            "screened":      cache["results"],
            "updated_at":    cache["updated_at"],
            "total_scanned": cache["total_scanned"],
            "running":       cache["running"],
        }

    except Exception as e:
        logger.error(f"[스크리닝 API]: {e}")
        return {"error": str(e)}


@router.post("/screening/refresh")
async def refresh_screening():
    """수동 스크리닝 재실행 (백그라운드)"""
    from analyzer.screener import get_cache, run_screening
    cache = get_cache()
    if cache["running"]:
        return {"message": "이미 실행 중입니다."}
    asyncio.create_task(run_screening())
    return {"message": "스크리닝을 시작했습니다. 잠시 후 새로고침하세요."}


# ──────────────────────────────────────────
# 감시 종목 전체 현황
# ──────────────────────────────────────────

# ──────────────────────────────────────────
# 백테스트
# ──────────────────────────────────────────

def _run_backtest_sync(
    code: str, start: str, end: str,
    strategy: str, hold_days: int,
    take_profit: float, stop_loss: float,
) -> dict:
    """
    백테스트 로직
    ─ 과거 기간(start~end) → 통계 학습 (변동성, 수익률 분포, MDD)
    ─ 현재가 → 시뮬레이션 기준점
    ─ 과거 패턴을 현재가에 적용 → 향후 시나리오 도출
    """
    from pykrx import stock as krx
    import math

    # ── 종목명 ──────────────────────────────────────────
    try:
        _n = krx.get_market_ticker_name(code)
        name = _n if isinstance(_n, str) and _n else code
    except Exception:
        name = code

    # ── 날짜 파싱 & 미래 예측 모드 감지 ─────────────────
    today     = datetime.today()
    today_str = today.strftime("%Y%m%d")
    start_dt  = datetime.strptime(start, "%Y%m%d")
    end_dt    = datetime.strptime(end,   "%Y%m%d")
    is_future_mode = end_dt.date() > today.date()

    # ── 과거 패턴 학습용 데이터 ──────────────────────────
    if is_future_mode:
        # end가 미래 → 실제 데이터로 학습
        if start_dt.date() < today.date():
            # start~오늘 구간 활용
            learn_start, learn_end = start, today_str
        else:
            # start도 미래 → 최근 2년(약 730일) 데이터로 학습
            learn_start = (today - timedelta(days=730)).strftime("%Y%m%d")
            learn_end   = today_str
        df = krx.get_market_ohlcv_by_date(learn_start, learn_end, code)
    else:
        df = krx.get_market_ohlcv_by_date(start, end, code)

    if df is None or df.empty:
        return {"error": "해당 기간의 데이터가 없습니다. 날짜 범위를 확인하세요."}
    if len(df) < 10:
        return {"error": f"데이터가 부족합니다 ({len(df)}거래일). 더 긴 기간을 선택하세요."}

    # ── 현재가 조회 (시뮬레이션 기준점) ──────────────────
    week_ago_str = (today - timedelta(days=10)).strftime("%Y%m%d")
    try:
        df_now = krx.get_market_ohlcv_by_date(week_ago_str, today_str, code)
        if df_now is not None and not df_now.empty:
            current_price = float(df_now["종가"].iloc[-1])
            current_date  = df_now.index[-1].strftime("%Y-%m-%d")
        else:
            raise ValueError("현재가 조회 실패")
    except Exception:
        current_price = float(df["종가"].iloc[-1])
        current_date  = df.index[-1].strftime("%Y-%m-%d")

    # ── 과거 통계 계산 ────────────────────────────────────
    closes        = df["종가"].astype(float)
    daily_ret     = closes.pct_change().dropna()
    n_days        = len(df)

    # 연환산 수익률 (기하평균)
    hist_total    = float(closes.iloc[-1] / closes.iloc[0] - 1)
    annual_return = (1 + hist_total) ** (252 / n_days) - 1

    # 연간 변동성
    annual_vol    = float(daily_ret.std() * math.sqrt(252))

    # 최대 낙폭 (MDD)
    cummax        = closes.cummax()
    mdd_pct       = float(((closes - cummax) / cummax * 100).min())

    # 샤프 비율 (무위험 이자율 3.5% 가정)
    rf_daily      = 0.035 / 252
    exc_ret       = daily_ret - rf_daily
    sharpe        = float(exc_ret.mean() / exc_ret.std() * math.sqrt(252)) if exc_ret.std() > 0 else 0.0

    # 칼마 비율 (연환산수익률 / |MDD|)
    calmar        = round(annual_return / abs(mdd_pct / 100), 2) if mdd_pct != 0 else 0.0

    # ── 현재가 기준 시나리오 예측 ─────────────────────────
    # 낙관: 연환산수익률 + 1σ / 기본: 연환산수익률 / 비관: 연환산수익률 − 1σ / 최악: 기간 비례 MDD
    def _proj(t_yr: float) -> dict:
        base  = (1 + annual_return) ** t_yr
        vol_t = annual_vol * math.sqrt(t_yr)
        bull  = base * (1 + vol_t)
        bear  = max(base * (1 - vol_t), 0.0)   # 변동성 > 100% 시 음수 방지
        # 최악: 기간이 짧을수록 전체 MDD 발생 가능성이 낮으므로 기간 비례 적용 (최대 1년치)
        worst = max(base * (1 + (mdd_pct / 100) * min(t_yr, 1.0)), 0.0)
        return {
            "bull_pct":  round((bull  - 1) * 100, 1),
            "base_pct":  round((base  - 1) * 100, 1),
            "bear_pct":  round((bear  - 1) * 100, 1),
            "worst_pct": round((worst - 1) * 100, 1),
            "bull_price":  int(current_price * bull),
            "base_price":  int(current_price * base),
            "bear_price":  int(current_price * bear),
            "worst_price": int(current_price * worst),
        }

    projections = {
        "1m": _proj(1 / 12),
        "3m": _proj(3 / 12),
        "6m": _proj(6 / 12),
        "1y": _proj(1.0),
    }
    if is_future_mode:
        forecast_years = max((end_dt - today).days / 365.0, 1 / 12)
        projections["target"] = _proj(forecast_years)

    # 수익률 곡선 (현재가 기준으로 정규화)
    equity_curve = [
        {"date": d.strftime("%Y-%m-%d"),
         "pct":  round((float(v) / float(closes.iloc[0]) - 1) * 100, 2)}
        for d, v in zip(df.index, closes)
    ]

    # ── 공통 결과 ────────────────────────────────────────
    common = {
        "code": code, "name": name, "strategy": strategy,
        "current_price": int(current_price),
        "current_date":  current_date,
        "hist_start":    df.index[0].strftime("%Y-%m-%d"),
        "hist_end":      df.index[-1].strftime("%Y-%m-%d"),
        "hist_days":     n_days,
        "hist_total_return_pct": round(hist_total * 100, 2),
        "annual_return_pct":     round(annual_return * 100, 2),
        "annual_return_note":    (
            f"주의: {n_days}거래일({round(n_days/21):.0f}개월) — 연환산 수치 오차 가능"
            if n_days < 126 else None
        ),
        "annual_vol_pct":        round(annual_vol * 100, 2),
        "mdd_pct":               round(mdd_pct, 2),
        "sharpe":                round(sharpe, 2),
        "calmar":                round(calmar, 2),
        "projections":           projections,
        "equity_curve":          equity_curve,
        "is_future_mode":        is_future_mode,
        "target_date":           end_dt.strftime("%Y-%m-%d") if is_future_mode else None,
    }

    # ── 전략 1: 단순 보유 (패턴 학습 + 예측) ──────────────
    if strategy == "hold":
        return {**common, "strategy": "단순 보유"}

    # ── 전략 2: 시그널 진입 (과거 시그널 검증 + 현재 진입 판단) ──
    if strategy == "signal":
        df2          = df.copy()
        df2["va5"]   = df2["거래량"].rolling(5).mean().shift(1)
        df2["pc"]    = df2["종가"].shift(1)
        vol_thr      = settings.volume_surge_ratio
        price_thr    = 1.0 + settings.price_surge_pct / 100.0

        trades = []
        i = 5
        while i < len(df2) - 1:
            row = df2.iloc[i]
            va, pc = row["va5"], row["pc"]
            if (va > 0 and row["거래량"] >= va * vol_thr
                    and pc > 0 and row["종가"] >= pc * price_thr):
                ei  = i + 1
                ep  = float(df2.iloc[ei]["시가"])
                edt = df2.index[ei].strftime("%Y-%m-%d")
                edi = min(ei + hold_days, len(df2) - 1)
                xp  = float(df2.iloc[edi]["종가"])
                xdt = df2.index[edi].strftime("%Y-%m-%d")
                why = "보유 만료"
                for j in range(ei + 1, edi + 1):
                    hi = float(df2.iloc[j]["고가"])
                    lo = float(df2.iloc[j]["저가"])
                    if (hi / ep - 1) * 100 >= take_profit:
                        xp, xdt, why = ep * (1 + take_profit / 100), df2.index[j].strftime("%Y-%m-%d"), f"익절 (+{take_profit:.0f}%)"
                        edi = j; break
                    if (lo / ep - 1) * 100 <= -stop_loss:
                        xp, xdt, why = ep * (1 - stop_loss / 100), df2.index[j].strftime("%Y-%m-%d"), f"손절 (-{stop_loss:.0f}%)"
                        edi = j; break
                ret = round((xp / ep - 1) * 100, 2)
                trades.append({"entry_date": edt, "entry_price": int(ep),
                                "exit_date": xdt, "exit_price": int(xp),
                                "return_pct": ret, "exit_reason": why})
                i = edi + 1
            else:
                i += 1

        rets = [t["return_pct"] for t in trades]
        wins = [r for r in rets if r > 0]

        # 복리 누적 수익률 (단순 합산이 아닌 곱연산)
        compound = 1.0
        for r in rets:
            compound *= (1 + r / 100)
        total_compound_pct = round((compound - 1) * 100, 2)

        # 과거 시그널 거래 통계 기반 다음 진입 시나리오 예측
        signal_projection = None
        if trades:
            avg_r   = sum(rets) / len(rets)
            var_r   = sum((r - avg_r) ** 2 for r in rets) / len(rets)
            std_r   = var_r ** 0.5
            worst_r = min(rets)
            signal_projection = {
                "bull_pct":    round(avg_r + std_r, 1),
                "base_pct":    round(avg_r, 1),
                "bear_pct":    round(avg_r - std_r, 1),
                "worst_pct":   round(worst_r, 1),
                "bull_price":  int(max(current_price * (1 + (avg_r + std_r) / 100), 0)),
                "base_price":  int(max(current_price * (1 + avg_r / 100), 0)),
                "bear_price":  int(max(current_price * (1 + (avg_r - std_r) / 100), 0)),
                "worst_price": int(max(current_price * (1 + worst_r / 100), 0)),
                "hold_days":   hold_days,
                "sample_count": len(trades),
            }

        # 현재 시그널 여부 판단 (df_now 기반)
        signal_now = False
        try:
            df_chk = krx.get_market_ohlcv_by_date(
                (today - timedelta(days=14)).strftime("%Y%m%d"),
                today_str, code
            )
            if df_chk is not None and len(df_chk) >= 6:
                va5_now = float(df_chk["거래량"].iloc[-6:-1].mean())
                vol_now = float(df_chk["거래량"].iloc[-1])
                pc_now  = float(df_chk["종가"].iloc[-2])
                cl_now  = float(df_chk["종가"].iloc[-1])
                signal_now = (va5_now > 0 and vol_now >= va5_now * vol_thr
                              and pc_now > 0 and cl_now >= pc_now * price_thr)
        except Exception:
            pass

        return {
            **common, "strategy": "시그널 진입",
            "trade_count":       len(trades),
            "win_rate":          round(len(wins) / len(trades) * 100, 1) if trades else 0.0,
            "avg_return_pct":    round(sum(rets) / len(rets), 2) if rets else 0.0,
            "total_return_pct":  total_compound_pct,
            "signal_now":        signal_now,
            "signal_projection": signal_projection,
            "trades":            trades,
        }

    return {"error": f"알 수 없는 전략: {strategy}"}


@router.get("/backtest/{code}")
async def get_backtest(
    code: str,
    start: str,
    end: str,
    strategy: str  = "hold",
    hold_days: int = 20,
    take_profit: float = 10.0,
    stop_loss:   float = 5.0,
):
    """백테스트 실행 (단순보유 / 시그널진입)"""
    try:
        loop   = asyncio.get_event_loop()
        result = await loop.run_in_executor(
            None,
            lambda: _run_backtest_sync(code, start, end, strategy, hold_days, take_profit, stop_loss),
        )
        return result
    except Exception as e:
        logger.error(f"[백테스트 API] {code}: {e}")
        return {"error": str(e)}


@router.get("/watchlist")
async def get_watchlist_status():
    """감시 종목 전체 현황 (스냅샷 + 시그널 상태)"""
    try:
        codes     = list(get_watch_set())
        snapshots = await fetch_all_snapshots(codes)

        result = []
        for s in snapshots:
            signal = "🚨 매수" if (
                s["volume_ratio"] >= settings.volume_surge_ratio
                and s["change_pct"] >= settings.price_surge_pct
            ) else "🔥 거래량" if s["volume_ratio"] >= settings.volume_surge_ratio else "–"

            result.append({**s, "signal": signal})

        result.sort(key=lambda x: x["change_pct"], reverse=True)
        return {
            "watchlist": result,
            "updated":   datetime.now().strftime("%H:%M:%S"),
        }

    except Exception as e:
        logger.error(f"[감시목록 API]: {e}")
        return {"error": str(e)}
