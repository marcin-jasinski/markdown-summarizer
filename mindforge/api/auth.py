"""
Authentication subsystem for MindForge API.

Implements:
- Discord OAuth 2.0 provider
- Basic (email / password) auth provider
- JWT access + refresh token issuance with HttpOnly cookies
- Auto-refresh on expiry < 5 min
- Refresh token rotation
- Account linking (connect additional providers)
- ``IdentityResolver`` shared by API, Discord bot, and Slack bot

Security notes:
- Passwords hashed with bcrypt (cost ≥ 12).
- JWT ``state`` param validated on every OAuth callback (CSRF protection).
- Refresh tokens are one-time-use (rotation on each use).
- ``Secure`` cookie flag is configurable for local development.
"""

from __future__ import annotations

import hashlib
import hmac
import logging
import secrets
import time
import urllib.parse
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Protocol
from uuid import UUID

import httpx

try:
    import bcrypt as _bcrypt

    _BCRYPT_AVAILABLE = True
except ImportError:  # pragma: no cover
    _BCRYPT_AVAILABLE = False

try:
    import jwt as _jwt

    _JWT_AVAILABLE = True
except ImportError:  # pragma: no cover
    _JWT_AVAILABLE = False

from mindforge.domain.models import User
from mindforge.domain.ports import ExternalIdentityRepository
from mindforge.infrastructure.config import AppSettings

log = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Data structures
# ---------------------------------------------------------------------------


@dataclass
class UserInfo:
    """Provider-independent user profile returned after OAuth exchange."""

    provider: str
    external_id: str
    display_name: str
    email: str | None = None
    avatar_url: str | None = None


@dataclass
class TokenPair:
    access_token: str
    refresh_token: str
    access_expires_at: datetime
    refresh_expires_at: datetime


# ---------------------------------------------------------------------------
# AuthProvider Protocol
# ---------------------------------------------------------------------------


class AuthProvider(Protocol):
    @property
    def name(self) -> str: ...

    def get_authorization_url(self, state: str) -> str: ...

    async def exchange_code(self, code: str, redirect_uri: str) -> UserInfo: ...


# ---------------------------------------------------------------------------
# Discord OAuth 2.0 provider
# ---------------------------------------------------------------------------

_DISCORD_AUTH_URL = "https://discord.com/oauth2/authorize"
_DISCORD_TOKEN_URL = "https://discord.com/api/oauth2/token"
_DISCORD_USER_URL = "https://discord.com/api/users/@me"


class DiscordAuthProvider:
    """Discord OAuth 2.0 provider."""

    def __init__(
        self,
        client_id: str,
        client_secret: str,
    ) -> None:
        self._client_id = client_id
        self._client_secret = client_secret

    @property
    def name(self) -> str:
        return "discord"

    def get_authorization_url(self, state: str) -> str:
        params = {
            "client_id": self._client_id,
            "redirect_uri": "",  # set at call time via redirect_uri param
            "response_type": "code",
            "scope": "identify email",
            "state": state,
            "prompt": "none",
        }
        return f"{_DISCORD_AUTH_URL}?{urllib.parse.urlencode(params)}"

    def get_authorization_url_with_redirect(self, state: str, redirect_uri: str) -> str:
        params = {
            "client_id": self._client_id,
            "redirect_uri": redirect_uri,
            "response_type": "code",
            "scope": "identify email",
            "state": state,
            "prompt": "none",
        }
        return f"{_DISCORD_AUTH_URL}?{urllib.parse.urlencode(params)}"

    async def exchange_code(self, code: str, redirect_uri: str) -> UserInfo:
        async with httpx.AsyncClient(timeout=10.0) as client:
            token_resp = await client.post(
                _DISCORD_TOKEN_URL,
                data={
                    "client_id": self._client_id,
                    "client_secret": self._client_secret,
                    "grant_type": "authorization_code",
                    "code": code,
                    "redirect_uri": redirect_uri,
                },
                headers={"Content-Type": "application/x-www-form-urlencoded"},
            )
            token_resp.raise_for_status()
            tokens = token_resp.json()
            access_token = tokens["access_token"]

            user_resp = await client.get(
                _DISCORD_USER_URL,
                headers={"Authorization": f"Bearer {access_token}"},
            )
            user_resp.raise_for_status()
            data = user_resp.json()

        avatar_hash = data.get("avatar")
        avatar_url: str | None = None
        if avatar_hash:
            avatar_url = (
                f"https://cdn.discordapp.com/avatars/{data['id']}/{avatar_hash}.png"
            )

        return UserInfo(
            provider="discord",
            external_id=str(data["id"]),
            display_name=data.get("global_name") or data.get("username", ""),
            email=data.get("email"),
            avatar_url=avatar_url,
        )


