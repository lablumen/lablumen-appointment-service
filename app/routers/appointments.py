"""Appointment booking, listing, status updates, and the staff operations queue.

Booking holds a Redis slot-lock for the date+slot while it writes the appointment and one
appointment_test_mapping row per selected test (snapshotting price_at_booking from the catalog),
then publishes an `appointment.booked` event to SQS for notification-service.
"""

import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from ..auth import CurrentUser, get_current_user, require_roles
from ..db import get_session
from ..models import Appointment, AppointmentTestMapping, LabTest
from ..redis_client import acquire_slot_lock, release_slot_lock
from ..schemas import AppointmentCreate, AppointmentOut
from ..sqs import publish_event

router = APIRouter(tags=["appointments"])

require_staff = require_roles("LAB_STAFF", "LAB_ADMIN")
_VALID_STATUSES = {"Booked", "Cancelled", "Checked-In", "Completed"}


@router.post("/appointments", response_model=AppointmentOut, status_code=status.HTTP_201_CREATED)
async def book_appointment(
    payload: AppointmentCreate,
    user: CurrentUser = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> Appointment:
    """Book a slot: persist appointment + per-test mappings under a Redis slot-lock."""
    if not payload.tests:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Select at least one test")

    slot_key = f"{payload.appointment_date}T{payload.time_slot}"
    if not await acquire_slot_lock(slot_key):
        raise HTTPException(status.HTTP_409_CONFLICT, "Slot is being booked by another request")
    try:
        # Snapshot catalog prices for the selected tests.
        test_ids = [sel.test_id for sel in payload.tests]
        price_rows = (
            await session.execute(
                select(LabTest.test_id, LabTest.base_cost).where(LabTest.test_id.in_(test_ids))
            )
        ).all()
        price_map = {row.test_id: row.base_cost for row in price_rows}
        unknown = [str(tid) for tid in test_ids if tid not in price_map]
        if unknown:
            raise HTTPException(status.HTTP_400_BAD_REQUEST, f"Unknown test(s): {unknown}")

        appointment = Appointment(
            account_owner_id=uuid.UUID(user.sub),
            appointment_date=payload.appointment_date,
            time_slot=payload.time_slot,
            status="Booked",
        )
        session.add(appointment)
        await session.flush()  # assign appointment_id

        for sel in payload.tests:
            session.add(
                AppointmentTestMapping(
                    appointment_id=appointment.appointment_id,
                    test_id=sel.test_id,
                    patient_id=sel.patient_id,
                    price_at_booking=price_map[sel.test_id],
                )
            )
        await session.commit()
        await session.refresh(appointment)
    finally:
        await release_slot_lock(slot_key)

    await publish_event(
        "appointment.booked",
        user.email,
        {
            "appointment_id": str(appointment.appointment_id),
            "appointment_date": str(appointment.appointment_date),
            "time_slot": str(appointment.time_slot),
            "test_count": str(len(payload.tests)),
        },
    )
    return appointment


@router.get("/appointments", response_model=list[AppointmentOut])
async def list_my_appointments(
    user: CurrentUser = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> list[Appointment]:
    """List the caller's appointments; staff see all appointments."""
    is_staff = bool({"LAB_STAFF", "LAB_ADMIN"}.intersection(user.groups))
    stmt = select(Appointment).order_by(
        Appointment.appointment_date.desc(), Appointment.time_slot.desc()
    )
    if not is_staff:
        stmt = stmt.where(Appointment.account_owner_id == uuid.UUID(user.sub))
    return list((await session.execute(stmt)).scalars().all())


@router.get("/appointments/ops")
async def operations_queue(
    _staff: CurrentUser = Depends(require_staff),
    session: AsyncSession = Depends(get_session),
) -> list[dict]:
    """Staff operations queue: one row per ordered test, with patient/test/report status.

    Drives the staff grid and the report-upload picker (rows where report_id is null still
    need a PDF uploaded).
    """
    sql = text(
        """
        SELECT
            atm.mapping_id,
            a.appointment_id,
            a.appointment_date,
            a.time_slot,
            a.status,
            (pp.first_name || ' ' || pp.last_name) AS patient_name,
            lt.name AS test_name,
            atm.price_at_booking,
            lr.report_id
        FROM appointment_test_mapping atm
        JOIN appointments a ON a.appointment_id = atm.appointment_id
        JOIN lab_tests lt ON lt.test_id = atm.test_id
        JOIN patient_profiles pp ON pp.patient_id = atm.patient_id
        LEFT JOIN lab_reports lr ON lr.mapping_id = atm.mapping_id
        ORDER BY a.appointment_date DESC, a.time_slot DESC
        """
    )
    rows = (await session.execute(sql)).mappings().all()
    return [
        {
            "mapping_id": str(r["mapping_id"]),
            "appointment_id": str(r["appointment_id"]),
            "appointment_date": str(r["appointment_date"]),
            "time_slot": str(r["time_slot"]),
            "status": r["status"],
            "patient_name": r["patient_name"],
            "test_name": r["test_name"],
            "price_at_booking": str(r["price_at_booking"]),
            "report_id": str(r["report_id"]) if r["report_id"] else None,
            "has_report": r["report_id"] is not None,
        }
        for r in rows
    ]


@router.patch("/appointments/{appointment_id}/status", response_model=AppointmentOut)
async def update_appointment_status(
    appointment_id: uuid.UUID,
    new_status: str,
    _staff: CurrentUser = Depends(require_staff),
    session: AsyncSession = Depends(get_session),
) -> Appointment:
    """Staff-only: transition an appointment to a new status."""
    if new_status not in _VALID_STATUSES:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            f"Invalid status; must be one of {sorted(_VALID_STATUSES)}",
        )
    appointment = await session.get(Appointment, appointment_id)
    if appointment is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Appointment not found")
    appointment.status = new_status
    await session.commit()
    await session.refresh(appointment)
    return appointment
