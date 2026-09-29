-- Owner-scoped confirmed memory; no Qdrant operation.
BEGIN;
CREATE TABLE IF NOT EXISTS memory_facts (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    kind VARCHAR(40) NOT NULL,
    text TEXT NOT NULL,
    source_message_id UUID REFERENCES chat_messages(id) ON DELETE SET NULL,
    status VARCHAR(20) NOT NULL DEFAULT 'pending'
        CONSTRAINT memory_fact_status CHECK (status IN ('pending', 'confirmed', 'rejected')),
    created_at TIMESTAMPTZ NOT NULL,
    confirmed_at TIMESTAMPTZ,
    expires_at TIMESTAMPTZ NOT NULL
);
CREATE INDEX IF NOT EXISTS ix_memory_facts_owner_status ON memory_facts(user_id, status, expires_at);
CREATE TABLE IF NOT EXISTS chat_tasks (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    expires_at TIMESTAMPTZ NOT NULL
);
CREATE INDEX IF NOT EXISTS ix_chat_tasks_user_id ON chat_tasks(user_id);
CREATE INDEX IF NOT EXISTS ix_chat_tasks_expires_at ON chat_tasks(expires_at);
CREATE INDEX IF NOT EXISTS ix_chat_sessions_owner ON chat_sessions(user_id);
CREATE INDEX IF NOT EXISTS ix_chat_messages_retention ON chat_messages(session_id, created_at);
CREATE TABLE IF NOT EXISTS schema_migrations (
    version VARCHAR(128) PRIMARY KEY, applied_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
INSERT INTO schema_migrations(version) VALUES ('20260929_02_memory') ON CONFLICT DO NOTHING;
-- Block legacy raw-chat recall until the confirmed-only mirror is rebuilt.
UPDATE users SET consent_flags = COALESCE(consent_flags, '{}'::jsonb)
    || '{"external_memory_sync_pending": true}'::jsonb
WHERE consent_flags->>'external_memory' = 'true';
COMMIT;
