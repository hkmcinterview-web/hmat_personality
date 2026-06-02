import streamlit as st
import pandas as pd
import plotly.graph_objects as go
import requests
from datetime import datetime

st.set_page_config(page_title="HMAT 인성검사 모의테스트", layout="centered", page_icon="🧭")

# ── 스타일 (스펙 분석 앱과 동일 톤) ──────────────────────────────────────────────
st.markdown("""
<style>
  @import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&display=swap');
  html, body, [class*="css"] { font-family: 'Inter', sans-serif; }
  .stApp { background: #0f0f10; color: #e8e6e3; }
  .hero { padding: 2.2rem 0 1.2rem; text-align: center; }
  .hero-badge {
    display: inline-block;
    background: rgba(124,106,245,0.12); border: 1px solid rgba(124,106,245,0.3);
    color: #9d8cf5; font-size: 0.72rem; font-weight: 600;
    letter-spacing: 0.12em; text-transform: uppercase;
    padding: 0.3rem 0.9rem; border-radius: 999px; margin-bottom: 1rem;
  }
  .hero-title { font-size: 1.9rem; font-weight: 700; color: #f5f3f0; letter-spacing: -0.03em; line-height: 1.25; margin: 0.4rem 0; }
  .hero-sub { font-size: 0.88rem; color: #7a7772; margin-top: 0.5rem; }
  .metric-row { display: flex; gap: 0.75rem; margin-bottom: 1rem; }
  .metric-box { flex: 1; background: #1a1a1b; border: 1px solid #2a2a2c; border-radius: 12px; padding: 1.1rem 1.2rem; text-align: center; }
  .metric-val { font-size: 1.6rem; font-weight: 700; color: #f5f3f0; letter-spacing: -0.04em; line-height: 1; }
  .metric-label { font-size: 0.75rem; color: #5a5855; margin-top: 0.35rem; font-weight: 500; }
  .status-ok { background: rgba(52,168,120,0.1); border: 1px solid rgba(52,168,120,0.25); color: #34a878; border-radius: 10px; padding: 0.75rem 1rem; font-size: 0.85rem; font-weight: 500; margin-bottom: 0.5rem; }
  .status-warn { background: rgba(205,140,91,0.1); border: 1px solid rgba(205,140,91,0.25); color: #cd8c5b; border-radius: 10px; padding: 0.75rem 1rem; font-size: 0.85rem; font-weight: 500; margin-bottom: 0.5rem; }
  .status-bad { background: rgba(220,80,80,0.1); border: 1px solid rgba(220,80,80,0.28); color: #e07070; border-radius: 10px; padding: 0.75rem 1rem; font-size: 0.85rem; font-weight: 500; margin-bottom: 0.5rem; }
  hr.divider { border: none; border-top: 1px solid #2a2a2c; margin: 1.4rem 0; }
  .q-card { background: #1a1a1b; border: 1px solid #2a2a2c; border-radius: 12px; padding: 1rem 1.2rem; margin-bottom: 0.7rem; }
  .q-text { font-size: 0.92rem; color: #e8e6e3; font-weight: 500; line-height: 1.45; }
  .q-num { font-size: 0.7rem; color: #5a5855; font-weight: 700; letter-spacing: 0.1em; margin-bottom: 0.3rem; }
  .pct-card { background: #1a1a1b; border: 1px solid #2a2a2c; border-radius: 14px; padding: 1rem 1.2rem; margin-bottom: 0.6rem; }
  .pct-label { font-size: 0.72rem; font-weight: 600; letter-spacing: 0.06em; text-transform: uppercase; color: #5a5855; margin-bottom: 0.4rem; }
  .pct-bar-bg { background: #2a2a2c; border-radius: 999px; height: 6px; margin-top: 0.5rem; overflow: hidden; }
  .pct-bar-fill { height: 6px; border-radius: 999px; }
  div[data-baseweb="select"] > div { background: #111112 !important; border-color: #2a2a2c !important; border-radius: 10px !important; color: #e8e6e3 !important; }
  div[data-baseweb="select"] * { color: #e8e6e3 !important; }
  div[data-baseweb="radio"] * { color: #c8c6c3 !important; }
  label { color: #9a9895 !important; font-size: 0.82rem !important; font-weight: 500 !important; }
  .stButton button { background: #7c6af5 !important; color: #fff !important; border: none !important; border-radius: 10px !important; font-weight: 600 !important; }
  ::-webkit-scrollbar { width: 5px; }
  ::-webkit-scrollbar-track { background: #0f0f10; }
  ::-webkit-scrollbar-thumb { background: #2a2a2c; border-radius: 999px; }

  @media (max-width: 640px) {
    .block-container { padding: 2rem 0.7rem 4rem !important; }
    .hero-title { font-size: 1.3rem !important; }
    .metric-row { flex-wrap: wrap !important; gap: 0.4rem !important; }
    .metric-val { font-size: 1.1rem !important; }
    .q-text { font-size: 0.85rem !important; }
  }
</style>
""", unsafe_allow_html=True)


# ════════════════════════════════════════════════════════════════════════════════
# 1) 문항 설계
# ════════════════════════════════════════════════════════════════════════════════
# axis: 6개 성향 축
AXES = ["분석성", "실행력", "협업성", "도전성", "신중성", "주도성"]

