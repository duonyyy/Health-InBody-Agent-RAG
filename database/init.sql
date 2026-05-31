CREATE EXTENSION IF NOT EXISTS pgcrypto;

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
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_inbody_measurements_user_date
    ON inbody_measurements(user_id, measurement_date DESC);

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
