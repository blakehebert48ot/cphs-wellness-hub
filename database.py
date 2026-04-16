import sqlite3
import os

DATABASE_FILE = 'app.db'

def get_db_connection():
    """Establishes and returns a database connection."""
    conn = sqlite3.connect(DATABASE_FILE)
    conn.row_factory = sqlite3.Row  # This allows dict-like access by column name
    return conn

def init_db():
    """Initializes the database schema if it doesn't already exist."""
    conn = get_db_connection()
    c = conn.cursor()
    
    # Create the wins table
    c.execute('''
        CREATE TABLE IF NOT EXISTS wins (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            habit TEXT NOT NULL,
            category TEXT DEFAULT 'Movement',
            timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    
    # Safely migrate existing tables by trying to add the column
    try:
        c.execute("ALTER TABLE wins ADD COLUMN category TEXT DEFAULT 'Movement'")
    except sqlite3.OperationalError:
        pass # Column likely already exists

    try:
        c.execute("ALTER TABLE wins ADD COLUMN upvotes INTEGER DEFAULT 0")
    except sqlite3.OperationalError:
        pass # Column likely already exists

    try:
        c.execute("ALTER TABLE wins ADD COLUMN ai_cheer TEXT")
    except sqlite3.OperationalError:
        pass # Column likely already exists
    
    conn.commit()
    conn.close()
    print("Database initialized.")
    cleanup_old_wins()

def cleanup_old_wins():
    """Removes wins older than 30 days to keep the feed fresh."""
    conn = get_db_connection()
    c = conn.cursor()
    # Delete records where timestamp is older than 30 days
    c.execute("DELETE FROM wins WHERE timestamp < datetime('now', '-30 days')")
    deleted_count = c.rowcount
    conn.commit()
    conn.close()
    if deleted_count > 0:
        print(f"Cleanup: Removed {deleted_count} old entries.")

if __name__ == '__main__':
    # Initialize the database when script is run directly
    init_db()
