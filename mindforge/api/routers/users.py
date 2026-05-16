"""
Users router — stub endpoints for user-specific data.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends

from mindforge.api.deps import get_current_user
from mindforge.api.schemas import UserStatsResponse

router = APIRouter()


@router.get("/me/stats", response_model=UserStatsResponse)
async def get_my_stats(current_user=Depends(get_current_user)) -> UserStatsResponse:
    return UserStatsResponse(streak_days=0, due_today=0)
