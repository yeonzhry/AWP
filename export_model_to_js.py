"""
model.joblib을 브라우저(JS)에서 그대로 돌릴 수 있는 JSON 데이터로 내보내는 스크립트
--------------------------------
TF-IDF + 로지스틱회귀 모델은 사실 "숫자 몇 개(가중치)"로 이루어져 있어서,
그 숫자만 JSON으로 뽑아내면 파이썬 서버 없이도 브라우저에서 완전히 동일한 계산을 재현할 수 있습니다.

사용법:
    python export_model_to_js.py --model model.joblib --output model_data.json
"""

import argparse
import json

import joblib


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--model", default="model.joblib")
    parser.add_argument("--output", default="model_data.json")
    args = parser.parse_args()

    bundle = joblib.load(args.model)
    vectorizer = bundle["vectorizer"]
    clf = bundle["model"]

    data = {
        "vocabulary": {word: int(idx) for word, idx in vectorizer.vocabulary_.items()},
        "idf": vectorizer.idf_.tolist(),
        "coef": clf.coef_[0].tolist(),
        "intercept": float(clf.intercept_[0]),
    }

    with open(args.output, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False)

    import os
    size_kb = os.path.getsize(args.output) / 1024
    print(f"'{args.output}' 생성 완료 ({size_kb:.0f} KB, 단어 {len(data['vocabulary'])}개)")
    print("이 파일 내용을 comment_filter_demo.html의 MODEL_DATA 자리에 붙여넣으면 됩니다.")


if __name__ == "__main__":
    main()
