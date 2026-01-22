"""Initial database migration."""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = '001_initial_schema'
down_revision = None
branch_labels = None
depends_on = None


def upgrade():
    """Create initial tables."""
    
    # Tenants table
    op.create_table(
        'tenants',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('name', sa.String(255), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint('id')
    )
    
    # Bling tokens table
    op.create_table(
        'bling_tokens',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('tenant_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('access_token', sa.Text(), nullable=False),
        sa.Column('refresh_token', sa.Text(), nullable=False),
        sa.Column('expires_at', sa.DateTime(), nullable=False),
        sa.Column('token_type', sa.String(50), nullable=True),
        sa.Column('scope', sa.String(500), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(['tenant_id'], ['tenants.id'], ),
        sa.PrimaryKeyConstraint('id')
    )
    
    op.create_index('ix_bling_tokens_tenant_id', 'bling_tokens', ['tenant_id'])
    
    # Jobs table
    op.create_table(
        'jobs',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('tenant_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('type', sa.String(100), nullable=False),
        sa.Column('status', sa.Enum('DRAFT', 'QUEUED', 'RUNNING', 'DONE', 'FAILED', name='jobstatusenum'), nullable=False),
        sa.Column('input_payload', postgresql.JSON(astext_type=sa.Text()), nullable=True),
        sa.Column('job_metadata', postgresql.JSON(astext_type=sa.Text()), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('started_at', sa.DateTime(), nullable=True),
        sa.Column('finished_at', sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(['tenant_id'], ['tenants.id'], ),
        sa.PrimaryKeyConstraint('id')
    )
    
    op.create_index('ix_jobs_tenant_id', 'jobs', ['tenant_id'])
    op.create_index('ix_jobs_status', 'jobs', ['status'])
    
    # Job items table
    op.create_table(
        'job_items',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('job_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('status', sa.Enum('PENDING', 'RUNNING', 'OK', 'ERROR', name='jobitemstatusenum'), nullable=False),
        sa.Column('payload', postgresql.JSON(astext_type=sa.Text()), nullable=True),
        sa.Column('result', postgresql.JSON(astext_type=sa.Text()), nullable=True),
        sa.Column('error_message', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('started_at', sa.DateTime(), nullable=True),
        sa.Column('finished_at', sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(['job_id'], ['jobs.id'], ),
        sa.PrimaryKeyConstraint('id')
    )
    
    op.create_index('ix_job_items_job_id', 'job_items', ['job_id'])
    op.create_index('ix_job_items_status', 'job_items', ['status'])


def downgrade():
    """Drop all tables."""
    
    op.drop_index('ix_job_items_status', table_name='job_items')
    op.drop_index('ix_job_items_job_id', table_name='job_items')
    op.drop_table('job_items')
    
    op.drop_index('ix_jobs_status', table_name='jobs')
    op.drop_index('ix_jobs_tenant_id', table_name='jobs')
    op.drop_table('jobs')
    
    op.drop_index('ix_bling_tokens_tenant_id', table_name='bling_tokens')
    op.drop_table('bling_tokens')
    
    op.drop_table('tenants')
