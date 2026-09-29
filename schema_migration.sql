-- Run once against your Neon Postgres DB (Neon SQL editor, psql, or any client).
-- Base.metadata.create_all() only creates missing tables, not new columns on
-- existing ones, so these need to be applied by hand.

ALTER TABLE users  ADD COLUMN IF NOT EXISTS google_id VARCHAR UNIQUE;
ALTER TABLE users  ALTER COLUMN password_hash DROP NOT NULL;
ALTER TABLE events ADD COLUMN IF NOT EXISTS media JSON DEFAULT '[]'::json;

-- Only if you already ran an earlier version of this migration that added
-- image_url (superseded by media, which supports multiple photos/videos):
-- ALTER TABLE events DROP COLUMN IF EXISTS image_url;
