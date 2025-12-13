"""convert datetime columns to timestamptz

Revision ID: 13d97ae3ceb6
Revises: 2b8d7e700652
Create Date: 2025-12-13 14:47:18.677966

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '13d97ae3ceb6'
down_revision = '2b8d7e700652'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Convert all datetime columns to timestamptz
    # Users table
    op.execute('ALTER TABLE users ALTER COLUMN created_at TYPE TIMESTAMPTZ USING created_at AT TIME ZONE \'UTC\'')
    op.execute('ALTER TABLE users ALTER COLUMN updated_at TYPE TIMESTAMPTZ USING updated_at AT TIME ZONE \'UTC\'')

    # Tokens table
    op.execute('ALTER TABLE tokens ALTER COLUMN expires_at TYPE TIMESTAMPTZ USING expires_at AT TIME ZONE \'UTC\'')
    op.execute('ALTER TABLE tokens ALTER COLUMN last_used_at TYPE TIMESTAMPTZ USING last_used_at AT TIME ZONE \'UTC\'')
    op.execute('ALTER TABLE tokens ALTER COLUMN created_at TYPE TIMESTAMPTZ USING created_at AT TIME ZONE \'UTC\'')

    # Audit logs table
    op.execute('ALTER TABLE audit_logs ALTER COLUMN timestamp TYPE TIMESTAMPTZ USING timestamp AT TIME ZONE \'UTC\'')

    # FCS files table
    op.execute('ALTER TABLE fcs_files ALTER COLUMN uploaded_at TYPE TIMESTAMPTZ USING uploaded_at AT TIME ZONE \'UTC\'')


def downgrade() -> None:
    # Convert all timestamptz columns back to timestamp (without timezone)
    # Users table
    op.execute('ALTER TABLE users ALTER COLUMN created_at TYPE TIMESTAMP USING created_at AT TIME ZONE \'UTC\'')
    op.execute('ALTER TABLE users ALTER COLUMN updated_at TYPE TIMESTAMP USING updated_at AT TIME ZONE \'UTC\'')

    # Tokens table
    op.execute('ALTER TABLE tokens ALTER COLUMN expires_at TYPE TIMESTAMP USING expires_at AT TIME ZONE \'UTC\'')
    op.execute('ALTER TABLE tokens ALTER COLUMN last_used_at TYPE TIMESTAMP USING last_used_at AT TIME ZONE \'UTC\'')
    op.execute('ALTER TABLE tokens ALTER COLUMN created_at TYPE TIMESTAMP USING created_at AT TIME ZONE \'UTC\'')

    # Audit logs table
    op.execute('ALTER TABLE audit_logs ALTER COLUMN timestamp TYPE TIMESTAMP USING timestamp AT TIME ZONE \'UTC\'')

    # FCS files table
    op.execute('ALTER TABLE fcs_files ALTER COLUMN uploaded_at TYPE TIMESTAMP USING uploaded_at AT TIME ZONE \'UTC\'')

