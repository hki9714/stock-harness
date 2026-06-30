from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional


@dataclass
class StockSnapshot:
    """특정 시점의 종목 스냅샷"""
    code: str
    name: str
    price: float
    prev_close: float
    volume: int
    avg_volume_5d: float          # 5일 평균 거래량
    change_pct: float             # 전일 대비 등락률 %
    volume_ratio: float           # 거래량 / 5일 평균
    timestamp: datetime = field(default_factory=datetime.now)


@dataclass
class SentimentSnapshot:
    """네이버 토론 감성 분석 결과"""
    code: str
    positive_ratio: float         # 긍정 비율 0~1
    positive_count: int           # 최근 1시간 긍정 게시글 수
    total_count: int              # 최근 1시간 전체 게시글 수
    sample_titles: list           # 대표 게시글 제목 3개
    timestamp: datetime = field(default_factory=datetime.now)


@dataclass
class BuySignal:
    """종합 매수 시그널"""
    code: str
    name: str
    score: int                      # 기본 조건 충족 수 (0~3)

    # ── 기본 조건 ────────────────────────────────────────────────
    volume_surge: bool = False      # 거래량 급등 + 주가 상승
    price_surge: bool = False       # 전일 대비 5%+
    sentiment_surge: bool = False   # 토론 긍정 급증

    # ── 기술적 분석 조건 ─────────────────────────────────────────
    golden_cross: bool = False      # MA5가 MA20을 상향 돌파 (이미지04/10)
    dead_cross: bool = False        # MA5가 MA20을 하향 돌파
    ma_uptrend: bool = False        # 정배열 MA5 > MA10 > MA20 (강세 구조)
    long_bull: bool = False         # 장대양봉 (몸통 70%+, 등락률 2%+)  이미지11 58%
    long_bear: bool = False         # 장대음봉
    resistance_break: bool = False  # 20일 고가 돌파 (저항 → 지지 전환) 이미지03
    volume_breakout: bool = False   # 수렴 후 거래량 급증 (쐐기/삼각형) 이미지06/15
    technical_score: int = 0        # 기술적 조건 합산 점수

    # ── 수치 데이터 ──────────────────────────────────────────────
    price: float = 0.0
    change_pct: float = 0.0
    volume_ratio: float = 0.0
    positive_ratio: float = 0.0
    ma5: float = 0.0
    ma20: float = 0.0
    high_20d: float = 0.0
    sample_titles: list = field(default_factory=list)
    timestamp: datetime = field(default_factory=datetime.now)

    @property
    def is_buy(self) -> bool:
        """
        매수 시그널 판정:
        필수: 거래량급등 + 주가상승
        보조: 감성급증 OR 기술적 조건 2개 이상 (이미지 확률 기반)
        """
        tech_count = sum([
            self.golden_cross,
            self.ma_uptrend,
            self.long_bull,
            self.resistance_break,
            self.volume_breakout,
        ])
        return (
            self.volume_surge
            and self.price_surge
            and (self.sentiment_surge or tech_count >= 2)
        )

    @property
    def is_volume_alert(self) -> bool:
        """거래량 단독 급등 알림"""
        return self.volume_surge and self.volume_ratio >= 3.0


@dataclass
class VolumeAlert:
    """거래량 급등 단독 알림"""
    code: str
    name: str
    price: float
    change_pct: float
    volume_ratio: float           # 전일 평균 대비 배수
    volume: int
    timestamp: datetime = field(default_factory=datetime.now)


@dataclass
class PriceDropAlert:
    """당일 시가 대비 급락 알림"""
    code: str
    name: str
    price: float
    open_price: float
    drop_pct: float               # 시가 대비 하락률 (음수)
    timestamp: datetime = field(default_factory=datetime.now)
