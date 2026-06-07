"""
합격 vs 탈락 변별력 비교 (현대·기아 통합 풀링)

analyze_essays.py 가 만든 data/per_essay_*.json 들을 모아서:
  - 변별 지표(본인기여·행동깊이 등 1~5 품질점수)는 회사 통합(pool)으로
    합격 vs 탈락을 비교한다. → 모수가 커져 신뢰도가 올라간다.
  - 정량 수치·인재상 빈도는 회사마다 실제로 다르므로 회사별로 분리 표시한다.

근거
  - 직무 역량(품질 점수)은 현대·기아 생산/제조가 사실상 동일 → 통합이 타당.
  - 정량 개수(현대 ~5 vs 기아 ~9)와 가치 체계(Hyundai Way vs KIAN)는
    회사마다 달라 통합 평균이 양쪽 모두에 안 맞는다 → 분리.

사용법
  python compare_stats.py
  (data/ 안의 per_essay_*.json 을 자동으로 모두 읽는다)
"""

import glob
import json
import statistics
from pathlib import Path

# 회사 통합으로 풀링할 변별 지표 (직무 역량 = 회사 무관, 1~5 / 0~3 정규화 점수)
QUALITY_FLAT = {
    "star_quality.situation_clarity": "상황구체성",
    "star_quality.role_ownership": "본인기여",
    "star_quality.action_depth": "행동깊이",
    "star_quality.result_causality": "결과인과",
    "field_experience_depth": "현장경험깊이",
    "jd_keyword_depth": "직무용어깊이",
    "bars.experience_specificity": "경험구체성(BARS)",
    "bars.job_relevance": "직무연관성(BARS)",
    "bars.logical_structure": "논리구조(BARS)",
    "bars.distinctiveness": "차별성(BARS)",
    "bars.value_fit": "가치적합성(BARS)",
}

# 회사별로 분리해서 봐야 하는 지표 (수치·문체는 회사마다 다름)
COMPANY_SPECIFIC = {
    "quantitative_count": "정량(전체)",
    "quantitative_core_count": "정량(핵심)",
    "quantitative_suspicious": "과장의심",
    "abstract_word_count": "추상어",
}


def get(d: dict, dotted: str):
    """'star_quality.role_ownership' 같은 점 경로로 중첩 값 추출."""
    cur = d
    for part in dotted.split("."):
        if not isinstance(cur, dict) or part not in cur:
            return None
        cur = cur[part]
    return cur


def mean(v):
    return round(statistics.mean(v), 2) if v else None


def load_essays():
    """data/per_essay_*.json 전부 읽어 평탄한 레코드 리스트로."""
    records = []
    for path in sorted(glob.glob("data/per_essay_*.json")):
        try:
            data = json.loads(Path(path).read_text(encoding="utf-8"))
        except Exception as e:
            print(f"  (건너뜀) {path}: {e}")
            continue
        for r in data:
            # 구버전 파일에 company/label 없으면 파일명에서 유추
            stem = Path(path).stem  # per_essay_passed_kia
            parts = stem.split("_")
            r.setdefault("label", parts[2] if len(parts) > 2 else "unknown")
            r.setdefault("company", parts[3] if len(parts) > 3 else "unknown")
            records.append(r)
    return records


def main():
    records = load_essays()
    if not records:
        print("data/per_essay_*.json 가 없습니다. 먼저 analyze_essays.py 를 실행하세요.")
        return

    passed = [r for r in records if r.get("label") == "passed"]
    failed = [r for r in records if r.get("label") == "failed"]

    print("=" * 64)
    print(f"변별력 비교  (합격 {len(passed)}개 / 탈락 {len(failed)}개, 현대·기아 통합)")
    print("=" * 64)
    print(f"{'지표':<20}{'합격':>8}{'탈락':>8}{'격차':>8}   변별력")
    print("-" * 64)

    discrimination = {}
    for dotted, kr in QUALITY_FLAT.items():
        pv = [get(r, dotted) for r in passed if get(r, dotted) is not None]
        fv = [get(r, dotted) for r in failed if get(r, dotted) is not None]
        pm, fm = mean(pv), mean(fv)
        if pm is None or fm is None:
            continue
        gap = round(pm - fm, 2)
        mark = "★강함" if gap >= 0.8 else ("○약함" if gap >= 0.3 else "· 없음")
        print(f"{kr:<20}{pm:>8}{fm:>8}{gap:>8}   {mark}")
        discrimination[kr] = {"passed": pm, "failed": fm, "gap": gap}

    # 회사별 분리 지표
    print("\n" + "=" * 64)
    print("회사별 분리 지표 (정량·문체 — 통합하면 안 되는 항목)")
    print("=" * 64)
    companies = sorted({r.get("company") for r in records})
    company_stats = {}
    for comp in companies:
        comp_passed = [r for r in passed if r.get("company") == comp]
        if not comp_passed:
            continue
        row = {}
        line = f"[{comp}] 합격 {len(comp_passed)}개  "
        for key, kr in COMPANY_SPECIFIC.items():
            v = [r[key] for r in comp_passed if key in r]
            m = mean(v)
            row[kr] = m
            line += f"{kr} {m}  "
        company_stats[comp] = row
        print(line)

    # 가치 빈도 (회사별)
    print("\n" + "-" * 64)
    print("인재상/가치 빈도 (회사별, 합격자)")
    print("-" * 64)
    value_freq = {}
    for comp in companies:
        comp_passed = [r for r in passed if r.get("company") == comp]
        if not comp_passed:
            continue
        counter = {}
        for r in comp_passed:
            for v in r.get("values_matched", []):
                counter[v] = counter.get(v, 0) + 1
        counter = dict(sorted(counter.items(), key=lambda x: -x[1]))
        value_freq[comp] = counter
        top = ", ".join(f"{k}({n})" for k, n in list(counter.items())[:5])
        print(f"[{comp}] {top}")

    out = {
        "n_passed": len(passed), "n_failed": len(failed),
        "discrimination_pooled": discrimination,
        "company_specific": company_stats,
        "value_freq_by_company": value_freq,
    }
    Path("data/comparison.json").write_text(
        json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")
    print("\n저장: data/comparison.json")
    print("\n해석: '격차'가 클수록(★) 합격/탈락을 잘 가르는 지표.")
    print("      격차가 거의 없으면 → 그 차이는 자소서 밖(스펙·외부)에 있을 가능성.")


if __name__ == "__main__":
    main()
