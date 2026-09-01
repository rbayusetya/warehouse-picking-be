"""rename_handover_columns

Revision ID: 08e53341e9eb
Revises:
Create Date: 2026-06-14 22:50:30.983714

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect
from sqlalchemy.engine.mock import MockConnection


revision: str = '08e53341e9eb'
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _has_column(table: str, column: str) -> bool:
    conn = op.get_bind()
    inspector = inspect(conn)
    columns = [c["name"] for c in inspector.get_columns(table)]
    return column in columns


def _create_all_tables() -> None:
    """Create all tables from scratch (fresh database or offline mode)."""
    op.create_table('picking_lists',
        sa.Column('id', sa.String(length=36), nullable=False),
        sa.Column('picking_id', sa.String(length=100), nullable=False),
        sa.Column('date', sa.String(length=20), nullable=False),
        sa.Column('no_ds', sa.String(length=100), nullable=True),
        sa.Column('expedition', sa.String(length=100), nullable=False),
        sa.Column('plate', sa.String(length=50), nullable=True),
        sa.Column('driver', sa.String(length=200), nullable=False),
        sa.Column('status', sa.String(length=30), nullable=True),
        sa.Column('source_file', sa.String(length=255), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.Column('updated_at', sa.DateTime(), nullable=True),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_picking_lists_picking_id'), 'picking_lists', ['picking_id'], unique=False)
    op.create_table('uploaded_files',
        sa.Column('id', sa.String(length=36), nullable=False),
        sa.Column('filename', sa.String(length=255), nullable=False),
        sa.Column('original_name', sa.String(length=255), nullable=False),
        sa.Column('file_url', sa.Text(), nullable=True),
        sa.Column('uploaded_by', sa.String(length=200), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.PrimaryKeyConstraint('id')
    )
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
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_users_username'), 'users', ['username'], unique=True)
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
        sa.UniqueConstraint('picking_list_id')
    )
    op.create_table('history_entries',
        sa.Column('id', sa.String(length=36), nullable=False),
        sa.Column('picking_list_id', sa.String(length=36), nullable=False),
        sa.Column('at', sa.String(length=30), nullable=False),
        sa.Column('by', sa.String(length=200), nullable=True),
        sa.Column('text', sa.Text(), nullable=False),
        sa.ForeignKeyConstraint(['picking_list_id'], ['picking_lists.id']),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_history_entries_picking_list_id'), 'history_entries', ['picking_list_id'], unique=False)
    op.create_table('picking_items',
        sa.Column('id', sa.String(length=36), nullable=False),
        sa.Column('picking_list_id', sa.String(length=36), nullable=False),
        sa.Column('code', sa.String(length=100), nullable=False),
        sa.Column('name', sa.String(length=300), nullable=False),
        sa.Column('category', sa.String(length=100), nullable=False),
        sa.Column('planned_qty', sa.Float(), nullable=True),
        sa.Column('actual_qty', sa.Float(), nullable=True),
        sa.Column('confirmed', sa.Boolean(), nullable=True),
        sa.Column('note', sa.Text(), nullable=True),
        sa.ForeignKeyConstraint(['picking_list_id'], ['picking_lists.id']),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_picking_items_picking_list_id'), 'picking_items', ['picking_list_id'], unique=False)
    op.create_table('dealer_confirmations',
        sa.Column('id', sa.String(length=36), nullable=False),
        sa.Column('picking_item_id', sa.String(length=36), nullable=False),
        sa.Column('dealer_code', sa.String(length=50), nullable=False),
        sa.Column('status', sa.String(length=20), nullable=False),
        sa.Column('signature_dealer_url', sa.Text(), nullable=True),
        sa.Column('signature_driver_url', sa.Text(), nullable=True),
        sa.Column('created_at', sa.String(length=30), nullable=False),
        sa.ForeignKeyConstraint(['picking_item_id'], ['picking_items.id']),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_dealer_confirmations_picking_item_id'), 'dealer_confirmations', ['picking_item_id'], unique=False)
    op.create_table('picking_item_dealers',
        sa.Column('id', sa.String(length=36), nullable=False),
        sa.Column('picking_item_id', sa.String(length=36), nullable=False),
        sa.Column('no_so', sa.String(length=100), nullable=True),
        sa.Column('code', sa.String(length=50), nullable=False),
        sa.Column('dealer', sa.String(length=300), nullable=False),
        sa.Column('qty', sa.Float(), nullable=True),
        sa.ForeignKeyConstraint(['picking_item_id'], ['picking_items.id']),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_picking_item_dealers_picking_item_id'), 'picking_item_dealers', ['picking_item_id'], unique=False)
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
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_settlements_picking_item_id'), 'settlements', ['picking_item_id'], unique=False)
    op.create_table('dealer_returns',
        sa.Column('id', sa.String(length=36), nullable=False),
        sa.Column('dealer_confirmation_id', sa.String(length=36), nullable=False),
        sa.Column('driver', sa.String(length=200), nullable=False),
        sa.Column('return_date', sa.String(length=20), nullable=False),
        sa.Column('notes', sa.Text(), nullable=True),
        sa.ForeignKeyConstraint(['dealer_confirmation_id'], ['dealer_confirmations.id']),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('dealer_confirmation_id')
    )


def upgrade() -> None:
    conn = op.get_bind()

    if isinstance(conn, MockConnection):
        _create_all_tables()
        return

    inspector = inspect(conn)
    tables = inspector.get_table_names()

    if "handovers" in tables:
        has_old = _has_column("handovers", "receiver_name")
        has_old_photo = _has_column("handovers", "photo_url")
        has_old_sig = _has_column("handovers", "signature_url")

        if has_old:
            with op.batch_alter_table("handovers") as batch_op:
                batch_op.alter_column("receiver_name", new_column_name="admin_name")
                batch_op.add_column(sa.Column("driver_name", sa.String(200), nullable=False, server_default=""))
                if has_old_photo:
                    batch_op.alter_column("photo_url", new_column_name="signature_admin_url")
                if has_old_sig:
                    batch_op.alter_column("signature_url", new_column_name="signature_driver_url")
        else:
            if not _has_column("handovers", "admin_name"):
                with op.batch_alter_table("handovers") as batch_op:
                    batch_op.add_column(sa.Column("admin_name", sa.String(200), nullable=False, server_default=""))
            if not _has_column("handovers", "driver_name"):
                with op.batch_alter_table("handovers") as batch_op:
                    batch_op.add_column(sa.Column("driver_name", sa.String(200), nullable=False, server_default=""))
            if not _has_column("handovers", "signature_admin_url") and has_old_photo:
                with op.batch_alter_table("handovers") as batch_op:
                    batch_op.alter_column("photo_url", new_column_name="signature_admin_url")
            if not _has_column("handovers", "signature_driver_url") and has_old_sig:
                with op.batch_alter_table("handovers") as batch_op:
                    batch_op.alter_column("signature_url", new_column_name="signature_driver_url")
    else:
        _create_all_tables()


def downgrade() -> None:
    op.drop_table('dealer_returns')
    op.drop_index(op.f('ix_settlements_picking_item_id'), table_name='settlements')
    op.drop_table('settlements')
    op.drop_index(op.f('ix_picking_item_dealers_picking_item_id'), table_name='picking_item_dealers')
    op.drop_table('picking_item_dealers')
    op.drop_index(op.f('ix_dealer_confirmations_picking_item_id'), table_name='dealer_confirmations')
    op.drop_table('dealer_confirmations')
    op.drop_index(op.f('ix_picking_items_picking_list_id'), table_name='picking_items')
    op.drop_table('picking_items')
    op.drop_index(op.f('ix_history_entries_picking_list_id'), table_name='history_entries')
    op.drop_table('history_entries')
    op.drop_table('handovers')
    op.drop_index(op.f('ix_users_username'), table_name='users')
    op.drop_table('users')
    op.drop_table('uploaded_files')
    op.drop_index(op.f('ix_picking_lists_picking_id'), table_name='picking_lists')
    op.drop_table('picking_lists')
