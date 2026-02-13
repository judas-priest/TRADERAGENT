"""Initial schema with all tables

Revision ID: initial
Revises: 
Create Date: 2026-02-13

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'initial'
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Create exchange_credentials table
    op.create_table('exchange_credentials',
    sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
    sa.Column('name', sa.String(length=100), nullable=False),
    sa.Column('exchange_id', sa.String(length=50), nullable=False),
    sa.Column('api_key_encrypted', sa.Text(), nullable=False),
    sa.Column('api_secret_encrypted', sa.Text(), nullable=False),
    sa.Column('password_encrypted', sa.Text(), nullable=True),
    sa.Column('is_sandbox', sa.Boolean(), nullable=False),
    sa.Column('is_active', sa.Boolean(), nullable=False),
    sa.Column('created_at', sa.DateTime(), nullable=False),
    sa.Column('updated_at', sa.DateTime(), nullable=False),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('name')
    )

    # Create bots table
    op.create_table('bots',
    sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
    sa.Column('name', sa.String(length=100), nullable=False),
    sa.Column('credentials_id', sa.Integer(), nullable=False),
    sa.Column('symbol', sa.String(length=20), nullable=False),
    sa.Column('strategy', sa.Enum('grid', 'dca', 'hybrid', name='strategy_type'), nullable=False),
    sa.Column('status', sa.Enum('running', 'paused', 'stopped', 'error', name='bot_status'), nullable=False),
    sa.Column('config_version', sa.Integer(), nullable=False),
    sa.Column('config_data', sa.Text(), nullable=False),
    sa.Column('total_invested', sa.DECIMAL(precision=20, scale=8), nullable=False),
    sa.Column('current_profit', sa.DECIMAL(precision=20, scale=8), nullable=False),
    sa.Column('total_trades', sa.Integer(), nullable=False),
    sa.Column('started_at', sa.DateTime(), nullable=True),
    sa.Column('stopped_at', sa.DateTime(), nullable=True),
    sa.Column('created_at', sa.DateTime(), nullable=False),
    sa.Column('updated_at', sa.DateTime(), nullable=False),
    sa.ForeignKeyConstraint(['credentials_id'], ['exchange_credentials.id'], ),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('name')
    )
    op.create_index('idx_bot_status', 'bots', ['status'], unique=False)
    op.create_index('idx_bot_symbol', 'bots', ['symbol'], unique=False)

    # Create orders table
    op.create_table('orders',
    sa.Column('id', sa.BigInteger(), autoincrement=True, nullable=False),
    sa.Column('bot_id', sa.Integer(), nullable=False),
    sa.Column('exchange_order_id', sa.String(length=100), nullable=False),
    sa.Column('symbol', sa.String(length=20), nullable=False),
    sa.Column('order_type', sa.Enum('limit', 'market', name='order_type'), nullable=False),
    sa.Column('side', sa.Enum('buy', 'sell', name='order_side'), nullable=False),
    sa.Column('price', sa.DECIMAL(precision=20, scale=8), nullable=False),
    sa.Column('amount', sa.DECIMAL(precision=20, scale=8), nullable=False),
    sa.Column('filled', sa.DECIMAL(precision=20, scale=8), nullable=False),
    sa.Column('status', sa.Enum('open', 'closed', 'canceled', 'expired', 'rejected', name='order_status'), nullable=False),
    sa.Column('grid_level', sa.Integer(), nullable=True),
    sa.Column('is_dca', sa.Boolean(), nullable=False),
    sa.Column('created_at', sa.DateTime(), nullable=False),
    sa.Column('updated_at', sa.DateTime(), nullable=False),
    sa.Column('filled_at', sa.DateTime(), nullable=True),
    sa.ForeignKeyConstraint(['bot_id'], ['bots.id'], ),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index('idx_order_bot_status', 'orders', ['bot_id', 'status'], unique=False)
    op.create_index('idx_order_exchange_id', 'orders', ['exchange_order_id'], unique=False)
    op.create_index('idx_order_symbol', 'orders', ['symbol'], unique=False)

    # Create trades table
    op.create_table('trades',
    sa.Column('id', sa.BigInteger(), autoincrement=True, nullable=False),
    sa.Column('bot_id', sa.Integer(), nullable=False),
    sa.Column('exchange_trade_id', sa.String(length=100), nullable=False),
    sa.Column('exchange_order_id', sa.String(length=100), nullable=False),
    sa.Column('symbol', sa.String(length=20), nullable=False),
    sa.Column('side', sa.Enum('buy', 'sell', name='trade_side'), nullable=False),
    sa.Column('price', sa.DECIMAL(precision=20, scale=8), nullable=False),
    sa.Column('amount', sa.DECIMAL(precision=20, scale=8), nullable=False),
    sa.Column('fee', sa.DECIMAL(precision=20, scale=8), nullable=False),
    sa.Column('fee_currency', sa.String(length=10), nullable=False),
    sa.Column('profit', sa.DECIMAL(precision=20, scale=8), nullable=True),
    sa.Column('executed_at', sa.DateTime(), nullable=False),
    sa.Column('created_at', sa.DateTime(), nullable=False),
    sa.ForeignKeyConstraint(['bot_id'], ['bots.id'], ),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index('idx_trade_bot', 'trades', ['bot_id'], unique=False)
    op.create_index('idx_trade_exchange_id', 'trades', ['exchange_trade_id'], unique=False)
    op.create_index('idx_trade_executed_at', 'trades', ['executed_at'], unique=False)

    # Create grid_levels table
    op.create_table('grid_levels',
    sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
    sa.Column('bot_id', sa.Integer(), nullable=False),
    sa.Column('level', sa.Integer(), nullable=False),
    sa.Column('price', sa.DECIMAL(precision=20, scale=8), nullable=False),
    sa.Column('buy_order_id', sa.String(length=100), nullable=True),
    sa.Column('sell_order_id', sa.String(length=100), nullable=True),
    sa.Column('is_active', sa.Boolean(), nullable=False),
    sa.Column('created_at', sa.DateTime(), nullable=False),
    sa.Column('updated_at', sa.DateTime(), nullable=False),
    sa.ForeignKeyConstraint(['bot_id'], ['bots.id'], ),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index('idx_grid_bot_active', 'grid_levels', ['bot_id', 'is_active'], unique=False)
    op.create_index('idx_grid_bot_level', 'grid_levels', ['bot_id', 'level'], unique=True)

    # Create dca_history table
    op.create_table('dca_history',
    sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
    sa.Column('bot_id', sa.Integer(), nullable=False),
    sa.Column('trigger_price', sa.DECIMAL(precision=20, scale=8), nullable=False),
    sa.Column('buy_price', sa.DECIMAL(precision=20, scale=8), nullable=False),
    sa.Column('amount', sa.DECIMAL(precision=20, scale=8), nullable=False),
    sa.Column('total_cost', sa.DECIMAL(precision=20, scale=8), nullable=False),
    sa.Column('average_price', sa.DECIMAL(precision=20, scale=8), nullable=False),
    sa.Column('dca_step', sa.Integer(), nullable=False),
    sa.Column('executed_at', sa.DateTime(), nullable=False),
    sa.Column('created_at', sa.DateTime(), nullable=False),
    sa.ForeignKeyConstraint(['bot_id'], ['bots.id'], ),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index('idx_dca_bot', 'dca_history', ['bot_id'], unique=False)
    op.create_index('idx_dca_executed_at', 'dca_history', ['executed_at'], unique=False)

    # Create bot_logs table
    op.create_table('bot_logs',
    sa.Column('id', sa.BigInteger(), autoincrement=True, nullable=False),
    sa.Column('bot_id', sa.Integer(), nullable=False),
    sa.Column('level', sa.Enum('DEBUG', 'INFO', 'WARNING', 'ERROR', 'CRITICAL', name='log_level'), nullable=False),
    sa.Column('message', sa.Text(), nullable=False),
    sa.Column('context', sa.Text(), nullable=True),
    sa.Column('created_at', sa.DateTime(), nullable=False),
    sa.ForeignKeyConstraint(['bot_id'], ['bots.id'], ),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index('idx_log_bot_level', 'bot_logs', ['bot_id', 'level'], unique=False)
    op.create_index('idx_log_created_at', 'bot_logs', ['created_at'], unique=False)


def downgrade() -> None:
    op.drop_index('idx_log_created_at', table_name='bot_logs')
    op.drop_index('idx_log_bot_level', table_name='bot_logs')
    op.drop_table('bot_logs')
    op.drop_index('idx_dca_executed_at', table_name='dca_history')
    op.drop_index('idx_dca_bot', table_name='dca_history')
    op.drop_table('dca_history')
    op.drop_index('idx_grid_bot_level', table_name='grid_levels')
    op.drop_index('idx_grid_bot_active', table_name='grid_levels')
    op.drop_table('grid_levels')
    op.drop_index('idx_trade_executed_at', table_name='trades')
    op.drop_index('idx_trade_exchange_id', table_name='trades')
    op.drop_index('idx_trade_bot', table_name='trades')
    op.drop_table('trades')
    op.drop_index('idx_order_symbol', table_name='orders')
    op.drop_index('idx_order_exchange_id', table_name='orders')
    op.drop_index('idx_order_bot_status', table_name='orders')
    op.drop_table('orders')
    op.drop_index('idx_bot_symbol', table_name='bots')
    op.drop_index('idx_bot_status', table_name='bots')
    op.drop_table('bots')
    op.drop_table('exchange_credentials')
