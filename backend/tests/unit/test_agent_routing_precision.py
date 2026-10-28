"""Unit tests for routing precision and edge cases in SupervisorAgent."""

from agents import graph
from agents.nodes.supervisor import supervisor_agent


def test_supervisor_does_not_falsely_select_nutrition_for_training_words():
    # Words like 'kháng lực', 'bạn', 'đang' contain 'an', but must NOT trigger NutritionAgent
    state = {
        "question": "Gợi ý lịch tập kháng lực 3 buổi/tuần cho tôi",
        "history": [],
        "agent_trace": [],
        "errors": [],
    }
    result = supervisor_agent(state)
    assert graph.TRAINING_AGENT in result["selected_agents"]
    assert graph.NUTRITION_AGENT not in result["selected_agents"]


def test_supervisor_does_not_falsely_select_nutrition_for_pronoun_ban():
    state = {
        "question": "Tôi muốn hỏi bạn về bài tập gym",
        "history": [],
        "agent_trace": [],
        "errors": [],
    }
    result = supervisor_agent(state)
    assert graph.TRAINING_AGENT in result["selected_agents"]
    assert graph.NUTRITION_AGENT not in result["selected_agents"]


def test_supervisor_selects_nutrition_for_vietnamese_menu_keywords():
    state = {
        "question": "Gợi ý thực đơn giảm mỡ cho tôi",
        "history": [],
        "agent_trace": [],
        "errors": [],
    }
    result = supervisor_agent(state)
    assert graph.NUTRITION_AGENT in result["selected_agents"]


def test_supervisor_selects_training_for_gym_keywords():
    state = {
        "question": "Tôi muốn tập gym tăng cơ 4 buổi/tuần",
        "history": [],
        "agent_trace": [],
        "errors": [],
    }
    result = supervisor_agent(state)
    assert graph.TRAINING_AGENT in result["selected_agents"]


def test_web_search_agent_ignores_search_error_strings(monkeypatch):
    monkeypatch.setattr(
        graph,
        "tavily_search_health",
        lambda *args, **kwargs: "Lỗi tìm kiếm: Invalid API key\n\nThông tin chỉ mang tính tham khảo.",
    )
    state = {
        "question": "Tin tức sức khỏe mới nhất hôm nay",
        "selected_agents": [graph.WEB_SEARCH_AGENT],
        "tool_results": [],
        "agent_trace": [],
        "errors": [],
    }
    result = graph.web_search_agent(state)
    assert result["tool_results"] == []
    assert any("Web search is temporarily unavailable" in err for err in result["errors"])
