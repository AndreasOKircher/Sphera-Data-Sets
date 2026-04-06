"""Pure text utility functions for LCA dataset enrichment."""

from datetime import datetime, timezone
from typing import TypedDict
from core.llm import LLMClient

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


SUMMARY_SYSTEM = (
    "You are a technical writer specializing in Life Cycle Assessment (LCA). "
    "Your task is to summarize the text provided by the user. "
    "Always output ONLY the structured summary below — never add introductory sentences, "
    "meta-comments, caveats, or any text outside the format. "
    "Do not comment on the nature or quality of the input. Just summarize it.\n\n"
    "Use exactly this markdown format:\n\n"
    "**Process:** One sentence describing what the process, product, or dataset covers.\n"
    "**Output:** One sentence on what it produces, its function, or what the data represents.\n"
    "**Key characteristics:**\n"
    "- Key technical feature, scope, or component type\n"
    "- Data quality, coverage, or methodology note (only if mentioned)\n"
    "- Geographic or temporal scope (only if mentioned)\n\n"
    "Use only information present in the original text. "
    "Omit any bullet point if the information is not mentioned in the original."
)

FORMAT_SYSTEM = (
    "You are a technical editor. Reformat the following text for readability by adding "
    "paragraph breaks, markdown headers (##) for major sections, and bold (**) for key "
    "terms. Do NOT change, add, or remove any words. Return only the reformatted "
    "markdown, nothing else."
)


def enrich_dataset(data: dict, client: LLMClient) -> dict | None:
    """Enrich a single dataset record with a summary and formatted description.

    Parameters
    ----------
    data:
        A dataset record dict. Must contain ``uuid`` and
        ``technology_description``.
    client:
        An ``LLMClient`` implementation.

    Returns
    -------
    Enriched dict with 12 keys, or ``None`` if ``technology_description`` is
    missing/empty or if the formatted text fails the word/char count threshold.
    """
    technology_description = data.get("technology_description")
    if not technology_description:
        return None

    summary = client.complete(SUMMARY_SYSTEM, technology_description, 300)

    formatted = client.complete(FORMAT_SYSTEM, technology_description, 16000)

    counts = verify_counts(technology_description, formatted)
    if not counts["ok"]:
        return None

    return {
        "uuid": data["uuid"],
        "enriched_at": datetime.now(tz=timezone.utc).isoformat(),
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
