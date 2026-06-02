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

# 각 문항: (id, 텍스트, 축, 방향)  방향 +1=정방향, -1=역방향(역채점)
QUESTIONS = [
    # ── 분석성 ──
    ("A1", "나는 결정을 내리기 전에 데이터와 근거를 충분히 따져본다.", "분석성", +1),
    ("A2", "나는 근거보다 직관으로 빠르게 결정하는 편이다.", "분석성", -1),
    ("A3", "복잡한 문제는 논리적으로 잘게 나누어 접근한다.", "분석성", +1),
    # ── 실행력 ──
    ("E1", "목표가 정해지면 빠르게 추진력 있게 밀어붙인다.", "실행력", +1),
    ("E2", "충분히 준비될 때까지 행동을 미루는 편이다.", "실행력", -1),
    ("E3", "일단 시작하고 진행하면서 보완해 나간다.", "실행력", +1),
    # ── 협업성 ──
    ("C1", "혼자보다 팀으로 일할 때 더 좋은 결과가 나온다고 믿는다.", "협업성", +1),
    ("C2", "나는 혼자 일하는 것이 더 편하고 효율적이다.", "협업성", -1),
    ("C3", "동료의 어려움을 잘 살피고 먼저 돕는 편이다.", "협업성", +1),
    # ── 도전성 ──
    ("D1", "검증되지 않은 새로운 방식에 도전하는 것을 즐긴다.", "도전성", +1),
    ("D2", "익숙하고 안정적인 방식을 선호한다.", "도전성", -1),
    ("D3", "현재에 안주하지 않고 끊임없이 개선점을 찾는다.", "도전성", +1),
    # ── 신중성 ──
    ("N1", "나는 계획을 세우고 꼼꼼하게 점검하며 일한다.", "신중성", +1),
    ("N2", "세부사항보다 큰 그림 위주로 보며 디테일 점검은 소홀한 편이다.", "신중성", -1),
    ("N3", "마감 전 여러 번 검토해서 실수를 줄인다.", "신중성", +1),
    # ── 주도성 ──
    ("L1", "모임이나 프로젝트에서 자연스럽게 리드하는 역할을 맡는다.", "주도성", +1),
    ("L2", "나서기보다 뒤에서 따르는 것이 편하다.", "주도성", -1),
    ("L3", "내 의견을 적극적으로 제시하고 사람들을 설득한다.", "주도성", +1),
]

# 거짓말 척도(사회적 바람직성): "매우 그렇다"로 답할수록 과잉포장 의심
LIE_QUESTIONS = [
    ("LIE1", "나는 지금까지 단 한 번도 거짓말을 한 적이 없다."),
    ("LIE2", "나는 어떤 상황에서도 화를 내본 적이 전혀 없다."),
    ("LIE3", "나는 약속을 100% 단 한 번도 어긴 적이 없다."),
    ("LIE4", "나는 누군가를 미워하거나 시기해 본 적이 전혀 없다."),
]

# 일관성 쌍 (정방향 id, 역방향 id) — 같은 축을 반대로 물은 쌍
CONSISTENCY_PAIRS = [
    ("A1", "A2"), ("E1", "E2"), ("C1", "C2"),
    ("D1", "D2"), ("N1", "N2"), ("L1", "L2"),
]

# 직무별 이상 성향 프로파일 (0~100)
JOB_PROFILES = {
    "연구개발":            {"분석성": 92, "실행력": 60, "협업성": 65, "도전성": 72, "신중성": 88, "주도성": 55},
    "생산/제조":          {"분석성": 68, "실행력": 82, "협업성": 82, "도전성": 52, "신중성": 88, "주도성": 62},
    "사업/기획/경영지원":  {"분석성": 78, "실행력": 80, "협업성": 76, "도전성": 76, "신중성": 62, "주도성": 86},
    "품질":               {"분석성": 85, "실행력": 65, "협업성": 72, "도전성": 48, "신중성": 95, "주도성": 55},
}

LIKERT = ["① 전혀 아니다", "② 아니다", "③ 보통", "④ 그렇다", "⑤ 매우 그렇다"]
LIKERT_VAL = {opt: i + 1 for i, opt in enumerate(LIKERT)}


# ════════════════════════════════════════════════════════════════════════════════
# 2) 점수 계산 로직
# ════════════════════════════════════════════════════════════════════════════════
def score_axes(responses):
    """각 축 점수(0~100) 계산. 역방향 문항은 역채점(6-x)."""
    axis_scores = {a: [] for a in AXES}
    for qid, text, axis, direction in QUESTIONS:
        v = responses.get(qid)
        if v is None:
            continue
        adj = v if direction == +1 else (6 - v)   # 1~5 → 역채점 시 5~1
        axis_scores[axis].append(adj)
    result = {}
    for a in AXES:
        vals = axis_scores[a]
        result[a] = round((sum(vals) / len(vals) - 1) / 4 * 100) if vals else 0  # 1~5 → 0~100
    return result


