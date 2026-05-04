import uuid

import streamlit as st

import api_client as api

st.set_page_config(
    page_title="ContentGuard AI",
    page_icon="🛡️",
    layout="wide",
)

LEVEL_BADGE = {
    "LOW": "🟢 LOW",
    "MEDIUM": "🟡 MEDIUM",
    "HIGH": "🔴 HIGH",
    "CRITICAL": "🚨 CRITICAL",
}

STATUS_BADGE = {
    "PENDING": "⏳ PENDING",
    "APPROVED": "✅ APPROVED",
    "REMOVED": "🗑️ REMOVED",
    "HELD": "⏸️ HELD",
    "MONITORED": "👁️ MONITORED",
}

ACTION_OPTIONS = {
    "approve": "✅ 승인",
    "remove": "🗑️ 삭제",
    "hold": "⏸️ 보류",
    "monitor": "👁️ 모니터링",
}


def show_dashboard():
    st.title("🛡️ ContentGuard AI 대시보드")

    try:
        all_contents = api.get_contents()
    except Exception as e:
        st.error(f"API 연결 실패: {e}")
        return

    total = len(all_contents)
    pending = sum(1 for c in all_contents if c["review_status"] == "PENDING")
    approved = sum(1 for c in all_contents if c["review_status"] == "APPROVED")
    removed = sum(1 for c in all_contents if c["review_status"] == "REMOVED")
    held = sum(1 for c in all_contents if c["review_status"] == "HELD")

    col1, col2, col3, col4, col5 = st.columns(5)
    col1.metric("전체 콘텐츠", total)
    col2.metric("⏳ 심사 대기", pending, delta=f"{pending}건 검토 필요" if pending else None, delta_color="inverse")
    col3.metric("✅ 승인", approved)
    col4.metric("🗑️ 삭제", removed)
    col5.metric("⏸️ 보류", held)

    st.divider()

    col_a, col_b = st.columns(2)

    with col_a:
        st.subheader("위험 등급 분포")
        level_counts = {"LOW": 0, "MEDIUM": 0, "HIGH": 0, "CRITICAL": 0}
        for c in all_contents:
            level_counts[c["risk_level"]] = level_counts.get(c["risk_level"], 0) + 1
        st.bar_chart(level_counts)

    with col_b:
        st.subheader("최근 분석 내역")
        for item in all_contents[:5]:
            with st.container(border=True):
                c1, c2, c3 = st.columns([3, 1, 1])
                c1.write(item["text"][:50] + ("..." if len(item["text"]) > 50 else ""))
                c2.write(LEVEL_BADGE.get(item["risk_level"], item["risk_level"]))
                c3.write(STATUS_BADGE.get(item["review_status"], item["review_status"]))


def show_review_queue():
    st.title("⏳ 심사 큐")
    st.caption("AI가 분석한 콘텐츠를 검토하고 최종 판단을 내리세요.")

    try:
        pending = api.get_contents(status="PENDING")
    except Exception as e:
        st.error(f"API 연결 실패: {e}")
        return

    if not pending:
        st.success("심사 대기 중인 콘텐츠가 없습니다.")
        return

    st.info(f"총 {len(pending)}건 심사 대기 중")

    for item in pending:
        with st.expander(
            f"{LEVEL_BADGE.get(item['risk_level'])}  |  {item['content_id']}  |  {item['text'][:40]}...",
            expanded=True,
        ):
            col1, col2 = st.columns([2, 1])

            with col1:
                st.markdown(f"**콘텐츠**")
                st.write(item["text"])
                st.markdown(f"**AI 설명**")
                st.info(item.get("explanation") or "설명 없음")

            with col2:
                st.metric("위험 점수", f"{item['risk_score']:.2f}")
                st.write(f"위험 등급: {LEVEL_BADGE.get(item['risk_level'])}")
                st.write(f"권장 조치: `{item['recommended_action']}`")
                st.write(f"등록 시각: {item['created_at'][:19]}")

            st.markdown("**운영자 판단**")
            comment = st.text_input("메모 (선택)", key=f"comment_{item['content_id']}")

            btn_cols = st.columns(4)
            actions = [("approve", "✅ 승인"), ("monitor", "👁️ 모니터링"), ("hold", "⏸️ 보류"), ("remove", "🗑️ 삭제")]
            for i, (action, label) in enumerate(actions):
                if btn_cols[i].button(label, key=f"{action}_{item['content_id']}"):
                    try:
                        api.submit_review(item["content_id"], action, comment)
                        st.success(f"{label} 처리 완료")
                        st.rerun()
                    except Exception as e:
                        st.error(f"처리 실패: {e}")


