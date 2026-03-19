"""Initial schema — all core tables.

Revision ID: 0001
Revises:
Create Date: 2025-03-19
"""
from __future__ import annotations
from typing import Sequence, Union

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql
from alembic import op
import geoalchemy2

revision: str = "0001"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Enable PostGIS
    op.execute("CREATE EXTENSION IF NOT EXISTS postgis")

    op.create_table(
        "road_segments",
        sa.Column("id", sa.String(100), primary_key=True),
        sa.Column("pilot", sa.String(50), nullable=False),
        sa.Column("name", sa.String(200), nullable=True),
        sa.Column("geom", geoalchemy2.types.Geometry("LINESTRING", srid=4326), nullable=False),
        sa.Column("length_m", sa.Float, nullable=True),
        sa.Column("speed_limit_kmh", sa.SmallInteger, nullable=True),
        sa.Column("road_class", sa.String(50), nullable=True),
        sa.Column("lanes", sa.SmallInteger, nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), onupdate=sa.func.now(), nullable=False),
    )

    op.create_table(
        "speed_baseline",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("segment_id", sa.String(100), sa.ForeignKey("road_segments.id"), nullable=False),
        sa.Column("hour_of_day", sa.SmallInteger, nullable=False),
        sa.Column("day_of_week", sa.SmallInteger, nullable=False),
        sa.Column("local_hour_of_day", sa.SmallInteger, nullable=True),
        sa.Column("local_day_of_week", sa.SmallInteger, nullable=True),
        sa.Column("timezone", sa.String(64), server_default="UTC"),
        sa.Column("avg_speed_kmh", sa.Float, nullable=False),
        sa.Column("std_speed_kmh", sa.Float, nullable=True),
        sa.Column("sample_count", sa.Integer, server_default="0"),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), onupdate=sa.func.now(), nullable=False),
        sa.UniqueConstraint("segment_id", "hour_of_day", "day_of_week", name="uq_baseline_segment_hour_dow"),
    )

    op.create_table(
        "incidents",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("pilot", sa.String(50), nullable=False),
        sa.Column("incident_type", sa.String(100), nullable=False),
        sa.Column("severity", sa.SmallInteger, nullable=True),
        sa.Column("status", sa.String(50), server_default="active"),
        sa.Column("location_geom", geoalchemy2.types.Geometry("POINT", srid=4326), nullable=True),
        sa.Column("segment_id", sa.String(100), sa.ForeignKey("road_segments.id"), nullable=True),
        sa.Column("description", sa.Text, nullable=True),
        sa.Column("source", sa.String(100), nullable=True),
        sa.Column("external_id", sa.String(200), nullable=True),
        sa.Column("started_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("ended_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_incidents_segment_status", "incidents", ["segment_id", "status"])

    op.create_table(
        "road_assets",
        sa.Column("id", sa.String(100), primary_key=True),
        sa.Column("pilot", sa.String(50), nullable=False),
        sa.Column("asset_type", sa.String(100), nullable=False),
        sa.Column("location_geom", geoalchemy2.types.Geometry("POINT", srid=4326), nullable=True),
        sa.Column("segment_id", sa.String(100), sa.ForeignKey("road_segments.id"), nullable=True),
        sa.Column("installed_at", sa.Date, nullable=True),
        sa.Column("last_inspected", sa.Date, nullable=True),
        sa.Column("condition_score", sa.SmallInteger, nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )

    op.create_table(
        "damage_detections",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("asset_id", sa.String(100), sa.ForeignKey("road_assets.id"), nullable=True),
        sa.Column("camera_id", sa.String(100), nullable=True),
        sa.Column("defect_class", sa.String(10), nullable=False),
        sa.Column("confidence", sa.Float, nullable=False),
        sa.Column("bbox_json", postgresql.JSONB, nullable=True),
        sa.Column("s3_annotated_key", sa.String(500), nullable=True),
        sa.Column("detected_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("reviewed", sa.Boolean, server_default="false"),
        sa.Column("is_confirmed", sa.Boolean, nullable=True),
    )

    op.create_table(
        "maintenance_tickets",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("asset_id", sa.String(100), sa.ForeignKey("road_assets.id"), nullable=False),
        sa.Column("detection_id", sa.Integer, sa.ForeignKey("damage_detections.id"), nullable=True),
        sa.Column("pilot", sa.String(50), nullable=False),
        sa.Column("status", sa.String(50), server_default="open"),
        sa.Column("priority", sa.SmallInteger, server_default="3"),
        sa.Column("title", sa.String(300), nullable=False),
        sa.Column("description", sa.Text, nullable=True),
        sa.Column("assigned_to", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("created_by", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), onupdate=sa.func.now(), nullable=False),
        sa.Column("resolved_at", sa.DateTime(timezone=True), nullable=True),
    )

    op.create_table(
        "users",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("email", sa.String(320), unique=True, nullable=False),
        sa.Column("name", sa.String(200), nullable=True),
        sa.Column("role", sa.String(50), server_default="viewer"),
        sa.Column("pilot_scope", sa.String(100), nullable=True),
        sa.Column("password_hash", sa.String(200), nullable=True),
        sa.Column("is_active", sa.Boolean, server_default="true"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("last_login_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("ix_users_email", "users", ["email"], unique=True)

    op.create_table(
        "vehicle_tracks",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("track_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("camera_id", sa.String(100), nullable=False),
        sa.Column("segment_id", sa.String(100), sa.ForeignKey("road_segments.id"), nullable=True),
        sa.Column("vehicle_class", sa.String(50), nullable=True),
        sa.Column("observed_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("speed_kmh", sa.Float, nullable=True),
        sa.Column("direction", sa.SmallInteger, nullable=True),
    )
    op.create_index("ix_vehicle_tracks_observed", "vehicle_tracks", ["observed_at"])

    op.create_table(
        "push_subscriptions",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("endpoint", sa.Text, unique=True, nullable=False),
        sa.Column("p256dh", sa.Text, nullable=False),
        sa.Column("auth", sa.Text, nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("is_active", sa.Boolean, server_default="true"),
    )


def downgrade() -> None:
    op.drop_table("push_subscriptions")
    op.drop_table("vehicle_tracks")
    op.drop_table("users")
    op.drop_table("maintenance_tickets")
    op.drop_table("damage_detections")
    op.drop_table("road_assets")
    op.drop_index("ix_incidents_segment_status", "incidents")
    op.drop_table("incidents")
    op.drop_table("speed_baseline")
    op.drop_table("road_segments")