# ---------------------------------------------------------------------------
# Basic auth provider (email + bcrypt password)
# ---------------------------------------------------------------------------


class BasicAuthProvider:
    """Email / password authentication using bcrypt."""

    def __init__(self, cost_factor: int = 12) -> None:
        if not _BCRYPT_AVAILABLE:
            raise ImportError(
                "bcrypt package is required for BasicAuthProvider. "
                "Install it with: pip install bcrypt"
            )
        self._cost = cost_factor

    def hash_password(self, password: str) -> str:
        """Return a bcrypt hash of *password*."""
        return _bcrypt.hashpw(
            password.encode("utf-8"),
            _bcrypt.gensalt(rounds=self._cost),
        ).decode("utf-8")

    def verify_password(self, password: str, hashed: str) -> bool:
        """Return True if *password* matches *hashed*."""
        try:
            return _bcrypt.checkpw(
                password.encode("utf-8"),
                hashed.encode("utf-8"),
            )
        except Exception:
            return False


# ---------------------------------------------------------------------------
# JWT token service
# ---------------------------------------------------------------------------


class JWTService:
    """Issues and verifies JWT access + refresh tokens."""

    _ACCESS_SUBJECT = "access"
    _REFRESH_SUBJECT = "refresh"
    _MIN_HS256_KEY_BYTES = 32

    def __init__(
        self,
        secret: str,
        access_ttl_minutes: int = 60,
        refresh_ttl_days: int = 30,
    ) -> None:
        if not _JWT_AVAILABLE:
            raise ImportError(
                "PyJWT package is required. Install it with: pip install pyjwt[crypto]"
            )
        normalized_secret = secret.strip()
        if not normalized_secret:
            raise ValueError("JWT secret must not be empty")
        if len(normalized_secret.encode("utf-8")) < self._MIN_HS256_KEY_BYTES:
            raise ValueError("JWT secret must be at least 32 bytes for HS256")

        self._secret = normalized_secret
        self._access_ttl_minutes = access_ttl_minutes
        self._refresh_ttl_days = refresh_ttl_days

    def issue_pair(self, user_id: UUID) -> TokenPair:
        now = int(time.time())
        access_exp = now + self._access_ttl_minutes * 60
        refresh_exp = now + self._refresh_ttl_days * 86400

        access_token = _jwt.encode(
            {
                "sub": str(user_id),
                "type": self._ACCESS_SUBJECT,
                "iat": now,
                "exp": access_exp,
            },
            self._secret,
            algorithm="HS256",
        )
        refresh_token = _jwt.encode(
            {
                "sub": str(user_id),
                "type": self._REFRESH_SUBJECT,
                "iat": now,
                "exp": refresh_exp,
                "jti": secrets.token_hex(16),
            },
            self._secret,
            algorithm="HS256",
        )
        return TokenPair(
            access_token=access_token,
            refresh_token=refresh_token,
            access_expires_at=datetime.fromtimestamp(access_exp, tz=timezone.utc),
            refresh_expires_at=datetime.fromtimestamp(refresh_exp, tz=timezone.utc),
        )

    def decode_access(self, token: str) -> dict[str, Any]:
        """Decode and validate an access token; raise jwt.InvalidTokenError on failure."""
        payload = _jwt.decode(token, self._secret, algorithms=["HS256"])
        if payload.get("type") != self._ACCESS_SUBJECT:
            raise _jwt.InvalidTokenError("Not an access token")
        return payload

    def decode_refresh(self, token: str) -> dict[str, Any]:
        """Decode and validate a refresh token; raise jwt.InvalidTokenError on failure."""
        payload = _jwt.decode(token, self._secret, algorithms=["HS256"])
        if payload.get("type") != self._REFRESH_SUBJECT:
            raise _jwt.InvalidTokenError("Not a refresh token")
        return payload

    def is_expiring_soon(
        self, payload: dict[str, Any], threshold_seconds: int = 300
    ) -> bool:
        """Return True if the token expires within *threshold_seconds*."""
        exp = payload.get("exp", 0)
        return (exp - int(time.time())) < threshold_seconds


