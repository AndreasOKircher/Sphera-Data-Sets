# Multi-Provider LLM Support Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add VIO (OpenAI-compatible) as a second LLM provider alongside Anthropic, selectable via env var or CLI flag.

**Architecture:** Thin `LLMClient` protocol in `core/llm.py` with `complete(system, user, max_tokens) -> str` method. `AnthropicLLMClient` and `VIOLLMClient` implement it. All enrichment and query code uses the abstraction. Batch mode stays Anthropic-only.

**Tech Stack:** Python, `anthropic>=0.40.0`, `openai>=1.0.0`, `python-dotenv`

---

## Scope

This plan covers **multi-provider LLM support only**. MongoDB storage and RAG are independent subsystems — separate future plans.

## File Map

| File | Action | Responsibility |
|------|--------|----------------|
| `core/llm.py` | **Create** | `LLMClient` protocol, `AnthropicLLMClient`, `VIOLLMClient`, `create_llm_client()` factory |
| `core/enricher.py` | Modify | Change `enrich_dataset(data, client, model)` → `enrich_dataset(data, client: LLMClient)` |
| `enrich.py` | Modify | Use factory, add `--provider` flag, guard `--batch` for Anthropic only |
| `viewer/query.py` | Modify | Accept `LLMClient` instead of creating Anthropic client internally; normalize usage |
| `viewer/app.py` | Modify | Create `LLMClient` from env at startup, pass to query |
| `requirements.txt` | Modify | Add `openai>=1.0.0` |
| `.env.example` | **Create** | Document all env vars |
| `tests/test_llm.py` | **Create** | Unit tests for both provider implementations |
| `tests/test_enricher.py` | Modify | Update mock to `complete()` interface |
| `tests/test_query.py` | Modify | Update mock + Flask fixture to new `LLMClient` interface |

---

## Baseline: Current Call Patterns

**`core/enricher.py` lines 154–168:** Two sequential `client.messages.create(model=model, max_tokens=..., system=..., messages=[...])` calls. Response text via `resp.content[0].text`.

**`enrich.py` lines 147–158:** `process_one()` calls `client.messages.create()` with `system` as a list with `cache_control: ephemeral` — Anthropic-specific.

**`enrich.py` lines 386–424:** `run_batch()` uses `client.messages.batches.create/retrieve/results()` — Anthropic-SDK-specific, stays as-is.

**`viewer/query.py` lines 114–128:** Creates `anthropic.Anthropic(api_key=api_key)` internally, calls `client.messages.create()` with `cache_control`, returns usage dict.

---

## Task 1: Create `core/llm.py` — LLMClient protocol + AnthropicLLMClient

**Files:** Create `core/llm.py`, create `tests/test_llm.py`

- [ ] **Step 1: Write failing tests in `tests/test_llm.py`**

```python
"""Tests for core/llm.py LLM client abstraction."""
import pytest
from unittest.mock import MagicMock, patch
from core.llm import AnthropicLLMClient, create_llm_client


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
```

- [ ] **Step 2: Run — expect failure** (`pytest tests/test_llm.py` → `ModuleNotFoundError: core.llm`)

- [ ] **Step 3: Implement `core/llm.py` with `AnthropicLLMClient` only**

```python
"""Thin LLM provider abstraction for the Sphera enrichment pipeline."""
from typing import Protocol, runtime_checkable
import anthropic


@runtime_checkable
class LLMClient(Protocol):
    """Minimal interface for LLM text completion."""

    def complete(self, system: str, user: str, max_tokens: int) -> str:
        """Return the model's response as a plain string."""
        ...


class AnthropicLLMClient:
    """LLMClient backed by the Anthropic Messages API.

    Applies cache_control: ephemeral on the system prompt automatically.
    """

    def __init__(self, client: anthropic.Anthropic, model: str) -> None:
        self._client = client
        self._model = model

    def complete(self, system: str, user: str, max_tokens: int) -> str:
        resp = self._client.messages.create(
            model=self._model,
            max_tokens=max_tokens,
            system=[{"type": "text", "text": system, "cache_control": {"type": "ephemeral"}}],
            messages=[{"role": "user", "content": user}],
        )
        return resp.content[0].text


def create_llm_client(provider: str, **kwargs) -> LLMClient:
    """Factory for LLM clients.

    Parameters
    ----------
    provider:   "anthropic" or "vio"
    **kwargs:   For "anthropic": api_key, model
                For "vio":       api_key, model, base_url, tenant_id
    """
    if provider == "anthropic":
        client = anthropic.Anthropic(api_key=kwargs["api_key"])
        return AnthropicLLMClient(client=client, model=kwargs["model"])
    raise ValueError(f"Unknown LLM provider: {provider!r}. Expected 'anthropic' or 'vio'.")
```

