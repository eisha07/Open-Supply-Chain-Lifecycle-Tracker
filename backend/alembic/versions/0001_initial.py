"""Initial schema — all tables for OSLT v1.1

Revision ID: 0001_initial
Revises:
Create Date: 2025-08-30 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = "0001_initial"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # ── actors ────────────────────────────────────────────────────────────────
    op.create_table(
        "actors",
        sa.Column("did", sa.String(256), primary_key=True, index=True),
        sa.Column("display_name", sa.String(128), nullable=False),
        sa.Column("role", sa.Enum(
            "RAW_MATERIAL_SUPPLIER", "OEM_MANUFACTURER",
            "FIELD_TECHNICIAN", "RECYCLER_DISMANTLER", "PUBLIC",
            name="actorrole",
        ), nullable=False, index=True),
        sa.Column("public_key_hex", sa.String(64), nullable=False, unique=True),
        sa.Column("is_blacklisted", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True)),
    )

    # ── twins ─────────────────────────────────────────────────────────────────
    op.create_table(
        "twins",
        sa.Column("id", sa.String(256), primary_key=True, index=True),
        sa.Column("name", sa.String(256), nullable=False),
        sa.Column("product_type", sa.String(128), nullable=False),
        sa.Column("parent_twin_id", sa.String(256),
                  sa.ForeignKey("twins.id", ondelete="SET NULL"),
                  nullable=True, index=True),
        sa.Column("status", sa.Enum(
            "ACTIVE", "PROVENANCE_GAP_DETECTED", "TAMPERED_SAFETY_RISK",
            "UNSUITABLE_FOR_AUTOMOTIVE", "RECOMMENDED_FOR_STATIONARY_STORAGE",
            "DECOMMISSIONED", "SCRAPPED",
            name="twinstatus",
        ), nullable=False, server_default="ACTIVE", index=True),
        sa.Column("version_id", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("manufacturer_did", sa.String(256), nullable=False),
        sa.Column("manufacturing_date", sa.DateTime(timezone=True)),
        sa.Column("serial_number", sa.String(128), nullable=True, unique=True, index=True),
        sa.Column("material_weights_kg", sa.JSON()),
        sa.Column("baseline_chemistry", sa.JSON()),
        sa.Column("initial_capacity_kwh", sa.Float()),
        sa.Column("initial_safety_rating", sa.String(64)),
        sa.Column("current_capacity_kwh", sa.Float()),
        sa.Column("current_soh_pct", sa.Float()),
        sa.Column("current_chemistry", sa.JSON()),
        sa.Column("current_safety_rating", sa.String(64)),
        sa.Column("recyclability_score", sa.Float()),
        sa.Column("zkp_flags", sa.JSON()),
        sa.Column("has_provenance_gap", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("tamper_alert_payload", sa.JSON()),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True)),
    )

    # ── product_events (append-only ledger) ───────────────────────────────────
    op.create_table(
        "product_events",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("twin_id", sa.String(256),
                  sa.ForeignKey("twins.id", ondelete="CASCADE"),
                  nullable=False, index=True),
        sa.Column("event_type", sa.Enum(
            "EXTRACTION", "ASSEMBLY", "CUSTODY_TRANSFER", "REPAIR_PART_SWAP",
            "TELEMETRY_SNAPSHOT", "DECOMMISSION", "SECURITY_ALERT",
            "PROVENANCE_GAP_AUDIT",
            name="eventtype",
        ), nullable=False, index=True),
        sa.Column("sequence_num", sa.Integer(), nullable=False),
        sa.Column("actor_did", sa.String(256),
                  sa.ForeignKey("actors.did", ondelete="RESTRICT"),
                  nullable=False, index=True),
        sa.Column("actor_timestamp", sa.DateTime(timezone=True), nullable=False),
        sa.Column("server_timestamp", sa.DateTime(timezone=True),
                  server_default=sa.func.now(), nullable=False),
        sa.Column("metadata_json", sa.JSON(), nullable=False, server_default="{}"),
        sa.Column("cryptographic_signature", sa.Text(), nullable=False),
        sa.Column("previous_event_hash", sa.String(64)),
        sa.UniqueConstraint("twin_id", "sequence_num", name="uq_twin_sequence"),
    )
    op.create_index("ix_product_events_twin_seq", "product_events",
                    ["twin_id", "sequence_num"])

    # ── untrusted_telemetry (quarantine) ──────────────────────────────────────
    op.create_table(
        "untrusted_telemetry",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("twin_id", sa.String(256),
                  sa.ForeignKey("twins.id", ondelete="SET NULL"),
                  nullable=True, index=True),
        sa.Column("actor_did", sa.String(256), nullable=True),
        sa.Column("raw_payload", sa.JSON(), nullable=False),
        sa.Column("quarantine_reason", sa.String(128), nullable=False),
        sa.Column("detail", sa.Text()),
        sa.Column("reported_value", sa.Float()),
        sa.Column("expected_range_min", sa.Float()),
        sa.Column("expected_range_max", sa.Float()),
        sa.Column("ingested_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )

    # ── blacklisted_serials (counterfeit registry) ────────────────────────────
    op.create_table(
        "blacklisted_serials",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("serial_number", sa.String(256), nullable=False, unique=True, index=True),
        sa.Column("reason", sa.Text()),
        sa.Column("added_by_did", sa.String(256),
                  sa.ForeignKey("actors.did", ondelete="SET NULL"),
                  nullable=True, index=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )


def downgrade() -> None:
    op.drop_table("blacklisted_serials")
    op.drop_table("untrusted_telemetry")
    op.drop_index("ix_product_events_twin_seq", table_name="product_events")
    op.drop_table("product_events")
    op.drop_table("twins")
    op.drop_table("actors")
    # Drop enums
    op.execute("DROP TYPE IF EXISTS eventtype")
    op.execute("DROP TYPE IF EXISTS twinstatus")
    op.execute("DROP TYPE IF EXISTS actorrole")
