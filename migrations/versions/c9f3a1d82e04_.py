"""Add upload_task table

Revision ID: c9f3a1d82e04
Revises: 708dcbccc726
Create Date: 2026-04-26 00:00:00.000000
"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'c9f3a1d82e04'
down_revision = '708dcbccc726'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        'upload_task',
        sa.Column('id',           sa.Integer(),     nullable=False),
        sa.Column('task_id',      sa.String(36),    nullable=False),
        sa.Column('status',       sa.String(20),    nullable=False, server_default='pending'),
        sa.Column('filename',     sa.String(512),   nullable=True),
        sa.Column('file_type',    sa.String(20),    nullable=True),
        sa.Column('created_at',   sa.DateTime(),    nullable=False),
        sa.Column('completed_at', sa.DateTime(),    nullable=True),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('task_id'),
    )
    op.create_index('ix_upload_task_task_id', 'upload_task', ['task_id'], unique=True)


def downgrade():
    op.drop_index('ix_upload_task_task_id', table_name='upload_task')
    op.drop_table('upload_task')
