"""v2.0 multi-strategy schema: strategies, positions, signals, DCA deals

Revision ID: v2_multi_strategy
Revises: initial
Create Date: 2026-02-14

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'v2_multi_strategy'
down_revision: Union[str, None] = 'initial'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # --- Enum types ---
    strategy_type_v2 = sa.Enum(
        'smc', 'trend_follower', 'grid', 'dca', 'hybrid',
        name='strategy_type_v2',
    )
    strategy_state = sa.Enum(
        'idle', 'starting', 'active', 'paused', 'stopping', 'stopped', 'error',
        name='strategy_state',
    )
    signal_direction = sa.Enum('long', 'short', name='signal_direction')
    position_status_v2 = sa.Enum('open', 'closed', name='position_status_v2')
    exit_reason = sa.Enum(
        'take_profit', 'stop_loss', 'trailing_stop', 'breakeven',
        'partial_close', 'manual', 'signal_reversed', 'risk_limit', 'timeout',
        name='exit_reason',
    )
    dca_deal_status = sa.Enum('active', 'completed', 'cancelled', name='dca_deal_status')
    dca_order_status = sa.Enum('pending', 'filled', 'cancelled', name='dca_order_status')
    dca_order_side = sa.Enum('buy', 'sell', name='dca_order_side')
    dca_signal_type = sa.Enum(
        'start_deal', 'safety_order', 'take_profit', 'stop_loss',
        name='dca_signal_type',
    )

    # --- strategies table ---
    op.create_table('strategies',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('strategy_id', sa.String(length=100), nullable=False),
        sa.Column('strategy_type', strategy_type_v2, nullable=False),
        sa.Column('bot_id', sa.Integer(), nullable=True),
        sa.Column('state', strategy_state, nullable=False),
        sa.Column('config_data', sa.Text(), nullable=True),
        sa.Column('total_signals', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('executed_trades', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('profitable_trades', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('total_pnl', sa.DECIMAL(precision=20, scale=8), nullable=False, server_default='0'),
        sa.Column('error_count', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('last_error', sa.Text(), nullable=True),
        sa.Column('started_at', sa.DateTime(), nullable=True),
        sa.Column('stopped_at', sa.DateTime(), nullable=True),
        sa.Column('last_signal_at', sa.DateTime(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(['bot_id'], ['bots.id']),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('strategy_id'),
    )
    op.create_index('idx_strategy_type', 'strategies', ['strategy_type'], unique=False)
    op.create_index('idx_strategy_state', 'strategies', ['state'], unique=False)
    op.create_index('idx_strategy_bot', 'strategies', ['bot_id'], unique=False)

    # --- signals table (before positions, since positions reference signals) ---
    op.create_table('signals',
        sa.Column('id', sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column('strategy_db_id', sa.Integer(), nullable=False),
        sa.Column('symbol', sa.String(length=20), nullable=False),
        sa.Column('direction', signal_direction, nullable=False),
        sa.Column('entry_price', sa.DECIMAL(precision=20, scale=8), nullable=False),
        sa.Column('stop_loss', sa.DECIMAL(precision=20, scale=8), nullable=False),
        sa.Column('take_profit', sa.DECIMAL(precision=20, scale=8), nullable=False),
        sa.Column('confidence', sa.Float(), nullable=False),
        sa.Column('risk_reward_ratio', sa.Float(), nullable=False, server_default='0'),
        sa.Column('signal_reason', sa.String(length=200), nullable=True),
        sa.Column('was_executed', sa.Boolean(), nullable=False, server_default='false'),
        sa.Column('skip_reason', sa.String(length=200), nullable=True),
        sa.Column('metadata_json', sa.Text(), nullable=True),
        sa.Column('generated_at', sa.DateTime(), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(['strategy_db_id'], ['strategies.id']),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('idx_signal_strategy', 'signals', ['strategy_db_id'], unique=False)
    op.create_index('idx_signal_symbol', 'signals', ['symbol'], unique=False)
    op.create_index('idx_signal_generated', 'signals', ['generated_at'], unique=False)
    op.create_index('idx_signal_executed', 'signals', ['was_executed'], unique=False)

    # --- positions table ---
    op.create_table('positions',
        sa.Column('id', sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column('position_id', sa.String(length=100), nullable=False),
        sa.Column('strategy_db_id', sa.Integer(), nullable=False),
        sa.Column('symbol', sa.String(length=20), nullable=False),
        sa.Column('direction', signal_direction, nullable=False),
        sa.Column('status', position_status_v2, nullable=False, server_default='open'),
        sa.Column('entry_price', sa.DECIMAL(precision=20, scale=8), nullable=False),
        sa.Column('exit_price', sa.DECIMAL(precision=20, scale=8), nullable=True),
        sa.Column('stop_loss', sa.DECIMAL(precision=20, scale=8), nullable=False),
        sa.Column('take_profit', sa.DECIMAL(precision=20, scale=8), nullable=False),
        sa.Column('current_price', sa.DECIMAL(precision=20, scale=8), nullable=True),
        sa.Column('size', sa.DECIMAL(precision=20, scale=8), nullable=False),
        sa.Column('realized_pnl', sa.DECIMAL(precision=20, scale=8), nullable=True),
        sa.Column('unrealized_pnl', sa.DECIMAL(precision=20, scale=8), nullable=True),
        sa.Column('fee_total', sa.DECIMAL(precision=20, scale=8), nullable=False, server_default='0'),
        sa.Column('exit_reason', exit_reason, nullable=True),
        sa.Column('signal_db_id', sa.BigInteger(), nullable=True),
        sa.Column('opened_at', sa.DateTime(), nullable=False),
        sa.Column('closed_at', sa.DateTime(), nullable=True),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(['strategy_db_id'], ['strategies.id']),
        sa.ForeignKeyConstraint(['signal_db_id'], ['signals.id']),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('position_id'),
    )
    op.create_index('idx_position_strategy', 'positions', ['strategy_db_id'], unique=False)
    op.create_index('idx_position_status', 'positions', ['status'], unique=False)
    op.create_index('idx_position_symbol', 'positions', ['symbol'], unique=False)
    op.create_index('idx_position_opened', 'positions', ['opened_at'], unique=False)

    # --- dca_deals table ---
    op.create_table('dca_deals',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('strategy_db_id', sa.Integer(), nullable=False),
        sa.Column('symbol', sa.String(length=20), nullable=False),
        sa.Column('direction', signal_direction, nullable=False),
        sa.Column('status', dca_deal_status, nullable=False, server_default='active'),
        sa.Column('base_order_size', sa.DECIMAL(precision=20, scale=8), nullable=False),
        sa.Column('safety_order_size', sa.DECIMAL(precision=20, scale=8), nullable=False),
        sa.Column('max_safety_orders', sa.Integer(), nullable=False),
        sa.Column('filled_safety_orders', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('average_entry_price', sa.DECIMAL(precision=20, scale=8), nullable=False),
        sa.Column('take_profit_price', sa.DECIMAL(precision=20, scale=8), nullable=True),
        sa.Column('current_price', sa.DECIMAL(precision=20, scale=8), nullable=True),
        sa.Column('total_invested', sa.DECIMAL(precision=20, scale=8), nullable=False, server_default='0'),
        sa.Column('total_quantity', sa.DECIMAL(precision=20, scale=8), nullable=False, server_default='0'),
        sa.Column('realized_pnl', sa.DECIMAL(precision=20, scale=8), nullable=True),
        sa.Column('opened_at', sa.DateTime(), nullable=False),
        sa.Column('closed_at', sa.DateTime(), nullable=True),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(['strategy_db_id'], ['strategies.id']),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('idx_dca_deal_strategy', 'dca_deals', ['strategy_db_id'], unique=False)
    op.create_index('idx_dca_deal_status', 'dca_deals', ['status'], unique=False)
    op.create_index('idx_dca_deal_symbol', 'dca_deals', ['symbol'], unique=False)

    # --- dca_orders table ---
    op.create_table('dca_orders',
        sa.Column('id', sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column('deal_id', sa.Integer(), nullable=False),
        sa.Column('order_number', sa.Integer(), nullable=False),
        sa.Column('is_base_order', sa.Boolean(), nullable=False, server_default='false'),
        sa.Column('side', dca_order_side, nullable=False),
        sa.Column('price', sa.DECIMAL(precision=20, scale=8), nullable=False),
        sa.Column('amount', sa.DECIMAL(precision=20, scale=8), nullable=False),
        sa.Column('filled_amount', sa.DECIMAL(precision=20, scale=8), nullable=False, server_default='0'),
        sa.Column('status', dca_order_status, nullable=False, server_default='pending'),
        sa.Column('exchange_order_id', sa.String(length=100), nullable=True),
        sa.Column('deviation_pct', sa.Float(), nullable=False, server_default='0'),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('filled_at', sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(['deal_id'], ['dca_deals.id']),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('idx_dca_order_deal', 'dca_orders', ['deal_id'], unique=False)
    op.create_index('idx_dca_order_status', 'dca_orders', ['status'], unique=False)
    op.create_index('idx_dca_order_exchange', 'dca_orders', ['exchange_order_id'], unique=False)

    # --- dca_signals table ---
    op.create_table('dca_signals',
        sa.Column('id', sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column('deal_id', sa.Integer(), nullable=True),
        sa.Column('signal_type', dca_signal_type, nullable=False),
        sa.Column('direction', signal_direction, nullable=False),
        sa.Column('trigger_price', sa.DECIMAL(precision=20, scale=8), nullable=False),
        sa.Column('target_price', sa.DECIMAL(precision=20, scale=8), nullable=True),
        sa.Column('confidence', sa.Float(), nullable=False, server_default='0'),
        sa.Column('source_strategy', sa.String(length=100), nullable=True),
        sa.Column('reason', sa.String(length=200), nullable=True),
        sa.Column('was_executed', sa.Boolean(), nullable=False, server_default='false'),
        sa.Column('generated_at', sa.DateTime(), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(['deal_id'], ['dca_deals.id']),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('idx_dca_signal_deal', 'dca_signals', ['deal_id'], unique=False)
    op.create_index('idx_dca_signal_type', 'dca_signals', ['signal_type'], unique=False)
    op.create_index('idx_dca_signal_generated', 'dca_signals', ['generated_at'], unique=False)


def downgrade() -> None:
    # Drop tables in reverse dependency order
    op.drop_index('idx_dca_signal_generated', table_name='dca_signals')
    op.drop_index('idx_dca_signal_type', table_name='dca_signals')
    op.drop_index('idx_dca_signal_deal', table_name='dca_signals')
    op.drop_table('dca_signals')

    op.drop_index('idx_dca_order_exchange', table_name='dca_orders')
    op.drop_index('idx_dca_order_status', table_name='dca_orders')
    op.drop_index('idx_dca_order_deal', table_name='dca_orders')
    op.drop_table('dca_orders')

    op.drop_index('idx_dca_deal_symbol', table_name='dca_deals')
    op.drop_index('idx_dca_deal_status', table_name='dca_deals')
    op.drop_index('idx_dca_deal_strategy', table_name='dca_deals')
    op.drop_table('dca_deals')

    op.drop_index('idx_position_opened', table_name='positions')
    op.drop_index('idx_position_symbol', table_name='positions')
    op.drop_index('idx_position_status', table_name='positions')
    op.drop_index('idx_position_strategy', table_name='positions')
    op.drop_table('positions')

    op.drop_index('idx_signal_executed', table_name='signals')
    op.drop_index('idx_signal_generated', table_name='signals')
    op.drop_index('idx_signal_symbol', table_name='signals')
    op.drop_index('idx_signal_strategy', table_name='signals')
    op.drop_table('signals')

    op.drop_index('idx_strategy_bot', table_name='strategies')
    op.drop_index('idx_strategy_state', table_name='strategies')
    op.drop_index('idx_strategy_type', table_name='strategies')
    op.drop_table('strategies')

    # Drop enum types
    sa.Enum(name='dca_signal_type').drop(op.get_bind(), checkfirst=True)
    sa.Enum(name='dca_order_side').drop(op.get_bind(), checkfirst=True)
    sa.Enum(name='dca_order_status').drop(op.get_bind(), checkfirst=True)
    sa.Enum(name='dca_deal_status').drop(op.get_bind(), checkfirst=True)
    sa.Enum(name='exit_reason').drop(op.get_bind(), checkfirst=True)
    sa.Enum(name='position_status_v2').drop(op.get_bind(), checkfirst=True)
    sa.Enum(name='signal_direction').drop(op.get_bind(), checkfirst=True)
    sa.Enum(name='strategy_state').drop(op.get_bind(), checkfirst=True)
    sa.Enum(name='strategy_type_v2').drop(op.get_bind(), checkfirst=True)
