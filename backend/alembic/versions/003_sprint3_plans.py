"""Sprint 3: Add plans table for dry-run planning

Revision ID: 003_sprint3_plans
Revises: 002_sprint2_governance
Create Date: 2026-01-22

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID
import uuid


# revision identifiers, used by Alembic
revision = '003_sprint3_plans'
down_revision = '002_sprint2_governance'
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Create plans table."""
    from sqlalchemy.dialects.postgresql import ENUM
    
    # Create enum types using DO block to check if they exist
    op.execute("""
        DO $$ BEGIN
            CREATE TYPE plantypeenum AS ENUM ('NEW_PRINT', 'FIX');
        EXCEPTION
            WHEN duplicate_object THEN null;
        END $$;
    """)
    
    op.execute("""
        DO $$ BEGIN
            CREATE TYPE planstatusenum AS ENUM ('DRAFT', 'EXECUTED');
        EXCEPTION
            WHEN duplicate_object THEN null;
        END $$;
    """)
    
    plant_type_enum = ENUM('NEW_PRINT', 'FIX', name='plantypeenum', create_type=False)
    plan_status_enum = ENUM('DRAFT', 'EXECUTED', name='planstatusenum', create_type=False)
    
    op.create_table(
        'plans',
        sa.Column('id', UUID(as_uuid=True), primary_key=True, default=uuid.uuid4),
        sa.Column('tenant_id', UUID(as_uuid=True), sa.ForeignKey('tenants.id'), nullable=False),
        sa.Column('type', plant_type_enum, nullable=False),
        sa.Column('status', plan_status_enum, nullable=False),
        sa.Column('input_payload', sa.JSON, nullable=False),
        sa.Column('plan_payload', sa.JSON, nullable=False),
        sa.Column('created_at', sa.DateTime, nullable=False, server_default=sa.func.now()),
        sa.Column('executed_at', sa.DateTime, nullable=True),
    )

    # Create index on tenant_id for faster queries
    op.create_index('ix_plans_tenant_id', 'plans', ['tenant_id'])
    op.create_index('ix_plans_type', 'plans', ['type'])
    op.create_index('ix_plans_status', 'plans', ['status'])


def downgrade() -> None:
    """Drop plans table."""
    op.drop_index('ix_plans_status', table_name='plans')
    op.drop_index('ix_plans_type', table_name='plans')
    op.drop_index('ix_plans_tenant_id', table_name='plans')
    op.drop_table('plans')
    op.execute('DROP TYPE IF EXISTS plantypeenum')
    op.execute('DROP TYPE IF EXISTS planstatusenum')
