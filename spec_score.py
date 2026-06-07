"""
스펙(X축) 점수화 + 자소서(Y축) 결합 = 2축 데이터셋 생성

2축 모델(scoring_criteria.md §9)의 틀:
  X축 = 스펙(1차 스크리닝 통과력)   ← data/specs.csv 에서
  Y축 = 자소서 품질               ← data/per_essay_*.json 에서
  → 둘을 (파일명+회사)로 조인해 (x_score, y_score, label) 레코드를 만든다.

목적
  - 지금은 표본(특히 탈락)이 작아 곡선 추정은 못 하지만,
    데이터가 쌓이면 그대로 곡선 적합으로 이어지도록 '틀'을 미리 만든다.
  - 합격/탈락이 (X,Y) 평면 어디에 찍히는지 사분면으로 본다.

보안
  - data/specs.csv 는 실제 스펙(학점·학교 등)을 담으므로 data/ 안에 두어
    .gitignore 로 커밋 차단된다. repo 에는 빈 specs_template.csv 만 올린다.

사용법
  1) specs_template.csv 를 data/specs.csv 로 복사해 채운다.
       file 은 per_essay 결과의 파일명과 정확히 일치해야 조인된다.
  2) analyze_essays.py 를 먼저 돌려 data/per_essay_*.json 이 있어야 한다.
  3) python spec_score.py
       → data/axis2.json 저장 + 사분면 요약 출력
"""

import csv
import glob
import json
import statistics
from pathlib import Path

SPECS_CSV = "data/specs.csv"

# ── X축: 스펙 항목 가중치 (※ 임시값 — 합격/탈락 데이터로 캘리브레이션 필요) ──
# 각 항목을 0~1 로 정규화한 뒤 가중합 → ×100. 빈칸 항목은 빼고 남은 가중치로 재정규화.
WEIGHTS = {
    "gpa":               0.20,   # 학점 (gpa/gpa_scale)
    "english_level":     0.15,   # 어학 1~5 → /5
    "major_fit":         0.20,   # 전공-직무 적합 1~5 → /5
    "cert_count":        0.15,   # 직무자격증 개수 → min(n/2, 1)
    "internship_months": 0.20,   # 현장경험 개월 → min(m/6, 1)
    "project_award":     0.10,   # 프로젝트/수상 0~3 → /3
    "school_tier":       0.00,   # 블라인드 채용 → 기본 0 (분석용 기록만)
}

# ── Y축: 자소서 품질 지표와 만점(정규화용) ──
QUALITY_MAX = {
    "star_quality.situation_clarity": 5,
    "star_quality.role_ownership": 5,
    "star_quality.action_depth": 5,
    "star_quality.result_causality": 5,
    "field_experience_depth": 3,
    "jd_keyword_depth": 5,
    "bars.experience_specificity": 5,
    "bars.job_relevance": 5,
    "bars.logical_structure": 5,
    "bars.distinctiveness": 5,
    "bars.value_fit": 5,
}


def get(d: dict, dotted: str):
    cur = d
    for part in dotted.split("."):
        if not isinstance(cur, dict) or part not in cur:
            return None
        cur = cur[part]
    return cur


def to_float(s):
    try:
        return float(str(s).strip())
    except (ValueError, AttributeError):
        return None


def normalize_spec(row: dict) -> dict:
    """스펙 한 행을 항목별 0~1 정규화 값으로. 값 없으면 키 생략."""
    norm = {}
    gpa, scale = to_float(row.get("gpa")), to_float(row.get("gpa_scale"))
    if gpa is not None and scale:
        norm["gpa"] = min(gpa / scale, 1.0)
    el = to_float(row.get("english_level"))
    if el is not None:
        norm["english_level"] = min(el / 5, 1.0)
    mf = to_float(row.get("major_fit"))
    if mf is not None:
        norm["major_fit"] = min(mf / 5, 1.0)
    cc = to_float(row.get("cert_count"))
    if cc is not None:
        norm["cert_count"] = min(cc / 2, 1.0)
    im = to_float(row.get("internship_months"))
    if im is not None:
        norm["internship_months"] = min(im / 6, 1.0)
    pa = to_float(row.get("project_award"))
    if pa is not None:
        norm["project_award"] = min(pa / 3, 1.0)
    st = to_float(row.get("school_tier"))
    if st is not None:
        norm["school_tier"] = min(st / 5, 1.0)
    return norm


def x_score(norm: dict) -> float | None:
    """정규화된 스펙 → 0~100. 있는 항목의 가중치로 재정규화."""
    pairs = [(WEIGHTS[k], v) for k, v in norm.items() if WEIGHTS.get(k, 0) > 0]
    wsum = sum(w for w, _ in pairs)
    if wsum == 0:
        return None
    return round(100 * sum(w * v for w, v in pairs) / wsum, 1)


