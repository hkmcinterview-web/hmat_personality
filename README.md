# hmat_personality

현대차/기아 취업 준비 도구 모음.

## 구성

| 파일 | 설명 |
|------|------|
| `hmat_personality_app.py` | HMAT 인성검사 모의테스트 (Streamlit) |
| `scoring_criteria.md` | 자소서 채점 기준 명세서 (생산/제조 직무) |
| `analyze_essays.py` | 합격/불합격 자소서 통계 실측 스크립트 |

---

## 자소서 채점 모델 (설계 → 실측 → 코드)

`scoring_criteria.md` 가 진실의 원천(source of truth). 채점 철학·문항 구조·BARS 앵커가 정의돼 있다.

### 통계 실측 워크플로우

명세서의 예시값(정량 3.1개 등)을 **실제 합격 자소서 기반 숫자**로 교체하기 위한 절차.

```bash
# 1. 설치
pip install -r requirements_analysis.txt
export ANTHROPIC_API_KEY=sk-...

# 2. 자소서를 텍스트로 저장 (data/ 는 .gitignore 처리되어 절대 커밋 안 됨)
#    회사별로 폴더를 나눈다 — 인재상 체계가 다르기 때문 (현대=Hyundai Way / 기아=KIAN)
#    data/passed_hyundai/01.txt , 02.txt , ...   ← 현대차 합격
#    data/passed_kia/01.txt , ...                ← 기아 합격
#    data/failed_hyundai/01.txt , ...            ← 불합격 (모델 검증용)
#    * 파일 1개 = 지원자 1명
#    * Q1/Q2 구분하려면 본문에 [Q1] ... [Q2] ... 마커 삽입 (선택)

# 3. 실측 실행 (--company 로 회사 지정)
python analyze_essays.py --input-dir data/passed_hyundai --label passed --company hyundai
python analyze_essays.py --input-dir data/passed_kia     --label passed --company kia
python analyze_essays.py --input-dir data/failed_hyundai --label failed --company hyundai
```

> **현대 vs 기아**: 직무 신호(정량·STAR·현장경험)는 사실상 동일해 합쳐도 무방하지만,
> 인재상/가치 항목은 회사마다 체계가 달라(`--company`) 분리 집계한다.

### 산출물

| 파일 | 내용 | 공유 |
|------|------|------|
| `data/stats_passed_hyundai.json` | 합격자 평균/분포 + 플래그 임계값 제안 | ✅ 안전 (원문 없음) |
| `data/per_essay_passed_hyundai.json` | 자소서별 원시 지표 | ❌ 로컬 전용 (커밋 차단) |

`stats_passed_*.json` 의 `suggested_flag_thresholds` 값을 `scoring_criteria.md` §7 의
플래그 임계값으로 반영하면 된다.

### 불합격 자소서 = 모델 검증(validation)

불합격 자소서는 모델이 제대로 낮게 평가하는지 확인하는 용도다.
`stats_passed.json` vs `stats_failed.json` 을 비교했을 때:

- 불합격이 정량·STAR·BARS 점수가 더 낮으면 → 모델이 잘 구분하는 것
- 불합격인데 점수가 높게 나오면 → 해당 항목 가중치 재조정 필요 (모델 개선 신호)

---

## 보안 (절대 준수)

- 합격/불합격 자소서 **원문은 repo 에 올리지 않는다.** `data/` 는 `.gitignore` 처리됨.
- 앱·리포트에는 원문을 출력/인용하지 않고, "합격자 평균 대비 위치" 통계만 노출한다.
