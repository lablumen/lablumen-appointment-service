"""SQLAlchemy ORM models for tables this service queries.

The authoritative schema lives in the Alembic migrations (this service owns them); these models
mirror the migration for ORM access. Single-tenant: no organization scoping.
"""

import datetime
import uuid

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    Date,
    DateTime,
    ForeignKey,
    Numeric,
    String,
    Time,
    func,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    pass


class User(Base):
    __tablename__ = "users"

    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True)
    email: Mapped[str] = mapped_column(String(255), unique=True, nullable=False)
    created_at: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )


class PatientProfile(Base):
    __tablename__ = "patient_profiles"

    patient_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=func.gen_random_uuid()
    )
    account_owner_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.user_id", ondelete="CASCADE"), index=True
    )
    first_name: Mapped[str] = mapped_column(String(100))
    last_name: Mapped[str] = mapped_column(String(100))
    phone_number: Mapped[str] = mapped_column(String(20))
    date_of_birth: Mapped[datetime.date] = mapped_column(Date)
    biological_gender: Mapped[str] = mapped_column(String(20))
    relationship_to_owner: Mapped[str] = mapped_column(String(50))
    created_at: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    __table_args__ = (
        CheckConstraint(
            "biological_gender IN ('Male', 'Female', 'Other')", name="ck_patient_gender"
        ),
    )


class LabTest(Base):
    __tablename__ = "lab_tests"

    test_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=func.gen_random_uuid()
    )
    name: Mapped[str] = mapped_column(String(255))
    description: Mapped[str] = mapped_column(String)
    base_cost: Mapped[float] = mapped_column(Numeric(10, 2))
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, server_default="true")


class Appointment(Base):
    __tablename__ = "appointments"

    appointment_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=func.gen_random_uuid()
    )
    account_owner_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.user_id"), index=True
    )
    appointment_date: Mapped[datetime.date] = mapped_column(Date)
    time_slot: Mapped[datetime.time] = mapped_column(Time)
    status: Mapped[str] = mapped_column(String(50), default="Booked", server_default="Booked")
    created_at: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    __table_args__ = (
        CheckConstraint(
            "status IN ('Booked', 'Cancelled', 'Checked-In', 'Completed')",
            name="ck_appointment_status",
        ),
    )


class AppointmentTestMapping(Base):
    __tablename__ = "appointment_test_mapping"

    mapping_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=func.gen_random_uuid()
    )
    appointment_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("appointments.appointment_id", ondelete="CASCADE"),
        index=True,
    )
    test_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("lab_tests.test_id"), index=True
    )
    patient_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("patient_profiles.patient_id"), index=True
    )
    # Price snapshot at booking time (catalog prices drift); the only billing artifact retained.
    price_at_booking: Mapped[float] = mapped_column(Numeric(10, 2))
