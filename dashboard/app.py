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

    # 컨트롤 바
    ctl1, ctl2 = st.columns(2)
    with ctl1:
        sort_label = st.selectbox("정렬", ["위험도 높은 순", "최신 순"])
    with ctl2:
        level_label = st.selectbox("등급 필터", ["전체", "🚨 CRITICAL", "🔴 HIGH", "🟡 MEDIUM", "🟢 LOW"])

    sort_by    = "risk_score" if sort_label == "위험도 높은 순" else None
    risk_level = level_label.split()[-1] if level_label != "전체" else None

    try:
        pending = api.get_contents(status="PENDING", sort_by=sort_by, risk_level=risk_level)
    except Exception as e:
        st.error(f"API 연결 실패: {e}")
        return

    if not pending:
        st.success("심사 대기 중인 콘텐츠가 없습니다.")
        return

    # 긴급도 요약
    critical = sum(1 for c in pending if c["risk_level"] == "CRITICAL")
    high     = sum(1 for c in pending if c["risk_level"] == "HIGH")
    medium   = sum(1 for c in pending if c["risk_level"] == "MEDIUM")
    low      = sum(1 for c in pending if c["risk_level"] == "LOW")

    s1, s2, s3, s4, s5 = st.columns(5)
    s1.metric("전체 대기", len(pending))
    s2.metric("🚨 CRITICAL", critical, delta="즉시 처리" if critical else None, delta_color="inverse")
    s3.metric("🔴 HIGH",     high)
    s4.metric("🟡 MEDIUM",   medium)
    s5.metric("🟢 LOW",      low)

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

            with st.expander("모델별 예측 상세", expanded=False):
                try:
                    preds = api.get_predictions(item["content_id"])
                    if preds:
                        for p in preds:
                            badge = "✅ 선택됨" if p["is_selected"] else "👁️ 참고"
                            p_cols = st.columns([3, 1, 1, 1])
                            p_cols[0].write(f"**{p['model_name']}** `{p['model_version']}` — {badge}")
                            p_cols[1].metric("점수", f"{p['risk_score']:.2f}")
                            p_cols[2].metric("신뢰도", f"{p['confidence']:.2f}" if p.get("confidence") is not None else "-")
                            p_cols[3].metric("지연", f"{p['latency_ms']}ms" if p.get("latency_ms") is not None else "-")
                    else:
                        st.caption("저장된 모델 예측 없음 (구버전 데이터)")
                except Exception:
                    st.caption("모델 예측 조회 실패")

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

                st.markdown("**모델별 예측**")
                try:
                    preds = api.get_predictions(content_id)
                    for p in preds:
                        badge = "✅" if p["is_selected"] else "👁️"
                        with st.container(border=True):
                            pc1, pc2, pc3, pc4 = st.columns([3, 1, 1, 1])
                            pc1.write(f"{badge} `{p['model_name']}` ({p['model_type']})")
                            pc2.metric("점수", f"{p['risk_score']:.2f}")
                            pc3.metric("신뢰도", f"{p['confidence']:.2f}" if p.get("confidence") is not None else "-")
                            pc4.metric("지연", f"{p['latency_ms']}ms" if p.get("latency_ms") is not None else "-")
                except Exception:
                    st.caption("모델 예측 조회 실패")

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
