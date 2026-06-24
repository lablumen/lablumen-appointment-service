"""Patient profiles owned by the authenticated account.

An account owner (the logged-in Cognito user) can manage multiple patient profiles (self, family
members). Profiles are the booking unit — each ordered test is tied to one profile.
"""

import uuid

from fastapi import APIRouter, Depends, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..auth import CurrentUser, get_current_user
from ..db import get_session
from ..models import PatientProfile
from ..schemas import PatientProfileCreate, PatientProfileOut

router = APIRouter(tags=["patients"])


@router.post("/patients", response_model=PatientProfileOut, status_code=status.HTTP_201_CREATED)
async def create_patient_profile(
    payload: PatientProfileCreate,
    user: CurrentUser = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> PatientProfile:
    profile = PatientProfile(
        account_owner_id=uuid.UUID(user.sub),
        first_name=payload.first_name,
        last_name=payload.last_name,
        phone_number=payload.phone_number,
        date_of_birth=payload.date_of_birth,
        biological_gender=payload.biological_gender,
        relationship_to_owner=payload.relationship_to_owner,
    )
    session.add(profile)
    await session.commit()
    await session.refresh(profile)
    return profile


@router.get("/patients", response_model=list[PatientProfileOut])
async def list_patient_profiles(
    user: CurrentUser = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> list[PatientProfile]:
    rows = await session.execute(
        select(PatientProfile)
        .where(PatientProfile.account_owner_id == uuid.UUID(user.sub))
        .order_by(PatientProfile.created_at)
    )
    return list(rows.scalars().all())
