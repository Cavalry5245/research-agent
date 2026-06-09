import ast
from pathlib import Path

from app.research_workflow.schemas import ResearchRunCreateRequest


STREAMLIT_APP = Path("ui/streamlit_app.py")


def test_research_workflow_request_can_be_built_for_ui():
    req = ResearchRunCreateRequest(
        collection_id="COLL123",
        collection_name="IRSTD",
        goal="Create a review",
        options={"max_papers": 3, "semantic_scholar": True, "arxiv": False},
    )

    assert req.collection_id == "COLL123"
    assert req.collection_name == "IRSTD"
    assert req.goal == "Create a review"
    assert req.options.max_papers == 3
    assert req.options.semantic_scholar is True
    assert req.options.arxiv is False


def _streamlit_source() -> str:
    return STREAMLIT_APP.read_text(encoding="utf-8")


def _streamlit_tree() -> ast.Module:
    return ast.parse(_streamlit_source())


def _research_run_selectbox_call(tree: ast.Module) -> ast.Call:
    for node in ast.walk(tree):
        if (
            isinstance(node, ast.Call)
            and isinstance(node.func, ast.Attribute)
            and node.func.attr == "selectbox"
            and node.args
            and isinstance(node.args[0], ast.Constant)
            and node.args[0].value == "Select run"
        ):
            return node

    raise AssertionError("Research run selectbox was not found")


def test_research_workflow_ui_source_contains_required_wiring():
    source = _streamlit_source()

    for token in (
        "get_research_run_service",
        "selected_research_run_id",
        "st.error",
        "ResearchRunCreateRequest",
    ):
        assert token in source


def test_research_workflow_is_first_navigation_item():
    tree = _streamlit_tree()

    for node in ast.walk(tree):
        if not (
            isinstance(node, ast.Call)
            and isinstance(node.func, ast.Attribute)
            and node.func.attr == "radio"
            and node.args
            and isinstance(node.args[0], ast.Constant)
            and node.args[0].value == "导航"
        ):
            continue

        navigation_options = node.args[1]
        assert isinstance(navigation_options, ast.List)
        first_item = navigation_options.elts[0]
        assert isinstance(first_item, ast.Constant)
        assert first_item.value == "Research Workflow"
        return

    raise AssertionError("Streamlit sidebar navigation radio was not found")


def test_research_run_selector_index_uses_selected_session_state():
    source = _streamlit_source()
    tree = _streamlit_tree()

    assert 'st.session_state["selected_research_run_id"]' in source
    assert "selected_run_index" in source

    node = _research_run_selectbox_call(tree)
    index_keywords = [kw for kw in node.keywords if kw.arg == "index"]
    assert len(index_keywords) == 1
    assert isinstance(index_keywords[0].value, ast.Name)
    assert index_keywords[0].value.id == "selected_run_index"


def test_research_run_selector_preserves_valid_widget_state_before_render():
    source = _streamlit_source()
    tree = _streamlit_tree()
    selectbox = _research_run_selectbox_call(tree)
    pre_selectbox_source = "\n".join(source.splitlines()[: selectbox.lineno - 1])

    assert 'st.session_state.get("research_run_selector")' in pre_selectbox_source
    assert "selected_research_run_id = widget_selected_run_id" in pre_selectbox_source
    assert (
        'st.session_state.get("research_run_selector") != selected_research_run_id'
        not in pre_selectbox_source
    )
