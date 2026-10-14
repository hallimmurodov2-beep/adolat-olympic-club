"""V2 teaching: consent-bound existing student classroom enrollment.

Revision ID: d84f103f71aa
Revises: c16a7f429444
"""
from alembic import op
import sqlalchemy as sa

revision = 'd84f103f71aa'
down_revision = 'c16a7f429444'
branch_labels = None
depends_on = None


def upgrade():
    op.add_column('activities', sa.Column('edit_version', sa.Integer(), nullable=False, server_default='1'))
    op.create_index('ix_submission_review_queue', 'submissions', ['created_at', 'id'])
    op.create_table('enrollment_invitations',
        sa.Column('id', sa.String(36), primary_key=True),
        sa.Column('token_hash', sa.String(64), nullable=False, unique=True),
        sa.Column('classroom_id', sa.String(36), sa.ForeignKey('classrooms.id', ondelete='CASCADE'), nullable=False),
        sa.Column('user_id', sa.String(36), sa.ForeignKey('users.id', ondelete='CASCADE'), nullable=False),
        sa.Column('created_by', sa.String(36), sa.ForeignKey('users.id'), nullable=False),
        sa.Column('expires_at', sa.BigInteger(), nullable=False),
        sa.Column('accepted_at', sa.BigInteger(), nullable=True),
        sa.Column('created_at', sa.BigInteger(), nullable=False))
    op.create_index('ix_enrollment_invitations_classroom_id', 'enrollment_invitations', ['classroom_id'])


def downgrade():
    op.drop_index('ix_submission_review_queue', table_name='submissions')
    op.drop_column('activities', 'edit_version')
    op.drop_index('ix_enrollment_invitations_classroom_id', table_name='enrollment_invitations')
    op.drop_table('enrollment_invitations')
