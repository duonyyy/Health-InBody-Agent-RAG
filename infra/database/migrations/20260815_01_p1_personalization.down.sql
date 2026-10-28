-- Rollback is schema-safe but intentionally lossy for data created by P1.
BEGIN;

DELETE FROM schema_migrations WHERE version = '20260815_01_p1_personalization';

DROP TABLE IF EXISTS check_ins;
DROP TABLE IF EXISTS personalized_plans;
DROP TABLE IF EXISTS personalization_goals;

DROP INDEX IF EXISTS idx_inbody_measurements_owner_confirmed;
DROP INDEX IF EXISTS idx_inbody_measurements_owner_cursor;
ALTER TABLE inbody_measurements DROP COLUMN IF EXISTS delete_reason;
ALTER TABLE inbody_measurements DROP COLUMN IF EXISTS deleted_at;
ALTER TABLE inbody_measurements DROP COLUMN IF EXISTS confirmed_at;
ALTER TABLE inbody_measurements DROP COLUMN IF EXISTS confirmed_by_user;
ALTER TABLE inbody_measurements DROP COLUMN IF EXISTS confidence;
ALTER TABLE inbody_measurements DROP COLUMN IF EXISTS source_type;
ALTER TABLE inbody_measurements DROP COLUMN IF EXISTS measured_at;

ALTER TABLE users DROP COLUMN IF EXISTS deleted_at;
ALTER TABLE users DROP COLUMN IF EXISTS profile_confirmed_at;
ALTER TABLE users DROP COLUMN IF EXISTS consent_flags;
ALTER TABLE users DROP COLUMN IF EXISTS medical_conditions_data;
ALTER TABLE users DROP COLUMN IF EXISTS exercise_constraints;
ALTER TABLE users DROP COLUMN IF EXISTS dietary_preferences;
ALTER TABLE users DROP COLUMN IF EXISTS sex_at_birth;
ALTER TABLE users DROP COLUMN IF EXISTS age_range;
ALTER TABLE users DROP COLUMN IF EXISTS birth_date;
ALTER TABLE users DROP COLUMN IF EXISTS display_name;

COMMIT;
