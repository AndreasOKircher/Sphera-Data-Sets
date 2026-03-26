"""LLM query engine: rank datasets against a user question."""

import json
from core.llm import LLMClient

QUERY_SYSTEM = (
    "You are an LCA (Life Cycle Assessment) data analyst. "
    "The user will ask a question about selecting or comparing datasets. "
    "Analyze each dataset's relevance to the question and return a JSON array, "
    "ranked from most to least relevant. "
    "Each element must have exactly these keys:\n"
    '  "uuid": dataset UUID string\n'
    '  "name": dataset name string\n'
    '  "rank": integer starting at 1\n'
    '  "relevance_score": integer 1-5 (5 = highly relevant, 1 = not relevant)\n'
    '  "comment": 1-2 sentence explanation of relevance to the question\n'
    "Return ONLY the JSON array, no other text, no markdown code fences."
)

_ALL_FIELDS = ["classification", "location", "year", "description"]


def build_prompt(
    question: str,
    datasets: list[dict],
    fields: list[str] | None = None,
) -> str:
    """Build the user message for the LLM query.

    Uses enriched summary (_summary key) when available; falls back to the
    first 500 characters of technology_description.

    Parameters
    ----------
    fields:
        Which dataset fields to include per entry. Defaults to
        ["classification", "location", "year", "description"].
        UUID and name are always included regardless of this setting.
        Valid values: "classification", "location", "year",
                      "description", "synonyms", "dataset_type".
    """
    if fields is None:
        fields = list(_ALL_FIELDS)
    field_set = set(fields)

    lines = [f"Question: {question}\n", "Datasets:"]
    for d in datasets:
        entry_lines = [
            "\n---",
            f"UUID: {d.get('uuid', '')}",
            f"Name: {d.get('name_base', '')}",
        ]
        if "classification" in field_set:
            entry_lines.append(f"Classification: {d.get('classification', '')}")
        if "location" in field_set:
            entry_lines.append(f"Location: {d.get('location', '')}")
        if "year" in field_set:
            entry_lines.append(f"Year: {d.get('reference_year', '')}")
        if "synonyms" in field_set and d.get("synonyms"):
            entry_lines.append(f"Synonyms: {d.get('synonyms', '')}")
        if "dataset_type" in field_set and d.get("dataset_type"):
            entry_lines.append(f"Type: {d.get('dataset_type', '')}")
        if "description" in field_set:
            desc = d.get("_summary") or (d.get("technology_description") or "")[:500]
            entry_lines.append(f"Description: {desc}")
        lines.append("\n".join(entry_lines))
    return "\n".join(lines)


def parse_response(text: str) -> list[dict]:
    """Parse LLM response into a list of ranked dataset dicts.

    Strips optional markdown code fences before parsing.
    Returns empty list on any parse failure.
    """
    stripped = text.strip()
    if stripped.startswith("```"):
        lines = stripped.splitlines()
        inner = lines[1:-1] if lines and lines[-1].strip() == "```" else lines[1:]
        stripped = "\n".join(inner)
    try:
        result = json.loads(stripped)
        return result if isinstance(result, list) else []
    except (json.JSONDecodeError, ValueError):
        return []


def run_query(
    question: str,
    datasets: list[dict],
    client: LLMClient,
    fields: list[str] | None = None,
) -> list[dict]:
    """Call the LLM and return ranked dataset results."""
    results, _ = run_query_with_usage(question, datasets, client=client, fields=fields)
    return results


def run_query_with_usage(
    question: str,
    datasets: list[dict],
    client: LLMClient,
    fields: list[str] | None = None,
) -> tuple[list[dict], dict]:
    """Call the LLM and return (ranked results, usage dict).

    Usage dict keys: input_tokens, output_tokens,
    cache_creation_input_tokens, cache_read_input_tokens.
    All values are zero (usage not exposed through LLMClient abstraction).
    """
    user_message = build_prompt(question, datasets, fields=fields)
    text = client.complete(QUERY_SYSTEM, user_message, 4000)
    usage = {
        "input_tokens": 0,
        "output_tokens": 0,
        "cache_creation_input_tokens": 0,
        "cache_read_input_tokens": 0,
    }
    return parse_response(text), usage