def y_score(essay: dict) -> float | None:
    """자소서 품질 지표 평균 → 0~100 (각 지표를 만점으로 정규화 후 평균)."""
    vals = []
    for key, mx in QUALITY_MAX.items():
        v = get(essay, key)
        if isinstance(v, (int, float)):
            vals.append(v / mx)
    return round(100 * statistics.mean(vals), 1) if vals else None


def load_specs() -> dict:
    """data/specs.csv → {(file, company): row}. 주석(#)·빈 행 무시."""
    path = Path(SPECS_CSV)
    if not path.exists():
        return {}
    specs = {}
    with path.open(encoding="utf-8") as f:
        reader = csv.DictReader(r for r in f if not r.lstrip().startswith("#"))
        for row in reader:
            fname = (row.get("file") or "").strip()
            comp = (row.get("company") or "").strip()
            if not fname or not comp:
                continue
            specs[(fname, comp)] = row
    return specs


def load_essays() -> list:
    """data/per_essay_*.json 전부 → 레코드 리스트."""
    out = []
    for p in sorted(glob.glob("data/per_essay_*.json")):
        try:
            out.extend(json.loads(Path(p).read_text(encoding="utf-8")))
        except Exception as e:
            print(f"  (건너뜀) {p}: {e}")
    return out


def main():
    specs = load_specs()
    essays = load_essays()

    if not essays:
        print("data/per_essay_*.json 가 없습니다. 먼저 analyze_essays.py 를 실행하세요.")
        return
    if not specs:
        print(f"{SPECS_CSV} 가 없습니다. specs_template.csv 를 복사해 채우세요:")
        print(f"  cp specs_template.csv {SPECS_CSV}   (Windows: copy)")
        return

    rows, unmatched = [], []
    for e in essays:
        key = (e.get("file", ""), e.get("company", ""))
        spec = specs.get(key)
        y = y_score(e)
        if spec is None:
            unmatched.append(key)
            continue
        x = x_score(normalize_spec(spec))
        rows.append({
            "file": key[0], "company": key[1],
            "label": e.get("label"),
            "x_score": x, "y_score": y,
        })

    if not rows:
        print("조인된 레코드가 없습니다. specs.csv 의 file/company 가 자소서와 일치하는지 확인하세요.")
        if unmatched:
            print("  스펙 없는 자소서:", ", ".join(f"{f}/{c}" for f, c in unmatched[:10]))
        return

    # ── 사분면 요약 (중앙값 기준) ──
    xs = [r["x_score"] for r in rows if r["x_score"] is not None]
    ys = [r["y_score"] for r in rows if r["y_score"] is not None]
    x_mid = round(statistics.median(xs), 1) if xs else 50
    y_mid = round(statistics.median(ys), 1) if ys else 50

    print("=" * 60)
    print(f"2축 데이터셋  (n={len(rows)}, 미매칭 {len(unmatched)})")
    print(f"  X(스펙) 중앙값={x_mid}  |  Y(자소서) 중앙값={y_mid}")
    print("=" * 60)
    print(f"{'파일':<16}{'회사':<9}{'합/불':<8}{'X스펙':>7}{'Y자소서':>9}")
    print("-" * 60)
    for r in sorted(rows, key=lambda r: (r["label"] or "", -(r["x_score"] or 0))):
        print(f"{r['file']:<16}{r['company']:<9}{(r['label'] or '?'):<8}"
              f"{(r['x_score'] if r['x_score'] is not None else '-'):>7}"
              f"{(r['y_score'] if r['y_score'] is not None else '-'):>9}")

    # 라벨별 평균
    print("-" * 60)
    for lab in ("passed", "failed"):
        sub = [r for r in rows if r["label"] == lab]
        if not sub:
            continue
        mx = round(statistics.mean([r["x_score"] for r in sub if r["x_score"] is not None]), 1)
        my = round(statistics.mean([r["y_score"] for r in sub if r["y_score"] is not None]), 1)
        print(f"[{lab}] n={len(sub)}  X평균 {mx}  Y평균 {my}")

    out = {
        "x_median": x_mid, "y_median": y_mid,
        "weights": WEIGHTS,
        "records": rows,
        "unmatched_essays": [f"{f}/{c}" for f, c in unmatched],
    }
    Path("data/axis2.json").write_text(
        json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")
    print("\n저장: data/axis2.json")
    print("\n해석 가이드 (2축 모델):")
    print("  · 탈락인데 X(스펙) 낮고 Y(자소서) 높음 → '잘 썼지만 스펙에서 탈락' = 멘토/스펙 영역")
    print("  · 탈락인데 Y(자소서) 낮음            → 자소서가 원인 = AI가 잡아야 할 영역")
    print("  · 합격선 곡선은 표본(특히 탈락)이 쌓이면 이 데이터로 추정한다.")


if __name__ == "__main__":
    main()