- [ ] **Step 4: Run — expect pass** (`pytest tests/test_llm.py`)

- [ ] **Step 5: Commit**
```bash
git add core/llm.py tests/test_llm.py
git commit -m "feat: add core/llm.py with LLMClient protocol and AnthropicLLMClient"
```

---

## Task 2: Add VIOLLMClient to `core/llm.py`

**Files:** Modify `core/llm.py`, modify `tests/test_llm.py`

- [ ] **Step 1: Append failing tests for `VIOLLMClient` to `tests/test_llm.py`**

```python
from core.llm import VIOLLMClient


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
```

- [ ] **Step 2: Run — expect failure** (`pytest tests/test_llm.py -k VIO`)

- [ ] **Step 3: Add `VIOLLMClient` to `core/llm.py`**

Add `import openai` to imports, then add the class and update the factory:

```python
import openai   # add to imports


class VIOLLMClient:
    """LLMClient backed by the VIO API (OpenAI-compatible).

    Does NOT apply cache_control (VIO does not support it).
    """

    def __init__(self, client, model: str) -> None:
        self._client = client
        self._model = model

    def complete(self, system: str, user: str, max_tokens: int) -> str:
        resp = self._client.chat.completions.create(
            model=self._model,
            max_tokens=max_tokens,
            messages=[
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
        )
        return resp.choices[0].message.content
```

Update `create_llm_client` — add before the final `raise`:
```python
    if provider == "vio":
        client = openai.OpenAI(
            api_key=kwargs["api_key"],
            base_url=kwargs["base_url"],
            default_headers={
                "useLegacyCompletionsEndpoint": "false",
                "X-Tenant-ID": kwargs.get("tenant_id", "default_tenant"),
            },
        )
        return VIOLLMClient(client=client, model=kwargs["model"])
```

- [ ] **Step 4: Run all llm tests — expect pass** (`pytest tests/test_llm.py`)

- [ ] **Step 5: Commit**
```bash
git add core/llm.py tests/test_llm.py
git commit -m "feat: add VIOLLMClient to core/llm.py"
```

---

## Task 3: Update `core/enricher.py`

**Files:** Modify `core/enricher.py` (lines 3, 132–168), modify `tests/test_enricher.py`

Current signature at line 132: `enrich_dataset(data: dict, client: anthropic.Anthropic, model: str)`
New signature: `enrich_dataset(data: dict, client: LLMClient)`

- [ ] **Step 1: Update mock pattern in `tests/test_enricher.py`**

Replace `TestEnrichDataset` class — mocks change from `messages.create` to `complete`:

```python
class TestEnrichDataset:
    def _make_mock(self, side_effects):
        mock_client = MagicMock()
        mock_client.complete.side_effect = side_effects
        return mock_client

    def test_enrich_dataset_missing_field_returns_none(self):
        result = enrich_dataset({"uuid": "abc"}, MagicMock())
        assert result is None

    def test_enrich_dataset_empty_field_returns_none(self):
        result = enrich_dataset(
            {"uuid": "abc", "technology_description": ""}, MagicMock()
        )
        assert result is None

    def test_enrich_dataset_success(self):
        mock_client = self._make_mock(["A plain summary.", "**The** original text."])
        data = {"uuid": "test-uuid", "technology_description": "The original text."}
        result = enrich_dataset(data, mock_client)
        assert result is not None
        assert result["uuid"] == "test-uuid"
        assert result["technology_description_summary"] == "A plain summary."
        assert result["technology_description_formatted"] == "**The** original text."
        assert "ok" not in result
        assert len(result) == 12

    def test_enrich_dataset_fail_on_threshold(self):
        bloated = " ".join(["word"] * 100)
        mock_client = self._make_mock(["A plain summary.", bloated])
        result = enrich_dataset({"uuid": "abc", "technology_description": "one two three"}, mock_client)
        assert result is None

    def test_enrich_dataset_calls_complete_twice(self):
        mock_client = self._make_mock(["A plain summary.", "**The** original text."])
        enrich_dataset({"uuid": "test-uuid", "technology_description": "The original text."}, mock_client)
        assert mock_client.complete.call_count == 2
```

- [ ] **Step 2: Run — expect failure** (`pytest tests/test_enricher.py::TestEnrichDataset`)