# 현대차그룹 인재상(도전·창의·열정·협력·글로벌)을 6축에 매핑하여 측정
# 각 문항: (id, 텍스트, 축, 방향)  방향 +1=정방향, -1=역방향(역채점)
QUESTIONS = [
    # ── 분석성 (창의·논리) ──
    ("A1", "나는 중요한 결정을 내리기 전 데이터와 근거를 충분히 검토한다.", "분석성", +1),
    ("A2", "나는 근거를 따지기보다 직관적으로 빠르게 판단하는 편이다.", "분석성", -1),
    ("A3", "복잡한 문제를 만나면 원인을 끝까지 파고들어 분석한다.", "분석성", +1),
    # ── 실행력 (열정·추진) ──
    ("E1", "목표가 정해지면 주저 없이 빠르게 추진한다.", "실행력", +1),
    ("E2", "나는 모든 준비가 끝날 때까지 실행을 미루는 편이다.", "실행력", -1),
    ("E3", "결과로 증명하기 위해 끝까지 밀어붙인다.", "실행력", +1),
    # ── 협업성 (협력) ──
    ("C1", "혼자보다 팀으로 일할 때 더 좋은 성과가 난다고 믿는다.", "협업성", +1),
    ("C2", "나는 다른 사람과 맞추기보다 혼자 일하는 것이 편하다.", "협업성", -1),
    ("C3", "동료가 어려움을 겪으면 먼저 다가가 돕는 편이다.", "협업성", +1),
    # ── 도전성 (도전·글로벌) ──
    ("D1", "검증되지 않은 새로운 방식에도 기꺼이 도전한다.", "도전성", +1),
    ("D2", "나는 익숙하고 안정적인 방식을 더 선호한다.", "도전성", -1),
    ("D3", "현재에 안주하지 않고 더 나은 방법을 끊임없이 찾는다.", "도전성", +1),
    # ── 신중성 (책임·완결) ──
    ("N1", "나는 계획을 세우고 세부사항까지 꼼꼼히 점검한다.", "신중성", +1),
    ("N2", "큰 그림에 집중하느라 세부 점검은 소홀히 하는 편이다.", "신중성", -1),
    ("N3", "일을 마치기 전 여러 번 검토하여 실수를 줄인다.", "신중성", +1),
    # ── 주도성 (리더십) ──
    ("L1", "여럿이 모이면 자연스럽게 이끄는 역할을 맡는다.", "주도성", +1),
    ("L2", "나는 앞에 나서기보다 뒤에서 따르는 것이 편하다.", "주도성", -1),
    ("L3", "내 의견을 분명히 제시하고 사람들을 설득하는 편이다.", "주도성", +1),
]

# 거짓말 척도(사회적 바람직성): 높게 답할수록 과잉포장 의심
LIE_QUESTIONS = [
    ("LIE1", "나는 지금까지 단 한 번도 거짓말을 한 적이 없다."),
    ("LIE2", "나는 어떤 상황에서도 화를 내본 적이 전혀 없다."),
    ("LIE3", "나는 약속을 단 한 번도 어긴 적이 없다."),
    ("LIE4", "나는 누군가를 미워하거나 시기해 본 적이 전혀 없다."),
    ("LIE5", "나는 맡은 일에서 한 번도 실수한 적이 없다."),
]

# 일관성 쌍 (정방향 id, 역방향 id) — 같은 축을 반대로 물은 쌍
CONSISTENCY_PAIRS = [
    ("A1", "A2"), ("E1", "E2"), ("C1", "C2"),
    ("D1", "D2"), ("N1", "N2"), ("L1", "L2"),
]

# ── 강제선택형(PART 1, HMAT 시그니처) ──────────────────────────────────────────
# 축별 문장 풀 (세트마다 다른 문장 사용)
AXIS_FC_POOL = {
    "분석성": ["객관적 데이터로 판단한다", "원인을 끝까지 분석한다", "논리적 근거를 중시한다", "사실과 숫자를 먼저 확인한다"],
    "실행력": ["일단 빠르게 실행한다", "결과로 증명한다", "속도감 있게 추진한다", "망설임 없이 행동에 옮긴다"],
    "협업성": ["팀원과 함께 결정한다", "동료를 먼저 돕는다", "상대 의견을 경청한다", "조직의 화합을 중시한다"],
    "도전성": ["새로운 방식을 시도한다", "어려운 목표에 도전한다", "변화를 즐긴다", "기존의 틀을 깨려 한다"],
    "신중성": ["꼼꼼하게 점검한다", "계획을 세워 움직인다", "위험을 미리 대비한다", "실수가 없도록 재확인한다"],
    "주도성": ["앞장서서 이끈다", "의견을 적극 제시한다", "책임지고 결정한다", "사람들을 설득한다"],
}
# 각 세트의 3개 축 (6축이 각 4회 균등 등장)
FC_SET_AXES = [
    ["분석성", "실행력", "협업성"],
    ["도전성", "신중성", "주도성"],
    ["분석성", "협업성", "도전성"],
    ["실행력", "신중성", "주도성"],
    ["분석성", "실행력", "신중성"],
    ["협업성", "도전성", "주도성"],
    ["분석성", "도전성", "주도성"],
    ["실행력", "협업성", "신중성"],
]

