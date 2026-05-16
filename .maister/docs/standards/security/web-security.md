# Web Security Standards

## Server-Authoritative State

The server owns all grading, scoring, and session state. Client payloads must never contain security-critical state.

**Fields that must never appear in API responses to browsers:**
- `reference_answer`
- `grounding_context`
- `raw_prompt`
- `raw_completion`
- `cost`

```python
# NEVER in any API response
return {"reference_answer": artifact.summary_data.reference_answer}  # ❌

# CORRECT: return only evaluated results
return {"score": result.score, "feedback": result.feedback}
```

Redaction is enforced in `InteractionStore.list_for_user()` — **not only in routers** (defense-in-depth). The store never returns unredacted interaction data for user-facing queries.

## Password Hashing

Passwords must be hashed with bcrypt at cost factor **≥ 12**. Plaintext passwords must never be stored, logged, or transmitted.

```python
# CORRECT
hashed = bcrypt.hashpw(password.encode(), bcrypt.gensalt(rounds=12))

# NEVER
store_password(user_input_password)  # ❌ plaintext
log.info(f"User {email} registered with password {password}")  # ❌ log leak
```

## JWT Token Storage

JWT tokens must be stored in **HttpOnly, Secure, SameSite=Lax cookies**. Never return JWT in response body for the SPA to store in `localStorage` or `sessionStorage`.

The `Secure` flag is configurable via `AUTH_SECURE_COOKIES=false` for local HTTP development only.

```python
# CORRECT
response.set_cookie(
    key="token",
    value=jwt_token,
    httponly=True,
    secure=settings.auth_secure_cookies,
    samesite="lax",
)

# NEVER
return {"token": jwt_token}  # ❌ SPA stores in localStorage
```

## OAuth CSRF Protection

OAuth `state` parameter must be validated on **every** OAuth callback to prevent CSRF attacks.

```python
# CORRECT
if callback_state != session_state:
    raise HTTPException(status_code=400, detail="Invalid OAuth state")

# NEVER: skip state validation
```

## Untrusted Input Handling

All uploaded filenames, external URLs, and image URLs are **untrusted**. Always use the security helpers — never write ad-hoc filesystem or HTTP handling.

```python
# CORRECT
from mindforge.infrastructure.security.upload_sanitizer import UploadSanitizer
from mindforge.infrastructure.security.egress_policy import EgressPolicy

sanitizer.sanitize_filename(user_provided_filename)
egress_policy.check(external_url)

# NEVER
open(user_provided_filename, "rb")  # ❌ path traversal risk
requests.get(user_provided_url)     # ❌ SSRF risk
```

## Bot Platform Security

Discord and Slack bots must:
1. Enforce guild/channel/workspace allowlists before processing any command
2. Verify interaction ownership (user can only access their own data)
3. Always resolve platform IDs → internal UUIDs via `IdentityResolver` before calling any application service

```python
# CORRECT
user_id = await identity_resolver.resolve("discord", str(interaction.user.id))
result = await quiz_service.start_session(user_id=user_id, ...)

# NEVER
result = await quiz_service.start_session(user_id=interaction.user.id, ...)  # ❌ platform ID
```
