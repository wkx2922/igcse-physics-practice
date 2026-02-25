import sqlite3
import os
from datetime import datetime

DB_PATH = os.path.join(os.path.dirname(__file__), "users.db")


def _get_conn():
    conn = sqlite3.connect(DB_PATH)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS quiz_records (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            username TEXT NOT NULL,
            unit_name TEXT NOT NULL,
            topic TEXT NOT NULL,
            question_text TEXT NOT NULL,
            user_answer TEXT,
            correct_answer TEXT,
            is_correct INTEGER,
            time_spent REAL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    conn.commit()
    return conn


def save_quiz_record(user_id, username, unit_name, question_text, topic,
                     user_answer, correct_answer, is_correct, time_spent):
    conn = _get_conn()
    conn.execute("""
        INSERT INTO quiz_records 
        (user_id, username, unit_name, topic, question_text, user_answer, correct_answer, is_correct, time_spent)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (user_id, username, unit_name, question_text, topic, user_answer,
          correct_answer, 1 if is_correct else 0, time_spent))
    conn.commit()
    conn.close()


def get_user_stats(user_id):
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.execute("""
        SELECT 
            COUNT(*) as total,
            SUM(is_correct) as correct,
            unit_name,
            topic
        FROM quiz_records
        WHERE user_id = ?
        GROUP BY unit_name, topic
    """, (user_id,))
    results = cursor.fetchall()
    conn.close()
    return results
