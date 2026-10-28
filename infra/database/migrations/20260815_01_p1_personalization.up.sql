-- P1 personalization schema. Safe to re-run on an existing P0 database.
BEGIN;

CREATE TABLE IF NOT EXISTS schema_migrations (
    version VARCHAR(128) PRIMARY KEY,
    applied_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

ALTER TABLE users ADD COLUMN IF NOT EXISTS display_name VARCHAR(80);
ALTER TABLE users ADD COLUMN IF NOT EXISTS birth_date DATE;
ALTER TABLE users ADD COLUMN IF NOT EXISTS age_range VARCHAR(32);
ALTER TABLE users ADD COLUMN IF NOT EXISTS sex_at_birth VARCHAR(32);
ALTER TABLE users ADD COLUMN IF NOT EXISTS dietary_preferences JSONB;
ALTER TABLE users ADD COLUMN IF NOT EXISTS exercise_constraints JSONB;
ALTER TABLE users ADD COLUMN IF NOT EXISTS medical_conditions_data JSONB;
ALTER TABLE users ADD COLUMN IF NOT EXISTS consent_flags JSONB NOT NULL
    DEFAULT '{"health_data_processing": false, "personalization": false}'::jsonb;
ALTER TABLE users ADD COLUMN IF NOT EXISTS profile_confirmed_at TIMESTAMPTZ;
ALTER TABLE users ADD COLUMN IF NOT EXISTS deleted_at TIMESTAMPTZ;

ALTER TABLE inbody_measurements ADD COLUMN IF NOT EXISTS measured_at TIMESTAMPTZ;
UPDATE inbody_measurements
SET measured_at = measurement_date::timestamp AT TIME ZONE 'UTC'
WHERE measured_at IS NULL;
ALTER TABLE inbody_measurements ALTER COLUMN measured_at SET NOT NULL;
ALTER TABLE inbody_measurements ALTER COLUMN measured_at SET DEFAULT NOW();
ALTER TABLE inbody_measurements ADD COLUMN IF NOT EXISTS source_type VARCHAR(32) NOT NULL
    DEFAULT 'legacy_unconfirmed';
ALTER TABLE inbody_measurements ADD COLUMN IF NOT EXISTS confidence NUMERIC(4, 3);
ALTER TABLE inbody_measurements ADD COLUMN IF NOT EXISTS confirmed_by_user BOOLEAN NOT NULL DEFAULT FALSE;
ALTER TABLE inbody_measurements ADD COLUMN IF NOT EXISTS confirmed_at TIMESTAMPTZ;
ALTER TABLE inbody_measurements ADD COLUMN IF NOT EXISTS deleted_at TIMESTAMPTZ;
ALTER TABLE inbody_measurements ADD COLUMN IF NOT EXISTS delete_reason VARCHAR(240);

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

INSERT INTO schema_migrations(version)
VALUES ('20260815_01_p1_personalization')
ON CONFLICT (version) DO NOTHING;

COMMIT;