def build_fc_sets():
    """축별 문장 풀을 순서대로 소비하여 강제선택 세트 생성."""
    cursor = {a: 0 for a in AXES}
    sets = []
    for i, axes in enumerate(FC_SET_AXES, 1):
        opts = []
        for a in axes:
            idx = cursor[a] % len(AXIS_FC_POOL[a])
            opts.append((a, AXIS_FC_POOL[a][idx]))
            cursor[a] += 1
        sets.append({"id": f"F{i}", "options": opts})
    return sets

FC_SETS = build_fc_sets()

# 직무별 이상 성향 프로파일 (0~100) — 현직자 경험 기반 참고용 추정치
JOB_PROFILES = {
    "연구개발":            {"분석성": 92, "실행력": 60, "협업성": 65, "도전성": 72, "신중성": 88, "주도성": 55},
    "생산/제조":          {"분석성": 68, "실행력": 82, "협업성": 82, "도전성": 52, "신중성": 88, "주도성": 62},
    "사업/기획/경영지원":  {"분석성": 78, "실행력": 80, "협업성": 76, "도전성": 76, "신중성": 62, "주도성": 86},
    "품질":               {"분석성": 85, "실행력": 65, "협업성": 72, "도전성": 48, "신중성": 95, "주도성": 55},
}

# 6점 척도 (실제 HMAT 동일)
LIKERT = ["① 전혀 아니다", "② 아니다", "③ 약간 아니다", "④ 약간 그렇다", "⑤ 그렇다", "⑥ 매우 그렇다"]
LIKERT_VAL = {opt: i + 1 for i, opt in enumerate(LIKERT)}


# ════════════════════════════════════════════════════════════════════════════════
# 2) 점수 계산 로직
# ════════════════════════════════════════════════════════════════════════════════
def _fc_axis_raw(fc_responses):
    """강제선택 결과 → 축별 원점수(가깝다 +1, 멀다 -1)."""
    raw = {a: 0 for a in AXES}
    for sid, (close_axis, far_axis) in (fc_responses or {}).items():
        if close_axis:
            raw[close_axis] += 1
        if far_axis:
            raw[far_axis] -= 1
    return raw


def score_axes(responses, fc_responses=None):
    """각 축 점수(0~100). 리커트(6점) 기반 + 강제선택 보정.
    리커트 65% + 강제선택 35% 가중 (강제선택 없으면 리커트만)."""
    # 리커트 (역방향은 7-v 역채점), 1~6 → 0~100
    axis_likert = {a: [] for a in AXES}
    for qid, text, axis, direction in QUESTIONS:
        v = responses.get(qid)
        if v is None:
            continue
        adj = v if direction == +1 else (7 - v)
        axis_likert[axis].append(adj)
    likert100 = {}
    for a in AXES:
        vals = axis_likert[a]
        likert100[a] = (sum(vals) / len(vals) - 1) / 5 * 100 if vals else 50

    if not fc_responses:
        return {a: round(likert100[a]) for a in AXES}

    # 강제선택: 각 축 등장 4회 → 범위 -4~+4 → 0~100
    raw = _fc_axis_raw(fc_responses)
    appear = {a: FC_SET_AXES_FLAT.count(a) for a in AXES}
    fc100 = {a: (raw[a] + appear[a]) / (2 * appear[a]) * 100 if appear[a] else 50 for a in AXES}

    return {a: round(likert100[a] * 0.65 + fc100[a] * 0.35) for a in AXES}


def consistency_score(responses, fc_responses=None):
    """일관성 점수(0~100). 리커트 정/역 쌍 + 강제선택과 리커트 방향 일치."""
    diffs = []
    for pos_id, neg_id in CONSISTENCY_PAIRS:
        p = responses.get(pos_id)
        n = responses.get(neg_id)
        if p is None or n is None:
            continue
        diffs.append(abs(p - (7 - n)))   # 일관적이면 p ≈ (7-n), 0~5
    flagged = []
    for pos_id, neg_id in CONSISTENCY_PAIRS:
        p, n = responses.get(pos_id), responses.get(neg_id)
        if p is None or n is None:
            continue
        if abs(p - (7 - n)) >= 4:
            flagged.append((pos_id, neg_id))

    # 강제선택 ↔ 리커트 방향 모순: 리커트 점수 높은(>=70) 축을 '가장 멀다'로,
    # 낮은(<=30) 축을 '가장 가깝다'로 고르면 모순
    fc_penalty = 0
    if fc_responses:
        lk = score_axes(responses)  # 리커트만
        for sid, (close_axis, far_axis) in fc_responses.items():
            if close_axis and lk.get(close_axis, 50) <= 30:
                fc_penalty += 1
            if far_axis and lk.get(far_axis, 50) >= 70:
                fc_penalty += 1

    if not diffs:
        base = 100
    else:
        base = 100 - (sum(diffs) / len(diffs) / 5 * 100)
    score = round(max(0, base - fc_penalty * 6))
    return score, flagged


def lie_score(lie_responses):
    """사회적 바람직성. 5~6점(그렇다 이상)으로 답한 비율."""
    vals = [v for v in (lie_responses or {}).values() if v is not None]
    if not vals:
        return 0
    high = sum(1 for v in vals if v >= 5)
    return round(high / len(vals) * 100)


FC_SET_AXES_FLAT = [a for axes in FC_SET_AXES for a in axes]