- [ ] **Step 3: Update `core/enricher.py`**

  - Remove `import anthropic` (line 3)
  - Add `from core.llm import LLMClient`
  - Line 132: change to `def enrich_dataset(data: dict, client: LLMClient) -> dict | None:`
  - Lines 154–160: replace with `summary = client.complete(SUMMARY_SYSTEM, technology_description, 300)`
  - Lines 162–168: replace with `formatted = client.complete(FORMAT_SYSTEM, technology_description, 16000)`
  - Update docstring: remove `model` param reference, change `anthropic.Anthropic` to `LLMClient`

- [ ] **Step 4: Run all enricher tests — expect pass** (`pytest tests/test_enricher.py`)

- [ ] **Step 5: Commit**
```bash
git add core/enricher.py tests/test_enricher.py
git commit -m "refactor: update enricher to use LLMClient protocol"
```

---

## Task 4: Update `enrich.py`

**Files:** Modify `enrich.py`

Key changes:
- `process_one()`: use `client.complete()` instead of `client.messages.create()` with cache_control
- `main()`: add `--provider` arg, create client via factory, guard `--batch` for Anthropic only
- `run_batch()`: stays Anthropic-SDK-specific — only add a comment

- [ ] **Step 1: Update `process_one()` signature and body**

  - Remove `model: str` param; update type hint on `client` to `LLMClient`
  - Replace `_summary_call()` / `_format_call()` inner functions and ThreadPoolExecutor block (lines 144–164) with:
    ```python
    with ThreadPoolExecutor(max_workers=2) as ex:
        f_summary = ex.submit(client.complete, SUMMARY_SYSTEM, tech, 300)
        f_format  = ex.submit(client.complete, FORMAT_SYSTEM,   tech, 16000)
        summary   = f_summary.result()
        formatted = f_format.result()
    ```
  - Remove usage tracking block (lines 166–180): `_usage()`, `u_sum`, `u_fmt`, `call_in/out/hit/new`
  - Remove token display lines (lines 231–237): `tok_line` and the `out()` calls for it
  - Remove `token_totals` parameter and update block (lines 238–243)
  - Change `except anthropic.APIError as exc:` to `except Exception as exc:`
  - Add import: `from core.llm import create_llm_client, LLMClient`

- [ ] **Step 2: Update `main()` in `enrich.py`**

  - Add `--provider` argument:
    ```python
    parser.add_argument("--provider", default="anthropic", choices=["anthropic", "vio"],
                        help="LLM provider (default: anthropic)")
    ```
  - Replace `_check_api_key()` + `anthropic.Anthropic(api_key=key)` with provider-aware factory:
    ```python
    if args.provider == "anthropic":
        api_key = os.environ.get("ANTHROPIC_API_KEY", "")
        if not api_key:
            print("[ERROR] ANTHROPIC_API_KEY not set.", file=sys.stderr); sys.exit(1)
        llm_client = create_llm_client("anthropic", api_key=api_key, model=args.model)
    else:
        api_key = os.environ.get("API_TOKEN", "")
        if not api_key:
            print("[ERROR] API_TOKEN not set.", file=sys.stderr); sys.exit(1)
        base_url  = os.environ.get("VIO_BASE_URL", "https://vio.automotive-wan.com:446")
        tenant_id = os.environ.get("VIO_TENANT_ID", "default_tenant")
        llm_client = create_llm_client("vio", api_key=api_key, model=args.model,
                                       base_url=base_url, tenant_id=tenant_id)
    ```
  - Add `--batch` guard immediately after:
    ```python
    if args.batch and args.provider != "anthropic":
        print("[ERROR] --batch is only supported with --provider anthropic.", file=sys.stderr)
        sys.exit(1)
    ```
  - Update all `process_one()` calls: remove `args.model` argument, pass `llm_client`
  - For `run_batch()` call: keep passing raw `anthropic.Anthropic` client — reconstruct it:
    ```python
    raw_anthropic = anthropic.Anthropic(api_key=api_key)
    run_batch(uuids, raw_anthropic, args.model, ...)
    ```
  - Remove `token_totals` dict and session token summary at end of `--all` block

- [ ] **Step 3: Smoke test** (`python enrich.py --help` — verify `--provider` appears in output)

- [ ] **Step 4: Commit**
```bash
git add enrich.py
git commit -m "feat: add --provider flag to enrich.py, use LLMClient abstraction"
```

---

## Task 5: Update `viewer/query.py`

**Files:** Modify `viewer/query.py` (lines 4, 90–128), modify `tests/test_query.py`

New signature: `run_query_with_usage(question, datasets, client: LLMClient, fields=None)`
Usage dict: returns zeros for all fields (usage not available through the abstraction).

