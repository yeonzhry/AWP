# 댓글 필터링 모듈 (프론트엔드 + Supabase용)

## 이 모듈로 하는 일

`moderateComment(text)` 함수 하나로 욕설/역사부정 표현/AI 모델 판단까지 3단계 필터링을 프론트엔드(브라우저)에서 바로 처리합니다. 별도 백엔드 서버 없이 Supabase와 바로 연결해서 씁니다.

## 파일 만드는 법 (본인 모델 반영)

이 저장소엔 `moderation_template.js`(로직만 있고 모델 데이터는 비어있는 템플릿)가 들어있습니다. 실제 학습된 모델을 넣으려면:

```bash
pip install -r requirements.txt
python export_model_to_js.py --model model.joblib --output model_data.json
python build_demo.py --template moderation_template.js --model-data model_data.json --output moderation.js
```

생성된 `moderation.js`를 프론트엔드 프로젝트의 `src` 폴더 등에 넣고 import해서 쓰면 됩니다. (모델을 재학습할 때마다 이 과정을 다시 실행해서 `moderation.js`를 새로 만들어야 합니다.)

## 프론트엔드에서 사용법

```javascript
import { moderateComment } from './moderation.js';
import { createClient } from '@supabase/supabase-js';

const supabase = createClient(SUPABASE_URL, SUPABASE_ANON_KEY);

async function submitComment(text) {
  const result = moderateComment(text);

  if (result.action === "block") {
    alert(result.reason); // 또는 원하는 에러 UI
    return;
  }

  const { error } = await supabase.from("comments").insert({
    content: text,
    is_hidden: result.action === "review", // "review"면 화면에 안 보이게
  });

  if (error) {
    console.error(error);
    return;
  }

  if (result.action === "review") {
    alert("검토 대기 상태로 등록되었습니다. 관리자 확인 후 게시됩니다.");
  }
}
```

## Supabase 테이블에 필요한 컬럼

`comments` 테이블에 `is_hidden` (boolean, 기본값 false) 컬럼이 있어야 합니다. 관리자 페이지에서는 `is_hidden = true`인 댓글만 따로 불러와서 승인/거부 UI를 만들면 됩니다.

## 판단 기준

1. **욕설/비속어** → 즉시 `block`
2. **역사부정·2차가해 표현(키워드)** → `review`
3. **나머지는 AI 모델이 확률로 판단** → 0.8 이상 `block` / 0.4~0.8 `review` / 0.4 미만 `allow`

## 알려진 한계

- 이 필터는 브라우저(클라이언트)에서 실행되므로, 개발자도구로 우회해서 Supabase에 직접 요청을 보내는 게 기술적으로 가능합니다. 더 견고하게 만들려면 동일한 로직을 Supabase Edge Function에도 넣어 서버 쪽에서 한 번 더 검증하는 걸 권장합니다.
- 부정어("~아니다", "~안 되지")가 붙어 의미가 반대로 뒤집히는 문장은 키워드 필터가 맥락을 구분하지 못해 오탐(정상 댓글이 검토 대기로 분류)이 발생할 수 있습니다. 실제 차단이 아니라 검토 대기로 처리되므로 서비스 운영에 큰 지장은 없습니다.
