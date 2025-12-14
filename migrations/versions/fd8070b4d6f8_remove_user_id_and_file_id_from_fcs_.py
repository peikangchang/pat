"""remove_user_id_and_file_id_from_fcs_files

Revision ID: fd8070b4d6f8
Revises: 13d97ae3ceb6
Create Date: 2025-12-14 07:06:44.981331

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'fd8070b4d6f8'
down_revision = '13d97ae3ceb6'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Delete all existing FCS files (schema change makes old data incompatible)
    op.execute('DELETE FROM fcs_files')

    # Drop foreign key constraint for user_id
    op.drop_constraint('fcs_files_user_id_fkey', 'fcs_files', type_='foreignkey')

    # Drop columns
    op.drop_column('fcs_files', 'user_id')
    op.drop_column('fcs_files', 'file_id')


def downgrade() -> None:
    # Add columns back
    op.add_column('fcs_files', sa.Column('file_id', sa.String(length=50), nullable=False))
    op.add_column('fcs_files', sa.Column('user_id', sa.dialects.postgresql.UUID(as_uuid=True), nullable=False))

    # Recreate foreign key constraint
    op.create_foreign_key('fcs_files_user_id_fkey', 'fcs_files', 'users', ['user_id'], ['id'], ondelete='CASCADE')

    # Recreate indexes
    op.create_index(op.f('ix_fcs_files_file_id'), 'fcs_files', ['file_id'], unique=True)
    op.create_unique_constraint('fcs_files_file_id_key', 'fcs_files', ['file_id'])
