# tests/test_query_history.py
from unittest.mock import MagicMock
from viewer.query import build_prompt, run_query


def test_build_prompt_includes_history():
    history = [
        {"role": "user", "content": "What is steel?"},
        {"role": "assistant", "content": "Steel is an alloy of iron."},
    ]
    datasets = [{"uuid": "x", "name_base": "Steel", "technology_description": "desc"}]
    prompt = build_prompt("tell me more", datasets, history=history)
    assert "What is steel?" in prompt
    assert "Steel is an alloy of iron." in prompt


def test_build_prompt_no_history_unchanged():
    datasets = [{"uuid": "x", "name_base": "Steel", "technology_description": "desc"}]
    prompt_no_history = build_prompt("question", datasets)
    prompt_empty_history = build_prompt("question", datasets, history=[])
    assert prompt_no_history == prompt_empty_history


def test_run_query_passes_history_to_client():
    mock_client = MagicMock()
    mock_client.complete.return_value = "[]"
    history = [{"role": "user", "content": "prior question"},
               {"role": "assistant", "content": "prior answer"}]
    datasets = [{"uuid": "x", "name_base": "Test", "technology_description": "some text"}]
    run_query("follow-up", datasets, client=mock_client, history=history)
    call_args = mock_client.complete.call_args
    # The user message passed to the LLM should contain history
    user_message = call_args[0][1]
    assert "prior question" in user_message
