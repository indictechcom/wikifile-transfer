"""empty message

Revision ID: b434101b8d78
Revises: a5509aa15c77
Create Date: 2024-10-31 11:26:03.140699

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'b434101b8d78'
down_revision = 'a5509aa15c77'
branch_labels = None
depends_on = None


def upgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    with op.batch_alter_table('user', schema=None) as batch_op:
        batch_op.drop_column('site_language')

    # ### end Alembic commands ###


def downgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    with op.batch_alter_table('user', schema=None) as batch_op:
        batch_op.add_column(sa.Column('site_language', sa.VARCHAR(length=4), nullable=True))

    # ### end Alembic commands ###
