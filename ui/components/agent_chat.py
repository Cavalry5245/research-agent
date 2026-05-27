"""Agent chat component for Streamlit — supports react and supervisor modes."""

import streamlit as st


def render_agent_chat():
    """Render the agent chat interface with mode selection and conversation history."""

    col_mode, col_clear = st.columns([3, 1])
    with col_mode:
        agent_mode = st.radio(
            "Agent 模式",
            ["supervisor", "react"],
            horizontal=True,
            key="agent_mode_select",
            help="supervisor: 多 Agent 路由协作（推荐）；react: 单 Agent ReAct 工具调用",
        )
    with col_clear:
        st.write("")
        if st.session_state.get("agent_messages") and st.button(
            "清除对话", key="clear_agent_chat"
        ):
            st.session_state["agent_messages"] = []
            st.session_state.pop("agent_conversation_id", None)
            st.rerun()

    st.caption(
        f"当前模式: {'Supervisor 多 Agent 协作' if agent_mode == 'supervisor' else 'ReAct 单 Agent'}"
    )

    if "agent_messages" not in st.session_state:
        st.session_state["agent_messages"] = []

    for msg in st.session_state["agent_messages"]:
        with st.chat_message(msg["role"]):
            st.markdown(msg["content"])

    if prompt := st.chat_input("输入任务，例如：帮我分析 paper_001 的核心创新"):
        st.session_state["agent_messages"].append({"role": "user", "content": prompt})
        with st.chat_message("user"):
            st.markdown(prompt)

        with st.chat_message("assistant"):
            with st.spinner("Agent 思考中..."):
                try:
                    from app.agents.paper_research_agent import get_agent

                    agent = get_agent()
                    history = st.session_state["agent_messages"][:-1]
                    conversation_id = st.session_state.get("agent_conversation_id")

                    if agent_mode == "supervisor":
                        result = agent.execute_supervisor(
                            prompt,
                            conversation_id=conversation_id,
                        )
                        st.session_state["agent_conversation_id"] = result.get(
                            "conversation_id"
                        )
                        answer = result["answer"]
                        task_type = result.get("task_type", "")
                        if task_type:
                            st.caption(f"路由: {task_type}")
                    else:
                        result = agent.execute(
                            prompt,
                            chat_history=history,
                            conversation_id=conversation_id,
                        )
                        st.session_state["agent_conversation_id"] = result.get(
                            "conversation_id"
                        )
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