def job_fit(my_axes, job):
    """직무 이상 프로파일과의 적합도(0~100). 유클리드 거리 기반."""
    profile = JOB_PROFILES.get(job)
    if not profile:
        return None
    sq = sum((my_axes[a] - profile[a]) ** 2 for a in AXES)
    dist = (sq / len(AXES)) ** 0.5            # 0~100 범위 RMSE
    return max(0, round(100 - dist))


# ════════════════════════════════════════════════════════════════════════════════
# 데이터 저장/조회 (구글 폼 쓰기 + 응답시트 CSV 읽기)
# ════════════════════════════════════════════════════════════════════════════════
# [설정 필요] 구글 폼을 만든 뒤 secrets.toml 또는 Streamlit Secrets에 등록:
#   HMAT_FORM_URL    = ".../formResponse"          (폼 제출용)
#   HMAT_RESULTS_CSV = ".../pub?output=csv"         (응답시트 게시 CSV, 영구 조회용)
# 그리고 아래 FORM_ENTRIES 의 entry.xxx 를 실제 폼 entry id 로 교체하세요.
FORM_POST_URL    = st.secrets.get("HMAT_FORM_URL", "")
HMAT_RESULTS_CSV = st.secrets.get("HMAT_RESULTS_CSV", "")
FORM_ENTRIES = {
    "이름":   "entry.1111111111",
    "전화":   "entry.2222222222",
    "직무":   "entry.3333333333",
    "분석성": "entry.4444444444",
    "실행력": "entry.5555555555",
    "협업성": "entry.6666666666",
    "도전성": "entry.7777777777",
    "신중성": "entry.8888888888",
    "주도성": "entry.9999999999",
    "일관성": "entry.1010101010",
    "과잉포장": "entry.1212121212",
    "적합도": "entry.1313131313",
    "시각":   "entry.1414141414",
}

def save_response(payload):
    if not FORM_POST_URL:
        return
    data = {FORM_ENTRIES[k]: payload[k] for k in FORM_ENTRIES if k in payload and not FORM_ENTRIES[k].endswith("11111111")}
    # entry id 가 아직 placeholder 면 전송하지 않음 (잘못된 응답 방지)
    if any(v.startswith("entry.1111") or v.startswith("entry.9999") for v in [FORM_ENTRIES["이름"], FORM_ENTRIES["주도성"]]):
        # 기본 placeholder 상태 → 저장 스킵
        pass
    full = {FORM_ENTRIES[k]: payload[k] for k in FORM_ENTRIES if k in payload}
    try:
        requests.post(FORM_POST_URL, data=full,
                      headers={"Content-Type": "application/x-www-form-urlencoded"},
                      timeout=5)
    except Exception:
        pass

@st.cache_data(ttl=60)
def _load_results_csv(url):
    return pd.read_csv(url)

def load_past_results(name, phone, job):
    """응답시트에서 같은 이름+전화+직무의 과거 기록을 시간순으로 반환."""
    if not HMAT_RESULTS_CSV or not name or not phone:
        return []
    try:
        df = _load_results_csv(HMAT_RESULTS_CSV)
    except Exception:
        return []
    # 컬럼명 유연 매칭
    def col(*names):
        for n in names:
            for c in df.columns:
                if n in str(c):
                    return c
        return None
    c_name, c_phone, c_job = col("이름"), col("전화", "휴대"), col("직무")
    if not (c_name and c_phone and c_job):
        return []
    phone_norm = str(phone).replace("-", "").strip()
    sub = df[
        (df[c_name].astype(str).str.strip() == str(name).strip()) &
        (df[c_phone].astype(str).str.replace("-", "", regex=False).str.strip() == phone_norm) &
        (df[c_job].astype(str).str.strip() == str(job).strip())
    ]
    out = []
    for _, r in sub.iterrows():
        rec = {"axes": {}}
        for a in AXES:
            ca = col(a)
            rec["axes"][a] = float(r[ca]) if ca and pd.notna(r[ca]) else 0
        cc, cl, cf, ct = col("일관성"), col("과잉포장"), col("적합도"), col("시각")
        rec["cons"] = float(r[cc]) if cc and pd.notna(r[cc]) else 0
        rec["lie"]  = float(r[cl]) if cl and pd.notna(r[cl]) else 0
        rec["fit"]  = float(r[cf]) if cf and pd.notna(r[cf]) else 0
        rec["time"] = str(r[ct]) if ct else ""
        rec["job"]  = job
        out.append(rec)
    return out


# ════════════════════════════════════════════════════════════════════════════════
# 3) 화면
# ════════════════════════════════════════════════════════════════════════════════
CARD_BG, GRID_COL, TEXT_COL, MUTED_COL = "#1a1a1b", "#2a2a2c", "#e8e6e3", "#5a5855"
ACCENT, ACCENT2 = "#7c6af5", "#cd8c5b"

st.markdown("""
<div class="hero">
  <div class="hero-badge">HMAT Personality</div>
  <div class="hero-title">HMAT 인성검사 모의 테스트</div>
  <div class="hero-sub">반복 응시로 답변 일관성과 직무 성향을 점검하세요</div>
</div>
""", unsafe_allow_html=True)

if 'hmat_done' not in st.session_state:
    st.session_state.hmat_done = False
