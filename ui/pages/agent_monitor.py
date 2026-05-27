"""Agent Monitor page — execution timeline, tool stats, and routing decisions."""

from __future__ import annotations

import json

import streamlit as st

from app.services.memory_store import MemoryStore


def render_agent_monitor():
    """Render the Agent monitoring tab."""
    st.header("🔍 Agent 监控")
    st.caption("查看 Agent 执行追踪、路由决策和工具调用统计")

    store = _get_monitor_store()

    tab_timeline, tab_routing, tab_tools = st.tabs(
        ["执行时间线", "路由决策", "工具统计"]
    )

    with tab_timeline:
        _render_timeline(store)

    with tab_routing:
        _render_routing_decisions(store)

    with tab_tools:
        _render_tool_stats(store)


@st.cache_resource
def _get_monitor_store() -> MemoryStore:
    return MemoryStore()


def _render_timeline(store: MemoryStore):
    """Show recent execution traces as a timeline."""
    st.subheader("最近执行记录")

    limit = st.slider("显示条数", 10, 200, 50, key="timeline_limit")
    traces = store.get_traces(limit=limit)

    if not traces:
        st.info("暂无执行记录")
        return

    for trace in traces:
        agent_id = trace["agent_id"]
        action = trace["action"]
        duration = trace.get("duration_ms") or 0
        created_at = trace.get("created_at", 0)

        col1, col2, col3 = st.columns([2, 2, 1])
        with col1:
            st.text(f"{agent_id} / {action}")
        with col2:
            input_data = json.loads(trace.get("input_data", "{}"))
            summary = _summarize_data(input_data)
            st.caption(summary)
        with col3:
            st.caption(f"{duration:.1f} ms")

        if st.checkbox("详情", key=f"detail_{trace['id']}", value=False):
            output_data = json.loads(trace.get("output_data", "{}"))
            metadata = json.loads(trace.get("metadata", "{}"))
            st.json({"input": input_data, "output": output_data, "metadata": metadata})


def _render_routing_decisions(store: MemoryStore):
    """Show supervisor routing decisions."""
    st.subheader("路由决策历史")

    traces = store.get_traces(agent_id="supervisor", limit=100)
    routing_traces = [
        t
        for t in traces
        if json.loads(t.get("metadata", "{}")).get("type") == "routing_decision"
    ]

    if not routing_traces:
        st.info("暂无路由决策记录")
        return

    for trace in routing_traces:
        output = json.loads(trace.get("output_data", "{}"))
        input_data = json.loads(trace.get("input_data", "{}"))

        user_input = input_data.get("user_input", "")[:80]
        classified = output.get("classified_type", "?")
        routed_to = output.get("routed_to", "?")
        scores = output.get("confidence_scores", {})

        with st.container():
            st.markdown(f"**输入**: {user_input}")
            col1, col2, col3 = st.columns(3)
            with col1:
                st.metric("分类", classified)
            with col2:
                st.metric("路由到", routed_to)
            with col3:
                if scores:
                    top_score = max(scores.values()) if scores else 0
                    st.metric("最高匹配", top_score)
            if scores:
                st.caption(f"匹配分数: {scores}")
            st.divider()


def _render_tool_stats(store: MemoryStore):
    """Aggregate and display tool call statistics."""
    st.subheader("工具调用统计")

    traces = store.get_traces(limit=500)
    tool_traces = [t for t in traces if t["action"] == "tool_call"]

    if not tool_traces:
        st.info("暂无工具调用记录")
        return

    tools: dict[str, list[float]] = {}
    for t in tool_traces:
        input_data = json.loads(t.get("input_data", "{}"))
        tool_name = input_data.get("tool", t["agent_id"])
        duration = t.get("duration_ms") or 0
        tools.setdefault(tool_name, []).append(duration)

    st.metric("总调用次数", len(tool_traces))

    col1, col2 = st.columns(2)
    with col1:
        st.markdown("**按工具统计**")
        for name, durations in sorted(tools.items(), key=lambda x: -len(x[1])):
            avg_ms = sum(durations) / len(durations)
            st.text(f"{name}: {len(durations)} 次, 平均 {avg_ms:.1f}ms")

    with col2:
        st.markdown("**耗时分布**")
        chart_data = {name: sum(durations) for name, durations in tools.items()}
        if chart_data:
            import pandas as pd

            df = pd.DataFrame(
                {
                    "工具": list(chart_data.keys()),
                    "总耗时(ms)": list(chart_data.values()),
                }
            )
            st.bar_chart(df.set_index("工具"))


def _summarize_data(data: dict) -> str:
    """Create a short summary of input/output data."""
    if not data:
        return ""
    keys = list(data.keys())[:3]
    parts = []
    for k in keys:
        v = data[k]
        if isinstance(v, str) and len(v) > 40:
            v = v[:40] + "..."
        parts.append(f"{k}={v}")
    return ", ".join(parts)
