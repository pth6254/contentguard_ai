"""Scope content IDs per client and persist review history and webhook deliveries."""
import secrets
import sqlalchemy as sa
from alembic import op

revision = "e91a2b4c630f"
down_revision = "d4f7c9e2b851"
branch_labels = None
depends_on = None
_NAMING = {"fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",
           "uq": "uq_%(table_name)s_%(column_0_name)s"}


def upgrade():
    bind = op.get_bind()
    op.add_column("model_predictions", sa.Column("content_record_id", sa.Integer(), nullable=True))
    op.execute(sa.text("UPDATE model_predictions SET content_record_id = "
                       "(SELECT id FROM contents WHERE contents.content_id = model_predictions.content_id)"))
    old_fks = sa.inspect(bind).get_foreign_keys("model_predictions")
    with op.batch_alter_table("model_predictions", naming_convention=_NAMING) as batch:
        for fk in old_fks:
            if fk["constrained_columns"] == ["content_id"]:
                batch.drop_constraint(fk["name"] or "fk_model_predictions_content_id_contents", type_="foreignkey")
        batch.create_foreign_key("fk_predictions_record", "contents", ["content_record_id"], ["id"])
        batch.alter_column("content_record_id", existing_type=sa.Integer(), nullable=False)
        batch.create_index("ix_model_predictions_content_record_id", ["content_record_id"])

    inspector = sa.inspect(bind)
    old_uqs = inspector.get_unique_constraints("contents")
    for index in inspector.get_indexes("contents"):
        if index["unique"] and index["column_names"] == ["content_id"] and not index.get("duplicates_constraint"):
            op.drop_index(index["name"], table_name="contents")
    with op.batch_alter_table("contents", naming_convention=_NAMING) as batch:
        for uq in old_uqs:
            if uq["column_names"] == ["content_id"]:
                batch.drop_constraint(uq["name"] or "uq_contents_content_id", type_="unique")
        batch.create_unique_constraint("uq_contents_client_content", ["client_id", "content_id"])
        batch.add_column(sa.Column("review_version", sa.Integer(), nullable=False, server_default="0"))
    if "ix_contents_content_id" not in {i["name"] for i in sa.inspect(bind).get_indexes("contents")}:
        op.create_index("ix_contents_content_id", "contents", ["content_id"])
    op.create_index("uq_contents_operator_content", "contents", ["content_id"], unique=True,
                    postgresql_where=sa.text("client_id IS NULL"), sqlite_where=sa.text("client_id IS NULL"))

    op.add_column("clients", sa.Column("webhook_secret", sa.String(64), nullable=True))
    for row in bind.execute(sa.text("SELECT id FROM clients")).fetchall():
        bind.execute(sa.text("UPDATE clients SET webhook_secret=:secret WHERE id=:id"),
                     {"secret": secrets.token_hex(32), "id": row[0]})
    with op.batch_alter_table("clients") as batch:
        batch.alter_column("webhook_secret", existing_type=sa.String(64), nullable=False)

    op.create_table("review_events",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("content_record_id", sa.Integer(), nullable=False, index=True),
        sa.Column("content_id", sa.String(), nullable=False),
        sa.Column("client_id", sa.Integer()), sa.Column("operator_id", sa.Integer()),
        sa.Column("actor", sa.String(), nullable=False),
        sa.Column("previous_status", sa.String(), nullable=False),
        sa.Column("previous_action", sa.String()), sa.Column("previous_comment", sa.Text()),
        sa.Column("action", sa.String(), nullable=False), sa.Column("status", sa.String(), nullable=False),
        sa.Column("comment", sa.Text()), sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.UniqueConstraint("content_record_id", "version", name="uq_review_event_version"))
    op.create_table("webhook_deliveries",
        sa.Column("id", sa.String(32), primary_key=True),
        sa.Column("review_event_id", sa.Integer(), sa.ForeignKey("review_events.id"), nullable=False, unique=True),
        sa.Column("url", sa.Text(), nullable=False), sa.Column("secret", sa.String(64), nullable=False),
        sa.Column("body", sa.Text(), nullable=False),
        sa.Column("status", sa.String(), nullable=False, index=True),
        sa.Column("attempts", sa.Integer(), nullable=False),
        sa.Column("next_attempt_at", sa.DateTime(), nullable=False, index=True),
        sa.Column("last_error", sa.String()), sa.Column("delivered_at", sa.DateTime()))


def downgrade():
    bind = op.get_bind()
    duplicates = bind.execute(sa.text("SELECT content_id FROM contents GROUP BY content_id HAVING COUNT(*) > 1 LIMIT 1")).first()
    if duplicates:
        raise RuntimeError("고객별 중복 콘텐츠 ID를 정리한 후 다운그레이드하세요.")
    op.drop_table("webhook_deliveries")
    op.drop_table("review_events")
    with op.batch_alter_table("clients") as batch:
        batch.drop_column("webhook_secret")
    op.drop_index("uq_contents_operator_content", table_name="contents")
    with op.batch_alter_table("contents", naming_convention=_NAMING) as batch:
        batch.drop_constraint("uq_contents_client_content", type_="unique")
        batch.create_unique_constraint("uq_contents_content_id", ["content_id"])
        batch.drop_column("review_version")
    with op.batch_alter_table("model_predictions", naming_convention=_NAMING) as batch:
        batch.drop_constraint("fk_predictions_record", type_="foreignkey")
        batch.drop_index("ix_model_predictions_content_record_id")
        batch.drop_column("content_record_id")
        batch.create_foreign_key("fk_model_predictions_content_id_contents", "contents", ["content_id"], ["content_id"])
