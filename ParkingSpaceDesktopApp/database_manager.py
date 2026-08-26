import os
import hashlib
import secrets
import hmac
import base64
from typing import Optional, Dict, Any, List, Tuple
from datetime import datetime

# Driver setup
try:
    import mysql.connector
    HAS_MYSQL_CONNECTOR = True
except ImportError:
    HAS_MYSQL_CONNECTOR = False

try:
    # pyrefly: ignore [missing-source-for-stubs]
    import pymysql
    HAS_PYMYSQL = True
except ImportError:
    HAS_PYMYSQL = False

def hash_password(password: str) -> str:
    """Hashes a password using PBKDF2 with HMAC-SHA256."""
    iterations = 210000
    salt = secrets.token_bytes(16)
    hash_bytes = hashlib.pbkdf2_hmac('sha256', password.encode('utf-8'), salt, iterations)
    
    salt_b64 = base64.b64encode(salt).decode('ascii')
    hash_b64 = base64.b64encode(hash_bytes).decode('ascii')
    
    return f"pbkdf2_sha256${iterations}${salt_b64}${hash_b64}"

def verify_password(password: str, encoded_hash: str) -> bool:
    """Verifies a password against the encoded hash."""
    try:
        parts = encoded_hash.split('$')
        if len(parts) != 4 or parts[0] != 'pbkdf2_sha256':
            return False
            
        iterations = int(parts[1])
        salt = base64.b64decode(parts[2])
        stored_hash = base64.b64decode(parts[3])
        
        computed_hash = hashlib.pbkdf2_hmac('sha256', password.encode('utf-8'), salt, iterations)
        return hmac.compare_digest(computed_hash, stored_hash)
    except Exception:
        return False

class DatabaseError(Exception):
    pass