if 'attempt_count' not in st.session_state:
    st.session_state.attempt_count = 0

# ── 입력 폼 ───────────────────────────────────────────────────────────────────
with st.form("hmat_form"):
    nc1, nc2 = st.columns(2)
    with nc1:
        user_name = st.text_input("이름", placeholder="홍길동", key="user_name")
    with nc2:
        user_phone = st.text_input("휴대폰 번호", placeholder="010-1234-5678", key="user_phone")
    st.markdown("<div style='font-size:0.72rem;color:#5a5855;margin:-0.3rem 0 0.6rem;'>이름·번호는 회차별 성장 기록을 이어보기 위해 사용됩니다.</div>", unsafe_allow_html=True)

    target_job = st.selectbox("지원 직무", list(JOB_PROFILES.keys()))

    # ── PART 1: 강제선택 (HMAT 시그니처) ──────────────────────────────────────
    st.markdown("<hr class='divider'>", unsafe_allow_html=True)
    st.markdown("<div style='font-size:0.9rem;font-weight:700;color:#9d8cf5;margin-bottom:0.2rem;'>PART 1 · 강제선택</div>", unsafe_allow_html=True)
    st.markdown("<div style='font-size:0.8rem;color:#7a7772;margin-bottom:0.9rem;'>각 세트에서 자신과 <b>가장 가까운 것</b>과 <b>가장 먼 것</b>을 하나씩 고르세요. (실제 HMAT PART1 형식)</div>", unsafe_allow_html=True)

    fc_responses = {}
    for si, s in enumerate(FC_SETS, 1):
        sentences = [o[1] for o in s["options"]]
        axis_map = {o[1]: o[0] for o in s["options"]}
        items = "".join(f"<div style='font-size:0.85rem;color:#e8e6e3;margin:0.2rem 0;'>· {snt}</div>" for snt in sentences)
        st.markdown(f"<div class='q-card'><div class='q-num'>SET {si}</div>{items}</div>", unsafe_allow_html=True)
        fcc1, fcc2 = st.columns(2)
        with fcc1:
            close = st.radio(f"⭕ 가장 가깝다", sentences, index=None, key=f"fc_c_{s['id']}")
        with fcc2:
            far = st.radio(f"❌ 가장 멀다", sentences, index=None, key=f"fc_f_{s['id']}")
        ca = axis_map.get(close) if close else None
        fa = axis_map.get(far) if far else None
        if close and far and close == far:
            fa = None
        fc_responses[s["id"]] = (ca, fa)

    # ── PART 2: 리커트 6점 ────────────────────────────────────────────────────
    st.markdown("<hr class='divider'>", unsafe_allow_html=True)
    st.markdown("<div style='font-size:0.9rem;font-weight:700;color:#9d8cf5;margin-bottom:0.2rem;'>PART 2 · 동의 정도</div>", unsafe_allow_html=True)
    st.markdown("<div style='font-size:0.8rem;color:#7a7772;margin-bottom:0.9rem;'>각 문항에 솔직하게 답해주세요. 정답은 없습니다.</div>", unsafe_allow_html=True)

    responses = {}
    for idx, (qid, text, axis, direction) in enumerate(QUESTIONS, 1):
        st.markdown(f"<div class='q-card'><div class='q-num'>Q{idx}</div><div class='q-text'>{text}</div></div>", unsafe_allow_html=True)
        choice = st.radio(f"q_{qid}", LIKERT, index=None, horizontal=True, label_visibility="collapsed", key=f"q_{qid}")
        responses[qid] = LIKERT_VAL[choice] if choice else None

    st.markdown("<hr class='divider'>", unsafe_allow_html=True)
    st.markdown("<div style='font-size:0.82rem;color:#7a7772;margin-bottom:0.8rem;'>추가 문항입니다.</div>", unsafe_allow_html=True)

    lie_responses = {}
    base = len(QUESTIONS)
    for j, (lid, text) in enumerate(LIE_QUESTIONS, 1):
        st.markdown(f"<div class='q-card'><div class='q-num'>Q{base + j}</div><div class='q-text'>{text}</div></div>", unsafe_allow_html=True)
        choice = st.radio(f"q_{lid}", LIKERT, index=None, horizontal=True, label_visibility="collapsed", key=f"q_{lid}")
        lie_responses[lid] = LIKERT_VAL[choice] if choice else None

    submitted = st.form_submit_button("결과 분석하기", use_container_width=True)

if 'history' not in st.session_state:
    st.session_state.history = []

if submitted:
    if not user_name.strip() or not user_phone.strip():
        st.markdown("<div class='status-warn'>⚠ 이름과 휴대폰 번호를 입력해주세요. (회차 기록 저장에 필요합니다)</div>", unsafe_allow_html=True)
    else:
        st.session_state.hmat_done = True
        st.session_state.attempt_count += 1
        st.session_state.last_responses = responses
        st.session_state.last_lie = lie_responses
        st.session_state.last_fc = fc_responses
        st.session_state.last_job = target_job
        st.session_state.user_name_v = user_name.strip()
        st.session_state.user_phone_v = user_phone.strip()

        # 회차 결과 계산 후 누적
        _axes = score_axes(responses, fc_responses)
        _cons, _flagged = consistency_score(responses, fc_responses)
        _lie = lie_score(lie_responses)
        _fit = job_fit(_axes, target_job)
        st.session_state.history.append({
            "attempt": st.session_state.attempt_count,
            "job": target_job,
            "axes": _axes,
            "cons": _cons,
            "lie": _lie,
            "fit": _fit,
            "time": datetime.now().strftime("%m-%d %H:%M"),
        })


