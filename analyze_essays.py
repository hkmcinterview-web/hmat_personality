"""
합격/불합격 자소서 통계 실측 스크립트 (생산/제조 직무)

scoring_criteria.md v0.2 의 채점 기준을 Claude API로 자동 적용해
자소서별 지표를 추출하고, 합격자 평균/분포를 산출한다.

목적
  1) 합격 자소서 50개 → 실측 통계(정량개수·STAR·추상어 등) 산출
     → 명세서의 예시값을 실측값으로 교체, Layer3 플래그 임계값 결정
  2) 불합격 자소서 → 모델 검증(validation): 제대로 낮게 나오는지 확인

보안 (절대 준수)
  - 자소서 원문은 로컬 data/ 폴더에만 둔다 (.gitignore 처리됨).
  - 이 스크립트는 '집계 통계'만 stats_*.json 으로 저장한다.
  - per-essay 원시결과(per_essay_*.json)는 원문 일부를 포함할 수 있어
    .gitignore 로 커밋 차단된다.

사용법
  1) pip install -r requirements_analysis.txt
  2) export ANTHROPIC_API_KEY=sk-...
  3) 자소서를 텍스트로 저장:
       data/passed/applicant01.txt , applicant02.txt , ...
       data/failed/applicant01.txt , ...   (검증용)
     - 파일 1개 = 지원자 1명.
     - Q1/Q2 를 구분하려면 본문에 [Q1] ... [Q2] ... 마커를 넣으면 된다.
       마커가 없으면 전체를 하나로 분석한다.
  4) 실행:
       python analyze_essays.py --input-dir data/passed --label passed
       python analyze_essays.py --input-dir data/failed --label failed
  5) 산출:
       data/stats_passed.json      (집계 통계 — 안전, 공유 가능)
       data/per_essay_passed.json  (자소서별 원시 — 로컬 전용, 커밋 차단)
"""

import argparse
import json
import os
import re
import statistics
import sys
from pathlib import Path

MODEL = os.environ.get("ANTHROPIC_MODEL", "claude-sonnet-4-6")

# ── 추상어 사전 (차별성 역지표) ───────────────────────────────
ABSTRACT_WORDS = ["열정", "도전", "성장", "소통", "협력", "노력", "책임감", "최선"]

# ── 생산/제조 JD 키워드 (직무 연관성) ─────────────────────────
JD_KEYWORDS = {
    "공통": ["4M", "개선활동", "불량", "품질", "공정", "표준화", "생산성", "원가", "현장", "실습"],
    "생산기술": ["PLC", "MES", "TPM", "택타임", "라인밸런싱", "공정최적화", "치공구", "스마트팩토리"],
    "품질": ["CTQ", "QFD", "Fishbone", "Pareto", "SPC", "FMEA", "6시그마", "8D", "PPM", "Cpk"],
    "공정기술": ["IE", "동작분석", "표준작업", "레이아웃", "공수", "싸이클타임"],
}

# ── Hyundai Way 10 인재상 (Q2 가치적합성) ─────────────────────
HYUNDAI_WAY = [
    "안전과 품질", "집요함", "시도와 발전", "민첩한 실행", "협업",
    "회복탄력성", "다양성 포용", "전문성", "윤리 준수", "데이터 기반 사고",
]
# 생산/제조 직무 적합 가치(자연 선택) — 그 외는 이례적 선택
JOB_FIT_VALUES = {
    "안전과 품질", "집요함", "시도와 발전", "민첩한 실행",
    "협업", "전문성", "데이터 기반 사고",
}