class DatabaseManager:
    def __init__(self):
        self.host = os.environ.get('AI_PARKING_DB_HOST', '127.0.0.1')
        self.port = int(os.environ.get('AI_PARKING_DB_PORT', '3306'))
        self.user = os.environ.get('AI_PARKING_DB_USER', 'root')
        self.password = os.environ.get('AI_PARKING_DB_PASSWORD', '')
        self.database = os.environ.get('AI_PARKING_DB_NAME', 'ai_parking_system')
        self._check_driver()
        
    def _check_driver(self):
        if not HAS_MYSQL_CONNECTOR and not HAS_PYMYSQL:
            raise DatabaseError("Thiếu thư viện kết nối MySQL. Vui lòng cài mysql-connector-python hoặc pymysql.")
            
    def get_connection(self):
        try:
            if HAS_MYSQL_CONNECTOR:
                return mysql.connector.connect(
                    host=self.host,
                    port=self.port,
                    user=self.user,
                    password=self.password,
                    database=self.database,
                    connection_timeout=5
                )
            elif HAS_PYMYSQL:
                return pymysql.connect(
                    host=self.host,
                    port=self.port,
                    user=self.user,
                    password=self.password,
                    database=self.database,
                    connect_timeout=5
                )
        except Exception as e:
            raise DatabaseError(f"Không thể kết nối CSDL: {str(e)}")

    def test_connection(self) -> bool:
        try:
            with self.get_connection() as conn:
                return True
        except Exception:
            return False
            
    def count_users(self) -> int:
        try:
            conn = self.get_connection()
            try:
                with conn.cursor() as cursor:
                    cursor.execute("SELECT COUNT(id) FROM tai_khoan")
                    return cursor.fetchone()[0]
            finally:
                conn.close()
        except Exception as e:
            raise DatabaseError(f"Lỗi đếm số user: {e}")

    def create_user(self, username: str, password_raw: str, ho_ten: str) -> bool:
        try:
            conn = self.get_connection()
            try:
                with conn.cursor() as cursor:
                    cursor.execute("SELECT COUNT(id) FROM tai_khoan")
                    count = cursor.fetchone()[0]
                    role = 'admin' if count == 0 else 'staff'
                    
                    cursor.execute("SELECT id FROM tai_khoan WHERE username = %s", (username,))
                    if cursor.fetchone():
                        raise DatabaseError("Tên đăng nhập đã tồn tại")
                        
                    pwd_hash = hash_password(password_raw)
                    sql = "INSERT INTO tai_khoan (username, password_hash, ho_ten, role) VALUES (%s, %s, %s, %s)"
                    cursor.execute(sql, (username, pwd_hash, ho_ten, role))
                    conn.commit()
                    return True
            finally:
                conn.close()
        except DatabaseError:
            raise
        except Exception as e:
            raise DatabaseError(f"Lỗi tạo tài khoản: {e}")

    def authenticate_user(self, username: str, password_raw: str) -> Optional[Dict[str, Any]]:
        try:
            conn = self.get_connection()
            try:
                # Use dictionary cursor if possible, but fallback to tuple for broader compatibility
                cursor = conn.cursor()
                cursor.execute("SELECT id, username, password_hash, ho_ten, role, is_active FROM tai_khoan WHERE username = %s", (username,))
                row = cursor.fetchone()
                if row:
                    uid, uname, pwd_hash, name, role, active = row
                    if not active:
                        raise DatabaseError("Tài khoản đã bị khóa")
                    if verify_password(password_raw, pwd_hash):
                        return {
                            'user_id': uid,
                            'username': uname,
                            'ho_ten': name,
                            'role': role
                        }
                return None
            finally:
                if 'cursor' in locals() and cursor is not None:
                    cursor.close()
                conn.close()
        except DatabaseError:
            raise
        except Exception as e:
            raise DatabaseError(f"Lỗi đăng nhập: {e}")
            
    def update_last_login(self, user_id: int):
        try:
            conn = self.get_connection()
            try:
                with conn.cursor() as cursor:
                    cursor.execute("UPDATE tai_khoan SET last_login = NOW() WHERE id = %s", (user_id,))
                    conn.commit()
            finally:
                conn.close()
        except Exception as e:
            print(f"Warning: Failed to update last login: {e}")

    # pyrefly: ignore [bad-function-definition]
    def upsert_active_parking_session(self, transaction_id: str, run_id: str, input_mode: str, input_source: str, slot_id: str, gio_vao: float, user_id: int = None):
        try:
            conn = self.get_connection()
            try:
                with conn.cursor() as cursor:
                    gio_vao_dt = datetime.fromtimestamp(gio_vao).strftime('%Y-%m-%d %H:%M:%S.%f')
                    sql = """
                        INSERT INTO lich_su_xe (transaction_id, run_id, input_mode, input_source, slot_id, gio_vao, created_by)
                        VALUES (%s, %s, %s, %s, %s, %s, %s)
                        ON DUPLICATE KEY UPDATE 
                            gio_ra = NULL,
                            so_giay = NULL,
                            so_phut = NULL,
                            thanh_tien = NULL
                    """
                    cursor.execute(sql, (transaction_id, run_id, input_mode, input_source, slot_id, gio_vao_dt, user_id))
                    conn.commit()
            finally:
                conn.close()
        except Exception as e:
            print(f"Warning: Failed to upsert parking session: {e}")

    def complete_parking_session(self, transaction_id: str, gio_ra: float, duration: float, fee: int, reason: str):
        try:
            conn = self.get_connection()
            try:
                with conn.cursor() as cursor:
                    gio_ra_dt = datetime.fromtimestamp(gio_ra).strftime('%Y-%m-%d %H:%M:%S.%f')
                    so_giay = int(duration)
                    so_phut = so_giay // 60
                    sql = """
                        UPDATE lich_su_xe 
                        SET gio_ra = %s, so_giay = %s, so_phut = %s, thanh_tien = %s, completion_reason = %s
                        WHERE transaction_id = %s
                    """
                    cursor.execute(sql, (gio_ra_dt, so_giay, so_phut, fee, reason, transaction_id))
                    conn.commit()
            finally:
                conn.close()
        except Exception as e:
            print(f"Warning: Failed to complete parking session: {e}")
            
    # pyrefly: ignore [bad-function-definition]
    def save_completed_transaction(self, transaction: Any, user_id: int = None):
        # Uses standard upsert followed by update for consistency, or direct insert for completed
        try:
            conn = self.get_connection()
            try:
                with conn.cursor() as cursor:
                    gio_vao_dt = datetime.fromtimestamp(transaction.started_at).strftime('%Y-%m-%d %H:%M:%S.%f')
                    gio_ra_dt = datetime.fromtimestamp(transaction.ended_at).strftime('%Y-%m-%d %H:%M:%S.%f')
                    so_giay = int(transaction.duration_seconds)
                    so_phut = so_giay // 60
                    
                    sql = """
                        INSERT INTO lich_su_xe (transaction_id, run_id, input_mode, input_source, slot_id, gio_vao, gio_ra, so_giay, so_phut, gia_moi_gio, buoc_lam_tron, thanh_tien, completion_reason, created_by)
                        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                        ON DUPLICATE KEY UPDATE 
                            gio_ra = VALUES(gio_ra),
                            so_giay = VALUES(so_giay),
                            so_phut = VALUES(so_phut),
                            thanh_tien = VALUES(thanh_tien),
                            completion_reason = VALUES(completion_reason)
                    """
                    cursor.execute(sql, (
                        transaction.transaction_id, transaction.run_id, transaction.input_mode, transaction.input_source, 
                        transaction.position_id, gio_vao_dt, gio_ra_dt, so_giay, so_phut, 
                        transaction.hourly_rate_vnd, transaction.rounding_vnd, transaction.fee_vnd, transaction.completion_reason, user_id
                    ))
                    conn.commit()
            finally:
                conn.close()
        except Exception as e:
            print(f"Warning: Failed to save completed transaction: {e}")

    def fetch_dashboard_summary(self) -> Dict[str, Any]:
        try:
            conn = self.get_connection()
            try:
                with conn.cursor() as cursor:
                    cursor.execute("SELECT tong_so_luot, xe_dang_do, tong_doanh_thu FROM vw_dashboard_summary")
                    row = cursor.fetchone()
                    if row:
                        return {'tong_so_luot': row[0], 'xe_dang_do': row[1], 'tong_doanh_thu': int(row[2])}
                    return {'tong_so_luot': 0, 'xe_dang_do': 0, 'tong_doanh_thu': 0}
            finally:
                conn.close()
        except Exception as e:
            raise DatabaseError(f"Lỗi lấy summary: {e}")

    def fetch_revenue_by_slot(self) -> List[Tuple[str, int]]:
        try:
            conn = self.get_connection()
            try:
                with conn.cursor() as cursor:
                    cursor.execute("SELECT slot_id, doanh_thu FROM vw_doanh_thu_theo_slot ORDER BY doanh_thu DESC LIMIT 10")
                    return [(row[0], int(row[1])) for row in cursor.fetchall()]
            finally:
                conn.close()
        except Exception as e:
            raise DatabaseError(f"Lỗi lấy doanh thu slot: {e}")
            
    def fetch_frequency_by_slot(self) -> List[Tuple[str, int]]:
        try:
            conn = self.get_connection()
            try:
                with conn.cursor() as cursor:
                    cursor.execute("SELECT slot_id, so_luot FROM vw_tan_suat_theo_slot ORDER BY so_luot DESC LIMIT 8")
                    return [(row[0], int(row[1])) for row in cursor.fetchall()]
            finally:
                conn.close()
        except Exception as e:
            raise DatabaseError(f"Lỗi lấy tần suất slot: {e}")
            
    def _build_history_where_clause(self, filters: Dict[str, Any]) -> Tuple[str, List[Any]]:
        conditions = []
        params = []
        
        filter_type = filters.get("time_filter", "Hôm nay")
        if filter_type == "Hôm nay":
            conditions.append("DATE(gio_vao) = CURDATE()")
        elif filter_type == "7 ngày":
            conditions.append("gio_vao >= DATE_SUB(CURDATE(), INTERVAL 7 DAY)")
        elif filter_type == "30 ngày":
            conditions.append("gio_vao >= DATE_SUB(CURDATE(), INTERVAL 30 DAY)")
            
        slot = filters.get("slot_id")
        if slot:
            conditions.append("slot_id LIKE %s")
            params.append(f"%{slot}%")
            
        mode = filters.get("input_mode")
        if mode and mode != "Tất cả":
            conditions.append("input_mode = %s")
            params.append(mode)
            
        status = filters.get("status")
        if status == "Đang đỗ":
            conditions.append("gio_ra IS NULL")
        elif status == "Đã rời":
            conditions.append("gio_ra IS NOT NULL")
            
        where_clause = "WHERE " + " AND ".join(conditions) if conditions else ""
        return where_clause, params

    # pyrefly: ignore [bad-function-definition]
    def count_parking_history(self, filters: Dict[str, Any] = None) -> int:
        try:
            conn = self.get_connection()
            try:
                with conn.cursor() as cursor:
                    where_clause, params = self._build_history_where_clause(filters or {})
                    sql = f"SELECT COUNT(id) FROM lich_su_xe {where_clause}"
                    cursor.execute(sql, params)
                    return cursor.fetchone()[0]
            finally:
                conn.close()
        except Exception as e:
            raise DatabaseError(f"Lỗi đếm lịch sử: {e}")

    # pyrefly: ignore [bad-function-definition]
    def fetch_parking_history(self, filters: Dict[str, Any] = None, limit: int = 100, offset: int = 0) -> List[Dict[str, Any]]:
        try:
            conn = self.get_connection()
            try:
                with conn.cursor() as cursor:
                    where_clause, params = self._build_history_where_clause(filters or {})
                    sql = f"""
                        SELECT transaction_id, slot_id, gio_vao, gio_ra, so_giay, thanh_tien, input_mode, input_source
                        FROM lich_su_xe 
                        {where_clause}
                        ORDER BY gio_vao DESC 
                        LIMIT %s OFFSET %s
                    """
                    cursor.execute(sql, params + [limit, offset])
                    results = []
                    for row in cursor.fetchall():
                        results.append({
                            'id': row[0],
                            'slot_id': row[1],
                            'gio_vao': row[2],
                            'gio_ra': row[3],
                            'duration': row[4],
                            'fee': row[5],
                            'mode': row[6],
                            'source': row[7]
                        })
                    return results
            finally:
                conn.close()
        except Exception as e:
            raise DatabaseError(f"Lỗi lấy lịch sử: {e}")
            
    def fetch_billing_config(self) -> Dict[str, Any]:
        try:
            conn = self.get_connection()
            try:
                with conn.cursor() as cursor:
                    cursor.execute("SELECT gia_moi_gio, buoc_lam_tron, phi_toi_thieu, refresh_dashboard_ms FROM cau_hinh WHERE id = 1")
                    row = cursor.fetchone()
                    if row:
                        return {
                            'hourly_rate_vnd': row[0],
                            'rounding_vnd': row[1],
                            'minimum_fee_vnd': row[2],
                            'refresh_dashboard_ms': row[3]
                        }
                    return {}
            finally:
                conn.close()
        except Exception as e:
            print(f"Warning: Failed to fetch billing config: {e}")
            return {}

    def update_billing_config(self, gia_moi_gio: int, buoc_lam_tron: int, phi_toi_thieu: int, refresh_dashboard_ms: int) -> bool:
        try:
            conn = self.get_connection()
            try:
                with conn.cursor() as cursor:
                    sql = """
                        UPDATE cau_hinh 
                        SET gia_moi_gio = %s, buoc_lam_tron = %s, phi_toi_thieu = %s, refresh_dashboard_ms = %s 
                        WHERE id = 1
                    """
                    cursor.execute(sql, (gia_moi_gio, buoc_lam_tron, phi_toi_thieu, refresh_dashboard_ms))
                    conn.commit()
                    return True
            finally:
                conn.close()
        except Exception as e:
            raise DatabaseError(f"Lỗi cập nhật cấu hình: {e}")

    # pyrefly: ignore [bad-function-definition]
    def fetch_revenue_by_day(self, filters: Dict[str, Any] = None) -> List[Tuple[str, int]]:
        try:
            conn = self.get_connection()
            try:
                with conn.cursor() as cursor:
                    where_clause, params = self._build_history_where_clause(filters or {})
                    if "gio_ra IS NOT NULL" not in where_clause:
                        if where_clause:
                            where_clause += " AND gio_ra IS NOT NULL AND thanh_tien IS NOT NULL"
                        else:
                            where_clause = "WHERE gio_ra IS NOT NULL AND thanh_tien IS NOT NULL"
                            
                    sql = f"""
                        SELECT DATE(gio_ra) as day, SUM(thanh_tien) as revenue
                        FROM lich_su_xe 
                        {where_clause}
                        GROUP BY DATE(gio_ra)
                        ORDER BY day ASC
                        LIMIT 30
                    """
                    cursor.execute(sql, params)
                    return [(str(row[0]), int(row[1] or 0)) for row in cursor.fetchall()]
            finally:
                conn.close()
        except Exception as e:
            raise DatabaseError(f"Lỗi lấy doanh thu theo ngày: {e}")

    # pyrefly: ignore [bad-function-definition]
    def fetch_revenue_statistics(self, filters: Dict[str, Any] = None) -> Dict[str, Any]:
        try:
            conn = self.get_connection()
            try:
                with conn.cursor() as cursor:
                    stats = {}
                    # Total revenue
                    cursor.execute("SELECT COALESCE(SUM(thanh_tien), 0) FROM lich_su_xe WHERE gio_ra IS NOT NULL AND thanh_tien IS NOT NULL")
                    stats['total'] = int(cursor.fetchone()[0])
                    
                    # Today
                    cursor.execute("SELECT COALESCE(SUM(thanh_tien), 0) FROM lich_su_xe WHERE gio_ra IS NOT NULL AND thanh_tien IS NOT NULL AND DATE(gio_ra) = CURDATE()")
                    stats['today'] = int(cursor.fetchone()[0])
                    
                    # 7 days
                    cursor.execute("SELECT COALESCE(SUM(thanh_tien), 0) FROM lich_su_xe WHERE gio_ra IS NOT NULL AND thanh_tien IS NOT NULL AND gio_ra >= DATE_SUB(CURDATE(), INTERVAL 7 DAY)")
                    stats['7days'] = int(cursor.fetchone()[0])
                    
                    # 30 days
                    cursor.execute("SELECT COALESCE(SUM(thanh_tien), 0) FROM lich_su_xe WHERE gio_ra IS NOT NULL AND thanh_tien IS NOT NULL AND gio_ra >= DATE_SUB(CURDATE(), INTERVAL 30 DAY)")
                    stats['30days'] = int(cursor.fetchone()[0])
                    
                    # Count and Average
                    where_clause, params = self._build_history_where_clause(filters or {})
                    if "gio_ra IS NOT NULL" not in where_clause:
                        if where_clause:
                            where_clause += " AND gio_ra IS NOT NULL AND thanh_tien IS NOT NULL"
                        else:
                            where_clause = "WHERE gio_ra IS NOT NULL AND thanh_tien IS NOT NULL"
                            
                    cursor.execute(f"SELECT COUNT(id), COALESCE(AVG(thanh_tien), 0) FROM lich_su_xe {where_clause}", params)
                    row = cursor.fetchone()
                    stats['completed_count'] = int(row[0])
                    stats['average_fee'] = int(row[1])
                    
                    return stats
            finally:
                conn.close()
        except Exception as e:
            raise DatabaseError(f"Lỗi lấy thống kê doanh thu: {e}")
