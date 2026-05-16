"""
Prompt template for the Summarizer agent.

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
    return load_prompt("summarizer_system.md", locale)


def user_template(locale: str = "pl") -> str:
    """Return the user message template for the given locale."""
    return load_prompt("summarizer_user.md", locale)


def image_context_template(locale: str = "pl") -> str:
    """Return the image context snippet template for the given locale."""
    return load_prompt("summarizer_image_context.md", locale)


def article_context_template(locale: str = "pl") -> str:
    """Return the article context snippet template for the given locale."""
    return load_prompt("summarizer_article_context.md", locale)


def prior_concepts_template(locale: str = "pl") -> str:
    """Return the prior-concepts snippet template for the given locale."""
    return load_prompt("summarizer_prior_concepts.md", locale)
