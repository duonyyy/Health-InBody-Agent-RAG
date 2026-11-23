-- Migration: Add status and idempotency payload to chat_tasks
BEGIN;

ALTER TABLE chat_tasks ADD COLUMN IF NOT EXISTS status VARCHAR(20) NOT NULL DEFAULT 'pending';
ALTER TABLE chat_tasks ADD COLUMN IF NOT EXISTS result_payload TEXT;
ALTER TABLE chat_tasks ADD COLUMN IF NOT EXISTS created_at TIMESTAMPTZ NOT NULL DEFAULT NOW();
ALTER TABLE chat_tasks ADD COLUMN IF NOT EXISTS updated_at TIMESTAMPTZ;

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_constraint WHERE conname = 'chat_task_status'
    ) THEN
        ALTER TABLE chat_tasks ADD CONSTRAINT chat_task_status
            CHECK (status IN ('pending', 'processing', 'completed', 'failed'));
    END IF;
END $$;

CREATE INDEX IF NOT EXISTS ix_chat_tasks_owner_status ON chat_tasks(user_id, status);

INSERT INTO schema_migrations(version) VALUES ('20261123_04_chat_task_idempotency') ON CONFLICT DO NOTHING;

COMMIT;