- [ ] **Step 1: Update `tests/test_query.py`**

  Replace `_make_mock_client` helper and rewrite the five `test_run_query_*` tests:

  ```python
  def _make_mock_llm_client(response_text: str):
      mock_client = MagicMock()
      mock_client.complete.return_value = response_text
      return mock_client


  def test_run_query_returns_parsed_results():
      results = run_query("Which is steel?", [DATASET_A, DATASET_B],
                          client=_make_mock_llm_client(VALID_JSON))
      assert len(results) == 2
      assert results[0]["rank"] == 1


  def test_run_query_passes_question_in_prompt():
      mock_client = _make_mock_llm_client(VALID_JSON)
      run_query("my unique question xyz", [DATASET_A], client=mock_client)
      call_args = mock_client.complete.call_args
      user_msg = call_args.args[1] if call_args.args else call_args.kwargs["user"]
      assert "my unique question xyz" in user_msg


  def test_run_query_malformed_llm_response_returns_empty():
      results = run_query("test", [DATASET_A],
                          client=_make_mock_llm_client("Sorry, I cannot answer."))
      assert results == []
  ```

  Remove `test_run_query_uses_default_model` and `test_run_query_uses_custom_model` (model is now in the client).

  Update `flask_client` fixture: replace `app.config["ANTHROPIC_API_KEY"] = "fake-key"` with `app.config["LLM_CLIENT"] = MagicMock()`.

  Update monkeypatched lambda signature from `(question, datasets, api_key, model, fields=None)` to `(question, datasets, client, fields=None)`.

- [ ] **Step 2: Run — expect failure** (`pytest tests/test_query.py`)

- [ ] **Step 3: Update `viewer/query.py`**

  - Remove `import anthropic` (line 4)
  - Add `from core.llm import LLMClient`
  - Update `run_query` signature (line 90): replace `api_key: str, model: str = DEFAULT_QUERY_MODEL` with `client: LLMClient`; update delegate call
  - Update `run_query_with_usage` signature (line 102): same change
  - Replace body of `run_query_with_usage` (lines 114–128):
    ```python
    user_message = build_prompt(question, datasets, fields=fields)
    text = client.complete(QUERY_SYSTEM, user_message, 4000)
    usage = {
        "input_tokens": 0,
        "output_tokens": 0,
        "cache_creation_input_tokens": 0,
        "cache_read_input_tokens": 0,
    }
    return parse_response(text), usage
    ```

- [ ] **Step 4: Run all query tests — expect pass** (`pytest tests/test_query.py`)

- [ ] **Step 5: Commit**
```bash
git add viewer/query.py tests/test_query.py
git commit -m "refactor: viewer/query.py accepts LLMClient, removes internal Anthropic instantiation"
```

---

## Task 6: Update `viewer/app.py`

**Files:** Modify `viewer/app.py`

- [ ] **Step 1: Update `viewer/app.py`**

  - Add `from core.llm import create_llm_client`
  - Replace `app.config["ANTHROPIC_API_KEY"] = ...` (line 30) with:
    ```python
    def _build_llm_client():
        provider = os.environ.get("LLM_PROVIDER", "anthropic")
        model    = os.environ.get("LLM_MODEL", "claude-haiku-4-5")
        if provider == "anthropic":
            api_key = os.environ.get("ANTHROPIC_API_KEY", "")
            return create_llm_client("anthropic", api_key=api_key, model=model) if api_key else None
        if provider == "vio":
            api_key   = os.environ.get("API_TOKEN", "")
            base_url  = os.environ.get("VIO_BASE_URL", "https://vio.automotive-wan.com:446")
            tenant_id = os.environ.get("VIO_TENANT_ID", "default_tenant")
            return create_llm_client("vio", api_key=api_key, model=model,
                                     base_url=base_url, tenant_id=tenant_id) if api_key else None
        return None

    app.config["LLM_CLIENT"] = _build_llm_client()
    ```
  - In `/query` route, replace `api_key = app.config.get("ANTHROPIC_API_KEY", "")` and error guard with:
    ```python
    llm_client = app.config.get("LLM_CLIENT")
    if llm_client is None:
        return jsonify({"error": "LLM provider not configured. Check LLM_PROVIDER and API key env vars."}), 503
    ```
  - Replace `run_query_with_usage(question, selected, api_key=api_key, model=model, ...)` with:
    ```python
    results, usage = run_query_with_usage(question, selected, client=llm_client, fields=fields)
    ```
  - Remove `model = body.get("model", ...)` line (model is in the client now)