# ── 결과 ──────────────────────────────────────────────────────────────────────
if st.session_state.hmat_done:
    responses = st.session_state.last_responses
    lie_responses = st.session_state.last_lie
    fc_responses = st.session_state.get("last_fc", {})
    target_job = st.session_state.last_job

    my_axes = score_axes(responses, fc_responses)
    cons, flagged = consistency_score(responses, fc_responses)
    lie = lie_score(lie_responses)
    fit = job_fit(my_axes, target_job)

    st.markdown("<hr class='divider'>", unsafe_allow_html=True)
    st.markdown(f"<div style='font-size:0.78rem;font-weight:600;letter-spacing:0.1em;text-transform:uppercase;color:#5a5855;margin-bottom:0.8rem;'>{target_job} · 분석 결과 (시도 {st.session_state.attempt_count}회)</div>", unsafe_allow_html=True)

    # 핵심 메트릭
    fit_color = "#34a878" if fit >= 75 else ("#cd8c5b" if fit >= 55 else "#e07070")
    cons_color = "#34a878" if cons >= 80 else ("#cd8c5b" if cons >= 60 else "#e07070")
    st.markdown(f"""
    <div class="metric-row">
      <div class="metric-box">
        <div class="metric-val" style="color:{fit_color};">{fit}%</div>
        <div class="metric-label">직무 적합도</div>
      </div>
      <div class="metric-box">
        <div class="metric-val" style="color:{cons_color};">{cons}점</div>
        <div class="metric-label">답변 일관성</div>
      </div>
      <div class="metric-box">
        <div class="metric-val" style="color:{'#e07070' if lie >= 50 else '#f5f3f0'};">{lie}%</div>
        <div class="metric-label">과잉포장 지수</div>
      </div>
    </div>
    """, unsafe_allow_html=True)

    # 레이더 차트 — 내 성향 vs 직무 이상
    profile = JOB_PROFILES[target_job]
    cats = AXES + [AXES[0]]
    my_vals = [my_axes[a] for a in AXES] + [my_axes[AXES[0]]]
    job_vals = [profile[a] for a in AXES] + [profile[AXES[0]]]

    fig = go.Figure()
    fig.add_trace(go.Scatterpolar(r=job_vals, theta=cats, fill='toself', name=f'{target_job} 이상형',
                                  line=dict(color=ACCENT2, width=2), fillcolor='rgba(205,140,91,0.1)'))
    fig.add_trace(go.Scatterpolar(r=my_vals, theta=cats, fill='toself', name='나',
                                  line=dict(color=ACCENT, width=2), fillcolor='rgba(124,106,245,0.18)'))
    fig.update_layout(
        paper_bgcolor=CARD_BG, plot_bgcolor=CARD_BG,
        polar=dict(bgcolor=CARD_BG,
                   radialaxis=dict(visible=True, range=[0, 100], gridcolor=GRID_COL, linecolor=GRID_COL,
                                   tickfont=dict(color=MUTED_COL, size=9)),
                   angularaxis=dict(gridcolor=GRID_COL, linecolor=GRID_COL, tickfont=dict(color=TEXT_COL, size=11))),
        legend=dict(orientation="h", yanchor="bottom", y=-0.12, xanchor="center", x=0.5,
                    font=dict(color=TEXT_COL, size=11)),
        margin=dict(l=50, r=50, t=30, b=50), height=420, dragmode=False,
        font=dict(family="Inter", color=TEXT_COL))
    st.plotly_chart(fig, use_container_width=True,
                    config={'displayModeBar': False, 'scrollZoom': False, 'doubleClick': False})

    st.markdown(f"<div style='font-size:0.72rem;color:#5a5855;text-align:center;margin:-0.3rem 0 0.6rem;'>※ '{target_job} 이상형'은 현직자 경험 기반 <b>참고용 추정치</b>이며, 향후 실제 합격자 데이터로 보정됩니다.</div>", unsafe_allow_html=True)

    # 일관성 경고
    if cons < 60:
        st.markdown(f"<div class='status-bad'>⚠ 답변 일관성이 낮습니다 ({cons}점). 실제 HMAT의 신뢰도 검증에서 불리할 수 있어요.</div>", unsafe_allow_html=True)
    elif cons < 80:
        st.markdown(f"<div class='status-warn'>답변 일관성 보통 ({cons}점). 비슷한 질문에 일관되게 답하는 연습이 필요해요.</div>", unsafe_allow_html=True)
    else:
        st.markdown(f"<div class='status-ok'>✦ 답변 일관성 우수 ({cons}점). 신뢰도 측면에서 안정적입니다.</div>", unsafe_allow_html=True)

    if flagged:
        pair_texts = []
        qmap = {q[0]: q[1] for q in QUESTIONS}
        for p, n in flagged:
            pair_texts.append(f"「{qmap[p]}」 ↔ 「{qmap[n]}」")
        lines = "".join(f"<div style='margin:0.3rem 0;font-size:0.8rem;'>• {t}</div>" for t in pair_texts)
        st.markdown(f"<div class='status-warn'><b>모순이 큰 문항 쌍</b>{lines}</div>", unsafe_allow_html=True)

    # 과잉포장 경고
    if lie >= 50:
        st.markdown(f"<div class='status-bad'>⚠ 과잉포장 지수가 높습니다 ({lie}%). '완벽한 사람'처럼 답하면 실제 검사의 거짓말 척도에 걸릴 수 있어요.</div>", unsafe_allow_html=True)

    # 직무 적합도 해설 + 축별 갭
    st.markdown("<hr class='divider'>", unsafe_allow_html=True)
    st.markdown("<div style='font-size:0.78rem;font-weight:600;letter-spacing:0.1em;text-transform:uppercase;color:#5a5855;margin-bottom:0.8rem;'>축별 상세 비교</div>", unsafe_allow_html=True)

    for a in AXES:
        mine, ideal = my_axes[a], profile[a]
        gap = mine - ideal
        if abs(gap) <= 10:
            tag, tcolor = "적정", "#34a878"
        elif gap < 0:
            tag, tcolor = f"{abs(gap)} 부족", "#cd8c5b"
        else:
            tag, tcolor = f"{gap} 초과", "#9d8cf5"
        st.markdown(f"""
        <div class="pct-card">
          <div style="display:flex;justify-content:space-between;align-items:center;">
            <div class="pct-label" style="margin-bottom:0;">{a}</div>
            <div style="font-size:0.74rem;font-weight:600;color:{tcolor};">{tag}</div>
          </div>
          <div style="display:flex;gap:0.5rem;align-items:center;margin-top:0.5rem;font-size:0.72rem;color:#7a7772;">
            <span>나 <b style="color:#e8e6e3;">{mine}</b></span>
            <span>·</span>
            <span>이상형 <b style="color:#cd8c5b;">{ideal}</b></span>
          </div>
          <div class="pct-bar-bg"><div class="pct-bar-fill" style="width:{mine}%;background:{ACCENT};"></div></div>
        </div>
        """, unsafe_allow_html=True)

    # ── 회차별 추이 & 비교 피드백 (과거 기록 + 이번 세션 병합) ────────────────
    _name = st.session_state.get("user_name_v", "")
    _phone = st.session_state.get("user_phone_v", "")
    past = load_past_results(_name, _phone, target_job)
    session_hist = [h for h in st.session_state.history if h["job"] == target_job]

    # 병합 + 중복 제거 (time/fit/cons/lie 동일하면 같은 기록)
    merged, seen = [], set()
    for h in past + session_hist:
        key = (h.get("time", ""), round(h["fit"]), round(h["cons"]), round(h["lie"]))
        if key in seen:
            continue
        seen.add(key)
        merged.append(h)
    # 시간순 정렬 후 회차 번호 재부여
    merged.sort(key=lambda h: h.get("time", ""))
    for i, h in enumerate(merged, 1):
        h["attempt"] = i
    hist = merged

    if len(hist) >= 2:
        st.markdown("<hr class='divider'>", unsafe_allow_html=True)
        st.markdown(f"<div style='font-size:0.78rem;font-weight:600;letter-spacing:0.1em;text-transform:uppercase;color:#5a5855;margin-bottom:0.8rem;'>회차별 성장 추이 ({target_job}, 총 {len(hist)}회)</div>", unsafe_allow_html=True)

        xs = [f"{h['attempt']}차" for h in hist]
        fig_t = go.Figure()
        fig_t.add_trace(go.Scatter(x=xs, y=[h["fit"] for h in hist], name="직무 적합도",
                                   mode="lines+markers", line=dict(color=ACCENT, width=2.5),
                                   marker=dict(size=8)))
        fig_t.add_trace(go.Scatter(x=xs, y=[h["cons"] for h in hist], name="일관성",
                                   mode="lines+markers", line=dict(color="#34a878", width=2.5),
                                   marker=dict(size=8)))
        fig_t.add_trace(go.Scatter(x=xs, y=[h["lie"] for h in hist], name="과잉포장",
                                   mode="lines+markers", line=dict(color="#e07070", width=2, dash="dot"),
                                   marker=dict(size=7)))
        fig_t.update_layout(
            paper_bgcolor=CARD_BG, plot_bgcolor=CARD_BG,
            font=dict(color=TEXT_COL, family="Inter", size=11),
            margin=dict(l=10, r=10, t=20, b=10), height=280,
            yaxis=dict(range=[0, 100], showgrid=True, gridcolor=GRID_COL, fixedrange=True),
            xaxis=dict(showgrid=False, fixedrange=True),
            legend=dict(orientation="h", yanchor="bottom", y=-0.25, xanchor="center", x=0.5,
                        font=dict(size=10)),
            dragmode=False)
        st.plotly_chart(fig_t, use_container_width=True,
                        config={'displayModeBar': False, 'scrollZoom': False, 'doubleClick': False})

        # 직전 회차 대비 구체 피드백
        prev, curr = hist[-2], hist[-1]
        fb = []

        d_fit = curr["fit"] - prev["fit"]
        if d_fit > 0:
            fb.append(("up", f"직무 적합도가 <b>{prev['fit']}% → {curr['fit']}%</b> ({d_fit:+d}%p) 올랐어요. 직무 성향에 더 가까워졌습니다."))
        elif d_fit < 0:
            fb.append(("down", f"직무 적합도가 <b>{prev['fit']}% → {curr['fit']}%</b> ({d_fit:+d}%p) 낮아졌어요. 직전 답변이 직무 성향에 더 맞았습니다."))
        else:
            fb.append(("flat", f"직무 적합도는 <b>{curr['fit']}%</b>로 동일합니다."))

        d_cons = curr["cons"] - prev["cons"]
        if d_cons > 0:
            fb.append(("up", f"답변 일관성이 <b>{prev['cons']} → {curr['cons']}점</b> ({d_cons:+d}) 좋아졌어요. 비슷한 질문에 더 일관되게 답했습니다."))
        elif d_cons < 0:
            fb.append(("down", f"답변 일관성이 <b>{prev['cons']} → {curr['cons']}점</b> ({d_cons:+d}) 떨어졌어요. 정·반대 문항 답이 엇갈렸습니다."))

        d_lie = curr["lie"] - prev["lie"]
        if d_lie < 0:
            fb.append(("up", f"과잉포장 지수가 <b>{prev['lie']}% → {curr['lie']}%</b> ({d_lie:+d}%p) 줄었어요. 더 자연스러운 답변입니다."))
        elif d_lie > 0:
            fb.append(("down", f"과잉포장 지수가 <b>{prev['lie']}% → {curr['lie']}%</b> ({d_lie:+d}%p) 늘었어요. '완벽한 사람'처럼 답한 문항이 많아졌습니다."))

        # 축별 변화 — 이상형에 가까워진/멀어진 축
        profile = JOB_PROFILES[target_job]
        improved, worsened = [], []
        for a in AXES:
            prev_gap = abs(prev["axes"][a] - profile[a])
            curr_gap = abs(curr["axes"][a] - profile[a])
            if curr_gap < prev_gap - 5:
                improved.append(f"{a}(이상형과 {prev_gap}→{curr_gap})")
            elif curr_gap > prev_gap + 5:
                worsened.append(f"{a}(이상형과 {prev_gap}→{curr_gap})")
        if improved:
            fb.append(("up", "이상형에 가까워진 축: <b>" + " · ".join(improved) + "</b>"))
        if worsened:
            fb.append(("down", "이상형에서 멀어진 축: <b>" + " · ".join(worsened) + "</b>"))

        icon_map = {"up": "🟢", "down": "🔴", "flat": "⚪"}
        fb_html = "".join(
            f"<div style='display:flex;gap:0.5rem;margin:0.45rem 0;font-size:0.84rem;color:#e8e6e3;line-height:1.5;'>"
            f"<div style='flex-shrink:0;'>{icon_map[t]}</div><div>{msg}</div></div>"
            for t, msg in fb
        )
        st.markdown(f"""
        <div style="background:#1a1a1b;border:1px solid #2a2a2c;border-radius:14px;padding:1.1rem 1.3rem;margin-top:0.5rem;">
          <div style="font-size:0.78rem;font-weight:600;letter-spacing:0.08em;text-transform:uppercase;color:{ACCENT};margin-bottom:0.7rem;">
            {prev['attempt']}차 → {curr['attempt']}차 변화 피드백
          </div>
          {fb_html}
        </div>
        """, unsafe_allow_html=True)

        # 최고 기록 대비
        best_fit = max(h["fit"] for h in hist)
        best_cons = max(h["cons"] for h in hist)
        if curr["fit"] == best_fit and len(hist) >= 3:
            st.markdown(f"<div class='status-ok'>🏆 이번이 역대 최고 직무 적합도({best_fit}%)예요!</div>", unsafe_allow_html=True)

    elif len(hist) == 1:
        st.markdown("<div style='font-size:0.78rem;color:#5a5855;margin-top:1rem;text-align:center;'>💡 한 번 더 응시하면 직전 회차와 비교한 성장 피드백을 볼 수 있어요.</div>", unsafe_allow_html=True)

    # 데이터 저장 (이번 회차가 방금 제출된 경우에만 1회)
    if submitted:
        save_response({
            "이름": st.session_state.get("user_name_v", ""),
            "전화": st.session_state.get("user_phone_v", ""),
            "직무": target_job,
            "분석성": my_axes["분석성"], "실행력": my_axes["실행력"], "협업성": my_axes["협업성"],
            "도전성": my_axes["도전성"], "신중성": my_axes["신중성"], "주도성": my_axes["주도성"],
            "일관성": cons, "과잉포장": lie, "적합도": fit,
            "시각": st.session_state.history[-1]["time"] if st.session_state.history else datetime.now().strftime("%m-%d %H:%M"),
        })

    st.markdown("<hr class='divider'>", unsafe_allow_html=True)
    st.markdown("""
    <div style="text-align:center;color:#5a5855;font-size:0.74rem;padding:0.5rem 0;">
      본 테스트는 실제 HMAT를 간소화한 <b>참고용 모의 검사</b>이며, 합격을 보장하지 않습니다.<br>
      여러 번 반복하며 일관성과 직무 성향을 점검해 보세요.
    </div>
    <div style="text-align:center;color:#3a3836;font-size:0.7rem;padding:0.6rem 0 1.5rem;">
      ⓒ 2026 공대생현직자 잡앤유 All rights reserved.
    </div>
    """, unsafe_allow_html=True)
