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
    score: int                    # 충족 조건 수 (최대 3)

    # 조건별 충족 여부
    volume_surge: bool = False    # 거래량 급등 + 주가 상승
    price_surge: bool = False     # 전일 대비 5%+
    sentiment_surge: bool = False # 토론 긍정 급증

    # 수치 데이터
    price: float = 0.0
    change_pct: float = 0.0
    volume_ratio: float = 0.0
    positive_ratio: float = 0.0
    sample_titles: list = field(default_factory=list)
    timestamp: datetime = field(default_factory=datetime.now)

    @property
    def is_buy(self) -> bool:
        """3조건 모두 충족 시 매수 시그널"""
        return self.volume_surge and self.price_surge and self.sentiment_surge

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
