"""
comment_filter_demo.html 템플릿에 model_data.json 내용을 끼워넣어서
바로 열어볼 수 있는 최종 데모 파일을 만드는 스크립트.

사용법:
    python export_model_to_js.py --model model.joblib --output model_data.json
    python build_demo.py --template comment_filter_demo.html --model-data model_data.json --output comment_filter_demo_final.html

그 다음 comment_filter_demo_final.html을 더블클릭해서 브라우저로 열면
실제 학습된 모델이 그대로 작동하는 데모를 볼 수 있습니다.
"""

import argparse


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--template", default="comment_filter_demo.html")
    parser.add_argument("--model-data", default="model_data.json")
    parser.add_argument("--output", default="comment_filter_demo_final.html")
    args = parser.parse_args()

    with open(args.template, "r", encoding="utf-8") as f:
        html = f.read()

    with open(args.model_data, "r", encoding="utf-8") as f:
        model_json = f.read()

    placeholder_start = "/*__MODEL_DATA__*/ null /*__END_MODEL_DATA__*/"
    if placeholder_start not in html:
        print("[오류] 템플릿에서 placeholder를 찾을 수 없습니다. comment_filter_demo.html이 최신 버전인지 확인하세요.")
        return

    html = html.replace(placeholder_start, model_json)

    with open(args.output, "w", encoding="utf-8") as f:
        f.write(html)

    print(f"'{args.output}' 생성 완료. 브라우저로 열어서 확인하세요.")


if __name__ == "__main__":
    main()
