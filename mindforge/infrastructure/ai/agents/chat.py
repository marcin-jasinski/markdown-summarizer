"""
Prompt templates for the Chat service.

All prompt text is stored in ``*.md`` files alongside this module and loaded
at import time.  To change a prompt, edit the corresponding markdown file.
"""

from mindforge.infrastructure.ai.prompts import load_prompt

_BASE_VERSION = "1.1.0"

VERSION = f"{_BASE_VERSION}+pl"


def version(locale: str = "pl") -> str:
    """Return the locale-encoded prompt version string."""
    return f"{_BASE_VERSION}+{locale}"


SYSTEM_WITH_CONTEXT = load_prompt("chat_system_with_context.md", "pl")
SYSTEM_NO_CONTEXT = load_prompt("chat_system_no_context.md", "pl")
