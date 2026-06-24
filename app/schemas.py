import datetime
import uuid
from decimal import Decimal

from pydantic import BaseModel, ConfigDict


class LabTestOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    test_id: uuid.UUID
    name: str
    description: str
    base_cost: Decimal
    is_active: bool


class TestSelection(BaseModel):
    test_id: uuid.UUID
    patient_id: uuid.UUID


class AppointmentCreate(BaseModel):
    appointment_date: datetime.date
    time_slot: datetime.time
    tests: list[TestSelection]


class AppointmentOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    appointment_id: uuid.UUID
    appointment_date: datetime.date
    time_slot: datetime.time
    status: str


class PatientProfileCreate(BaseModel):
    first_name: str
    last_name: str
    phone_number: str
    date_of_birth: datetime.date
    biological_gender: str
    relationship_to_owner: str


class PatientProfileOut(PatientProfileCreate):
    model_config = ConfigDict(from_attributes=True)

    patient_id: uuid.UUID
