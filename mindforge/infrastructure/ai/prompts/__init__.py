"""
Prompt loader utility.

All prompt text lives in ``{locale}/*.md`` subdirectories of this package.
The prompts are organized by language (e.g. ``pl/`` for Polish).

File resolution order for ``load_prompt("summarizer_system.md", locale="en")``:

1. ``en/summarizer_system.md``   (requested locale)
2. ``pl/summarizer_system.md``   (fallback to default ``pl``)

Usage::

    from mindforge.infrastructure.ai.prompts import load_prompt

    SYSTEM_PROMPT = load_prompt("summarizer_system.md", "pl")
"""

from pathlib import Path

_PROMPTS_DIR = Path(__file__).parent
_DEFAULT_LOCALE = "pl"


def load_prompt(filename: str, locale: str = _DEFAULT_LOCALE) -> str:
    """Return the contents of a locale-aware prompt markdown file.

    Resolution order:
    1. ``{locale}/{filename}``    — requested locale variant
    2. ``pl/{filename}``          — default Polish fallback (when *locale* != 'pl')

    Parameters
    ----------
    filename:
        Base name of the prompt file (e.g. ``"summarizer_system.md"``).
        The ``.md`` extension is required.
    locale:
        BCP-47-style locale tag (e.g. ``"pl"``, ``"en"``).  Defaults to
        ``"pl"``.

    Raises
    ------
    FileNotFoundError
        If no matching prompt file is found after exhausting all candidates.
    """
    candidates: list[Path] = [_PROMPTS_DIR / locale / filename]
    if locale != _DEFAULT_LOCALE:
        candidates.append(_PROMPTS_DIR / _DEFAULT_LOCALE / filename)
    for path in candidates:
        if path.exists():
            return path.read_text(encoding="utf-8")
    raise FileNotFoundError(
        f"No prompt file found for {filename!r} (locale={locale!r}). "
        f"Searched: {[str(p) for p in candidates]}"
    )
