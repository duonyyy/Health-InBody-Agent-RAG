CREATE EXTENSION IF NOT EXISTS pgcrypto;

CREATE TABLE IF NOT EXISTS schema_migrations (
    version VARCHAR(128) PRIMARY KEY,
    applied_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

INSERT INTO schema_migrations(version)
VALUES ('20260815_01_p1_personalization')
ON CONFLICT (version) DO NOTHING;

INSERT INTO schema_migrations(version)
VALUES ('20260929_02_memory')
ON CONFLICT (version) DO NOTHING;

CREATE TABLE IF NOT EXISTS users (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    external_id VARCHAR(128) UNIQUE,
    full_name VARCHAR(255),
    email VARCHAR(255) UNIQUE,
    sex VARCHAR(32),
    birth_year INTEGER,
    height_cm NUMERIC(6, 2),
    activity_level VARCHAR(64),
    goal VARCHAR(64),
    medical_conditions TEXT,
    display_name VARCHAR(80),
    birth_date DATE,
    age_range VARCHAR(32),
    sex_at_birth VARCHAR(32),
    dietary_preferences JSONB,
    exercise_constraints JSONB,
    medical_conditions_data JSONB,
    consent_flags JSONB NOT NULL DEFAULT '{"health_data_processing": false, "personalization": false}'::jsonb,
    profile_confirmed_at TIMESTAMPTZ,
    deleted_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS inbody_measurements (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    measurement_date DATE NOT NULL,
    height_cm NUMERIC(6, 2),
    weight_kg NUMERIC(6, 2),
    bmi NUMERIC(5, 2),
    smm_kg NUMERIC(6, 2),
    bfm_kg NUMERIC(6, 2),
    pbf_percent NUMERIC(5, 2),
    visceral_fat_level NUMERIC(5, 2),
    body_water_l NUMERIC(6, 2),
    recommendation_goal VARCHAR(64),
    source_file VARCHAR(512),
    raw_payload JSONB,
    measured_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    source_type VARCHAR(32) NOT NULL DEFAULT 'legacy_unconfirmed',
    confidence NUMERIC(4, 3),
    confirmed_by_user BOOLEAN NOT NULL DEFAULT FALSE,
    confirmed_at TIMESTAMPTZ,
    deleted_at TIMESTAMPTZ,
    delete_reason VARCHAR(240),
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_inbody_measurements_user_date
    ON inbody_measurements(user_id, measurement_date DESC);

CREATE INDEX IF NOT EXISTS idx_inbody_measurements_owner_cursor
    ON inbody_measurements(user_id, measured_at DESC, id DESC)
    WHERE deleted_at IS NULL;

CREATE INDEX IF NOT EXISTS idx_inbody_measurements_owner_confirmed
    ON inbody_measurements(user_id, measured_at DESC, id DESC)
    WHERE deleted_at IS NULL AND confirmed_by_user IS TRUE;

CREATE TABLE IF NOT EXISTS personalization_goals (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    version INTEGER NOT NULL CHECK (version > 0),
    goal_type VARCHAR(32) NOT NULL,
    target_weight_kg NUMERIC(6, 2),
    target_date DATE,
    training_days_per_week INTEGER,
    weekly_activity_level VARCHAR(32),
    constraints JSONB NOT NULL DEFAULT '[]'::jsonb,
    status VARCHAR(32) NOT NULL DEFAULT 'active',
    supersedes_goal_id UUID REFERENCES personalization_goals(id) ON DELETE SET NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE (user_id, version)
);

CREATE INDEX IF NOT EXISTS idx_personalization_goals_owner_history
    ON personalization_goals(user_id, version DESC);

CREATE UNIQUE INDEX IF NOT EXISTS uq_personalization_goals_owner_active
    ON personalization_goals(user_id) WHERE status = 'active';

CREATE TABLE IF NOT EXISTS personalized_plans (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    version INTEGER NOT NULL CHECK (version > 0),
    status VARCHAR(32) NOT NULL DEFAULT 'draft',
    input_snapshot JSONB NOT NULL,
    goal_version INTEGER,
    measurement_ids JSONB NOT NULL DEFAULT '[]'::jsonb,
    evidence_ids JSONB NOT NULL DEFAULT '[]'::jsonb,
    citations JSONB NOT NULL DEFAULT '[]'::jsonb,
    safety_result JSONB NOT NULL,
    content JSONB NOT NULL,
    archived_at TIMESTAMPTZ,
    archive_reason VARCHAR(240),
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE (user_id, version)
);

CREATE INDEX IF NOT EXISTS idx_personalized_plans_owner_history
    ON personalized_plans(user_id, version DESC);

CREATE UNIQUE INDEX IF NOT EXISTS uq_personalized_plans_owner_active
    ON personalized_plans(user_id) WHERE status = 'active';

CREATE TABLE IF NOT EXISTS check_ins (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    checked_at TIMESTAMPTZ NOT NULL,
    adherence INTEGER,
    energy_level INTEGER,
    sleep_quality INTEGER,
    soreness INTEGER,
    symptoms JSONB NOT NULL DEFAULT '[]'::jsonb,
    note TEXT,
    safety_result JSONB NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_check_ins_owner_cursor
    ON check_ins(user_id, checked_at DESC, id DESC);

CREATE TABLE IF NOT EXISTS chat_sessions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    bot_id VARCHAR(128) NOT NULL DEFAULT 'health-inbody-agent',
    user_id UUID REFERENCES users(id) ON DELETE SET NULL,
    external_user_id VARCHAR(128),
    title VARCHAR(255),
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_chat_sessions_external_user
    ON chat_sessions(external_user_id, created_at DESC);

CREATE TABLE IF NOT EXISTS chat_messages (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    session_id UUID NOT NULL REFERENCES chat_sessions(id) ON DELETE CASCADE,
    role VARCHAR(32) NOT NULL,
    content TEXT NOT NULL,
    route VARCHAR(64),
    metadata JSONB,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_chat_messages_session_created
    ON chat_messages(session_id, created_at ASC);

CREATE TABLE IF NOT EXISTS documents (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    external_id VARCHAR(128) UNIQUE,
    title VARCHAR(512),
    content TEXT NOT NULL,
    source VARCHAR(512),
    document_type VARCHAR(128),
    content_type VARCHAR(128),
    domain VARCHAR(128) NOT NULL DEFAULT 'health_inbody',
    metadata JSONB,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_documents_content_type
    ON documents(content_type);

CREATE TABLE IF NOT EXISTS document_chunks (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    document_id UUID REFERENCES documents(id) ON DELETE CASCADE,
    qdrant_point_id VARCHAR(128) UNIQUE,
    chunk_index INTEGER NOT NULL,
    content TEXT NOT NULL,
    content_type VARCHAR(128),
    token_count INTEGER,
    metadata JSONB,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_document_chunks_document_index
    ON document_chunks(document_id, chunk_index);

CREATE TABLE IF NOT EXISTS uploaded_files (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID REFERENCES users(id) ON DELETE SET NULL,
    original_filename VARCHAR(512) NOT NULL,
    storage_path VARCHAR(1024),
    mime_type VARCHAR(128),
    file_size_bytes BIGINT,
    processing_status VARCHAR(64) NOT NULL DEFAULT 'pending',
    extracted_text TEXT,
    parsed_payload JSONB,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Confirmed memory and owner-scoped asynchronous task results.
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
