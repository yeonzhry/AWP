/**
 * 댓글 필터링 모듈 (프론트엔드용)
 * --------------------------------
 * 사용법:
 *   import { moderateComment } from './moderation.js';
 *   const result = moderateComment("댓글 내용");
 *   // result = { action: "allow" | "review" | "block", reason: "..." }
 *
 * action 처리 방법:
 *   - "allow"  : 그대로 저장, 바로 게시
 *   - "review" : 저장은 하되 is_hidden=true 등으로 화면에서 숨김, 관리자 검토 후 승인
 *   - "block"  : 저장하지 않고 사용자에게 에러 메시지(reason) 표시
 *
 * ⚠️ 주의: 이건 프론트엔드(브라우저)에서 실행되는 필터라, 개발자도구로 우회하는 게
 * 기술적으로 가능합니다. 완벽하게 막으려면 Supabase Edge Function 등 서버 쪽에도
 * 동일한 로직을 넣어서 이중으로 검증하는 걸 권장합니다.
 */

// 1단계: 욕설/비속어 (즉시 차단)
export const PROFANITY_KEYWORDS = ["시발", "씨발", "개새끼", "병신", "지랄", "쪽바리", "년", "새끼"];

// 2단계: 역사부정/2차가해 표현 (검토 대기)
export const SENSITIVE_KEYWORDS = [
  "매춘부", "자발적 매춘", "위안부는 없었다", "강제성이 없", "강제연행은 없",
  "돈 벌러 간", "직업여성", "성노예 아니", "자발적으로 갔",
  "성매매", "매춘이", "매춘 아니",
  "위안부는 거짓", "위안부는 조작", "위안부는 날조", "숫자를 부풀",
  "그만 좀 우려먹", "돈 뜯어내려고", "국뽕 팔아", "이제 그만해",
  "다 옛날 일", "언제까지 우려먹을", "가짜 피해자", "창녀"
];

function normalize(text) {
  return text.toLowerCase().replace(/[^\w가-힣]/g, "");
}

function containsAny(text, keywords) {
  const norm = normalize(text);
  return keywords.some(kw => norm.includes(normalize(kw)));
}

// 3단계: 실제 학습된 TF-IDF + 로지스틱회귀 모델 (model.joblib에서 뽑아낸 가중치)
const MODEL_DATA = /*__MODEL_DATA__*/ null /*__END_MODEL_DATA__*/;
const BLOCK_THRESHOLD = 0.8;
const REVIEW_THRESHOLD = 0.4;

function tokenize(text) {
  return (text.toLowerCase().match(/[\p{L}\p{N}_]{2,}/gu)) || [];
}

function buildNgrams(tokens) {
  const ngrams = tokens.slice();
  for (let i = 0; i < tokens.length - 1; i++) {
    ngrams.push(tokens[i] + " " + tokens[i + 1]);
  }
  return ngrams;
}

function mlPredictProba(text) {
  if (!MODEL_DATA) return null;
  const tokens = tokenize(text);
  const ngrams = buildNgrams(tokens);

  const counts = {};
  for (const t of ngrams) {
    const idx = MODEL_DATA.vocabulary[t];
    if (idx !== undefined) counts[idx] = (counts[idx] || 0) + 1;
  }

  const idxList = Object.keys(counts);
  const vec = {};
  let normSq = 0;
  for (const idx of idxList) {
    const val = counts[idx] * MODEL_DATA.idf[idx];
    vec[idx] = val;
    normSq += val * val;
  }
  const norm = Math.sqrt(normSq);

  let z = MODEL_DATA.intercept;
  if (norm > 0) {
    for (const idx of idxList) {
      z += (vec[idx] / norm) * MODEL_DATA.coef[idx];
    }
  }
  return 1 / (1 + Math.exp(-z));
}

export function moderateComment(text) {
  if (!text || !text.trim()) {
    return { action: "block", reason: "빈 댓글" };
  }
  if (containsAny(text, PROFANITY_KEYWORDS)) {
    return { action: "block", reason: "욕설/비속어 감지" };
  }
  if (containsAny(text, SENSITIVE_KEYWORDS)) {
    return { action: "review", reason: "역사부정·2차가해 관련 표현 감지, 관리자 검토 필요" };
  }
  const score = mlPredictProba(text);
  if (score === null) {
    return { action: "allow", reason: "문제 없음 (모델 데이터 없음, 키워드 필터만 적용)" };
  }
  if (score >= BLOCK_THRESHOLD) {
    return { action: "block", reason: `AI 모델 악성 판단 (확률 ${score.toFixed(2)})` };
  } else if (score >= REVIEW_THRESHOLD) {
    return { action: "review", reason: `AI 모델 애매 판단, 관리자 검토 필요 (확률 ${score.toFixed(2)})` };
  } else {
    return { action: "allow", reason: `문제 없음 (악성 확률 ${score.toFixed(2)})` };
  }
}
