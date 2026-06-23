"""
감성 분석 엔진
- 우선: snunlp/KR-FinBert-SC (금융 특화 한국어 BERT)
- 폴백: 키워드 기반 룰 (모델 로드 실패 시)
"""
from typing import List, Dict, Tuple
import re

# 긍정/부정 키워드 (폴백용)
POSITIVE_KEYWORDS = [
    "급등", "상한가", "돌파", "신고가", "매수", "호재", "실적", "흑자",
    "상승", "강세", "저평가", "추천", "올라", "오른다", "기대", "좋다",
    "성장", "기관매수", "외인매수", "목표가상향",
]
NEGATIVE_KEYWORDS = [
    "급락", "하한가", "하락", "매도", "악재", "적자", "손실", "폭락",
    "약세", "공매도", "위험", "손절", "떨어", "내린다", "걱정", "나쁘다",
    "목표가하향", "실망", "불안",
]

# 모델 로드 (선택적)
_model = None
_tokenizer = None
_model_loaded = False


def _try_load_model():
    global _model, _tokenizer, _model_loaded
    if _model_loaded:
        return
    try:
        from transformers import pipeline
        _model = pipeline(
            "text-classification",
            model="snunlp/KR-FinBert-SC",
            device=-1,           # CPU
            truncation=True,
            max_length=128,
        )
        _model_loaded = True
        print("[감성 분석] KR-FinBert-SC 모델 로드 완료")
    except Exception as e:
        print(f"[감성 분석] 모델 로드 실패, 키워드 폴백 사용: {e}")
        _model_loaded = True  # 재시도 방지


def _keyword_sentiment(text: str) -> str:
    """키워드 기반 폴백 감성 분류"""
    pos = sum(1 for kw in POSITIVE_KEYWORDS if kw in text)
    neg = sum(1 for kw in NEGATIVE_KEYWORDS if kw in text)
    if pos > neg:
        return "positive"
    elif neg > pos:
        return "negative"
    return "neutral"


def analyze_posts(posts: List[Dict]) -> Tuple[float, int, int]:
    """
    게시글 리스트 감성 분석
    반환: (positive_ratio, positive_count, total_count)
    """
    _try_load_model()

    if not posts:
        return 0.0, 0, 0

    titles = [p["title"] for p in posts]
    results = []

    if _model is not None:
        try:
            # FinBert 배치 추론
            preds = _model(titles, batch_size=16)
            for pred in preds:
                label = pred["label"].lower()
                if "pos" in label:
                    results.append("positive")
                elif "neg" in label:
                    results.append("negative")
                else:
                    results.append("neutral")
        except Exception as e:
            print(f"[감성 분석] 추론 실패, 키워드 폴백: {e}")
            results = [_keyword_sentiment(t) for t in titles]
    else:
        results = [_keyword_sentiment(t) for t in titles]

    total = len(results)
    positive = results.count("positive")
    ratio = positive / total if total > 0 else 0.0

    return round(ratio, 3), positive, total
