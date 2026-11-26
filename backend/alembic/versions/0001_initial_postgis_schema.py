"""Initial SmartNav AI PostgreSQL + PostGIS schema

Revision ID: 0001_initial_postgis
Revises:
Create Date: 2026-11-26
"""

from alembic import op
import sqlalchemy as sa

from app.database.spatial import PointGeography

revision = "0001_initial_postgis"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    if bind.dialect.name == "postgresql":
        op.execute("CREATE EXTENSION IF NOT EXISTS postgis")

    op.create_table(
        "users",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("full_name", sa.String(length=120), nullable=False),
        sa.Column("email", sa.String(length=255), nullable=False),
        sa.Column("hashed_password", sa.String(length=255), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_users_email", "users", ["email"], unique=True)

    op.create_table(
        "favorite_places",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("label", sa.String(length=160), nullable=False),
        sa.Column("address", sa.Text(), nullable=True),
        sa.Column("category", sa.String(length=64), nullable=False),
        sa.Column("lat", sa.Float(), nullable=False),
        sa.Column("lng", sa.Float(), nullable=False),
        sa.Column("location", PointGeography(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_favorite_places_user_id", "favorite_places", ["user_id"])

    op.create_table(
        "route_history",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("origin_label", sa.String(length=255), nullable=True),
        sa.Column("destination_label", sa.String(length=255), nullable=True),
        sa.Column("origin_lat", sa.Float(), nullable=False),
        sa.Column("origin_lng", sa.Float(), nullable=False),
        sa.Column("dest_lat", sa.Float(), nullable=False),
        sa.Column("dest_lng", sa.Float(), nullable=False),
        sa.Column("origin_point", PointGeography(), nullable=True),
        sa.Column("dest_point", PointGeography(), nullable=True),
        sa.Column("profile", sa.String(length=32), nullable=False),
        sa.Column("distance_meters", sa.Float(), nullable=False),
        sa.Column("duration_seconds", sa.Float(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_route_history_user_id", "route_history", ["user_id"])

    op.create_table(
        "navigation_sessions",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("origin_label", sa.String(length=255), nullable=True),
        sa.Column("destination_label", sa.String(length=255), nullable=True),
        sa.Column("origin_lat", sa.Float(), nullable=False),
        sa.Column("origin_lng", sa.Float(), nullable=False),
        sa.Column("dest_lat", sa.Float(), nullable=False),
        sa.Column("dest_lng", sa.Float(), nullable=False),
        sa.Column("last_lat", sa.Float(), nullable=True),
        sa.Column("last_lng", sa.Float(), nullable=True),
        sa.Column("last_point", PointGeography(), nullable=True),
        sa.Column("profile", sa.String(length=32), nullable=False),
        sa.Column("route_distance_meters", sa.Float(), nullable=False),
        sa.Column("route_duration_seconds", sa.Float(), nullable=False),
        sa.Column("remaining_distance_meters", sa.Float(), nullable=True),
        sa.Column("reroute_count", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("ended_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("ix_navigation_sessions_user_id", "navigation_sessions", ["user_id"])

    op.create_table(
        "navigation_breadcrumbs",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "session_id",
            sa.Integer(),
            sa.ForeignKey("navigation_sessions.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("lat", sa.Float(), nullable=False),
        sa.Column("lng", sa.Float(), nullable=False),
        sa.Column("point", PointGeography(), nullable=True),
        sa.Column("accuracy_meters", sa.Float(), nullable=True),
        sa.Column("speed_mps", sa.Float(), nullable=True),
        sa.Column("heading_deg", sa.Float(), nullable=True),
        sa.Column("recorded_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_navigation_breadcrumbs_session_id", "navigation_breadcrumbs", ["session_id"])


def downgrade() -> None:
    op.drop_table("navigation_breadcrumbs")
    op.drop_table("navigation_sessions")
    op.drop_table("route_history")
    op.drop_table("favorite_places")
    op.drop_table("users")
