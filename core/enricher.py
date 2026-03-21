"""Pure text utility functions for LCA dataset enrichment.

No external dependencies — standard library only.
"""

from typing import TypedDict

_STRIP_CHARS = str.maketrans("", "", "#*_`\n\r")


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

    Characters removed: ``#``, ``*``, ``_``, backtick, ``\\n``, ``\\r``.
    All other characters (spaces, punctuation, alphanumeric, Unicode) are
    preserved exactly as-is.
    """
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