# 채점 기준을 담은 시스템 프롬프트 (50개 호출 내내 동일 → 캐싱 대상)
SYSTEM_PROMPT = f"""당신은 현대자동차 생산/제조 직무 채용 평가관이다.
scoring_criteria.md v0.2 기준에 따라 자소서를 분석하고 지표를 추출한다.

[추출 지표 정의]
- char_count: 공백 포함 전체 글자 수
- quantitative_count: 측정된 성과를 나타내는 정량 표현 개수
    (예: "불량률 3%→0.8%", "택타임 12초 단축", "팀원 5명"). 단순 연도/나이는 제외.
- quantitative_suspicious: 위 정량 중 '과장 의심' 개수.
    트리거: ①개인 단독인데 비현실적 비율(예 혼자 매출300%) ②측정근거/기간 없는 큰 수치
    ③상황 대비 규모 비현실(학부 팀플에 억대 절감) ④baseline 없는 % 개선.
- star_situation / star_action / star_result: 상황·행동·결과 요소 유무 (true/false)
- abstract_word_count: 다음 추상어의 총 등장 횟수: {ABSTRACT_WORDS}
- field_experience: 인턴/현장실습 등 현장경험 언급 여부 (true/false)
- certification: 직무 관련 자격증 언급 여부 (true/false)
- jd_keywords_matched: 아래 키워드 중 '실제 사용 맥락과 함께' 등장한 것만 리스트로.
    단순 나열/자랑은 제외. 키워드 목록: {json.dumps(JD_KEYWORDS, ensure_ascii=False)}
- hyundai_way_values: 본문에서 다룬 Hyundai Way 가치명 리스트. 목록: {HYUNDAI_WAY}
    (명시적으로 고르지 않았어도 내용상 해당하면 포함)

[BARS 1~5 채점] (각 항목 점수마다 글의 상태로 판단)
- experience_specificity: 5=STAR4요소+정량2개↑+역할명확 / 3=행동·결과 중 하나 모호 / 1=다짐만
- job_relevance: 5=키워드다수+사용맥락+직무이해관통 / 3=키워드나열만 / 1=직무무관
- logical_structure: 5=두괄식+단락별1메시지+문항의도응답 / 3=결론묻힘 / 1=동문서답
- distinctiveness: 5=고유에피소드+추상어0 / 3=평범+추상어일부 / 1=추상어도배
- value_fit: 5=가치를행동으로증명+가치–경험–직무삼각연결 / 3=경험연결약함 / 1=가치오해

반드시 아래 JSON 스키마로만 응답한다(설명 금지):
{{
  "char_count": int,
  "quantitative_count": int,
  "quantitative_suspicious": int,
  "star_situation": bool, "star_action": bool, "star_result": bool,
  "abstract_word_count": int,
  "field_experience": bool,
  "certification": bool,
  "jd_keywords_matched": [str],
  "hyundai_way_values": [str],
  "bars": {{
    "experience_specificity": int, "job_relevance": int,
    "logical_structure": int, "distinctiveness": int, "value_fit": int
  }}
}}"""


def analyze_one(client, text: str) -> dict:
    """자소서 1개를 Claude 로 분석해 지표 dict 반환."""
    resp = client.messages.create(
        model=MODEL,
        max_tokens=1024,
        system=[{
            "type": "text",
            "text": SYSTEM_PROMPT,
            "cache_control": {"type": "ephemeral"},  # 50개 호출 내내 캐시 재사용
        }],
        messages=[{"role": "user", "content": f"다음 자소서를 분석하라:\n\n{text}"}],
    )
    raw = resp.content[0].text.strip()
    # 코드펜스 제거 후 JSON 파싱
    raw = re.sub(r"^```(?:json)?|```$", "", raw, flags=re.MULTILINE).strip()
    return json.loads(raw)


def aggregate(results: list[dict]) -> dict:
    """자소서별 지표 → 합격자 평균/분포 집계."""
    n = len(results)

    def vals(key):
        return [r[key] for r in results if key in r]

    def stat(key):
        v = vals(key)
        if not v:
            return {}
        return {
            "mean": round(statistics.mean(v), 2),
            "median": round(statistics.median(v), 2),
            "min": min(v), "max": max(v),
            "stdev": round(statistics.stdev(v), 2) if len(v) > 1 else 0,
        }

    # STAR 완성도(0~3) 파생
    star_scores = [
        sum([r.get("star_situation", False), r.get("star_action", False),
             r.get("star_result", False)])
        for r in results
    ]

    # 빈도 집계
    def freq(key):
        counter = {}
        for r in results:
            for item in r.get(key, []):
                counter[item] = counter.get(item, 0) + 1
        return dict(sorted(counter.items(), key=lambda x: -x[1]))

    bars_keys = ["experience_specificity", "job_relevance",
                 "logical_structure", "distinctiveness", "value_fit"]
    bars_stat = {}
    for k in bars_keys:
        v = [r["bars"][k] for r in results if "bars" in r and k in r["bars"]]
        if v:
            bars_stat[k] = {"mean": round(statistics.mean(v), 2),
                            "median": round(statistics.median(v), 2)}

    return {
        "sample_size": n,
        "numeric": {
            "char_count": stat("char_count"),
            "quantitative_count": stat("quantitative_count"),
            "quantitative_suspicious": stat("quantitative_suspicious"),
            "abstract_word_count": stat("abstract_word_count"),
            "star_completeness_0to3": {
                "mean": round(statistics.mean(star_scores), 2) if star_scores else 0,
                "median": round(statistics.median(star_scores), 2) if star_scores else 0,
            },
        },
        "rates": {
            "field_experience": round(sum(r.get("field_experience", False) for r in results) / n, 2) if n else 0,
            "certification": round(sum(r.get("certification", False) for r in results) / n, 2) if n else 0,
        },
        "bars": bars_stat,
        "jd_keyword_freq": freq("jd_keywords_matched"),
        "hyundai_way_freq": freq("hyundai_way_values"),
        "suggested_flag_thresholds": _suggest_thresholds(
            stat("quantitative_count"), stat("abstract_word_count")),
    }


