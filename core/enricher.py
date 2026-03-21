"""Pure text utility functions for LCA dataset enrichment."""

import anthropic
from datetime import datetime
from typing import TypedDict

_STRIP_CHARS = str.maketrans("", "", "#*_`")


class CountsResult(TypedDict):
    word_count: int
    formatted_word_count: int
    word_count_diff: int
    word_count_diff_pct: float
    char_count: int
    formatted_char_count: int
    char_count_diff: int
    char_count_diff_pct: float
    ok: bool


def clean_text(text: str) -> str:
    """Strip formatting characters from *text* and return the result.

    Newlines (``\\n``, ``\\r``) are replaced with a space to preserve word
    boundaries.  Pure formatting markers (``#``, ``*``, ``_``, backtick) are
    removed entirely.  All other characters (spaces, punctuation, alphanumeric,
    Unicode) are preserved exactly as-is.
    """
    text = text.replace('\n', ' ').replace('\r', ' ')
    return text.translate(_STRIP_CHARS)


def count_words(text: str) -> int:
    """Return the number of whitespace-delimited tokens in *text* after cleaning."""
    return len(clean_text(text).split())


def count_chars(text: str) -> int:
    """Return ``len()`` of *text* after cleaning."""
    return len(clean_text(text))


def verify_counts(
    original: str,
    formatted: str,
    threshold_pct: float = 2.0,
) -> CountsResult:
    """Compare word and character counts between *original* and *formatted* text.

    Parameters
    ----------
    original:
        The source text before any LLM formatting.
    formatted:
        The LLM-formatted text to compare against *original*.
    threshold_pct:
        Maximum allowed percentage difference (inclusive) for both word and
        character counts.  Defaults to ``2.0`` (i.e. 2 %).

    Returns
    -------
    dict with the following keys:

    * ``word_count`` — word count of *original*
    * ``formatted_word_count`` — word count of *formatted*
    * ``word_count_diff`` — ``formatted_word_count - word_count``
    * ``word_count_diff_pct`` — ``abs(diff) / word_count * 100``
    * ``char_count`` — character count of *original*
    * ``formatted_char_count`` — character count of *formatted*
    * ``char_count_diff`` — ``formatted_char_count - char_count``
    * ``char_count_diff_pct`` — ``abs(diff) / char_count * 100``
    * ``ok`` — ``True`` if **both** diff percentages are <= *threshold_pct*

    Note: the ``ok`` key must **not** be written to JSON output files; that
    stripping is the responsibility of the caller (``enrich_dataset``).
    """
    word_count = count_words(original)
    formatted_word_count = count_words(formatted)
    word_count_diff = formatted_word_count - word_count
    word_count_diff_pct = (
        abs(word_count_diff) / word_count * 100 if word_count else 0.0
    )

    char_count = count_chars(original)
    formatted_char_count = count_chars(formatted)
    char_count_diff = formatted_char_count - char_count
    char_count_diff_pct = (
        abs(char_count_diff) / char_count * 100 if char_count else 0.0
    )

    ok = word_count_diff_pct <= threshold_pct and char_count_diff_pct <= threshold_pct

    return {
        "word_count": word_count,
        "formatted_word_count": formatted_word_count,
        "word_count_diff": word_count_diff,
        "word_count_diff_pct": word_count_diff_pct,
        "char_count": char_count,
        "formatted_char_count": formatted_char_count,
        "char_count_diff": char_count_diff,
        "char_count_diff_pct": char_count_diff_pct,
        "ok": ok,
    }


_SUMMARY_SYSTEM = (
    "You are a technical writer specializing in Life Cycle Assessment (LCA). Write a "
    "3-5 sentence plain-language summary of the following technology description. Focus "
    "on what the process is, what it produces, and its key characteristics. Do not add "
    "any information not present in the original text."
)

_FORMAT_SYSTEM = (
    "You are a technical editor. Reformat the following text for readability by adding "
    "paragraph breaks, markdown headers (##) for major sections, and bold (**) for key "
    "terms. Do NOT change, add, or remove any words. Return only the reformatted "
    "markdown, nothing else."
)


def enrich_dataset(data: dict, client: anthropic.Anthropic, model: str) -> dict | None:
    """Enrich a single dataset record with a summary and formatted description.

    Parameters
    ----------
    data:
        A dataset record dict. Must contain ``uuid`` and
        ``technology_description``.
    client:
        An ``anthropic.Anthropic`` client (or compatible mock).
    model:
        The Claude model identifier to use for both API calls.

    Returns
    -------
    Enriched dict with 12 keys, or ``None`` if ``technology_description`` is
    missing/empty or if the formatted text fails the word/char count threshold.
    """
    technology_description = data.get("technology_description")
    if not technology_description:
        return None

    resp = client.messages.create(
        model=model,
        max_tokens=300,
        system=_SUMMARY_SYSTEM,
        messages=[{"role": "user", "content": technology_description}],
    )
    summary = resp.content[0].text

    resp = client.messages.create(
        model=model,
        max_tokens=16000,
        system=_FORMAT_SYSTEM,
        messages=[{"role": "user", "content": technology_description}],
    )
    formatted = resp.content[0].text

    counts = verify_counts(technology_description, formatted)
    if not counts["ok"]:
        return None

    return {
        "uuid": data["uuid"],
        "enriched_at": datetime.utcnow().isoformat(),
        "technology_description_word_count": counts["word_count"],
        "technology_description_formatted_word_count": counts["formatted_word_count"],
        "technology_description_word_count_diff": counts["word_count_diff"],
        "technology_description_word_count_diff_pct": counts["word_count_diff_pct"],
        "technology_description_char_count": counts["char_count"],
        "technology_description_formatted_char_count": counts["formatted_char_count"],
        "technology_description_char_count_diff": counts["char_count_diff"],
        "technology_description_char_count_diff_pct": counts["char_count_diff_pct"],
        "technology_description_summary": summary,
        "technology_description_formatted": formatted,
    }
