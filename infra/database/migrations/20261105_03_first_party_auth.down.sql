BEGIN;
DROP TABLE IF EXISTS auth_credentials;
DELETE FROM schema_migrations WHERE version = '20261105_03_first_party_auth';
COMMIT;
