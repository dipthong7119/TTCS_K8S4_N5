import re

with open("backend/alembic/versions/a6d2f891c104_add_ocpp_raw_status_scoped_idempotency_.py", "r", encoding="utf-8") as f:
    content = f.read()

new_downgrade = """def downgrade() -> None:
    op.drop_index("ix_connector_errors_connector_timestamp", table_name="connector_errors")
    op.drop_index("uq_ocpp_message_per_charge_point", table_name="ocpp_messages")
    op.create_index("ix_ocpp_messages_msg_id", "ocpp_messages", ["msg_id"], unique=True)
    with op.batch_alter_table("ocpp_messages") as batch_op:
        batch_op.drop_column("request_hash")
    with op.batch_alter_table("connectors") as batch_op:
        batch_op.drop_column("ocpp_status")
    with op.batch_alter_table("charge_points") as batch_op:
        batch_op.drop_column("ocpp_status")
"""

content = re.sub(r"def downgrade\(\) -> None:.*?(?=\Z|\n\n)", new_downgrade, content, flags=re.DOTALL)

with open("backend/alembic/versions/a6d2f891c104_add_ocpp_raw_status_scoped_idempotency_.py", "w", encoding="utf-8") as f:
    f.write(content)
