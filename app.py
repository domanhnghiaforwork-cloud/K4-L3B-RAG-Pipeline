"""Streamlit chat interface for the RAG pipeline."""

from __future__ import annotations

import streamlit as st
from dotenv import load_dotenv

from src.task10_generation import generate_with_citation


load_dotenv()

st.set_page_config(page_title="RAG Chatbot", page_icon="🤖", layout="wide")


def render_sources(sources: list[dict], retrieval_source: str | None = None) -> None:
    """Render source metadata and evidence without cluttering the main answer."""
    if not sources:
        st.caption("Không có nguồn phù hợp trong corpus hiện tại.")
        return
    label = f"Nguồn đã dùng ({retrieval_source})" if retrieval_source else "Nguồn đã dùng"
    with st.expander(label, expanded=False):
        for index, source in enumerate(sources, start=1):
            metadata = source["metadata"]
            st.markdown(f"**[S{index}] {metadata['title']}**")
            url = metadata.get("url")
            if url:
                st.markdown(f"Nguồn: [{metadata['source']}]({url})")
            else:
                st.markdown(f"Nguồn: `{metadata['source']}`")
            st.caption(
                f"Phương thức: {source['retrieval_method']} · "
                f"Điểm: {float(source['score']):.4f} · "
                f"Chunk: {metadata.get('chunk_index', 'N/A')}"
            )
            excerpt = source["content"].strip()
            if len(excerpt) > 600:
                excerpt = excerpt[:600].rstrip() + "…"
            st.markdown(excerpt)
            if index < len(sources):
                st.divider()


if "messages" not in st.session_state:
    st.session_state.messages = []

with st.sidebar:
    st.title("RAG Chatbot")
    st.caption("Hỏi đáp có dẫn nguồn từ tài liệu của nhóm")
    top_k = st.slider("Số chunks", min_value=1, max_value=10, value=5)
    if st.button("Xóa lịch sử chat", use_container_width=True):
        st.session_state.messages = []
        st.rerun()

st.title("RAG Chatbot")
st.caption("Câu trả lời chỉ dựa trên corpus đã được index và luôn kèm nguồn kiểm chứng.")

for message in st.session_state.messages:
    with st.chat_message(message["role"]):
        st.markdown(message["content"])
        if message["role"] == "assistant":
            render_sources(message.get("sources", []), message.get("retrieval_source"))

query = st.chat_input("Nhập câu hỏi...")

if query:
    user_message = {"role": "user", "content": query}
    st.session_state.messages.append(user_message)
    with st.chat_message("user"):
        st.markdown(query)

    with st.chat_message("assistant"):
        with st.spinner("Đang tìm tài liệu và tạo câu trả lời..."):
            try:
                result = generate_with_citation(query, top_k=top_k)
            except Exception as error:
                result = {
                    "answer": "Không thể xử lý câu hỏi lúc này. Hãy kiểm tra index và cấu hình dịch vụ.",
                    "sources": [],
                    "retrieval_source": "none",
                }
                st.error(f"Lỗi pipeline: {error}")
        st.markdown(result["answer"])
        render_sources(result["sources"], result["retrieval_source"])

    st.session_state.messages.append(
        {
            "role": "assistant",
            "content": result["answer"],
            "sources": result["sources"],
            "retrieval_source": result["retrieval_source"],
        }
    )