# ---------------------------------------------------------------------------
# OAuth state (CSRF) helpers
# ---------------------------------------------------------------------------


def generate_oauth_state() -> str:
    """Generate a cryptographically random state token for OAuth CSRF protection."""
    return secrets.token_urlsafe(32)


def validate_oauth_state(expected: str, received: str) -> bool:
    """Constant-time comparison to validate OAuth state parameter."""
    return hmac.compare_digest(expected, received)


# ---------------------------------------------------------------------------
# Identity resolver — shared by API, Discord, and Slack adapters
# ---------------------------------------------------------------------------


class IdentityResolver:
    """Resolves external platform identities to internal ``user_id`` UUIDs.

    Auto-provisions a new user on first contact.
    """

    def __init__(self, identity_repo: ExternalIdentityRepository) -> None:
        self._repo = identity_repo

    async def resolve(
        self,
        user_info: UserInfo,
    ) -> UUID:
        """Return the internal ``user_id`` for the given external identity.

        Creates a new user if no mapping exists yet.
        """
        user_id = await self._repo.find_user_id(
            user_info.provider, user_info.external_id
        )
        if user_id is not None:
            return user_id

        # Auto-provision new user
        user_id = await self._repo.create_user_and_link(
            provider=user_info.provider,
            external_id=user_info.external_id,
            display_name=user_info.display_name,
            email=user_info.email,
            avatar_url=user_info.avatar_url,
        )
        log.info(
            "Auto-provisioned user",
            extra={
                "user_id": str(user_id),
                "provider": user_info.provider,
                "external_id": user_info.external_id,
            },
        )
        return user_id

    async def link(
        self,
        user_id: UUID,
        user_info: UserInfo,
    ) -> None:
        """Link an additional provider to an existing ``user_id``."""
        # Guard: reject if already linked to a different user
        existing_uid = await self._repo.find_user_id(
            user_info.provider, user_info.external_id
        )
        if existing_uid is not None and existing_uid != user_id:
            raise ValueError(
                f"The {user_info.provider} identity '{user_info.external_id}' "
                "is already linked to a different account."
            )
        await self._repo.link(
            user_id=user_id,
            provider=user_info.provider,
            external_id=user_info.external_id,
            email=user_info.email,
            metadata={
                "avatar_url": user_info.avatar_url,
                "display_name": user_info.display_name,
            },
        )


# ---------------------------------------------------------------------------
# Factory helpers for composition roots
# ---------------------------------------------------------------------------


def make_discord_provider(settings: AppSettings) -> DiscordAuthProvider | None:
    if not settings.discord_client_id or not settings.discord_client_secret:
        return None
    return DiscordAuthProvider(
        client_id=settings.discord_client_id,
        client_secret=settings.discord_client_secret,
    )


def make_jwt_service(settings: AppSettings) -> JWTService:
    return JWTService(
        secret=settings.jwt_secret,
        access_ttl_minutes=settings.jwt_access_token_ttl_minutes,
        refresh_ttl_days=settings.jwt_refresh_token_ttl_days,
    )


def make_basic_auth_provider(settings: AppSettings) -> BasicAuthProvider | None:
    if not settings.enable_basic_auth:
        return None
    return BasicAuthProvider(cost_factor=settings.bcrypt_cost_factor)
