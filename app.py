# -*- coding: utf-8 -*-
"""
서논술형 답안 자동 채점 웹앱 (Streamlit)

실행 방법
--------
    pip install -r requirements.txt
    streamlit run app.py

구성
----
- rubric.py : 세트1~3, 문항1~3의 채점 기준(키워드 그룹, 오개념, 방향, 모범답안)
- grader.py : 채점 로직 (키워드 매칭 / 방법 명칭 검증 / 오개념 방지 / 결론 방향 확인)
- app.py    : 이 파일. Streamlit UI
"""

import streamlit as st
from rubric import ALL_SETS
from grader import grade_q1, grade_q2, grade_q3

st.set_page_config(page_title="서논술형 자동 채점기", page_icon="📝", layout="wide")

st.title("📝 서논술형 답안 자동 채점기")
st.caption(
    "규칙 기반(키워드 매칭) 채점기입니다. 완전한 의미 이해가 아니라 '1차 스크리닝' 도구이므로, "
    "최종 판단은 반드시 사람이 다시 확인하는 것을 권장합니다."
)

with st.expander("ℹ️ 채점 판정 기준 안내 (반영된 5가지 원칙)"):
    st.markdown(
        """
1. **의미 기반 인정** — 지정된 용어가 없어도, 조건에서 허용한 표현의 '동의어 묶음' 중 하나만 있으면 인정합니다.
2. **방법 특성 검증** — 문항2에서 학생이 표기한 설명 방법(예: '비교와 대조')의 특징적 표현이 실제 문장에 있는지 확인합니다.
3. **선택지별 모범 답안** — 하위 항목(㉠㉡㉢, (1)(2), Ⓐ/Ⓑ)마다 모범 답안을 모두 제공합니다.
4. **오개념 방지** — 반대 개념/다른 상황의 키워드가 섞이면 오개념으로 플래그합니다.
5. **결론 방향 확인** — 조건이 요구하는 결론(예: "예술로 보기 어렵다")이 명확히 드러나는지 별도로 검사합니다.
        """
    )

# ---------------------------------------------------------------------------
# 사이드바: 세트 선택
# ---------------------------------------------------------------------------
set_key = st.sidebar.radio("세트를 선택하세요", list(ALL_SETS.keys()))
set_cfg = ALL_SETS[set_key]
st.sidebar.markdown("---")
st.sidebar.write(set_cfg["title"])

tab1, tab2, tab3 = st.tabs(["문항1 (표 완성형)", "문항2 (문장 이어쓰기)", "문항3 (영상 기획안)"])


def render_feedback(key_label, r):
    """단일 항목 채점 결과를 UI에 렌더링."""
    if r["passed"]:
        st.success(f"✅ {key_label} — 통과")
    else:
        st.error(f"❌ {key_label} — 미통과")

    cols = st.columns([1, 1])
    with cols[0]:
        if r.get("label") is not None:
            st.write(f"**표기한 설명 방법**: {r['label']} ({r.get('label_status', '-')})")
        if r["missing_required"]:
            miss_str = " / ".join([" · ".join(g) for g in r["missing_required"]])
            st.write(f"**누락된 필수 내용**: {miss_str}")
        if r["missing_direction"]:
            miss_str = " / ".join([" · ".join(g) for g in r["missing_direction"]])
            st.write(f"**누락된 결론 방향**: {miss_str}")
    with cols[1]:
        if r["opposite_hits"]:
            st.write(f"**오개념 의심 키워드**: {['/'.join(g) for g in r['opposite_hits']]}")
        if r["scene1_hits"]:
            st.write(f"**장면1과 유사(대비 실패 의심)**: {['/'.join(g) for g in r['scene1_hits']]}")

    if r["notes"]:
        for n in r["notes"]:
            st.caption(f"· {n}")

    with st.expander(f"📌 모범 답안 보기 — {key_label}"):
        st.write(r["model_answer"])


# ---------------------------------------------------------------------------
# 문항1
# ---------------------------------------------------------------------------
with tab1:
    q1cfg = set_cfg["q1"]
    st.subheader(q1cfg["title"])

    answers = {}
    for key, cfg in q1cfg["items"].items():
        answers[key] = st.text_input(cfg["label"], key=f"{set_key}_q1_{key}")

    if st.button("채점하기", key=f"{set_key}_q1_btn"):
        results, score, total = grade_q1(set_cfg, answers)
        st.markdown(f"### 결과: {score} / {total}")
        for key, r in results.items():
            render_feedback(r["label_text"], r)
            st.divider()

