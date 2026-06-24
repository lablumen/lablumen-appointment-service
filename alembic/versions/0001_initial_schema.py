"""initial schema (single-tenant)

Revision ID: 0001
Revises:
Create Date: 2026-06-17

Corrected vs. BLUEPRINT.md: lab_reports maps to appointment_test_mapping (not appointment_id),
price_at_booking added to the mapping, all timestamps are TIMESTAMPTZ, every FK is indexed.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from pgvector.sqlalchemy import Vector
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "0001"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

UUID = postgresql.UUID(as_uuid=True)


def upgrade() -> None:
    op.execute('CREATE EXTENSION IF NOT EXISTS "uuid-ossp"')
    op.execute("CREATE EXTENSION IF NOT EXISTS vector")

    op.create_table(
        "users",
        sa.Column("user_id", UUID, primary_key=True),  # = Cognito 'sub'
        sa.Column("email", sa.String(255), nullable=False, unique=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False
        ),
    )

    op.create_table(
        "user_roles",
        sa.Column(
            "user_id", UUID, sa.ForeignKey("users.user_id", ondelete="CASCADE"), nullable=False
        ),
        sa.Column("role_name", sa.String(50), nullable=False),
        sa.PrimaryKeyConstraint("user_id", "role_name"),
        sa.CheckConstraint(
            "role_name IN ('PATIENT', 'LAB_STAFF', 'LAB_ADMIN')", name="ck_user_roles_role_name"
        ),
    )

    op.create_table(
        "patient_profiles",
        sa.Column("patient_id", UUID, primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column(
            "account_owner_id",
            UUID,
            sa.ForeignKey("users.user_id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("first_name", sa.String(100), nullable=False),
        sa.Column("last_name", sa.String(100), nullable=False),
        sa.Column("phone_number", sa.String(20), nullable=False),
        sa.Column("date_of_birth", sa.Date, nullable=False),
        sa.Column("biological_gender", sa.String(20), nullable=False),
        sa.Column("relationship_to_owner", sa.String(50), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False
        ),
        sa.CheckConstraint(
            "biological_gender IN ('Male', 'Female', 'Other')", name="ck_patient_gender"
        ),
    )
    op.create_index("ix_patient_profiles_account_owner_id", "patient_profiles", ["account_owner_id"])

    op.create_table(
        "lab_tests",
        sa.Column("test_id", UUID, primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("description", sa.Text, nullable=False),
        sa.Column("base_cost", sa.Numeric(10, 2), nullable=False),
        sa.Column("is_active", sa.Boolean, server_default=sa.text("true"), nullable=False),
    )

    op.create_table(
        "appointments",
        sa.Column(
            "appointment_id", UUID, primary_key=True, server_default=sa.text("gen_random_uuid()")
        ),
        sa.Column(
            "account_owner_id", UUID, sa.ForeignKey("users.user_id"), nullable=False
        ),
        sa.Column("appointment_date", sa.Date, nullable=False),
        sa.Column("time_slot", sa.Time, nullable=False),
        sa.Column("status", sa.String(50), server_default="Booked", nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False
        ),
        sa.CheckConstraint(
            "status IN ('Booked', 'Cancelled', 'Checked-In', 'Completed')",
            name="ck_appointment_status",
        ),
    )
    op.create_index("ix_appointments_account_owner_id", "appointments", ["account_owner_id"])

    op.create_table(
        "appointment_test_mapping",
        sa.Column("mapping_id", UUID, primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column(
            "appointment_id",
            UUID,
            sa.ForeignKey("appointments.appointment_id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("test_id", UUID, sa.ForeignKey("lab_tests.test_id"), nullable=False),
        sa.Column(
            "patient_id", UUID, sa.ForeignKey("patient_profiles.patient_id"), nullable=False
        ),
        # Price snapshot at booking; the only billing artifact retained (patients pay at the lab).
        sa.Column("price_at_booking", sa.Numeric(10, 2), nullable=False),
    )
    op.create_index("ix_atm_appointment_id", "appointment_test_mapping", ["appointment_id"])
    op.create_index("ix_atm_test_id", "appointment_test_mapping", ["test_id"])
    op.create_index("ix_atm_patient_id", "appointment_test_mapping", ["patient_id"])

    op.create_table(
        "lab_reports",
        sa.Column("report_id", UUID, primary_key=True, server_default=sa.text("gen_random_uuid()")),
        # One report per ordered test/patient -> supports multi-test, multi-patient appointments.
        sa.Column(
            "mapping_id",
            UUID,
            sa.ForeignKey("appointment_test_mapping.mapping_id", ondelete="CASCADE"),
            nullable=False,
            unique=True,
        ),
        sa.Column("s3_url", sa.String(512), nullable=False),
        sa.Column("ai_layman_summary", sa.Text, nullable=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False
        ),
    )

    op.create_table(
        "report_embeddings",
        sa.Column(
            "embedding_id", UUID, primary_key=True, server_default=sa.text("gen_random_uuid()")
        ),
        sa.Column(
            "report_id",
            UUID,
            sa.ForeignKey("lab_reports.report_id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("chunk_content", sa.Text, nullable=False),
        sa.Column("embedding", Vector(1536)),  # amazon.titan-embed-text-v1 dimensions
    )
    op.create_index("ix_report_embeddings_report_id", "report_embeddings", ["report_id"])
    # HNSW index for fast cosine similarity (report-scoped queries filter by report_id).
    op.execute(
        "CREATE INDEX ix_report_embeddings_hnsw ON report_embeddings "
        "USING hnsw (embedding vector_cosine_ops)"
    )


def downgrade() -> None:
    op.drop_table("report_embeddings")
    op.drop_table("lab_reports")
    op.drop_table("appointment_test_mapping")
    op.drop_table("appointments")
    op.drop_table("lab_tests")
    op.drop_table("patient_profiles")
    op.drop_table("user_roles")
    op.drop_table("users")
