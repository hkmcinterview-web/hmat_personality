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
  3) 자소서를 텍스트로 저장 (회사별로 폴더를 나눈다 — 인재상이 다르므로):
       data/passed_hyundai/01.txt , 02.txt , ...   (현대차 합격)
       data/passed_kia/01.txt , ...                (기아 합격)
       data/failed_hyundai/01.txt , ...            (검증용)
     - 파일 1개 = 지원자 1명.
     - Q1/Q2 를 구분하려면 본문에 [Q1] ... [Q2] ... 마커를 넣으면 된다.
       마커가 없으면 전체를 하나로 분석한다.
  4) 실행 (--company 로 회사 지정):
       python analyze_essays.py --input-dir data/passed_hyundai --label passed --company hyundai
       python analyze_essays.py --input-dir data/passed_kia     --label passed --company kia
       python analyze_essays.py --input-dir data/failed_hyundai --label failed --company hyundai
  5) 산출 (회사별로 분리 저장):
       data/stats_passed_hyundai.json      (집계 통계 — 안전, 공유 가능)
       data/per_essay_passed_hyundai.json  (자소서별 원시 — 로컬 전용, 커밋 차단)

  주의: 직무 신호(정량·STAR·현장경험 등)는 현대·기아가 사실상 동일하지만,
        인재상/가치(value_framework_freq)는 회사마다 체계가 달라 분리 집계한다.
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
    "품질": ["CTQ", "QFD", "Fishbone", "Pareto", "SPC", "FMEA", "6시그마", "8D", "PPM", "Cpk", "PPAP"],
    "공정기술": ["IE", "동작분석", "표준작업", "레이아웃", "공수", "싸이클타임"],
}

# ── 회사별 인재상/가치 프레임 (Q2 가치적합성) ─────────────────
# 현대차·기아는 그룹은 같지만 인재상 체계가 다르다.
VALUE_FRAMEWORKS = {
    "hyundai": {
        "name": "Hyundai Way 10 인재상",
        "values": [
            "안전과 품질", "집요함", "시도와 발전", "민첩한 실행", "협업",
            "회복탄력성", "다양성 포용", "전문성", "윤리 준수", "데이터 기반 사고",
        ],
    },
    "kia": {
        "name": "기아 인재상(KIAN) + 가치와 행동",
        "values": [
            # KIAN 인재상 4
            "창조", "혁신", "행동", "탐험",
            # 기아 가치와 행동 5
            "사람을 생각합니다", "함께 더 멀리 나아갑니다", "서로에게 힘을 실어줍니다",
            "과감히 한계에 도전합니다", "어제보다 더 나은 오늘을 추구합니다",
        ],
    },
}


