"""seed lab_tests catalog

Revision ID: 0002
Revises: 0001
Create Date: 2026-06-17

Seed applied as a versioned migration (not on service boot), per BLUEPRINT.md section 2.
"""

from collections.abc import Sequence

from alembic import op

revision: str = "0002"
down_revision: str | None = "0001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute(
        """
        INSERT INTO lab_tests (name, description, base_cost) VALUES
        ('Complete Blood Count (CBC)', 'Evaluates overall cellular health by measuring red blood cells, white blood cells, and platelets.', 45.00),
        ('Comprehensive Metabolic Panel (CMP)', 'Checks your body''s fluid balance, blood sugar levels, and liver and kidney functions.', 65.00),
        ('Lipid Profile', 'Measures cardiovascular risk by calculating total cholesterol, HDL, LDL, and triglycerides.', 50.00),
        ('Thyroid Function Panel', 'Evaluates metabolism speed by measuring TSH, Free T3, and Free T4 hormone levels.', 75.00),
        ('Hemoglobin A1c (HbA1c)', 'Provides a 3-month average of blood glucose levels to screen for diabetes.', 40.00),
        ('Urinalysis (UA)', 'Analyzes physical, chemical, and microscopic properties of urine to check for infections or kidney issues.', 30.00),
        ('Vitamin D & Vitamin B12 Panel', 'Measures essential nutrient absorption levels in the bloodstream.', 90.00),
        ('Liver Function Test (LFT)', 'Isolates specific liver enzymes like ALT, AST, ALP, and bilirubin to check for organ damage.', 55.00),
        ('Renal Function Panel (RFP)', 'Evaluates kidney health specifically using blood urea nitrogen (BUN), creatinine, and eGFR.', 60.00);
        """
    )


def downgrade() -> None:
    op.execute("DELETE FROM lab_tests")
