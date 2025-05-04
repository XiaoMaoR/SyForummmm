import sqlite3
import json
from typing import Optional

def create_connection(db_file: str) -> Optional[sqlite3.Connection]:
    try:
        conn = sqlite3.connect(db_file)
        conn.execute("PRAGMA journal_mode=WAL")
        return conn
    except sqlite3.Error as e:
        print(f"Error connecting to database: {e}")
        return None

def create_table(conn: sqlite3.Connection) -> None:
    try:
        sql = '''CREATE TABLE IF NOT EXISTS agreements (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    data TEXT NOT NULL UNIQUE
                )'''
        conn.execute(sql)
        conn.commit()
    except sqlite3.Error as e:
        print(f"Error creating table: {e}")

def insert_agreement(conn: sqlite3.Connection, data: dict) -> Optional[int]:
    json_data = json.dumps(data)
    cur = conn.cursor()
    cur.execute("SELECT id FROM agreements WHERE data = ?", (json_data,))
    existing = cur.fetchone()
    if existing:
        return None
    
    sql = '''INSERT INTO agreements(data)
             VALUES(?)'''
    cur.execute(sql, (json_data,))
    conn.commit()
    return cur.lastrowid

def get_agreement(conn: sqlite3.Connection, agreement_id: int) -> Optional[dict]:
    sql = '''SELECT data FROM agreements WHERE id = ?'''
    cur = conn.cursor()
    cur.execute(sql, (agreement_id,))
    row = cur.fetchone()
    return json.loads(row[0]) if row else None

def get_all_agreements(conn: sqlite3.Connection) -> list[dict]:
    sql = '''SELECT data FROM agreements'''
    cur = conn.cursor()
    cur.execute(sql)
    return [json.loads(row[0]) for row in cur.fetchall()]

def create_forum_table(conn: sqlite3.Connection) -> None:
    try:
        sql = '''CREATE TABLE IF NOT EXISTS forum_data (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    data TEXT NOT NULL UNIQUE
                )'''
        conn.execute(sql)
        conn.commit()
    except sqlite3.Error as e:
        print(f"Error creating forum table: {e}")

def insert_forum_data(conn: sqlite3.Connection, data: dict) -> Optional[int]:
    json_data = json.dumps(data)
    cur = conn.cursor()
    cur.execute("SELECT id FROM forum_data WHERE data = ?", (json_data,))
    existing = cur.fetchone()
    if existing:
        return None
    
    sql = '''INSERT INTO forum_data(data)
             VALUES(?)'''
    cur.execute(sql, (json_data,))
    conn.commit()
    return cur.lastrowid

def get_forum_data(conn: sqlite3.Connection, data_id: int) -> Optional[dict]:
    sql = '''SELECT data FROM forum_data WHERE id = ?'''
    cur = conn.cursor()
    cur.execute(sql, (data_id,))
    row = cur.fetchone()
    return json.loads(row[0]) if row else None

def update_forum_data(conn: sqlite3.Connection, data_id: int, data: dict) -> None:
    json_data = json.dumps(data)
    sql = '''UPDATE forum_data SET data = ? WHERE id = ?'''
    cur = conn.cursor()
    cur.execute(sql, (json_data, data_id))
    conn.commit()