- [ ] **Step 2: Update `test_query_route_no_api_key` in `tests/test_query.py`**

  Replace `app_mod.app.config["ANTHROPIC_API_KEY"] = ""` with `app_mod.app.config["LLM_CLIENT"] = None`.

- [ ] **Step 3: Run full test suite — expect pass** (`pytest tests/`)

- [ ] **Step 4: Commit**
```bash
git add viewer/app.py tests/test_query.py
git commit -m "feat: viewer/app.py creates LLMClient from env, passes to query"
```

---

## Task 7: requirements.txt + .env.example

**Files:** Modify `requirements.txt`, create `.env.example`

- [ ] **Step 1: Add `openai>=1.0.0` to `requirements.txt`** (after the `anthropic` line)

- [ ] **Step 2: Create `.env.example`**

```
# ──────────────────────────────────────────────────────
# Sphera LCA Dataset Tools — Environment Variables
# Copy to .env and fill in your values.
# ──────────────────────────────────────────────────────

# LLM Provider Selection
# Options: anthropic, vio
LLM_PROVIDER=anthropic

# Model to use (must match the selected provider)
# Anthropic examples: claude-haiku-4-5-20251001, claude-haiku-4-5
# VIO examples:       Default, VIO:GPT-4o, VIO:GPT-5-low
LLM_MODEL=claude-haiku-4-5-20251001

# ── Anthropic (required if LLM_PROVIDER=anthropic) ────
ANTHROPIC_API_KEY=

# ── VIO (required if LLM_PROVIDER=vio) ────────────────
API_TOKEN=
API_USERNAME=
VIO_BASE_URL=https://vio.automotive-wan.com:446
VIO_TENANT_ID=default_tenant
```

- [ ] **Step 3: Install new dependency** (`pip install openai>=1.0.0`)

- [ ] **Step 4: Run full test suite** (`pytest tests/`)

- [ ] **Step 5: Commit**
```bash
git add requirements.txt .env.example
git commit -m "chore: add openai dependency and .env.example for multi-provider support"
```

---

## Architecture Summary

```
                    ┌─────────────────────────────────┐
                    │      LLMClient (Protocol)        │
                    │  complete(system, user,           │
                    │          max_tokens) -> str       │
                    └────────────┬────────────────────-┘
                                 │ implements
               ┌─────────────────┴──────────────────────┐
               │                                         │
  ┌────────────▼─────────────┐       ┌──────────────────▼──────────┐
  │   AnthropicLLMClient     │       │       VIOLLMClient           │
  │  anthropic.Anthropic     │       │  openai.OpenAI (VIO config)  │
  │  + cache_control:ephemeral│      │  No cache_control            │
  │  resp.content[0].text    │       │  resp.choices[0].msg.content │
  └──────────────────────────┘       └─────────────────────────────┘
               │                                         │
               └──────────────┬──────────────────────────┘
                              │ created by
                    ┌─────────▼──────────────┐
                    │  create_llm_client()   │
                    │  in core/llm.py        │
                    └─────────┬──────────────┘
                              │ used by
           ┌──────────────────┼───────────────────────┐
           │                  │                       │
  ┌────────▼───────┐  ┌───────▼────────┐   ┌─────────▼───────┐
  │ core/enricher  │  │  enrich.py CLI │   │ viewer/app.py   │
  │ enrich_dataset │  │ process_one()  │   │ /query route    │
  │ (data, client) │  │ (uuid, client) │   │ → query.py      │
  └────────────────┘  └────────────────┘   └─────────────────┘

  Batch mode (Anthropic-only, intentionally not abstracted):
  enrich.py --batch → raw anthropic.Anthropic → client.messages.batches.*
  Guard: --batch + --provider vio → error + exit
```

## Key Invariants

1. `LLMClient.complete()` returns a plain `str` — no usage data exposed.
2. `cache_control: ephemeral` lives exclusively inside `AnthropicLLMClient.complete()`.
3. `run_batch()` is Anthropic-SDK-specific — stays on the raw client, guarded by `--provider` check.
4. Usage returned by `run_query_with_usage()` will be zeros — acceptable since it is only used for display in the viewer.
5. All existing tests continue to pass; mock pattern changes from `mock.messages.create.return_value = MagicMock(content=[...])` to `mock.complete.return_value = "string"`.

## Dependency Order

```
Task 1 (llm.py Anthropic)
  → Task 2 (llm.py VIO)
      → Task 3 (enricher.py)   — parallel with 4 and 5
      → Task 4 (enrich.py)     — parallel with 3 and 5
      → Task 5 (query.py)
          → Task 6 (app.py)
              → Task 7 (requirements + .env.example)
```
