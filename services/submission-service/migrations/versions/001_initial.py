"""initial schema

Revision ID: 001
Revises:
Create Date: 2024-01-01 00:00:00
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID

revision = "001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade():
    op.execute('CREATE EXTENSION IF NOT EXISTS "pgcrypto"')

    op.create_table(
        "submissions",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("user_id", UUID(as_uuid=True), nullable=False),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("age", sa.SmallInteger(), nullable=False),
        sa.Column("place_of_living", sa.String(255), nullable=False),
        sa.Column("gender", sa.String(50), nullable=False),
        sa.Column("country_of_origin", sa.String(2), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("photo_key", sa.String(512), nullable=False),
        sa.Column("status", sa.String(50), nullable=False, server_default="pending"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("NOW()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("NOW()")),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("ix_submissions_user_id", "submissions", ["user_id"])
    op.create_index("ix_submissions_gender", "submissions", ["gender"])
    op.create_index("ix_submissions_country", "submissions", ["country_of_origin"])
    op.create_index("ix_submissions_age", "submissions", ["age"])
    op.create_index("ix_submissions_created_at", "submissions", ["created_at"])
    op.create_index("ix_submissions_deleted_at", "submissions", ["deleted_at"],
                    postgresql_where=sa.text("deleted_at IS NULL"))

    op.create_table(
        "results",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("submission_id", UUID(as_uuid=True), sa.ForeignKey("submissions.id", ondelete="CASCADE"),
                  nullable=False, unique=True),
        sa.Column("classifier_version", sa.String(50), nullable=False),
        sa.Column("label", sa.String(255), nullable=False),
        sa.Column("confidence", sa.Float(), nullable=True),
        sa.Column("details", sa.Text(), nullable=True),
        sa.Column("classified_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("NOW()")),
    )
    op.create_index("ix_results_submission_id", "results", ["submission_id"])


def downgrade():
    op.drop_table("results")
    op.drop_table("submissions")
