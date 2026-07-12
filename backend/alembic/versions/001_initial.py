"""Initial migration: Create core tables

Revision ID: 001_initial
Revises: 
Create Date: 2024-01-01 00:00:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = '001_initial'
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Create users table
    op.create_table(
        'users',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('email', sa.String(255), nullable=False),
        sa.Column('username', sa.String(100), nullable=True),
        sa.Column('hashed_password', sa.String(255), nullable=False),
        sa.Column('full_name', sa.String(255), nullable=True),
        sa.Column('is_active', sa.Boolean(), nullable=False, server_default='true'),
        sa.Column('is_premium', sa.Boolean(), nullable=False, server_default='false'),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
        sa.Column('last_login', sa.DateTime(), nullable=True),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('email', name='uq_user_email'),
        sa.UniqueConstraint('username', name='uq_user_username'),
    )
    op.create_index('idx_user_is_active', 'users', ['is_active'])
    op.create_index('idx_user_created_at', 'users', ['created_at'])
    op.create_index('ix_users_email', 'users', ['email'])
    op.create_index('ix_users_username', 'users', ['username'])
    
    # Create generated_reports table
    op.create_table(
        'generated_reports',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('user_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('ticker', sa.String(10), nullable=False),
        sa.Column('company_name', sa.String(255), nullable=True),
        sa.Column('query', sa.String(500), nullable=False),
        sa.Column('fundamental_report', postgresql.JSONB(), nullable=True),
        sa.Column('technical_report', postgresql.JSONB(), nullable=True),
        sa.Column('sentiment_report', postgresql.JSONB(), nullable=True),
        sa.Column('final_report', sa.Text(), nullable=False),
        sa.Column('citations', postgresql.JSONB(), nullable=False, server_default='[]'),
        sa.Column('sentiment_score', sa.Integer(), nullable=True),
        sa.Column('bull_score', sa.Integer(), nullable=True, server_default='0'),
        sa.Column('bear_score', sa.Integer(), nullable=True, server_default='0'),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
        sa.Column('generation_time_ms', sa.Integer(), nullable=True),
        sa.Column('is_cached', sa.Boolean(), nullable=False, server_default='false'),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('idx_report_ticker_created', 'generated_reports', ['ticker', 'created_at'])
    op.create_index('idx_report_user_created', 'generated_reports', ['user_id', 'created_at'])
    op.create_index('idx_report_sentiment_score', 'generated_reports', ['sentiment_score'])
    op.create_index('ix_generated_reports_ticker', 'generated_reports', ['ticker'])
    op.create_index('ix_generated_reports_user_id', 'generated_reports', ['user_id'])
    
    # Create watchlists table
    op.create_table(
        'watchlists',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('user_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('name', sa.String(100), nullable=False),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('user_id', 'name', name='uq_watchlist_user_name'),
    )
    op.create_index('idx_watchlist_user', 'watchlists', ['user_id'])
    
    # Create watchlist_items table
    op.create_table(
        'watchlist_items',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('watchlist_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('ticker', sa.String(10), nullable=False),
        sa.Column('company_name', sa.String(255), nullable=True),
        sa.Column('entry_price', sa.Float(), nullable=True),
        sa.Column('current_price', sa.Float(), nullable=True),
        sa.Column('last_price_update', sa.DateTime(), nullable=True),
        sa.Column('price_change_percent', sa.Float(), nullable=True),
        sa.Column('latest_sentiment_score', sa.Integer(), nullable=True),
        sa.Column('latest_report_id', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('added_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(['watchlist_id'], ['watchlists.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['latest_report_id'], ['generated_reports.id'], ondelete='SET NULL'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('watchlist_id', 'ticker', name='uq_watchlist_item_ticker'),
    )
    op.create_index('idx_watchlist_item_ticker', 'watchlist_items', ['ticker'])
    op.create_index('idx_watchlist_item_sentiment', 'watchlist_items', ['latest_sentiment_score'])


def downgrade() -> None:
    # Drop all tables in reverse order (respecting foreign keys)
    op.drop_index('idx_watchlist_item_sentiment', table_name='watchlist_items')
    op.drop_index('idx_watchlist_item_ticker', table_name='watchlist_items')
    op.drop_table('watchlist_items')
    
    op.drop_index('idx_watchlist_user', table_name='watchlists')
    op.drop_table('watchlists')
    
    op.drop_index('ix_generated_reports_user_id', table_name='generated_reports')
    op.drop_index('ix_generated_reports_ticker', table_name='generated_reports')
    op.drop_index('idx_report_sentiment_score', table_name='generated_reports')
    op.drop_index('idx_report_user_created', table_name='generated_reports')
    op.drop_index('idx_report_ticker_created', table_name='generated_reports')
    op.drop_table('generated_reports')
    
    op.drop_index('idx_user_created_at', table_name='users')
    op.drop_index('idx_user_is_active', table_name='users')
    op.drop_index('ix_users_username', table_name='users')
    op.drop_index('ix_users_email', table_name='users')
    op.drop_table('users')
