"""Agent chat component for Streamlit."""

import streamlit as st


def render_agent_chat():
    """Render the agent chat interface with conversation history."""

    st.subheader("对话")

    # Display chat history
    if "agent_messages" not in st.session_state:
        st.session_state["agent_messages"] = []

    for msg in st.session_state["agent_messages"]:
        with st.chat_message(msg["role"]):
            st.markdown(msg["content"])

    # Chat input
    if prompt := st.chat_input("输入任务，例如：帮我分析 paper_001 的核心创新"):
        st.session_state["agent_messages"].append({"role": "user", "content": prompt})
        with st.chat_message("user"):
            st.markdown(prompt)

        with st.chat_message("assistant"):
            with st.spinner("Agent 思考中..."):
                try:
                    from app.agents.paper_research_agent import get_agent

                    agent = get_agent()
                    # Build chat history from session (exclude the last message)
                    history = st.session_state["agent_messages"][:-1]

                    result = agent.execute(prompt, chat_history=history)
                    answer = result["answer"]

                    st.markdown(answer)
                    st.session_state["agent_messages"].append(
                        {"role": "assistant", "content": answer}
                    )
                except Exception as e:
                    error_msg = f"Agent 执行出错: {e}"
                    st.error(error_msg)
                    st.session_state["agent_messages"].append(
                        {"role": "assistant", "content": error_msg}
                    )

    # Clear button
    if st.session_state.get("agent_messages") and st.button("清除对话", key="clear_agent_chat"):
        st.session_state["agent_messages"] = []
        st.rerun()