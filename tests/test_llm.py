"""Tests for core/llm.py LLM client abstraction."""
import pytest
from unittest.mock import MagicMock, patch
from core.llm import AnthropicLLMClient, VIOLLMClient, create_llm_client


class TestAnthropicLLMClient:
    def _make_client(self, response_text="hello"):
        mock_anthropic = MagicMock()
        mock_msg = MagicMock()
        mock_msg.content = [MagicMock(text=response_text)]
        mock_anthropic.messages.create.return_value = mock_msg
        return AnthropicLLMClient(client=mock_anthropic, model="claude-haiku-4-5-20251001"), mock_anthropic

    def test_complete_returns_string(self):
        client, _ = self._make_client("result text")
        assert client.complete("sys", "user", 100) == "result text"

    def test_complete_passes_system_with_cache_control(self):
        client, mock_anthropic = self._make_client()
        client.complete("my system prompt", "user msg", 200)
        call_kwargs = mock_anthropic.messages.create.call_args.kwargs
        system = call_kwargs["system"]
        assert isinstance(system, list)
        assert system[0]["text"] == "my system prompt"
        assert system[0]["cache_control"] == {"type": "ephemeral"}

    def test_complete_passes_user_as_message(self):
        client, mock_anthropic = self._make_client()
        client.complete("sys", "the user input", 300)
        call_kwargs = mock_anthropic.messages.create.call_args.kwargs
        assert call_kwargs["messages"][0]["role"] == "user"
        assert call_kwargs["messages"][0]["content"] == "the user input"

    def test_complete_passes_max_tokens(self):
        client, mock_anthropic = self._make_client()
        client.complete("sys", "user", 1234)
        assert mock_anthropic.messages.create.call_args.kwargs["max_tokens"] == 1234

    def test_complete_uses_stored_model(self):
        client, mock_anthropic = self._make_client()
        client.complete("sys", "user", 100)
        assert mock_anthropic.messages.create.call_args.kwargs["model"] == "claude-haiku-4-5-20251001"


class TestCreateLLMClientAnthropic:
    def test_factory_returns_anthropic_client(self):
        with patch("core.llm.anthropic.Anthropic") as mock_cls:
            mock_cls.return_value = MagicMock()
            result = create_llm_client("anthropic", api_key="test-key", model="claude-haiku-4-5-20251001")
        assert isinstance(result, AnthropicLLMClient)

    def test_factory_unknown_provider_raises(self):
        with pytest.raises(ValueError, match="unknown"):
            create_llm_client("bogus", api_key="key", model="model")


class TestVIOLLMClient:
    def _make_client(self, response_text="vio result"):
        mock_openai = MagicMock()
        mock_choice = MagicMock()
        mock_choice.message.content = response_text
        mock_openai.chat.completions.create.return_value = MagicMock(
            choices=[mock_choice],
            usage=MagicMock(prompt_tokens=10, completion_tokens=5),
        )
        return VIOLLMClient(client=mock_openai, model="Default"), mock_openai

    def test_complete_returns_string(self):
        client, _ = self._make_client("vio result")
        assert client.complete("sys", "user", 100) == "vio result"

    def test_complete_passes_system_as_first_message(self):
        client, mock_openai = self._make_client()
        client.complete("my system", "user msg", 200)
        messages = mock_openai.chat.completions.create.call_args.kwargs["messages"]
        assert messages[0]["role"] == "system"
        assert messages[0]["content"] == "my system"

    def test_complete_passes_user_as_second_message(self):
        client, mock_openai = self._make_client()
        client.complete("sys", "the user input", 300)
        messages = mock_openai.chat.completions.create.call_args.kwargs["messages"]
        assert messages[1]["role"] == "user"
        assert messages[1]["content"] == "the user input"

    def test_complete_passes_max_tokens(self):
        client, mock_openai = self._make_client()
        client.complete("sys", "user", 1234)
        assert mock_openai.chat.completions.create.call_args.kwargs["max_tokens"] == 1234

    def test_complete_uses_stored_model(self):
        client, mock_openai = self._make_client()
        client.complete("sys", "user", 100)
        assert mock_openai.chat.completions.create.call_args.kwargs["model"] == "Default"

    def test_no_cache_control_in_messages(self):
        client, mock_openai = self._make_client()
        client.complete("sys", "user", 100)
        messages = mock_openai.chat.completions.create.call_args.kwargs["messages"]
        for msg in messages:
            assert "cache_control" not in msg


class TestCreateLLMClientVIO:
    def test_factory_returns_vio_client(self):
        with patch("core.llm.openai.OpenAI") as mock_cls:
            mock_cls.return_value = MagicMock()
            result = create_llm_client(
                "vio", api_key="token", model="Default",
                base_url="https://vio.automotive-wan.com:446",
                tenant_id="default_tenant",
            )
        assert isinstance(result, VIOLLMClient)

    def test_factory_vio_passes_base_url(self):
        with patch("core.llm.openai.OpenAI") as mock_cls:
            mock_cls.return_value = MagicMock()
            create_llm_client("vio", api_key="tok", model="Default",
                              base_url="https://vio.example.com:446", tenant_id="t1")
            assert mock_cls.call_args.kwargs["base_url"] == "https://vio.example.com:446"

    def test_factory_vio_passes_custom_headers(self):
        with patch("core.llm.openai.OpenAI") as mock_cls:
            mock_cls.return_value = MagicMock()
            create_llm_client("vio", api_key="tok", model="Default",
                              base_url="https://vio.example.com:446", tenant_id="mytenant")
            headers = mock_cls.call_args.kwargs["default_headers"]
            assert headers["useLegacyCompletionsEndpoint"] == "false"
            assert headers["X-Tenant-ID"] == "mytenant"