def show_analysis():
    st.title("🔍 콘텐츠 분석")
    st.caption("텍스트를 입력하면 AI가 위험도를 분석합니다.")

    with st.form("analyze_form"):
        content_id = st.text_input("Content ID", value=f"C{str(uuid.uuid4())[:8].upper()}")
        text = st.text_area("분석할 텍스트", height=120, placeholder="분석할 내용을 입력하세요...")
        submitted = st.form_submit_button("분석 시작", type="primary")

    if submitted:
        if not text.strip():
            st.warning("텍스트를 입력하세요.")
            return
        with st.spinner("AI 분석 중..."):
            try:
                result = api.analyze_content(content_id, text)

                col1, col2, col3 = st.columns(3)
                col1.metric("위험 점수", f"{result['risk_score']:.2f}")
                col2.metric("위험 등급", LEVEL_BADGE.get(result["risk_level"]))
                col3.metric("권장 조치", result["recommended_action"])

                st.markdown("**AI 설명**")
                st.info(result.get("explanation") or "설명 없음")

            except requests.exceptions.HTTPError as e:
                if e.response.status_code == 400:
                    st.error(f"이미 존재하는 content_id입니다: {content_id}")
                else:
                    st.error(f"오류: {e}")
            except Exception as e:
                st.error(f"분석 실패: {e}")


def show_history():
    st.title("📋 전체 이력")

    status_filter = st.selectbox(
        "상태 필터",
        ["전체", "PENDING", "APPROVED", "REMOVED", "HELD", "MONITORED"],
    )

    try:
        status = None if status_filter == "전체" else status_filter
        contents = api.get_contents(status=status)
    except Exception as e:
        st.error(f"API 연결 실패: {e}")
        return

    st.caption(f"총 {len(contents)}건")

    for item in contents:
        with st.container(border=True):
            col1, col2, col3, col4 = st.columns([3, 1, 1, 1])
            col1.write(item["text"][:60] + ("..." if len(item["text"]) > 60 else ""))
            col2.write(LEVEL_BADGE.get(item["risk_level"], item["risk_level"]))
            col3.write(f"`{item['risk_score']:.2f}`")
            col4.write(STATUS_BADGE.get(item["review_status"], item["review_status"]))

            if item.get("explanation"):
                with st.expander("AI 설명 보기"):
                    st.write(item["explanation"])
                    if item.get("reviewer_comment"):
                        st.write(f"**운영자 메모:** {item['reviewer_comment']}")


# 사이드바 네비게이션
import requests

st.sidebar.title("🛡️ ContentGuard AI")
st.sidebar.divider()

page = st.sidebar.radio(
    "메뉴",
    ["대시보드", "심사 큐", "콘텐츠 분석", "전체 이력"],
    index=0,
)

try:
    requests.get("http://localhost:8000/health", timeout=2)
    st.sidebar.success("API 연결됨")
except Exception:
    st.sidebar.error("API 연결 안됨")

if page == "대시보드":
    show_dashboard()
elif page == "심사 큐":
    show_review_queue()
elif page == "콘텐츠 분석":
    show_analysis()
elif page == "전체 이력":
    show_history()
