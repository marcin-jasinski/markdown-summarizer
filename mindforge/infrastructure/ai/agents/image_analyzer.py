"""
Prompt template for the ImageAnalyzer agent.

All prompt text is stored in ``*.md`` files alongside this module and loaded
at import time.  To change a prompt, edit the corresponding markdown file.

Version-tagged — changing prompt files must be reflected in the agent's
``PROMPT_VERSION`` constant so that checkpoint fingerprints are invalidated.
"""

from mindforge.infrastructure.ai.prompts import load_prompt

_BASE_VERSION = "1.1.0"

VERSION = f"{_BASE_VERSION}+pl"


def system_prompt(locale: str = "pl") -> str:
    """Return the system prompt for the given locale, falling back to Polish."""
    return load_prompt("image_analyzer_system.md", locale)