def build_system_prompt(company: str) -> str:
    """회사별 가치 프레임을 반영한 시스템 프롬프트 생성 (한 번의 실행 내내 동일 → 캐싱)."""
    fw = VALUE_FRAMEWORKS[company]
    company_kr = "현대자동차" if company == "hyundai" else "기아"
    return f"""당신은 {company_kr} 생산/제조 직무 채용 평가관이다.
scoring_criteria.md 기준에 따라 자소서를 분석하고 지표를 추출한다.
변별이 목적이다. 합격·탈락이 똑같이 만점 나오면 안 된다.
따라서 '있다/없다'가 아니라 '얼마나 깊은가'로, 엄격하게 점수를 벌려라.

[추출 지표 정의]
- char_count: 공백 포함 전체 글자 수
- quantitative_count: 측정된 정량 표현 총 개수
    (예: "불량률 3%→0.8%", "택타임 12초 단축", "팀원 5명"). 단순 연도/나이는 제외.
- quantitative_core_count: 위 정량 중 '본인의 핵심 성과에 직접 연결된' 수치만.
    배경 설명용·단순 나열 수치는 제외. (많이 나열 ≠ 좋음)
- quantitative_suspicious: 위 정량 중 '과장 의심' 개수.
    트리거: ①개인 단독인데 비현실적 비율(예 혼자 매출300%) ②측정근거/기간 없는 큰 수치
    ③상황 대비 규모 비현실(학부 팀플에 억대 절감) ④baseline 없는 % 개선.
- abstract_word_count: 다음 추상어의 총 등장 횟수: {ABSTRACT_WORDS}
- field_experience_depth: 현장경험 깊이 (0~3)
    0=없음 / 1=단순 언급 / 2=경험을 구체적으로 서술 / 3=현장에서 직무 관련 문제를 직접 해결
- certification: 직무 관련 자격증 언급 여부 (true/false)
- jd_keyword_depth: 직무 용어를 '실제로 적용'했는가 (1~5)
    1=용어 없음 / 2=용어만 등장 / 3=용어 나열 / 4=일부 적용 맥락 / 5=경험 속에서 깊이 있게 활용
- jd_keywords_matched: 아래 키워드 중 '실제 사용 맥락과 함께' 등장한 것만 리스트로.
    단순 나열/자랑은 제외. 키워드 목록: {json.dumps(JD_KEYWORDS, ensure_ascii=False)}
- values_matched: 본문에서 다룬 '{fw['name']}' 가치명 리스트. 목록: {fw['values']}
    (명시적으로 고르지 않았어도 내용상 해당하면 포함)

[STAR 깊이 — 각 1~5, 엄격하게 벌릴 것] (단순 존재가 아니라 '질'을 본다)
- situation_clarity: 상황·배경 구체성. 1=불명 / 3=대략 / 5=선명하고 구체
- role_ownership: 본인 기여 명확도. 1='우리'로 뭉뚱그림 / 3=역할 일부 명확 / 5='내가' 한 일이 분명히 구분됨
    ★ 합/불을 가르는 핵심 지표. 팀 성과를 본인 것처럼 쓰면 낮게.
- action_depth: 행동의 주도성·깊이. 1=단순 참여·수행 / 3=주어진 일 충실 / 5=문제를 스스로 정의하고 주도적으로 해결
- result_causality: 결과–행동 인과. 1=결과가 행동과 무관·모호 / 3=결과 있으나 인과 약함 / 5=본인 행동→결과 인과가 분명+정량

[BARS 1~5 — 엄격하게. 5는 극히 드물게, 대부분 2~4로 벌릴 것]
- experience_specificity: 5=STAR 모든 깊이 높고 정량 핵심연결 / 3=일부 모호 / 1=다짐만
- job_relevance: 5=용어 깊이 활용+직무이해 관통 / 3=용어 나열 수준 / 1=직무무관
- logical_structure: 5=두괄식+단락별1메시지+문항의도 정확 응답 / 3=결론묻힘 / 1=동문서답
- distinctiveness: 5=고유 에피소드+진부함0 / 3=평범 / 1=누구나 쓸 글
- value_fit: 5=가치를 행동으로 증명+가치–경험–직무 삼각연결 / 3=경험연결 약함 / 1=가치오해

반드시 아래 JSON 스키마로만 응답한다(설명 금지):
{{
  "char_count": int,
  "quantitative_count": int,
  "quantitative_core_count": int,
  "quantitative_suspicious": int,
  "abstract_word_count": int,
  "field_experience_depth": int,
  "certification": bool,
  "jd_keyword_depth": int,
  "jd_keywords_matched": [str],
  "values_matched": [str],
  "star_quality": {{
    "situation_clarity": int, "role_ownership": int,
    "action_depth": int, "result_causality": int
  }},
  "bars": {{
    "experience_specificity": int, "job_relevance": int,
    "logical_structure": int, "distinctiveness": int, "value_fit": int
  }}
}}"""


