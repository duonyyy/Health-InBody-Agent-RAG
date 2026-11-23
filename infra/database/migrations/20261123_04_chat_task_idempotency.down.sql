-- Rollback migration: Add status and idempotency payload to chat_tasks
BEGIN;

ALTER TABLE chat_tasks DROP CONSTRAINT IF EXISTS chat_task_status;
DROP INDEX IF EXISTS ix_chat_tasks_owner_status;
ALTER TABLE chat_tasks DROP COLUMN IF EXISTS updated_at;
ALTER TABLE chat_tasks DROP COLUMN IF EXISTS created_at;
ALTER TABLE chat_tasks DROP COLUMN IF EXISTS result_payload;
ALTER TABLE chat_tasks DROP COLUMN IF EXISTS status;

DELETE FROM schema_migrations WHERE version = '20261123_04_chat_task_idempotency';

COMMIT;
