"""recreate schema with master tables

Revision ID: c1d2e3f4a5b6
Revises: befa64175889
Create Date: 2026-09-04 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'c1d2e3f4a5b6'
down_revision: Union[str, None] = 'befa64175889'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # ── Drop all existing tables (data is disposable) ──
    op.execute("DROP TABLE IF EXISTS dealer_returns CASCADE")
    op.execute("DROP TABLE IF EXISTS settlement_handovers CASCADE")
    op.execute("DROP TABLE IF EXISTS settlements CASCADE")
    op.execute("DROP TABLE IF EXISTS dealer_confirmations CASCADE")
    op.execute("DROP TABLE IF EXISTS picking_item_dealers CASCADE")
    op.execute("DROP TABLE IF EXISTS picking_items CASCADE")
    op.execute("DROP TABLE IF EXISTS history_entries CASCADE")
    op.execute("DROP TABLE IF EXISTS handovers CASCADE")
    op.execute("DROP TABLE IF EXISTS picking_lists CASCADE")
    op.execute("DROP TABLE IF EXISTS uploaded_files CASCADE")
    op.execute("DROP TABLE IF EXISTS users CASCADE")
    # Also drop old tables if they exist from previous schemas
    op.execute("DROP TABLE IF EXISTS trucks CASCADE")
    op.execute("DROP TABLE IF EXISTS ksu_items CASCADE")
    op.execute("DROP TABLE IF EXISTS dealers CASCADE")
    op.execute("DROP TABLE IF EXISTS sales_orders CASCADE")

    # ── Master Tables ──

    op.create_table('trucks',
        sa.Column('id', sa.String(length=36), nullable=False),
        sa.Column('expedition', sa.String(length=100), nullable=False),
        sa.Column('plate', sa.String(length=50), nullable=False),
        sa.Column('driver_name', sa.String(length=200), nullable=False),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('expedition', 'plate', 'driver_name', name='uq_truck'),
    )

    op.create_table('ksu_items',
        sa.Column('id', sa.String(length=36), nullable=False),
        sa.Column('code', sa.String(length=100), nullable=False),
        sa.Column('name', sa.String(length=300), nullable=False),
        sa.Column('category', sa.String(length=100), nullable=False),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('code'),
    )

    op.create_table('dealers',
        sa.Column('id', sa.String(length=36), nullable=False),
        sa.Column('code', sa.String(length=50), nullable=False),
        sa.Column('name', sa.String(length=300), nullable=False),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('code'),
    )

    op.create_table('sales_orders',
        sa.Column('id', sa.String(length=36), nullable=False),
        sa.Column('so_number', sa.String(length=100), nullable=False),
        sa.Column('ksu_item_id', sa.String(length=36), nullable=False),
        sa.Column('ksu_quantity', sa.Float(), nullable=False),
        sa.Column('dealer_id', sa.String(length=36), nullable=False),
        sa.ForeignKeyConstraint(['ksu_item_id'], ['ksu_items.id']),
        sa.ForeignKeyConstraint(['dealer_id'], ['dealers.id']),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('so_number'),
    )

    # ── Auth ──

    op.create_table('users',
        sa.Column('id', sa.String(length=36), nullable=False),
        sa.Column('username', sa.String(length=100), nullable=False),
        sa.Column('password_hash', sa.String(length=255), nullable=False),
        sa.Column('name', sa.String(length=200), nullable=False),
        sa.Column('role', sa.String(length=20), nullable=False),
        sa.Column('role_label', sa.String(length=100), nullable=False),
        sa.Column('expedition', sa.String(length=100), nullable=True),
        sa.Column('dealer_code', sa.String(length=50), nullable=True),
        sa.Column('is_active', sa.Boolean(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(op.f('ix_users_username'), 'users', ['username'], unique=True)

    # ── Transaction Tables ──

    op.create_table('picking_lists',
        sa.Column('id', sa.String(length=36), nullable=False),
        sa.Column('picking_id', sa.String(length=100), nullable=False),
        sa.Column('date', sa.String(length=20), nullable=False),
        sa.Column('no_ds', sa.String(length=100), nullable=True),
        sa.Column('truck_id', sa.String(length=36), nullable=False),
        sa.Column('status', sa.String(length=30), nullable=True),
        sa.Column('source_file', sa.String(length=255), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.Column('updated_at', sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(['truck_id'], ['trucks.id']),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('picking_id'),
    )
    op.create_index(op.f('ix_picking_lists_picking_id'), 'picking_lists', ['picking_id'], unique=False)

    op.create_table('picking_items',
        sa.Column('id', sa.String(length=36), nullable=False),
        sa.Column('picking_list_id', sa.String(length=36), nullable=False),
        sa.Column('ksu_item_id', sa.String(length=36), nullable=False),
        sa.Column('code', sa.String(length=100), nullable=False),
        sa.Column('name', sa.String(length=300), nullable=False),
        sa.Column('category', sa.String(length=100), nullable=False),
        sa.Column('planned_qty', sa.Float(), nullable=True),
        sa.Column('actual_qty', sa.Float(), nullable=True),
        sa.Column('confirmed', sa.Boolean(), nullable=True),
        sa.Column('note', sa.Text(), nullable=True),
        sa.ForeignKeyConstraint(['picking_list_id'], ['picking_lists.id']),
        sa.ForeignKeyConstraint(['ksu_item_id'], ['ksu_items.id']),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(op.f('ix_picking_items_picking_list_id'), 'picking_items', ['picking_list_id'], unique=False)

    op.create_table('picking_item_dealers',
        sa.Column('id', sa.String(length=36), nullable=False),
        sa.Column('picking_item_id', sa.String(length=36), nullable=False),
        sa.Column('dealer_id', sa.String(length=36), nullable=False),
        sa.Column('no_so', sa.String(length=100), nullable=True),
        sa.Column('qty', sa.Float(), nullable=True),
        sa.ForeignKeyConstraint(['picking_item_id'], ['picking_items.id']),
        sa.ForeignKeyConstraint(['dealer_id'], ['dealers.id']),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(op.f('ix_picking_item_dealers_picking_item_id'), 'picking_item_dealers', ['picking_item_id'], unique=False)

    # ── Operational Tables ──

    op.create_table('handovers',
        sa.Column('id', sa.String(length=36), nullable=False),
        sa.Column('picking_list_id', sa.String(length=36), nullable=False),
        sa.Column('admin_name', sa.String(length=200), nullable=False),
        sa.Column('driver_name', sa.String(length=200), nullable=False),
        sa.Column('signature_admin_url', sa.Text(), nullable=True),
        sa.Column('signature_driver_url', sa.Text(), nullable=True),
        sa.Column('created_by', sa.String(length=200), nullable=True),
        sa.Column('created_at', sa.String(length=30), nullable=False),
        sa.ForeignKeyConstraint(['picking_list_id'], ['picking_lists.id']),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('picking_list_id'),
    )

    op.create_table('settlements',
        sa.Column('id', sa.String(length=36), nullable=False),
        sa.Column('picking_item_id', sa.String(length=36), nullable=False),
        sa.Column('qty', sa.Float(), nullable=False),
        sa.Column('date', sa.String(length=20), nullable=False),
        sa.Column('driver', sa.String(length=200), nullable=False),
        sa.Column('note', sa.Text(), nullable=True),
        sa.Column('by', sa.String(length=200), nullable=True),
        sa.Column('at', sa.String(length=30), nullable=False),
        sa.ForeignKeyConstraint(['picking_item_id'], ['picking_items.id']),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(op.f('ix_settlements_picking_item_id'), 'settlements', ['picking_item_id'], unique=False)

    op.create_table('settlement_handovers',
        sa.Column('id', sa.String(length=36), nullable=False),
        sa.Column('settlement_id', sa.String(length=36), nullable=False),
        sa.Column('admin_name', sa.String(length=200), nullable=False),
        sa.Column('driver_name', sa.String(length=200), nullable=False),
        sa.Column('signature_admin_url', sa.Text(), nullable=True),
        sa.Column('signature_driver_url', sa.Text(), nullable=True),
        sa.Column('created_by', sa.String(length=200), nullable=True),
        sa.Column('created_at', sa.String(length=30), nullable=False),
        sa.ForeignKeyConstraint(['settlement_id'], ['settlements.id']),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('settlement_id'),
    )

    op.create_table('dealer_confirmations',
        sa.Column('id', sa.String(length=36), nullable=False),
        sa.Column('picking_item_id', sa.String(length=36), nullable=False),
        sa.Column('dealer_code', sa.String(length=50), nullable=False),
        sa.Column('status', sa.String(length=20), nullable=False),
        sa.Column('signature_dealer_url', sa.Text(), nullable=True),
        sa.Column('signature_driver_url', sa.Text(), nullable=True),
        sa.Column('created_at', sa.String(length=30), nullable=False),
        sa.ForeignKeyConstraint(['picking_item_id'], ['picking_items.id']),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(op.f('ix_dealer_confirmations_picking_item_id'), 'dealer_confirmations', ['picking_item_id'], unique=False)

    op.create_table('dealer_returns',
        sa.Column('id', sa.String(length=36), nullable=False),
        sa.Column('dealer_confirmation_id', sa.String(length=36), nullable=False),
        sa.Column('driver', sa.String(length=200), nullable=False),
        sa.Column('return_date', sa.String(length=20), nullable=False),
        sa.Column('notes', sa.Text(), nullable=True),
        sa.ForeignKeyConstraint(['dealer_confirmation_id'], ['dealer_confirmations.id']),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('dealer_confirmation_id'),
    )

    op.create_table('history_entries',
        sa.Column('id', sa.String(length=36), nullable=False),
        sa.Column('picking_list_id', sa.String(length=36), nullable=False),
        sa.Column('at', sa.String(length=30), nullable=False),
        sa.Column('by', sa.String(length=200), nullable=True),
        sa.Column('text', sa.Text(), nullable=False),
        sa.ForeignKeyConstraint(['picking_list_id'], ['picking_lists.id']),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(op.f('ix_history_entries_picking_list_id'), 'history_entries', ['picking_list_id'], unique=False)

    op.create_table('uploaded_files',
        sa.Column('id', sa.String(length=36), nullable=False),
        sa.Column('filename', sa.String(length=255), nullable=False),
        sa.Column('original_name', sa.String(length=255), nullable=False),
        sa.Column('file_url', sa.Text(), nullable=True),
        sa.Column('uploaded_by', sa.String(length=200), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.PrimaryKeyConstraint('id'),
    )


def downgrade() -> None:
    op.drop_table('uploaded_files')
    op.drop_index(op.f('ix_history_entries_picking_list_id'), table_name='history_entries')
    op.drop_table('history_entries')
    op.drop_table('dealer_returns')
    op.drop_index(op.f('ix_dealer_confirmations_picking_item_id'), table_name='dealer_confirmations')
    op.drop_table('dealer_confirmations')
    op.drop_table('settlement_handovers')
    op.drop_index(op.f('ix_settlements_picking_item_id'), table_name='settlements')
    op.drop_table('settlements')
    op.drop_table('handovers')
    op.drop_index(op.f('ix_picking_item_dealers_picking_item_id'), table_name='picking_item_dealers')
    op.drop_table('picking_item_dealers')
    op.drop_index(op.f('ix_picking_items_picking_list_id'), table_name='picking_items')
    op.drop_table('picking_items')
    op.drop_index(op.f('ix_picking_lists_picking_id'), table_name='picking_lists')
    op.drop_table('picking_lists')
    op.drop_table('sales_orders')
    op.drop_table('dealers')
    op.drop_table('ksu_items')
    op.drop_table('trucks')
    op.drop_index(op.f('ix_users_username'), table_name='users')
    op.drop_table('users')
