-- Repair legacy SmartBling SQLite schema for order tag tables.
-- Safe to run multiple times when guarded by PRAGMA checks.

-- order_tag_links
ALTER TABLE order_tag_links ADD COLUMN created_at DATETIME;
ALTER TABLE order_tag_links ADD COLUMN updated_at DATETIME;

-- order_tags
ALTER TABLE order_tags ADD COLUMN name_key VARCHAR(80);
ALTER TABLE order_tags ADD COLUMN created_at DATETIME;
ALTER TABLE order_tags ADD COLUMN updated_at DATETIME;

-- order_tag_assignments
ALTER TABLE order_tag_assignments ADD COLUMN created_at DATETIME;
ALTER TABLE order_tag_assignments ADD COLUMN updated_at DATETIME;
