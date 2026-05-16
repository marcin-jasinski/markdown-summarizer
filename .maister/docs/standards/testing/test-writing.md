## Test Writing

### Test Behavior
Focus on what code does, not how it does it, to allow safe refactoring.

### Clear Names
Use descriptive names explaining what's tested and expected (`shouldReturnErrorWhenUserNotFound`).

### Mock External Dependencies
Isolate tests by mocking databases, APIs, and external services.

### Fast Execution
Keep unit tests fast (milliseconds) so developers run them frequently.

### Risk-Based Testing
Prioritize testing based on business criticality and likelihood of bugs.

### Balance Coverage and Velocity
Adjust test coverage based on project needs and team workflow.

### Critical Path Focus
Ensure core user workflows and critical business logic are well-tested.

### Appropriate Depth
Match edge case testing to the risk profile of the code.

---

## Python Testing Conventions (MindForge)

### Test Discovery and Markers

```
tests/unit/       — no I/O, fast; run on every PR
tests/integration/ — real DB via testcontainers; @pytest.mark.integration
tests/e2e/        — full stack; @pytest.mark.e2e
```

Run without DB: `pytest -m "not integration"`

### Async Tests

`asyncio_mode = "auto"` is configured — **do not add `@pytest.mark.asyncio` decorators**. Just write `async def test_*`:

```python
# CORRECT: no decorator needed
async def test_quiz_session_starts() -> None:
    result = await service.start_session(...)
    assert result.session_id is not None

# AVOID: redundant decorator (asyncio_mode=auto makes it unnecessary)
@pytest.mark.asyncio  # ❌ not needed
async def test_something() -> None: ...
```

### LLM Test Double

Use `StubAIGateway` for deterministic LLM responses. Never mock at the `litellm` call level:

```python
from tests.conftest import StubAIGateway

gateway = StubAIGateway()
gateway.set_response("*", _stub_completion("expected summary text"))

# Wildcard "*" matches any prompt; or use specific patterns to match different agents
```

### Async Port Mocking

Use `AsyncMock` for all async port dependencies (retrieval, event publisher, session store, etc.):

```python
from unittest.mock import AsyncMock

def _make_quiz_service(
    *,
    gateway: StubAIGateway | None = None,
    retrieval: AsyncMock | None = None,
    quiz_sessions: AsyncMock | None = None,
) -> QuizService:
    return QuizService(
        gateway=gateway or AsyncMock(),
        retrieval=retrieval or AsyncMock(),
        quiz_sessions=quiz_sessions or AsyncMock(),
    )
```

### Test Factory Functions

Use `_make_*` factory functions (not fixtures) for domain objects and services. Accept keyword-only overrides for the fields under test:

```python
def _make_artifact(
    *,
    document_id: UUID | None = None,
    lesson_id: str = "test-lesson",
) -> DocumentArtifact:
    return DocumentArtifact(
        document_id=document_id or uuid4(),
        lesson_id=lesson_id,
        # ... sensible defaults
    )

# In test:
artifact = _make_artifact(lesson_id="custom-lesson")
```

### Integration Tests

Use `testcontainers` for real PostgreSQL/Neo4j containers. Mark with `@pytest.mark.integration`. Never use production credentials in tests.
