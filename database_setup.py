import sqlite3
import json # For storing complex types like lists/dicts as JSON strings

DATABASE_NAME = "ticketing_system.db"

def get_db_connection():
    """Establishes and returns a connection to the SQLite database."""
    conn = sqlite3.connect(DATABASE_NAME)
    conn.row_factory = sqlite3.Row # Access columns by name
    return conn

def create_users_table():
    """Creates the users table if it doesn't exist."""
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS users (
            user_id TEXT PRIMARY KEY,
            username TEXT UNIQUE NOT NULL,
            password_hash TEXT NOT NULL,
            role TEXT NOT NULL,
            is_active BOOLEAN NOT NULL DEFAULT TRUE,
            force_password_reset BOOLEAN NOT NULL DEFAULT FALSE,
            phone TEXT,
            email TEXT,
            department TEXT
        )
    ''')
    conn.commit()
    conn.close()

def create_tickets_table():
    """Creates the tickets table if it doesn't exist."""
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS tickets (
            id TEXT PRIMARY KEY,
            title TEXT NOT NULL,
            description TEXT NOT NULL,
            type TEXT NOT NULL,
            status TEXT NOT NULL DEFAULT 'Open',
            priority TEXT NOT NULL DEFAULT 'Medium',
            requester_user_id TEXT NOT NULL,
            created_by_user_id TEXT NOT NULL,
            assignee_user_id TEXT,
            comments TEXT, -- JSON string for list of comment dicts
            created_at TEXT NOT NULL, -- ISO format datetime string
            updated_at TEXT NOT NULL, -- ISO format datetime string
            sla_policy_id TEXT,
            response_due_at TEXT, -- ISO format datetime string
            resolution_due_at TEXT, -- ISO format datetime string
            responded_at TEXT, -- ISO format datetime string
            sla_paused_at TEXT, -- ISO format datetime string
            total_paused_duration_seconds REAL DEFAULT 0.0,
            response_sla_breach_notified BOOLEAN DEFAULT FALSE,
            resolution_sla_breach_notified BOOLEAN DEFAULT FALSE,
            response_sla_nearing_breach_notified BOOLEAN DEFAULT FALSE,
            resolution_sla_nearing_breach_notified BOOLEAN DEFAULT FALSE,
            attachments TEXT, -- JSON string for list of attachment dicts
            FOREIGN KEY (requester_user_id) REFERENCES users(user_id),
            FOREIGN KEY (created_by_user_id) REFERENCES users(user_id),
            FOREIGN KEY (assignee_user_id) REFERENCES users(user_id)
        )
    ''')
    conn.commit()
    conn.close()

def create_kb_articles_table():
    """Creates the kb_articles table if it doesn't exist."""
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS kb_articles (
            article_id TEXT PRIMARY KEY,
            title TEXT NOT NULL,
            content TEXT NOT NULL,
            author_user_id TEXT NOT NULL,
            keywords TEXT, -- JSON string for list of keywords
            category TEXT,
            created_at TEXT NOT NULL, -- ISO format datetime string
            updated_at TEXT NOT NULL, -- ISO format datetime string
            FOREIGN KEY (author_user_id) REFERENCES users(user_id)
        )
    ''')
    conn.commit()
    conn.close()

def create_notifications_table():
    """Creates the notifications table if it doesn't exist."""
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS notifications (
            notification_id TEXT PRIMARY KEY,
            user_id TEXT NOT NULL,
            ticket_id TEXT,
            message TEXT NOT NULL,
            timestamp TEXT NOT NULL, -- ISO format datetime string
            is_read BOOLEAN NOT NULL DEFAULT FALSE,
            FOREIGN KEY (user_id) REFERENCES users(user_id),
            FOREIGN KEY (ticket_id) REFERENCES tickets(id)
        )
    ''')
    conn.commit()
    conn.close()

def initialize_database():
    """Initializes all tables in the database."""
    create_users_table()
    create_tickets_table()
    create_kb_articles_table()
    create_notifications_table()
    print(f"Database '{DATABASE_NAME}' initialized successfully with all tables.")

if __name__ == '__main__':
    # This will run when the script is executed directly
    # It's a good way to set up the database for the first time
    initialize_database()
