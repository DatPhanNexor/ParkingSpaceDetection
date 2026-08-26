-- 001_initial_schema.sql
-- Extension to legacy ai_parking_system

CREATE TABLE IF NOT EXISTS schema_migrations (
    version VARCHAR(50) PRIMARY KEY,
    applied_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP
);

INSERT IGNORE INTO schema_migrations (version) VALUES ('001_initial_schema');

CREATE TABLE IF NOT EXISTS parking_slots (
    slot_id VARCHAR(10) PRIMARY KEY, -- S01 to S09
    label VARCHAR(50),
    is_active TINYINT(1) DEFAULT 1,
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP
);

-- Seed S01 to S09
INSERT IGNORE INTO parking_slots (slot_id, label) VALUES 
('S01', 'Slot 1'), ('S02', 'Slot 2'), ('S03', 'Slot 3'),
('S04', 'Slot 4'), ('S05', 'Slot 5'), ('S06', 'Slot 6'),
('S07', 'Slot 7'), ('S08', 'Slot 8'), ('S09', 'Slot 9');

CREATE TABLE IF NOT EXISTS active_session_locks (
    slot_id VARCHAR(10) PRIMARY KEY,
    session_id VARCHAR(100) NOT NULL UNIQUE,
    started_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    locked_by_service VARCHAR(100),
    FOREIGN KEY (slot_id) REFERENCES parking_slots(slot_id)
);

CREATE TABLE IF NOT EXISTS refresh_tokens (
    token_hash VARCHAR(255) PRIMARY KEY,
    user_id BIGINT UNSIGNED NOT NULL,
    expires_at DATETIME NOT NULL,
    revoked TINYINT(1) DEFAULT 0,
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES tai_khoan(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS processed_events (
    event_id VARCHAR(36) PRIMARY KEY,
    event_type VARCHAR(100) NOT NULL,
    processed_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    INDEX idx_event_type (event_type),
    INDEX idx_processed_at (processed_at)
);

CREATE TABLE IF NOT EXISTS outbox_events (
    id BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
    event_type VARCHAR(100) NOT NULL,
    payload JSON NOT NULL,
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    processed_at DATETIME NULL,
    INDEX idx_outbox_unprocessed (processed_at)
);

CREATE TABLE IF NOT EXISTS system_alerts (
    id BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
    level VARCHAR(20) NOT NULL, -- INFO, WARNING, ERROR
    source VARCHAR(100) NOT NULL,
    message TEXT NOT NULL,
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    INDEX idx_alert_level (level),
    INDEX idx_alert_created_at (created_at)
);

CREATE TABLE IF NOT EXISTS service_heartbeats (
    service_name VARCHAR(100) PRIMARY KEY,
    last_heartbeat DATETIME NOT NULL,
    status VARCHAR(50) NOT NULL
);