def _suggest_thresholds(quant_stat: dict, abstract_stat: dict) -> dict:
    """실측 평균 기반 Layer3 플래그 임계값 제안 (명세서 §7)."""
    out = {}
    if quant_stat:
        out["수치_빈약"] = f"정량 < {round(quant_stat['mean'] * 0.5, 1)}개 (합격자 평균의 50%)"
    if abstract_stat:
        out["추상어_과다"] = f"추상어 > {round(abstract_stat['mean'] * 2, 1)}개 (합격자 평균의 2배)"
    return out


def main():
    ap = argparse.ArgumentParser(description="자소서 통계 실측 / 모델 검증")
    ap.add_argument("--input-dir", required=True, help="자소서 .txt 폴더 (예: data/passed)")
    ap.add_argument("--label", required=True, choices=["passed", "failed"],
                    help="passed=합격(통계실측) / failed=불합격(모델검증)")
    ap.add_argument("--out-dir", default="data", help="산출물 폴더")
    args = ap.parse_args()

    in_dir = Path(args.input_dir)
    files = sorted(in_dir.glob("*.txt"))
    if not files:
        sys.exit(f"'{in_dir}' 에 .txt 자소서가 없습니다.")

    if not os.environ.get("ANTHROPIC_API_KEY"):
        sys.exit("환경변수 ANTHROPIC_API_KEY 가 필요합니다.")

    try:
        from anthropic import Anthropic
    except ImportError:
        sys.exit("anthropic SDK 가 필요합니다:  pip install -r requirements_analysis.txt")

    client = Anthropic()
    results, per_essay = [], []
    print(f"[{args.label}] {len(files)}개 분석 시작 (model={MODEL})\n")

    for i, f in enumerate(files, 1):
        text = f.read_text(encoding="utf-8").strip()
        if not text:
            print(f"  [{i}/{len(files)}] {f.name} — 빈 파일, 건너뜀")
            continue
        try:
            metrics = analyze_one(client, text)
            results.append(metrics)
            per_essay.append({"file": f.name, **metrics})
            print(f"  [{i}/{len(files)}] {f.name} ✓  "
                  f"정량 {metrics.get('quantitative_count', '?')}개, "
                  f"STAR {sum([metrics.get('star_situation'), metrics.get('star_action'), metrics.get('star_result')])}/3")
        except Exception as e:
            print(f"  [{i}/{len(files)}] {f.name} ✗  분석 실패: {e}")

    if not results:
        sys.exit("분석된 자소서가 없습니다.")

    out_dir = Path(args.out_dir)
    out_dir.mkdir(exist_ok=True)
    stats = aggregate(results)

    stats_path = out_dir / f"stats_{args.label}.json"
    stats_path.write_text(json.dumps(stats, ensure_ascii=False, indent=2), encoding="utf-8")
    per_path = out_dir / f"per_essay_{args.label}.json"
    per_path.write_text(json.dumps(per_essay, ensure_ascii=False, indent=2), encoding="utf-8")

    print("\n" + "=" * 50)
    print(f"집계 완료 (n={stats['sample_size']})")
    print("=" * 50)
    print(json.dumps(stats, ensure_ascii=False, indent=2))
    print(f"\n저장: {stats_path}  (집계 통계 — 공유 가능)")
    print(f"저장: {per_path}  (자소서별 — 로컬 전용, 커밋 차단됨)")


if __name__ == "__main__":
    main()
