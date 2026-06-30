import httpx
import asyncio
from bs4 import BeautifulSoup
from datetime import datetime, timedelta
from typing import List, Dict


HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0 Safari/537.36"
    ),
    "Referer": "https://finance.naver.com/",
}

BOARD_URL = "https://finance.naver.com/item/board.naver"


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
