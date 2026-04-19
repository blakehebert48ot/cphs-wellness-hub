import sqlite3
import os
import psycopg2
from psycopg2.extras import RealDictCursor

# Path for local development
DATABASE_FILE = 'app.db'

def get_db_connection():
    """Establishes and returns a database connection. Falls back to SQLite if DATABASE_URL is missing."""
    url = os.getenv('DATABASE_URL')
    if url:
        # Production: Postgres (Neon.tech)
        conn = psycopg2.connect(url, sslmode='require')
        return conn, "postgres"
    else:
        # Development: SQLite
        conn = sqlite3.connect(DATABASE_FILE)
        conn.row_factory = sqlite3.Row
        return conn, "sqlite"

def init_db():
    """Initializes the database schema if it doesn't already exist."""
    conn, db_type = get_db_connection()
    c = conn.cursor()
    
    if db_type == "postgres":
        # PostgreSQL schema
        c.execute('''
            CREATE TABLE IF NOT EXISTS wins (
                id SERIAL PRIMARY KEY,
                habit TEXT NOT NULL,
                category TEXT DEFAULT 'Movement',
                timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                upvotes INTEGER DEFAULT 0,
                ai_cheer TEXT
            )
        ''')
    else:
        # SQLite schema
        c.execute('''
            CREATE TABLE IF NOT EXISTS wins (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                habit TEXT NOT NULL,
                category TEXT DEFAULT 'Movement',
                timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
                upvotes INTEGER DEFAULT 0,
                ai_cheer TEXT
            )
        ''')
    
    conn.commit()
    conn.close()
    print(f"Database initialized ({db_type}).")

def cleanup_old_wins():
    """Removes wins older than 30 days to keep the feed fresh."""
    conn, db_type = get_db_connection()
    c = conn.cursor()
    if db_type == "postgres":
        c.execute("DELETE FROM wins WHERE timestamp < NOW() - INTERVAL '30 days'")
    else:
        c.execute("DELETE FROM wins WHERE timestamp < datetime('now', '-30 days')")
    conn.commit()
    conn.close()

if __name__ == '__main__':
    init_db()
