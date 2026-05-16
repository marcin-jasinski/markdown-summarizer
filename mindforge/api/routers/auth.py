"""Auth router — Discord OAuth, email/password, JWT cookies."""

from __future__ import annotations

import logging
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Cookie, Depends, HTTPException, Request, Response, status
from fastapi.responses import RedirectResponse

from mindforge.api.auth import (
    BasicAuthProvider,
    DiscordAuthProvider,
    IdentityResolver,
    JWTService,
    UserInfo,
    generate_oauth_state,
    make_basic_auth_provider,
    make_discord_provider,
    validate_oauth_state,
)
from mindforge.api.deps import (
    get_current_user,
    get_db_session,
    get_identity_repo,
    get_jwt_service,
    get_settings,
)
from mindforge.api.schemas import (
    LoginRequest,
    RegisterRequest,
    TokenResponse,
    UserResponse,
)
from mindforge.domain.models import User
from mindforge.infrastructure.config import AppSettings
from mindforge.infrastructure.persistence.identity_repo import (
    PostgresIdentityRepository,
)
from mindforge.infrastructure.persistence.models import ExternalIdentityModel, UserModel
from sqlalchemy import select

log = logging.getLogger(__name__)
router = APIRouter(prefix="/api/auth", tags=["auth"])

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_STATE_COOKIE = "oauth_state"
_ACCESS_COOKIE = "access_token"
_REFRESH_COOKIE = "refresh_token"


def _set_auth_cookies(response: Response, tokens, settings: AppSettings) -> None:
    secure = settings.auth_secure_cookies
    response.set_cookie(
        _ACCESS_COOKIE,
        tokens.access_token,
        httponly=True,
        secure=secure,
        samesite="lax",
        max_age=settings.jwt_access_token_ttl_minutes * 60,
    )
    response.set_cookie(
        _REFRESH_COOKIE,
        tokens.refresh_token,
        httponly=True,
        secure=secure,
        samesite="lax",
        max_age=settings.jwt_refresh_token_ttl_days * 86400,
        path="/api/auth/refresh",
    )


# ---------------------------------------------------------------------------
# Discord OAuth
# ---------------------------------------------------------------------------


@router.get("/login/discord")
async def discord_login(request: Request, response: Response) -> dict:
    settings: AppSettings = request.app.state.settings
    provider = make_discord_provider(settings)
    if provider is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Discord OAuth nie jest skonfigurowane.",
        )
    state = generate_oauth_state()
    url = provider.get_authorization_url_with_redirect(
        state=state,
        redirect_uri=settings.discord_redirect_uri,
    )
    response.set_cookie(
        _STATE_COOKIE,
        state,
        httponly=True,
        secure=settings.auth_secure_cookies,
        samesite="lax",
        max_age=600,
    )
    return {"authorization_url": url}


@router.get("/callback/discord")
async def discord_callback(
    request: Request,
    response: Response,
    code: str,
    state: str,
    oauth_state: Annotated[str | None, Cookie(alias=_STATE_COOKIE)] = None,
) -> TokenResponse:
    settings: AppSettings = request.app.state.settings

    if not oauth_state or not validate_oauth_state(oauth_state, state):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Nieprawidłowy parametr state (CSRF).",
        )

    provider = make_discord_provider(settings)
    if provider is None:
        raise HTTPException(
            status_code=503, detail="Discord OAuth nie jest skonfigurowane."
        )

    try:
        user_info = await provider.exchange_code(code, settings.discord_redirect_uri)
    except Exception as exc:
        log.warning("Discord OAuth exchange failed: %s", exc)
        raise HTTPException(
            status_code=400, detail="Wymiana kodu OAuth nie powiodła się."
        )

    identity_repo = get_identity_repo(request, await _get_session(request))
    resolver = IdentityResolver(identity_repo)
    user_id = await resolver.resolve(user_info)

    jwt_service: JWTService = request.app.state.jwt_service
    tokens = jwt_service.issue_pair(user_id)
    _set_auth_cookies(response, tokens, settings)
    response.delete_cookie(_STATE_COOKIE)

    return TokenResponse(access_token=tokens.access_token)


@router.get("/link/discord")
async def discord_link(
    request: Request,
    response: Response,
    current_user: Annotated[User, Depends(get_current_user)],
) -> dict:
    settings: AppSettings = request.app.state.settings
    provider = make_discord_provider(settings)
    if provider is None:
        raise HTTPException(
            status_code=503, detail="Discord OAuth nie jest skonfigurowane."
        )
    state = generate_oauth_state()
    url = provider.get_authorization_url_with_redirect(
        state=state, redirect_uri=settings.discord_redirect_uri
    )
    response.set_cookie(
        _STATE_COOKIE,
        state,
        httponly=True,
        secure=settings.auth_secure_cookies,
        samesite="lax",
        max_age=600,
    )
    return {"authorization_url": url}


