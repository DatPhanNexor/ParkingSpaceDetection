-- ai_parking_system.sql

CREATE DATABASE IF NOT EXISTS ai_parking_system CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
USE ai_parking_system;

-- Tài khoản đầu tiên được tạo qua màn hình Đăng ký sẽ có quyền admin.
CREATE TABLE IF NOT EXISTS tai_khoan (
    id BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
    username VARCHAR(50) NOT NULL UNIQUE,
    password_hash VARCHAR(255) NOT NULL,
    ho_ten VARCHAR(100) NOT NULL,
    role VARCHAR(20) NOT NULL DEFAULT 'staff',
    is_active TINYINT(1) NOT NULL DEFAULT 1,
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    last_login DATETIME NULL,
    INDEX idx_username (username),
    INDEX idx_role (role)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS lich_su_xe (
    id BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
    transaction_id VARCHAR(100) NOT NULL UNIQUE,
    run_id VARCHAR(100) NULL,
    input_mode VARCHAR(30) NOT NULL,
    input_source VARCHAR(500) NULL,
    slot_id VARCHAR(50) NOT NULL,
    gio_vao DATETIME(6) NOT NULL,
    gio_ra DATETIME(6) NULL,
    so_giay INT UNSIGNED NULL,
    so_phut INT UNSIGNED NULL,
    gia_moi_gio INT UNSIGNED NOT NULL DEFAULT 20000,
    buoc_lam_tron INT UNSIGNED NOT NULL DEFAULT 5000,
    thanh_tien BIGINT UNSIGNED NULL,
    completion_reason VARCHAR(100) NULL,
    created_by BIGINT UNSIGNED NULL,
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    INDEX idx_transaction_id (transaction_id),
    INDEX idx_slot_id (slot_id),
    INDEX idx_gio_vao (gio_vao),
    INDEX idx_gio_ra (gio_ra),
    INDEX idx_input_mode (input_mode),
    CONSTRAINT fk_lich_su_xe_tai_khoan FOREIGN KEY (created_by) REFERENCES tai_khoan(id) ON DELETE SET NULL ON UPDATE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS cau_hinh (
    id TINYINT UNSIGNED PRIMARY KEY,
    gia_moi_gio INT UNSIGNED NOT NULL DEFAULT 20000,
    buoc_lam_tron INT UNSIGNED NOT NULL DEFAULT 5000,
    phi_toi_thieu INT UNSIGNED NOT NULL DEFAULT 5000,
    refresh_dashboard_ms INT UNSIGNED NOT NULL DEFAULT 3000,
    updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

INSERT INTO cau_hinh (id, gia_moi_gio, buoc_lam_tron, phi_toi_thieu, refresh_dashboard_ms)
VALUES (1, 20000, 5000, 5000, 3000)
ON DUPLICATE KEY UPDATE
    gia_moi_gio = VALUES(gia_moi_gio),
    buoc_lam_tron = VALUES(buoc_lam_tron),
    phi_toi_thieu = VALUES(phi_toi_thieu),
    refresh_dashboard_ms = VALUES(refresh_dashboard_ms);

CREATE OR REPLACE VIEW vw_dashboard_summary AS
SELECT 
    COUNT(id) AS tong_so_luot,
    SUM(CASE WHEN gio_ra IS NULL THEN 1 ELSE 0 END) AS xe_dang_do,
    COALESCE(SUM(CASE WHEN gio_ra IS NOT NULL THEN thanh_tien ELSE 0 END), 0) AS tong_doanh_thu
FROM lich_su_xe;

CREATE OR REPLACE VIEW vw_doanh_thu_theo_slot AS
SELECT 
    slot_id,
    COUNT(id) AS so_luot,
    COALESCE(SUM(thanh_tien), 0) AS doanh_thu
FROM lich_su_xe
WHERE gio_ra IS NOT NULL
GROUP BY slot_id;

CREATE OR REPLACE VIEW vw_tan_suat_theo_slot AS
SELECT 
    slot_id,
    COUNT(id) AS so_luot
FROM lich_su_xe
GROUP BY slot_id;
