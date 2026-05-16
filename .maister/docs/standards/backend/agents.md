# AI Agent Standards

## Agent Class Structure

All agents must expose this exact interface:

```python
class MyAgent:
    __version__ = "1.0.0"
    PROMPT_VERSION = "v1"

    def __init__(self, *, prompts: PromptLoader | None = None) -> None:
        self._prompts = prompts or DefaultPromptLoader()

    @property
    def name(self) -> str:
        return _CAPABILITY.name

    @property
    def capabilities(self) -> tuple[AgentCapability, ...]:
        return (_CAPABILITY,)

    async def execute(self, context: AgentContext) -> AgentResult:
        ...
```

Define the capability constant at module level:

```python
_CAPABILITY = AgentCapability(
    name="my-agent",
    description="...",
    input_keys=frozenset({"summary"}),
    output_key="my_output",
)
```

## Version Management

Increment `__version__` **only** when the agent's logic or prompt changes. Never bump for unrelated code style changes — this would invalidate all cached step checkpoints.

## Model Selection

Request models by role, never by provider string:

```python
# CORRECT
result = await context.gateway.complete(model="large", messages=[...])
result = await context.gateway.complete(model="small", messages=[...])
result = await context.gateway.complete(model="vision", messages=[...])

# NEVER
result = await context.gateway.complete(model="openai/gpt-4o", ...)  # ❌ hardcoded
```

## LLM Gateway

All LLM calls flow through `AIGateway`. Never import or call a provider SDK directly:

```python
# CORRECT
result = await context.gateway.complete(model="large", messages=[...])

# NEVER
import openai
openai.chat.completions.create(...)  # ❌
```

## Prompt Files

Prompt files follow the pattern `{name}.{locale}.md`. Polish (`pl`) is the default locale. Every template must have at least a `.pl.md` baseline:

```
infrastructure/ai/prompts/pl/summarizer_system.pl.md   ✓
infrastructure/ai/prompts/en/summarizer_system.en.md   ✓ (when added)
infrastructure/ai/prompts/summarizer_system.md         ❌ (locale-neutral)
```

## Lesson Identity

Resolve `lesson_id` via the five-step deterministic algorithm:
1. `frontmatter["lesson_id"]`
2. `frontmatter["title"]` (slugified)
3. PDF metadata `Title`
4. Filename (without extension)
5. **REJECT** — raise `LessonIdentityError`; never fall back to `"unknown"`

```python
# NEVER
lesson_id = metadata.get("lesson_id", "unknown")  # ❌
```
