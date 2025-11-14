-- PostgreSQL initial schema for Data Room
-- Includes: users, user_roles, files, file_access_log, user_audit_log
-- Soft delete via deleted_at on core entities (users, files, user_roles)

-- Extensions
CREATE EXTENSION IF NOT EXISTS pgcrypto;     -- gen_random_uuid()
CREATE EXTENSION IF NOT EXISTS citext;       -- case-insensitive text

-- Enums
DO $$
BEGIN
  IF NOT EXISTS (SELECT 1 FROM pg_type WHERE typname = 'user_status') THEN
    CREATE TYPE user_status AS ENUM ('pending','active','suspended');
  END IF;
  IF NOT EXISTS (SELECT 1 FROM pg_type WHERE typname = 'user_role') THEN
    CREATE TYPE user_role AS ENUM ('owner','manager','viewer','guest');
  END IF;
  IF NOT EXISTS (SELECT 1 FROM pg_type WHERE typname = 'file_status') THEN
    CREATE TYPE file_status AS ENUM ('processing','ready','failed','archived');
  END IF;
  IF NOT EXISTS (SELECT 1 FROM pg_type WHERE typname = 'access_event') THEN
    CREATE TYPE access_event AS ENUM ('view','download','share');
  END IF;
  IF NOT EXISTS (SELECT 1 FROM pg_type WHERE typname = 'audit_event') THEN
    CREATE TYPE audit_event AS ENUM ('login','logout','token_refresh','role_change');
  END IF;
END$$;

-- Updated_at trigger helper
CREATE OR REPLACE FUNCTION set_updated_at()
RETURNS TRIGGER AS $$
BEGIN
  NEW.updated_at = NOW();
  RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- USERS
CREATE TABLE IF NOT EXISTS users (
  id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  email           CITEXT UNIQUE NOT NULL,
  password_hash   TEXT,
  status          user_status NOT NULL DEFAULT 'pending',
  full_name       VARCHAR(128),
  avatar_url      VARCHAR(512),
  phone           VARCHAR(32),
  google_id       VARCHAR(128) UNIQUE,
  google_access_token VARCHAR(2048),
  google_refresh_token VARCHAR(2048),
  google_token_expires_at TIMESTAMPTZ,
  created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  updated_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  deleted_at      TIMESTAMPTZ
);

CREATE TRIGGER trg_users_updated_at
BEFORE UPDATE ON users
FOR EACH ROW EXECUTE FUNCTION set_updated_at();

-- USER ROLES (system-scoped for now; can be extended to per-dataroom later)
CREATE TABLE IF NOT EXISTS user_roles (
  id              BIGSERIAL PRIMARY KEY,
  user_id         UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  role            user_role NOT NULL,
  created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  updated_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  deleted_at      TIMESTAMPTZ,
  CONSTRAINT user_roles_unique_user UNIQUE (user_id)
);

CREATE INDEX IF NOT EXISTS idx_user_roles_user_id ON user_roles(user_id) WHERE deleted_at IS NULL;

CREATE TRIGGER trg_user_roles_updated_at
BEFORE UPDATE ON user_roles
FOR EACH ROW EXECUTE FUNCTION set_updated_at();

-- FILES
CREATE TABLE IF NOT EXISTS files (
  id                UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  uploader_id       UUID REFERENCES users(id) ON DELETE SET NULL,
  storage_key       VARCHAR(512) UNIQUE NOT NULL,
  drive_file_id     VARCHAR(256) UNIQUE,
  original_name     VARCHAR(255) NOT NULL,
  extension         VARCHAR(32),
  mime_type         VARCHAR(128),
  size_bytes        BIGINT NOT NULL CHECK (size_bytes > 0),
  checksum_sha256   CHAR(64),
  version           INTEGER NOT NULL DEFAULT 1 CHECK (version >= 1),
  is_latest         BOOLEAN NOT NULL DEFAULT TRUE,
  status            file_status NOT NULL DEFAULT 'processing',
  scan_report       JSONB,
  created_at        TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  updated_at        TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  deleted_at        TIMESTAMPTZ
);

CREATE INDEX IF NOT EXISTS idx_files_is_latest ON files(is_latest) WHERE deleted_at IS NULL;
CREATE INDEX IF NOT EXISTS idx_files_checksum ON files(checksum_sha256) WHERE checksum_sha256 IS NOT NULL AND deleted_at IS NULL;

CREATE TRIGGER trg_files_updated_at
BEFORE UPDATE ON files
FOR EACH ROW EXECUTE FUNCTION set_updated_at();

-- FILE ACCESS LOG
CREATE TABLE IF NOT EXISTS file_access_log (
  id            BIGSERIAL PRIMARY KEY,
  file_id       UUID NOT NULL REFERENCES files(id) ON DELETE CASCADE,
  user_id       UUID REFERENCES users(id) ON DELETE SET NULL,
  event         access_event NOT NULL,
  ip            INET,
  user_agent    TEXT,
  created_at    TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_file_access_log_file_created_at ON file_access_log(file_id, created_at);

-- USER AUDIT LOG
CREATE TABLE IF NOT EXISTS user_audit_log (
  id            BIGSERIAL PRIMARY KEY,
  user_id       UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  event         audit_event NOT NULL,
  metadata      JSONB,
  created_at    TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_user_audit_log_user_created_at ON user_audit_log(user_id, created_at);

-- Optional row-level policies / future FKs can be added in later migrations.


