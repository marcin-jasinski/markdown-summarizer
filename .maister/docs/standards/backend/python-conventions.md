# Python Code Conventions

MindForge-specific Python conventions enforced across the entire `mindforge/` package.

## File Header

Every Python module must start with (in order):
1. Module docstring (triple-quoted) describing purpose, layer constraints, and key design decisions
2. `from __future__ import annotations`
3. Standard library imports
4. Third-party imports (with `try/except ImportError` guards for optional packages)
5. Local imports

```python
"""Application layer — pipeline orchestrator.

No database drivers, no LLM SDK imports — all I/O through injected ports.
"""
from __future__ import annotations

import logging
from contextlib import asynccontextmanager

try:
    import langfuse
    _LANGFUSE_AVAILABLE = True
except ImportError:
    _LANGFUSE_AVAILABLE = False

from mindforge.domain.models import DocumentArtifact
```

## Module Constants

Module-level constants use a leading underscore with SCREAMING_SNAKE_CASE:

```python
_MAX_CONTENT_CHARS = 60_000
_SESSION_PREFIX = "quiz:session:"
_CAPABILITY = AgentCapability(name="summarizer", ...)
```

## Section Dividers

Separate logical sections within a Python file with 79-character dashed comment banners:

```python
# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------

# ---------------------------------------------------------------------------
# Exceptions
# ---------------------------------------------------------------------------
```

## Logging

Module-level logger is named `log` (not `logger`):

```python
log = logging.getLogger(__name__)  # CORRECT

logger = logging.getLogger(__name__)  # ❌ wrong name
```

## Exception Classes

Define domain-specific exception classes extending appropriate builtins. Never raise bare `RuntimeError` or `Exception` from business logic:

```python
class DuplicateContentError(ValueError):
    def __init__(self, kb_id: UUID, content_hash: str) -> None:
        super().__init__(f"Content already ingested in KB {kb_id}: {content_hash}")

class QuizAccessDeniedError(PermissionError):
    ...

# NEVER from business logic:
raise RuntimeError("something failed")  # ❌
```

## Dataclasses

Use `@dataclass(frozen=True)` for:
- Domain events
- Value objects
- Result types (returned from application services)
- Agent capability descriptors

Use plain `@dataclass` (mutable) for:
- Aggregate roots with evolving state (Document, KnowledgeBase, DocumentArtifact)

```python
@dataclass(frozen=True)
class IngestionResult:
    document_id: UUID
    lesson_id: str
    is_duplicate: bool

@dataclass
class Document:
    document_id: UUID
    status: DocumentStatus  # mutates over time
```

## Type Annotations

All public functions and methods must have complete type annotations including return type. `-> None` must be explicit, not omitted.

```python
async def execute(self, context: AgentContext) -> AgentResult: ...  # CORRECT
async def save(self, document: Document) -> None: ...  # CORRECT
def process(items):  # ❌ missing annotations
```

## Optional Imports

Optional or heavy packages use `try/except ImportError` guards **at module top level** — never inside functions:

```python
# CORRECT: at top of file
try:
    import litellm
    _LITELLM_AVAILABLE = True
except ImportError:
    _LITELLM_AVAILABLE = False

# NEVER: lazy import inside function
def my_func() -> None:
    import heavy_package  # ❌
```

## Configuration Access

Never call `os.environ` at request time or in module-level code. Load settings via `mindforge/infrastructure/config.py` (Pydantic `AppSettings`) once at startup, then inject:

```python
# NEVER
DATABASE_URL = os.environ.get("DATABASE_URL")  # ❌ module-level

# NEVER inside a route handler
async def handler():
    url = os.environ["DATABASE_URL"]  # ❌

# CORRECT: inject from composition root
async def handler(settings: AppSettings = Depends(get_settings)):
    ...
```

## sys.path

Never manipulate `sys.path`. The package is installed via `pip install -e .` and imported as `mindforge.*`.

```python
sys.path.append("/path/to/repo")  # ❌ NEVER
sys.path.insert(0, ...)           # ❌ NEVER
```
