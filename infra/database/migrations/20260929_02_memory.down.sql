-- Lossy rollback: export memory facts and task ownership before using this file.
BEGIN;
DROP TABLE IF EXISTS chat_tasks;
DROP TABLE IF EXISTS memory_facts;
DROP INDEX IF EXISTS ix_chat_sessions_owner;
DROP INDEX IF EXISTS ix_chat_messages_retention;
DELETE FROM schema_migrations WHERE version = '20260929_02_memory';
COMMIT;