def analyze_one(client, text: str, system_prompt: str) -> dict:
    """자소서 1개를 Claude 로 분석해 지표 dict 반환."""
    resp = client.messages.create(
        model=MODEL,
        max_tokens=1024,
        system=[{
            "type": "text",
            "text": system_prompt,
            "cache_control": {"type": "ephemeral"},  # 실행 내내 캐시 재사용
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

    def stat(key, sub=None):
        if sub:
            v = [r[key][sub] for r in results if key in r and sub in r.get(key, {})]
        else:
            v = [r[key] for r in results if key in r]
        if not v:
            return {}
        return {
            "mean": round(statistics.mean(v), 2),
            "median": round(statistics.median(v), 2),
            "min": min(v), "max": max(v),
            "stdev": round(statistics.stdev(v), 2) if len(v) > 1 else 0,
        }

    # 빈도 집계
    def freq(key):
        counter = {}
        for r in results:
            for item in r.get(key, []):
                counter[item] = counter.get(item, 0) + 1
        return dict(sorted(counter.items(), key=lambda x: -x[1]))

    bars_keys = ["experience_specificity", "job_relevance",
                 "logical_structure", "distinctiveness", "value_fit"]
    bars_stat = {k: stat("bars", k) for k in bars_keys if stat("bars", k)}

    star_keys = ["situation_clarity", "role_ownership", "action_depth", "result_causality"]
    star_stat = {k: stat("star_quality", k) for k in star_keys if stat("star_quality", k)}

    return {
        "sample_size": n,
        "numeric": {
            "char_count": stat("char_count"),
            "quantitative_count": stat("quantitative_count"),
            "quantitative_core_count": stat("quantitative_core_count"),
            "quantitative_suspicious": stat("quantitative_suspicious"),
            "abstract_word_count": stat("abstract_word_count"),
            "field_experience_depth_0to3": stat("field_experience_depth"),
            "jd_keyword_depth_1to5": stat("jd_keyword_depth"),
        },
        "star_quality": star_stat,
        "rates": {
            "certification": round(sum(r.get("certification", False) for r in results) / n, 2) if n else 0,
        },
        "bars": bars_stat,
        "jd_keyword_freq": freq("jd_keywords_matched"),
        "value_framework_freq": freq("values_matched"),
        "suggested_flag_thresholds": _suggest_thresholds(
            stat("quantitative_core_count"), stat("abstract_word_count")),
    }


def _suggest_thresholds(quant_stat: dict, abstract_stat: dict) -> dict:
    """실측 평균 기반 Layer3 플래그 임계값 제안 (명세서 §7)."""
    out = {}
    if quant_stat:
        out["핵심수치_빈약"] = f"핵심정량 < {round(quant_stat['mean'] * 0.5, 1)}개 (합격자 평균의 50%)"
    if abstract_stat:
        out["추상어_과다"] = f"추상어 > {round(abstract_stat['mean'] * 2, 1)}개 (합격자 평균의 2배)"
    return out


def main():
    ap = argparse.ArgumentParser(description="자소서 통계 실측 / 모델 검증")
    ap.add_argument("--input-dir", required=True, help="자소서 .txt 폴더 (예: data/passed)")
    ap.add_argument("--label", required=True, choices=["passed", "failed"],
                    help="passed=합격(통계실측) / failed=불합격(모델검증)")
    ap.add_argument("--company", default="hyundai", choices=["hyundai", "kia"],
                    help="hyundai=현대차(Hyundai Way) / kia=기아(KIAN·가치와 행동)")
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
    system_prompt = build_system_prompt(args.company)
    results, per_essay = [], []
    print(f"[{args.label}/{args.company}] {len(files)}개 분석 시작 (model={MODEL})\n")

    for i, f in enumerate(files, 1):
        text = f.read_text(encoding="utf-8").strip()
        if not text:
            print(f"  [{i}/{len(files)}] {f.name} — 빈 파일, 건너뜀")
            continue
        try:
            metrics = analyze_one(client, text, system_prompt)
            results.append(metrics)
            per_essay.append({"file": f.name, "company": args.company,
                              "label": args.label, **metrics})
            sq = metrics.get("star_quality", {})
            print(f"  [{i}/{len(files)}] {f.name} ✓  "
                  f"핵심정량 {metrics.get('quantitative_core_count', '?')}/{metrics.get('quantitative_count', '?')}개, "
                  f"본인기여 {sq.get('role_ownership', '?')}/5, "
                  f"행동깊이 {sq.get('action_depth', '?')}/5")
        except Exception as e:
            print(f"  [{i}/{len(files)}] {f.name} ✗  분석 실패: {e}")

    if not results:
        sys.exit("분석된 자소서가 없습니다.")

    out_dir = Path(args.out_dir)
    out_dir.mkdir(exist_ok=True)
    stats = aggregate(results)
    stats["company"] = args.company

    stats_path = out_dir / f"stats_{args.label}_{args.company}.json"
    stats_path.write_text(json.dumps(stats, ensure_ascii=False, indent=2), encoding="utf-8")
    per_path = out_dir / f"per_essay_{args.label}_{args.company}.json"
    per_path.write_text(json.dumps(per_essay, ensure_ascii=False, indent=2), encoding="utf-8")

    print("\n" + "=" * 50)
    print(f"집계 완료 (n={stats['sample_size']})")
    print("=" * 50)
    print(json.dumps(stats, ensure_ascii=False, indent=2))
    print(f"\n저장: {stats_path}  (집계 통계 — 공유 가능)")
    print(f"저장: {per_path}  (자소서별 — 로컬 전용, 커밋 차단됨)")


if __name__ == "__main__":
    main()
