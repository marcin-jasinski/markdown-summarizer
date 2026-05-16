## API Design

### RESTful Principles
Use resource-based URLs with appropriate HTTP methods (GET, POST, PUT, PATCH, DELETE).

### Consistent Naming
Use lowercase, hyphenated or underscored names consistently across endpoints.

### Versioning
Implement versioning (URL path or headers) to manage breaking changes.

### Plural Nouns
Use plural nouns for resources (`/users`, `/products`).

### Limited Nesting
Keep URL nesting to 2-3 levels maximum for readability.

### Query Parameters
Use query parameters for filtering, sorting, and pagination.

### Proper Status Codes
Return appropriate HTTP status codes (200, 201, 400, 404, 500).

### Rate Limit Headers
Include rate limit information in response headers.

---

## FastAPI-Specific Conventions

### Thin Routers

Route handlers do only: input validation, authentication check, delegation to application service. No business logic.

```python
# CORRECT
@router.post("/quiz/sessions/{session_id}/answer")
async def submit_answer(
    session_id: UUID,
    payload: AnswerPayload,
    quiz_svc: QuizService = Depends(get_quiz_service),
    current_user: User = Depends(require_auth),
) -> EvaluationResponse:
    result = await quiz_svc.evaluate_answer(session_id, payload.answer, current_user.user_id)
    return EvaluationResponse.from_result(result)

# NEVER: business logic in router
@router.post("/quiz/...")
async def submit_answer(...):
    score = calculate_score(payload.answer, reference)  # ❌ business logic
```

### Dependency Injection

Always use `Depends()` for services, repos, and settings. Never import as module globals:

```python
# NEVER in routers
quiz_service = QuizService(...)  # ❌ module-level

# CORRECT
async def handler(svc: QuizService = Depends(get_quiz_service)): ...
```

### Async Handlers

All route handlers must be `async def`. Never use blocking I/O inside async handlers.
