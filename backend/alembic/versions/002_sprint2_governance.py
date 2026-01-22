"""Add Sprint 2 governance tables (models, colors, templates)

Revision ID: 002_sprint2_governance
Revises: 001_initial_schema
Create Date: 2026-01-21 10:00:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic
revision = '002_sprint2_governance'
down_revision = '001_initial_schema'
branch_labels = None
depends_on = None


def upgrade():
    # Create models table
    op.create_table(
        'models',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('tenant_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('code', sa.String(50), nullable=False),
        sa.Column('name', sa.String(255), nullable=False),
        sa.Column('allowed_sizes', sa.JSON(), nullable=False),
        sa.Column('size_order', sa.JSON(), nullable=True),
        sa.Column('is_active', sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.ForeignKeyConstraint(['tenant_id'], ['tenants.id'], ),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('tenant_id', 'code', name='uq_models_tenant_code')
    )
    op.create_index('ix_models_tenant_id', 'models', ['tenant_id'])
    op.create_index('ix_models_code', 'models', ['code'])

    # Create colors table
    op.create_table(
        'colors',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('tenant_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('code', sa.String(50), nullable=False),
        sa.Column('name', sa.String(255), nullable=False),
        sa.Column('is_active', sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.ForeignKeyConstraint(['tenant_id'], ['tenants.id'], ),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('tenant_id', 'code', name='uq_colors_tenant_code')
    )
    op.create_index('ix_colors_tenant_id', 'colors', ['tenant_id'])

    # Create model_templates table
    op.create_table(
        'model_templates',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('tenant_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('model_code', sa.String(50), nullable=False),
        sa.Column('template_kind', sa.String(50), nullable=False),  # Enum
        sa.Column('bling_product_id', sa.BigInteger(), nullable=False),
        sa.Column('bling_product_sku', sa.String(255), nullable=False),
        sa.Column('bling_product_name', sa.String(500), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.ForeignKeyConstraint(['tenant_id'], ['tenants.id'], ),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('tenant_id', 'model_code', 'template_kind', name='uq_model_templates_tenant_model_kind')
    )
    op.create_index('ix_model_templates_tenant_id', 'model_templates', ['tenant_id'])
    op.create_index('ix_model_templates_model_code', 'model_templates', ['model_code'])


def downgrade():
    op.drop_index('ix_model_templates_model_code', 'model_templates')
    op.drop_index('ix_model_templates_tenant_id', 'model_templates')
    op.drop_table('model_templates')
    
    op.drop_index('ix_colors_tenant_id', 'colors')
    op.drop_table('colors')
    
    op.drop_index('ix_models_code', 'models')
    op.drop_index('ix_models_tenant_id', 'models')
    op.drop_table('models')
