"""
댓글 필터링 모듈
--------------------------------
Django / Flask / FastAPI 어디서든 그대로 가져다 쓸 수 있는 독립적인 필터 함수입니다.
프레임워크에 종속되지 않게 만들어서, 댓글을 저장하기 직전에 이 함수 하나만 호출하면 됩니다.

사용 예:
    from moderation import moderate_comment

    result = moderate_comment("이 댓글 내용")
    if result["action"] == "block":
        # 저장하지 않고 에러 응답
        ...
    elif result["action"] == "review":
        # is_hidden=True 상태로 저장, 관리자 승인 대기
        ...
    else:  # "allow"
        # 바로 저장
        ...
"""

import os
import re
from typing import Literal

import joblib

try:
    from korcen import korcen as _korcen
    _KORCEN_AVAILABLE = True
except ImportError:
    _KORCEN_AVAILABLE = False
    print("[moderation] korcen 라이브러리가 설치되어 있지 않아 기본 키워드 사전만 사용합니다. "
          "설치하려면: pip install korcen")

# ------------------------------------------------------------------
# 0. ML 모델 로딩 (model.joblib이 없으면 3단계 없이 키워드 필터만 작동)
# ------------------------------------------------------------------

MODEL_PATH = os.environ.get("MODERATION_MODEL_PATH", "model.joblib")
BLOCK_THRESHOLD = 0.8   # 이 확률 이상이면 차단
REVIEW_THRESHOLD = 0.4  # 이 확률 이상이면 검토 대기, 미만이면 게시

_model_bundle = None
_model_load_attempted = False


def _get_model():
    """model.joblib을 한 번만 로드해서 재사용합니다 (요청마다 다시 불러오면 느려서)."""
    global _model_bundle, _model_load_attempted
    if _model_load_attempted:
        return _model_bundle
    _model_load_attempted = True
    if os.path.exists(MODEL_PATH):
        _model_bundle = joblib.load(MODEL_PATH)
        print(f"[moderation] ML 모델 로드 완료: {MODEL_PATH}")
    else:
        print(f"[moderation] ML 모델 파일을 찾을 수 없어 키워드 필터만 사용합니다: {MODEL_PATH}")
    return _model_bundle

# ------------------------------------------------------------------
# 1. 키워드 사전 (실제 운영 시에는 별도 파일/DB로 분리해서 관리하는 걸 추천)
# ------------------------------------------------------------------

# 명백한 욕설/비속어 - 발견 즉시 차단
# korcen이 대부분 잡아주지만, 사이트 특성상 자주 나올 만한 표현을 자체적으로 보강
PROFANITY_KEYWORDS = [
    "시발", "씨발", "개새끼", "병신", "지랄",
]

# 위안부 역사부정/피해자 비하 관련 - 발견 시 "review"(검토 대기)로 보류
# 즉시 차단이 아니라 검토 큐로 보내는 이유: 오탐 시 정당한 의견까지 막을 위험이 있어서
#
# 주의: "자발적 매춘", "위안부는 없었다" 같은 표현은 부정어가 붙으면 옹호 발언이 되기도 해서
# ML 모델에게 판단을 맡겨봤지만, 지금 데이터 양으로는 모델이 이 미묘한 차이를 구분하지 못했습니다
# (실제 테스트 결과 "자발적 매춘이지"가 오히려 통과되는 문제 발생).
# 이 사이트 특성상 "정상 댓글이 검토 대기로 가는 것"보다 "2차가해 댓글이 그냥 통과되는 것"이
# 훨씬 위험하므로, 안전한 쪽(키워드 즉시 검토)으로 되돌립니다.
# 데이터가 충분히 쌓이면(대조쌍 수백 개 이상) 다시 ML 모델 판단으로 전환을 시도해볼 수 있습니다.
SENSITIVE_KEYWORDS = [
    "매춘부", "자발적 매춘", "위안부는 없었다", "강제성이 없", "강제연행은 없",
    "돈 벌러 간", "직업여성", "성노예 아니", "자발적으로 갔",
    "성매매", "매춘이", "매춘 아니",
    # 숫자/사실 축소, 피해 부정 (부정어를 붙이기 어색해서 대체로 한 방향으로만 쓰이는 표현)
    "위안부는 거짓", "위안부는 조작", "위안부는 날조", "숫자를 부풀",
    # 2차가해성 발언 (피해자 비난, 문제 자체를 지치게 만드는 발언)
    "그만 좀 우려먹", "돈 뜯어내려고", "국뽕 팔아", "이제 그만해",
    "다 옛날 일", "언제까지 우려먹을",
    # TODO: 라벨링하면서 실제로 걸러지는 표현 패턴 보고 계속 보강
]

