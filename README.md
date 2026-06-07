# hmat_personality

현대차/기아 취업 준비 도구 모음.

## 구성

| 파일 | 설명 |
|------|------|
| `hmat_personality_app.py` | HMAT 인성검사 모의테스트 (Streamlit) |
| `scoring_criteria.md` | 자소서 채점 기준 명세서 (생산/제조 직무) |
| `analyze_essays.py` | 합격/불합격 자소서 통계 실측 스크립트 |
| `compare_stats.py` | 합격 vs 탈락 변별력 비교 (현대·기아 통합 풀링) |
| `spec_score.py` | 스펙(X축) 점수화 + 자소서(Y축) 결합 = 2축 데이터셋 |
| `specs_template.csv` | 스펙 입력 템플릿 (복사해서 `data/specs.csv` 로 채움) |

---

## 자소서 채점 모델 (설계 → 실측 → 코드)

`scoring_criteria.md` 가 진실의 원천(source of truth). 채점 철학·문항 구조·BARS 앵커가 정의돼 있다.

### 통계 실측 워크플로우

명세서의 예시값(정량 3.1개 등)을 **실제 합격 자소서 기반 숫자**로 교체하기 위한 절차.

```
# 권장 폴더 구조 (data/ 는 .gitignore — 절대 커밋 안 됨)
data/
  passed/
    passed_hyundai/   ← 현대차 합격 (01.txt, 02.txt, ...)
    passed_kia/       ← 기아 합격
  failed_hyundai/     ← 현대차 탈락 (모델 검증용)
  failed_kia/         ← 기아 탈락

파일 1개 = 지원자 1명.
Q1/Q2 구분하려면 본문에 [Q1] ... [Q2] ... 마커 삽입 (없으면 전체 통합 분석).
```

```bash
# 1. 설치 & API 키
pip install -r requirements_analysis.txt
export ANTHROPIC_API_KEY=sk-...   # Windows: $env:ANTHROPIC_API_KEY="sk-..."

# 2. 실측 실행 (--company 로 회사 지정)
python analyze_essays.py --input-dir data/passed/passed_hyundai --label passed --company hyundai
python analyze_essays.py --input-dir data/passed/passed_kia     --label passed --company kia
python analyze_essays.py --input-dir data/failed_hyundai        --label failed --company hyundai
python analyze_essays.py --input-dir data/failed_kia            --label failed --company kia
```

> **현대 vs 기아**: 직무 신호(정량·STAR·현장경험)는 사실상 동일해 합쳐도 무방하지만,
> 인재상/가치 항목은 회사마다 체계가 달라(`--company`) 분리 집계한다.
>
> **탈락 샘플 폴더 분리 필수**: `data/failed/` 에 현대·기아를 섞으면 `--company` 지정이
> 불가능하다. 회사별로 `failed_hyundai/` / `failed_kia/` 로 나눠 저장할 것.

### 산출물

| 파일 | 내용 | 공유 |
|------|------|------|
| `data/stats_passed_hyundai.json` | 합격자 평균/분포 + 플래그 임계값 제안 | ✅ 안전 (원문 없음) |
| `data/per_essay_passed_hyundai.json` | 자소서별 원시 지표 | ❌ 로컬 전용 (커밋 차단) |

`stats_passed_*.json` 의 `suggested_flag_thresholds` 값을 `scoring_criteria.md` §7 의
플래그 임계값으로 반영하면 된다.

### 합격 vs 탈락 변별력 비교 (현대·기아 통합)

각 회사 결과를 따로 내면 모수가 작아 신뢰도가 떨어진다. 그래서 비교 단계에서는:

```bash
python compare_stats.py   # data/per_essay_*.json 전부 자동 풀링
```

- **변별 지표**(본인기여·행동깊이·BARS 등 1~5 품질점수): **현대+기아 통합**으로
  합격 vs 탈락 비교 → 모수 최대, 신뢰도 ↑. '격차'가 클수록 잘 가르는 지표(★).
- **정량·문체·가치**: 회사마다 실제로 다르므로(현대 정량 ~5 vs 기아 ~9) **회사별 분리** 표시.

> 탈락자가 변별 지표에서 확연히 낮으면 → 자소서 안에 차이가 있던 것(모델 성공).
> 격차가 거의 없으면 → 탈락 사유는 자소서 밖(스펙·외부) → 2축의 스펙 축·멘토 영역.

산출: `data/comparison.json`

### 2축 모델 (스펙 X × 자소서 Y)

자소서 점수만으로 합/불이 안 갈리는 경우(잘 썼는데 탈락) → 원인은 스펙 축이다.
이를 보려고 스펙을 자소서에 매칭한다. (명세서 §9)

```bash
# 1) 템플릿을 복사해 채운다 (file 은 자소서 파일명과 정확히 일치)
cp specs_template.csv data/specs.csv        # Windows: copy specs_template.csv data\specs.csv

# 2) analyze_essays.py 가 먼저 돌아 per_essay_*.json 이 있어야 함

# 3) 2축 결합
python spec_score.py
```

- **X(스펙)**: 학점·어학·전공적합·자격증·현장경험·프로젝트를 가중합 → 0~100.
  가중치는 임시값(`spec_score.py` 의 `WEIGHTS`), 데이터 쌓이면 캘리브레이션.
- **Y(자소서)**: 품질 지표 11개 평균 → 0~100.
- 산출 `data/axis2.json` + 사분면 요약. 합격선 곡선은 탈락 표본이 쌓이면 추정.

> `data/specs.csv` 는 실제 스펙(학점 등)을 담으므로 `data/` 안에 둔다(.gitignore 보호).
> repo 에는 빈 `specs_template.csv` 만 올린다.

---

## 보안 (절대 준수)

- 합격/불합격 자소서 **원문은 repo 에 올리지 않는다.** `data/` 는 `.gitignore` 처리됨.
- 앱·리포트에는 원문을 출력/인용하지 않고, "합격자 평균 대비 위치" 통계만 노출한다.
