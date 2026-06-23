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
                title_td = row.select_one("td.title a")
                date_td = row.select_one("td.date")
                if not title_td or not date_td:
                    continue

                raw_date = date_td.get_text(strip=True)
                try:
                    # 오늘 날짜 + 시간 조합 (네이버 형식: "HH:MM" 또는 "YY.MM.DD")
                    if "." in raw_date and len(raw_date) > 5:
                        post_dt = datetime.strptime(
                            f"{datetime.now().year}.{raw_date}", "%Y.%y.%m.%d"
                        )
                    else:
                        time_part = datetime.strptime(raw_date, "%H:%M").time()
                        post_dt = datetime.combine(datetime.today(), time_part)
                except ValueError:
                    continue

                if post_dt < cutoff:
                    page_has_old = True
                    continue

                posts.append({
                    "title": title_td.get_text(strip=True),
                    "datetime": post_dt,
                    "views": _parse_int(row.select_one("td.hit")),
                    "agree": _parse_int(row.select_one("td.num")),
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