# (참고용으로 남겨둠) 문맥 의존적 표현 목록 - 향후 데이터가 충분히 쌓이면
# 이 목록을 SENSITIVE_KEYWORDS에서 분리해 ML 모델 판단으로 다시 전환을 시도해볼 수 있음
CONTEXT_DEPENDENT_KEYWORDS = [
    "매춘부", "자발적 매춘", "위안부는 없었다", "강제성이 없", "강제연행은 없",
    "돈 벌러 간", "직업여성", "성노예 아니", "자발적으로 갔",
    "성매매", "매춘이", "매춘 아니",
]


def _normalize(text: str) -> str:
    """자음/모음 분리, 특수문자 삽입 등으로 필터를 우회하려는 시도를 어느 정도 방지하기 위해
    텍스트를 정규화합니다. (완벽하지는 않으니 점진적으로 보강 필요)"""
    text = text.lower()
    text = re.sub(r"[^\w가-힣]", "", text)  # 특수문자/공백 제거
    return text


def contains_any(text: str, keywords: list[str]) -> bool:
    normalized = _normalize(text)
    return any(_normalize(kw) in normalized for kw in keywords)


def moderate_comment(text: str) -> dict:
    """
    댓글 텍스트를 검사해서 처리 방침을 반환합니다.

    Returns:
        {
            "action": "allow" | "review" | "block",
            "reason": str  # 사람이 읽을 수 있는 사유 (로그/관리자 화면용)
        }
    """
    if not text or not text.strip():
        return {"action": "block", "reason": "빈 댓글"}

    # 1단계: 명백한 욕설 -> 즉시 차단
    # korcen(공개 욕설 판단 라이브러리)로 폭넓게 잡고, 자체 키워드 사전으로 추가 보강
    if _KORCEN_AVAILABLE and _korcen.check(text):
        return {"action": "block", "reason": "욕설/비속어 감지 (korcen)"}
    if contains_any(text, PROFANITY_KEYWORDS):
        return {"action": "block", "reason": "욕설/비속어 감지 (자체 사전)"}

    # 2단계: 역사부정/민감 표현 -> 관리자 검토 대기
    if contains_any(text, SENSITIVE_KEYWORDS):
        return {"action": "review", "reason": "역사부정 관련 표현 감지, 관리자 검토 필요"}

    # 3단계: 위 키워드에 안 걸린 나머지는 ML 모델로 판단
    bundle = _get_model()
    if bundle is None:
        # 모델이 없으면 문맥 판단이 불가능하니, 맥락 의존적 키워드라도 안전하게 검토 대기로 보냄
        if contains_any(text, CONTEXT_DEPENDENT_KEYWORDS):
            return {"action": "review", "reason": "역사부정 관련 표현 감지(모델 미탑재), 관리자 검토 필요"}
        return {"action": "allow", "reason": "문제 없음 (모델 미탑재, 키워드 필터만 적용)"}

    vectorizer = bundle["vectorizer"]
    model = bundle["model"]
    vec = vectorizer.transform([text])
    # predict_proba는 [정상 확률, 악성 확률] 순서로 반환됨 (학습 시 label 1=악성 기준)
    score = model.predict_proba(vec)[0][1]

    if score >= BLOCK_THRESHOLD:
        return {"action": "block", "reason": f"AI 모델 악성 판단 (확률 {score:.2f})"}
    elif score >= REVIEW_THRESHOLD:
        return {"action": "review", "reason": f"AI 모델 애매 판단, 관리자 검토 필요 (확률 {score:.2f})"}
    else:
        return {"action": "allow", "reason": f"문제 없음 (악성 확률 {score:.2f})"}
