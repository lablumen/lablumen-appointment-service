from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..db import get_session
from ..models import LabTest
from ..schemas import LabTestOut

router = APIRouter(tags=["lab-tests"])


@router.get("/lab-tests", response_model=list[LabTestOut])
async def list_lab_tests(session: AsyncSession = Depends(get_session)) -> list[LabTest]:
    """Public catalog of active lab tests (seeded by migration 0002)."""
    result = await session.execute(
        select(LabTest).where(LabTest.is_active.is_(True)).order_by(LabTest.name)
    )
    return list(result.scalars().all())