# ---------------------------------------------------------------------------
# Basic auth (email / password)
# ---------------------------------------------------------------------------


@router.post("/register", status_code=status.HTTP_201_CREATED)
async def register(
    payload: RegisterRequest,
    request: Request,
    response: Response,
) -> TokenResponse:
    settings: AppSettings = request.app.state.settings
    basic = make_basic_auth_provider(settings)
    if basic is None:
        raise HTTPException(status_code=503, detail="Rejestracja nie jest aktywna.")

    password_hash = basic.hash_password(payload.password)

    async with request.app.state.session_factory() as session:
        repo = PostgresIdentityRepository(session)
        # Check if email already in use
        existing = await repo.find_user_id("basic", payload.email)
        if existing is not None:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Konto z tym adresem e-mail już istnieje.",
            )
        user_id = await repo.create_user_and_link(
            provider="basic",
            external_id=payload.email,
            display_name=payload.display_name,
            email=payload.email,
            metadata={"password_hash": password_hash},
        )
        await session.commit()

    jwt_service: JWTService = request.app.state.jwt_service
    tokens = jwt_service.issue_pair(user_id)
    _set_auth_cookies(response, tokens, settings)
    return TokenResponse(access_token=tokens.access_token)


@router.post("/login")
async def login(
    payload: LoginRequest,
    request: Request,
    response: Response,
) -> TokenResponse:
    settings: AppSettings = request.app.state.settings
    basic = make_basic_auth_provider(settings)
    if basic is None:
        raise HTTPException(
            status_code=503, detail="Logowanie hasłem nie jest aktywne."
        )

    async with request.app.state.session_factory() as session:
        repo = PostgresIdentityRepository(session)
        user_id = await repo.find_user_id("basic", payload.email)
        if user_id is None:
            raise HTTPException(
                status_code=401, detail="Nieprawidłowy e-mail lub hasło."
            )

        # Load password hash from external_identities metadata
        result = await session.execute(
            select(ExternalIdentityModel).where(
                ExternalIdentityModel.provider == "basic",
                ExternalIdentityModel.external_id == payload.email,
            )
        )
        identity = result.scalar_one_or_none()
        if identity is None:
            raise HTTPException(
                status_code=401, detail="Nieprawidłowy e-mail lub hasło."
            )

        stored_hash = (identity.metadata_ or {}).get("password_hash", "")
        if not basic.verify_password(payload.password, stored_hash):
            raise HTTPException(
                status_code=401, detail="Nieprawidłowy e-mail lub hasło."
            )

    jwt_service: JWTService = request.app.state.jwt_service
    tokens = jwt_service.issue_pair(user_id)
    _set_auth_cookies(response, tokens, settings)
    return TokenResponse(access_token=tokens.access_token)


# ---------------------------------------------------------------------------
# Token refresh
# ---------------------------------------------------------------------------


@router.post("/refresh")
async def refresh_token(
    request: Request,
    response: Response,
    refresh_token_cookie: Annotated[str | None, Cookie(alias=_REFRESH_COOKIE)] = None,
) -> TokenResponse:
    if not refresh_token_cookie:
        raise HTTPException(status_code=401, detail="Brak tokenu odświeżania.")

    settings: AppSettings = request.app.state.settings
    jwt_service: JWTService = request.app.state.jwt_service
    try:
        payload = jwt_service.decode_refresh(refresh_token_cookie)
    except Exception:
        raise HTTPException(
            status_code=401, detail="Token odświeżania jest nieprawidłowy."
        )

    user_id = UUID(payload["sub"])
    tokens = jwt_service.issue_pair(user_id)
    _set_auth_cookies(response, tokens, settings)
    return TokenResponse(access_token=tokens.access_token)


# ---------------------------------------------------------------------------
# Current user / logout
# ---------------------------------------------------------------------------


@router.get("/me", response_model=UserResponse)
async def me(current_user: Annotated[User, Depends(get_current_user)]) -> UserResponse:
    return UserResponse(
        user_id=current_user.user_id,
        display_name=current_user.display_name,
        email=current_user.email,
        avatar_url=current_user.avatar_url,
        created_at=current_user.created_at,
    )


@router.post("/logout")
async def logout(response: Response) -> dict:
    response.delete_cookie(_ACCESS_COOKIE)
    response.delete_cookie(_REFRESH_COOKIE, path="/api/auth/refresh")
    return {"detail": "Wylogowano pomyślnie."}


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


async def _get_session(request: Request):
    async with request.app.state.session_factory() as session:
        return session