# ---------------------------------------------------------------------------
# 문항2
# ---------------------------------------------------------------------------
with tab2:
    q2cfg = set_cfg["q2"]
    st.subheader(q2cfg["title"])
    st.info(f"**주어진 문장**: {q2cfg['prompt']}")
    st.caption(f"조건: {q2cfg['condition_note']}")

    part1_cfg = q2cfg["parts"]["part1"]
    part2_cfg = q2cfg["parts"]["part2"]

    p1 = st.text_area(
        part1_cfg["label"] + "  (문장 끝에 '(방법명)' 표기)",
        key=f"{set_key}_q2_p1",
        height=80,
    )
    p2 = st.text_area(
        part2_cfg["label"] + "  (문장 끝에 '(방법명)' 표기)",
        key=f"{set_key}_q2_p2",
        height=80,
    )

    if st.button("채점하기", key=f"{set_key}_q2_btn"):
        results, score, max_score, cross_notes, distinct_ok = grade_q2(set_cfg, p1, p2)
        st.markdown(f"### 결과: {score} / {max_score}")
        if cross_notes:
            for n in cross_notes:
                st.warning(n)
        render_feedback(results["part1"]["label_text"], results["part1"])
        st.divider()
        render_feedback(results["part2"]["label_text"], results["part2"])

# ---------------------------------------------------------------------------
# 문항3
# ---------------------------------------------------------------------------
with tab3:
    q3cfg = set_cfg["q3"]
    st.subheader(q3cfg["title"])
    st.caption(f"조건: {q3cfg['condition_note']}")

    parts_cfg = q3cfg["parts"]
    visual = st.text_area(parts_cfg["visual"]["label"], key=f"{set_key}_q3_visual", height=80)
    visual_effect = st.text_area(
        parts_cfg["visual_effect"]["label"], key=f"{set_key}_q3_visual_effect", height=80
    )
    audio = st.text_area(parts_cfg["audio"]["label"], key=f"{set_key}_q3_audio", height=80)
    audio_effect = st.text_area(
        parts_cfg["audio_effect"]["label"], key=f"{set_key}_q3_audio_effect", height=80
    )

    if st.button("채점하기", key=f"{set_key}_q3_btn"):
        results, score, total = grade_q3(set_cfg, visual, visual_effect, audio, audio_effect)
        st.markdown(f"### 결과: {score} / {total}")
        for key in ["visual", "visual_effect", "audio", "audio_effect"]:
            render_feedback(results[key]["label_text"], results[key])
            st.divider()

# ---------------------------------------------------------------------------
# 하단: 안내 문구 + 처음부터 다시 풀기 버튼 (한 줄 배치)
# ---------------------------------------------------------------------------
def _reset_all_answers():
    """세트1~3, 문항1~3에 입력된 모든 답안(session_state)을 초기화."""
    target_infixes = ("_q1_", "_q2_", "_q3_")
    keys_to_clear = [
        k for k in st.session_state.keys() if any(infix in k for infix in target_infixes)
    ]
    for k in keys_to_clear:
        del st.session_state[k]


st.markdown("---")
notice_col, button_col = st.columns([6, 1])
with notice_col:
    st.caption(
        "모든 문제를 제출하면 복습할 내용 탭에서 틀린 개념을 확인할 수 있어요. "
        "답안을 초기화하고 처음부터 다시 풀고 싶다면 다음의 버튼을 누르세요."
    )
with button_col:
    if st.button("처음부터 다시 풀기", key="reset_all_button", use_container_width=True):
        _reset_all_answers()
        st.rerun()

# key="reset_all_button" 버튼만 골라 파란색 · 작은 글씨의 링크 형태로 스타일링
st.markdown(
    """
    <style>
    .st-key-reset_all_button button {
        background: transparent !important;
        border: none !important;
        box-shadow: none !important;
        color: #1a73e8 !important;
        font-size: 0.8rem !important;
        padding: 0.1rem 0 !important;
    }
    .st-key-reset_all_button button:hover {
        color: #0b4fb3 !important;
        text-decoration: underline !important;
    }
    </style>
    """,
    unsafe_allow_html=True,
)

