import sqlite3
import hashlib
import os
import uuid
import time

DB_PATH = os.path.join(os.path.dirname(__file__), "users.db")


def _get_conn():
    conn = sqlite3.connect(DB_PATH)
    conn.execute(
        """CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            password_hash TEXT NOT NULL
        )"""
    )
    conn.execute("""CREATE TABLE IF NOT EXISTS sessions (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER NOT NULL,
        username TEXT NOT NULL,
        token TEXT UNIQUE NOT NULL,
        created_at REAL NOT NULL,
        FOREIGN KEY (user_id) REFERENCES users(id)
    )""")
    conn.commit()
    return conn


def _hash_password(password: str) -> str:
    return hashlib.sha256(password.encode()).hexdigest()


def register(username: str, password: str) -> tuple[bool, str]:
    if not username or not password:
        return False, "用户名和密码不能为空"
    conn = _get_conn()
    try:
        conn.execute(
            "INSERT INTO users (username, password_hash) VALUES (?, ?)",
            (username, _hash_password(password)),
        )
        conn.commit()
        return True, "注册成功！请登录"
    except sqlite3.IntegrityError:
        return False, "用户名已存在"
    finally:
        conn.close()


def authenticate(username: str, password: str) -> tuple[bool, str, str]:
    """Returns (success, message, token)"""
    if not username or not password:
        return False, "请输入用户名和密码", ""
    conn = _get_conn()
    row = conn.execute(
        "SELECT id, password_hash FROM users WHERE username = ?", (username,)
    ).fetchone()
    conn.close()
    if row is None:
        return False, "用户名不存在", ""
    if row[1] != _hash_password(password):
        return False, "密码错误", ""
    
    # Create session token
    token = str(uuid.uuid4())
    user_id = row[0]
    conn = _get_conn()
    conn.execute(
        "INSERT INTO sessions (user_id, username, token, created_at) VALUES (?, ?, ?, ?)",
        (user_id, username, token, time.time())
    )
    conn.commit()
    conn.close()
    
    return True, "登录成功", token


def validate_session(token: str) -> tuple[bool, int, str]:
    """Returns (is_valid, user_id, username)"""
    if not token:
        return False, 0, ""
    conn = _get_conn()
    row = conn.execute(
        "SELECT user_id, username FROM sessions WHERE token = ?", (token,)
    ).fetchone()
    conn.close()
    if row:
        return True, row[0], row[1]
    return False, 0, ""


def logout(token: str):
    """Clear session"""
    if not token:
        return
    conn = _get_conn()
    conn.execute("DELETE FROM sessions WHERE token = ?", (token,))
    conn.commit()
    conn.close()


def cleanup_sessions():
    """Remove old sessions (older than 7 days)"""
    conn = _get_conn()
    cutoff = time.time() - (7 * 24 * 60 * 60)
    conn.execute("DELETE FROM sessions WHERE created_at < ?", (cutoff,))
    conn.commit()
    conn.close()