def consistency_score(responses):
    """일관성 점수(0~100). 정/역 쌍의 모순 정도로 산출."""
    diffs = []
    for pos_id, neg_id in CONSISTENCY_PAIRS:
        p = responses.get(pos_id)
        n = responses.get(neg_id)
        if p is None or n is None:
            continue
        # 일관적이면 p 와 (6-n) 이 비슷해야 함
        diffs.append(abs(p - (6 - n)))
    if not diffs:
        return 100, []
    avg_diff = sum(diffs) / len(diffs)         # 0~4
    score = round(100 - (avg_diff / 4 * 100))
    # 모순이 큰 쌍 찾기
    flagged = []
    for pos_id, neg_id in CONSISTENCY_PAIRS:
        p, n = responses.get(pos_id), responses.get(neg_id)
        if p is None or n is None:
            continue
        if abs(p - (6 - n)) >= 3:
            flagged.append((pos_id, neg_id))
    return score, flagged


def lie_score(lie_responses):
    """사회적 바람직성 점수. 4~5로 답한 비율이 높을수록 과잉포장 위험."""
    if not lie_responses:
        return 0
    high = sum(1 for v in lie_responses.values() if v >= 4)
    return round(high / len(lie_responses) * 100)


def job_fit(my_axes, job):
    """직무 이상 프로파일과의 적합도(0~100). 유클리드 거리 기반."""
    profile = JOB_PROFILES.get(job)
    if not profile:
        return None
    sq = sum((my_axes[a] - profile[a]) ** 2 for a in AXES)
    dist = (sq / len(AXES)) ** 0.5            # 0~100 범위 RMSE
    return max(0, round(100 - dist))


# ════════════════════════════════════════════════════════════════════════════════
# 데이터 저장 (구글 폼) — 추후 entry id 채워넣기
# ════════════════════════════════════════════════════════════════════════════════
FORM_POST_URL = st.secrets.get("HMAT_FORM_URL", "")  # 없으면 저장 스킵
FORM_ENTRIES = {
    # "직무": "entry.xxxxx", "분석성": "entry.xxxxx", ... 추후 매핑
}

def save_response(payload):
    if not FORM_POST_URL or not FORM_ENTRIES:
        return
    data = {}
    for key, entry in FORM_ENTRIES.items():
        if key in payload:
            data[entry] = payload[key]
    try:
        requests.post(FORM_POST_URL, data=data,
                      headers={"Content-Type": "application/x-www-form-urlencoded"},
                      timeout=5)
    except Exception:
        pass


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
    target_job = st.selectbox("지원 직무", list(JOB_PROFILES.keys()))

    st.markdown("<hr class='divider'>", unsafe_allow_html=True)
    st.markdown("<div style='font-size:0.82rem;color:#7a7772;margin-bottom:0.8rem;'>각 문항에 솔직하게 답해주세요. 정답은 없습니다.</div>", unsafe_allow_html=True)

    responses = {}
    for idx, (qid, text, axis, direction) in enumerate(QUESTIONS, 1):
        st.markdown(f"<div class='q-card'><div class='q-num'>Q{idx}</div><div class='q-text'>{text}</div></div>", unsafe_allow_html=True)
        choice = st.radio(f"q_{qid}", LIKERT, index=2, horizontal=True, label_visibility="collapsed", key=f"q_{qid}")
        responses[qid] = LIKERT_VAL[choice]

    st.markdown("<hr class='divider'>", unsafe_allow_html=True)
    st.markdown("<div style='font-size:0.82rem;color:#7a7772;margin-bottom:0.8rem;'>추가 문항입니다.</div>", unsafe_allow_html=True)

    lie_responses = {}
    base = len(QUESTIONS)
    for j, (lid, text) in enumerate(LIE_QUESTIONS, 1):
        st.markdown(f"<div class='q-card'><div class='q-num'>Q{base + j}</div><div class='q-text'>{text}</div></div>", unsafe_allow_html=True)
        choice = st.radio(f"q_{lid}", LIKERT, index=2, horizontal=True, label_visibility="collapsed", key=f"q_{lid}")
        lie_responses[lid] = LIKERT_VAL[choice]

    submitted = st.form_submit_button("결과 분석하기", use_container_width=True)

if submitted:
    st.session_state.hmat_done = True
    st.session_state.attempt_count += 1
    st.session_state.last_responses = responses
    st.session_state.last_lie = lie_responses
    st.session_state.last_job = target_job


# ── 결과 ──────────────────────────────────────────────────────────────────────
if st.session_state.hmat_done:
    responses = st.session_state.last_responses
    lie_responses = st.session_state.last_lie
    target_job = st.session_state.last_job

    my_axes = score_axes(responses)
    cons, flagged = consistency_score(responses)
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

    # 데이터 저장
    save_response({
        "직무": target_job,
        "분석성": my_axes["분석성"], "실행력": my_axes["실행력"], "협업성": my_axes["협업성"],
        "도전성": my_axes["도전성"], "신중성": my_axes["신중성"], "주도성": my_axes["주도성"],
        "일관성": cons, "과잉포장": lie, "적합도": fit,
        "시각": datetime.now().strftime("%Y-%m-%d %H:%M"),
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
