import httpx
import asyncio
from bs4 import BeautifulSoup
from datetime import datetime, timedelta
from typing import List, Dict, Optional


HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0 Safari/537.36"
    ),
    "Referer": "https://finance.naver.com/",
}

BOARD_URL     = "https://finance.naver.com/item/board.naver"
MAIN_PAGE_URL = "https://finance.naver.com/item/main.naver"


async def fetch_discussion_posts(
    code: str,
    pages: int = 3,
    hours_back: int = 1,
) -> List[Dict]:
    """
    네이버 증권 토론방 최근 게시글 수집
    - pages: 크롤링할 페이지 수
    - hours_back: 몇 시간 이내 게시글만 수집
    """
    cutoff = datetime.now() - timedelta(hours=hours_back)
    posts = []

    async with httpx.AsyncClient(headers=HEADERS, timeout=10.0) as client:
        for page in range(1, pages + 1):
            try:
                res = await client.get(
                    BOARD_URL,
                    params={"code": code, "page": page},
                )
                res.raise_for_status()
            except Exception as e:
                print(f"[토론 크롤링 실패] {code} p{page}: {e}")
                break

            soup = BeautifulSoup(res.text, "html.parser")
            rows = soup.select("table.type2 tr")

            page_has_old = False
            for row in rows:
                tds      = row.find_all("td")
                title_td = row.select_one("td.title a")
                # 네이버 토론 현재 구조: tds[0]=날짜, tds[1]=제목, tds[2]=작성자, tds[3]=조회, tds[4]=공감
                if not title_td or len(tds) < 2:
                    continue

                raw_date = tds[0].get_text(strip=True)
                try:
                    # 네이버 현재 날짜 형식: "YYYY.MM.DD HH:MM"
                    post_dt = datetime.strptime(raw_date, "%Y.%m.%d %H:%M")
                except ValueError:
                    continue

                if post_dt < cutoff:
                    page_has_old = True
                    continue

                posts.append({
                    "title":    title_td.get_text(strip=True),
                    "datetime": post_dt,
                    "views":    _parse_int(tds[3]) if len(tds) > 3 else 0,
                    "agree":    _parse_int(tds[4]) if len(tds) > 4 else 0,
                })

            # 해당 페이지에 오래된 글이 있으면 더 이상 페이징 불필요
            if page_has_old:
                break

            await asyncio.sleep(0.3)  # 서버 부하 방지

    return posts


def _parse_int(td) -> int:
    if td is None:
        return 0
    try:
        return int(td.get_text(strip=True).replace(",", ""))
    except ValueError:
        return 0


def _num(el) -> float:
    if el is None:
        return 0.0
    try:
        return float(el.get_text(strip=True).replace(",", ""))
    except ValueError:
        return 0.0


def _parse_market_cap(em) -> int:
    """'1,856조 1,935' 형태(조 단위 + 억 단위)를 원 단위 정수로 변환"""
    if em is None:
        return 0
    raw = em.get_text(" ", strip=True)
    try:
        if "조" in raw:
            jo_part, eok_part = raw.split("조", 1)
            jo  = int(jo_part.replace(",", "").strip() or 0)
            eok = int(eok_part.replace(",", "").strip() or 0)
        else:
            jo, eok = 0, int(raw.replace(",", "").strip() or 0)
    except ValueError:
        return 0
    return jo * 10 ** 12 + eok * 10 ** 8


def _parse_roe(soup: BeautifulSoup) -> float:
    """'기업실적분석' 표에서 최근 연간 실적 중 확정치(추정치 제외) ROE(지배주주) 추출"""
    for table in soup.select("table.tb_type1.tb_num"):
        head_rows = table.select("thead tr")
        if len(head_rows) < 2:
            continue
        headers = [th.get_text(strip=True) for th in head_rows[1].find_all("th")]

        roe_row = None
        for tr in table.select("tbody tr"):
            th = tr.find("th")
            if th and "ROE" in th.get_text():
                roe_row = tr
                break
        if roe_row is None:
            continue

        values = [td.get_text(strip=True) for td in roe_row.find_all("td")]
        roe = 0.0
        for h, v in zip(headers[:4], values[:4]):  # 최근 연간 실적 4개 컬럼만
            if v and "(E)" not in h:
                try:
                    roe = float(v.replace(",", ""))
                except ValueError:
                    pass
        return roe
    return 0.0


async def fetch_fundamentals(code: str) -> Optional[Dict]:
    """
    네이버 증권 종목 메인 페이지에서 PER/PBR/EPS/BPS/배당수익률/시가총액/ROE 수집.
    KRX의 전종목 통계 API(get_market_fundamental_by_ticker 등)는 로그인 세션을
    요구하도록 바뀌어 더 이상 사용할 수 없어, 네이버 증권 크롤링으로 대체한다.
    """
    async with httpx.AsyncClient(headers=HEADERS, timeout=10.0) as client:
        try:
            res = await client.get(MAIN_PAGE_URL, params={"code": code})
            res.raise_for_status()
        except Exception as e:
            print(f"[재무 크롤링 실패] {code}: {e}")
            return None

    soup = BeautifulSoup(res.text, "html.parser")

    per       = _num(soup.select_one("#_per"))
    eps       = _num(soup.select_one("#_eps"))
    pbr       = _num(soup.select_one("#_pbr"))
    div_yield = _num(soup.select_one("#_dvr"))

    bps = 0.0
    pbr_em = soup.select_one("#_pbr")
    if pbr_em is not None:
        ems = pbr_em.find_parent("td").find_all("em")
        if len(ems) > 1:
            bps = _num(ems[1])

    market_cap = _parse_market_cap(soup.select_one("#_market_sum"))
    roe        = _parse_roe(soup)

    return {
        "per":        round(per, 2),
        "pbr":        round(pbr, 2),
        "eps":        round(eps, 0),
        "bps":        round(bps, 0),
        "roe":        round(roe, 2),
        "div_yield":  round(div_yield, 2),
        "market_cap": market_cap,
        "market_cap_trillion": round(market_cap / 1e12, 2),
    }
