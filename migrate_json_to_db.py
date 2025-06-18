import json
import sqlite3
from datetime import datetime, timezone
import os

# Assuming models.py, kb_article.py are in the same directory or accessible in PYTHONPATH
from models import User, Ticket, Notification
from kb_article import KBArticle
from database_setup import get_db_connection, DATABASE_NAME

# JSON file paths
USERS_JSON_FILE = "users.json"
TICKETS_JSON_FILE = "tickets.json"
KB_JSON_FILE = "knowledge_base.json"
NOTIFICATIONS_JSON_FILE = "notifications.json"

def migrate_users():
    print("Starting user migration...")
    try:
        with open(USERS_JSON_FILE, 'r', encoding='utf-8') as f:
            if os.path.getsize(USERS_JSON_FILE) == 0:
                print(f"{USERS_JSON_FILE} is empty. No users to migrate.")
                return
            users_data = json.load(f)
    except FileNotFoundError:
        print(f"{USERS_JSON_FILE} not found. No users to migrate.")
        return
    except json.JSONDecodeError:
        print(f"Error decoding JSON from {USERS_JSON_FILE}. Skipping user migration.")
        return

    conn = get_db_connection()
    cursor = conn.cursor()
    migrated_count = 0
    skipped_count = 0

    for user_dict in users_data:
        try:
            user = User.from_dict(user_dict)
            # Check if user already exists
            cursor.execute("SELECT user_id FROM users WHERE user_id = ?", (user.user_id,))
            if cursor.fetchone():
                print(f"User {user.username} (ID: {user.user_id}) already exists. Skipping.")
                skipped_count += 1
                continue

            cursor.execute('''
                INSERT INTO users (user_id, username, password_hash, role, is_active,
                                   force_password_reset, phone, email, department)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (user.user_id, user.username, user.password_hash, user.role, user.is_active,
                  user.force_password_reset, user.phone, user.email, user.department))
            migrated_count += 1
        except Exception as e:
            print(f"Error migrating user {user_dict.get('username', 'N/A')}: {e}")
            skipped_count +=1

    conn.commit()
    conn.close()
    print(f"Users migration complete. Migrated: {migrated_count}, Skipped/Errors: {skipped_count}")

def migrate_tickets():
    print("\nStarting ticket migration...")
    try:
        with open(TICKETS_JSON_FILE, 'r', encoding='utf-8') as f:
            if os.path.getsize(TICKETS_JSON_FILE) == 0:
                print(f"{TICKETS_JSON_FILE} is empty. No tickets to migrate.")
                return
            tickets_data = json.load(f)
    except FileNotFoundError:
        print(f"{TICKETS_JSON_FILE} not found. No tickets to migrate.")
        return
    except json.JSONDecodeError:
        print(f"Error decoding JSON from {TICKETS_JSON_FILE}. Skipping ticket migration.")
        return

    conn = get_db_connection()
    cursor = conn.cursor()
    migrated_count = 0
    skipped_count = 0

    for ticket_dict in tickets_data:
        try:
            ticket = Ticket.from_dict(ticket_dict)
            cursor.execute("SELECT id FROM tickets WHERE id = ?", (ticket.id,))
            if cursor.fetchone():
                print(f"Ticket {ticket.id} already exists. Skipping.")
                skipped_count += 1
                continue

            # Ensure datetime objects are converted to ISO format strings
            created_at_iso = ticket.created_at.isoformat() if ticket.created_at else None
            updated_at_iso = ticket.updated_at.isoformat() if ticket.updated_at else None
            response_due_at_iso = ticket.response_due_at.isoformat() if ticket.response_due_at else None
            resolution_due_at_iso = ticket.resolution_due_at.isoformat() if ticket.resolution_due_at else None
            responded_at_iso = ticket.responded_at.isoformat() if ticket.responded_at else None
            sla_paused_at_iso = ticket.sla_paused_at.isoformat() if ticket.sla_paused_at else None

            cursor.execute('''
                INSERT INTO tickets (
                    id, title, description, type, status, priority,
                    requester_user_id, created_by_user_id, assignee_user_id,
                    comments, created_at, updated_at, sla_policy_id,
                    response_due_at, resolution_due_at, responded_at, sla_paused_at,
                    total_paused_duration_seconds, response_sla_breach_notified,
                    resolution_sla_breach_notified, response_sla_nearing_breach_notified,
                    resolution_sla_nearing_breach_notified, attachments
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                ticket.id, ticket.title, ticket.description, ticket.type, ticket.status, ticket.priority,
                ticket.requester_user_id, ticket.created_by_user_id, ticket.assignee_user_id,
                json.dumps(ticket.comments) if ticket.comments else None,
                created_at_iso, updated_at_iso, ticket.sla_policy_id,
                response_due_at_iso, resolution_due_at_iso, responded_at_iso, sla_paused_at_iso,
                ticket.total_paused_duration_seconds, ticket.response_sla_breach_notified,
                ticket.resolution_sla_breach_notified, ticket.response_sla_nearing_breach_notified,
                ticket.resolution_sla_nearing_breach_notified,
                json.dumps(ticket.attachments) if ticket.attachments else None
            ))
            migrated_count += 1
        except Exception as e:
            print(f"Error migrating ticket {ticket_dict.get('id', 'N/A')}: {e}")
            skipped_count += 1

    conn.commit()
    conn.close()
    print(f"Tickets migration complete. Migrated: {migrated_count}, Skipped/Errors: {skipped_count}")

def migrate_kb_articles():
    print("\nStarting KB articles migration...")
    try:
        with open(KB_JSON_FILE, 'r', encoding='utf-8') as f:
            if os.path.getsize(KB_JSON_FILE) == 0:
                print(f"{KB_JSON_FILE} is empty. No KB articles to migrate.")
                return
            kb_data = json.load(f)
    except FileNotFoundError:
        print(f"{KB_JSON_FILE} not found. No KB articles to migrate.")
        return
    except json.JSONDecodeError:
        print(f"Error decoding JSON from {KB_JSON_FILE}. Skipping KB articles migration.")
        return

    conn = get_db_connection()
    cursor = conn.cursor()
    migrated_count = 0
    skipped_count = 0

    for article_dict in kb_data:
        try:
            article = KBArticle.from_dict(article_dict)
            cursor.execute("SELECT article_id FROM kb_articles WHERE article_id = ?", (article.article_id,))
            if cursor.fetchone():
                print(f"KB Article {article.article_id} already exists. Skipping.")
                skipped_count += 1
                continue

            created_at_iso = article.created_at.isoformat() if article.created_at else None
            updated_at_iso = article.updated_at.isoformat() if article.updated_at else None

            cursor.execute('''
                INSERT INTO kb_articles (
                    article_id, title, content, author_user_id,
                    keywords, category, created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                article.article_id, article.title, article.content, article.author_user_id,
                json.dumps(article.keywords) if article.keywords else None,
                article.category, created_at_iso, updated_at_iso
            ))
            migrated_count += 1
        except Exception as e:
            print(f"Error migrating KB Article {article_dict.get('article_id', 'N/A')}: {e}")
            skipped_count += 1

    conn.commit()
    conn.close()
    print(f"KB articles migration complete. Migrated: {migrated_count}, Skipped/Errors: {skipped_count}")

def migrate_notifications():
    print("\nStarting notifications migration...")
    try:
        with open(NOTIFICATIONS_JSON_FILE, 'r', encoding='utf-8') as f:
            if os.path.getsize(NOTIFICATIONS_JSON_FILE) == 0:
                print(f"{NOTIFICATIONS_JSON_FILE} is empty. No notifications to migrate.")
                return
            notifications_data = json.load(f)
    except FileNotFoundError:
        print(f"{NOTIFICATIONS_JSON_FILE} not found. No notifications to migrate.")
        return
    except json.JSONDecodeError:
        print(f"Error decoding JSON from {NOTIFICATIONS_JSON_FILE}. Skipping notifications migration.")
        return

    conn = get_db_connection()
    cursor = conn.cursor()
    migrated_count = 0
    skipped_count = 0

    for notif_dict in notifications_data:
        try:
            notification = Notification.from_dict(notif_dict)
            cursor.execute("SELECT notification_id FROM notifications WHERE notification_id = ?", (notification.notification_id,))
            if cursor.fetchone():
                print(f"Notification {notification.notification_id} already exists. Skipping.")
                skipped_count += 1
                continue

            timestamp_iso = notification.timestamp.isoformat() if notification.timestamp else None

            cursor.execute('''
                INSERT INTO notifications (
                    notification_id, user_id, ticket_id,
                    message, timestamp, is_read
                ) VALUES (?, ?, ?, ?, ?, ?)
            ''', (
                notification.notification_id, notification.user_id, notification.ticket_id,
                notification.message, timestamp_iso, notification.is_read
            ))
            migrated_count += 1
        except Exception as e:
            print(f"Error migrating notification {notif_dict.get('notification_id', 'N/A')}: {e}")
            skipped_count += 1

    conn.commit()
    conn.close()
    print(f"Notifications migration complete. Migrated: {migrated_count}, Skipped/Errors: {skipped_count}")

def run_all_migrations():
    print(f"Starting all data migrations to database: {DATABASE_NAME}\n")
    # It's important to migrate users first due to foreign key constraints
    migrate_users()
    # Tickets second, as they might reference users
    migrate_tickets()
    # KB articles can also reference users
    migrate_kb_articles()
    # Notifications can reference users and tickets
    migrate_notifications()
    print("\nAll migrations attempted.")

if __name__ == '__main__':
    # This ensures database schema exists before attempting to migrate data
    from database_setup import initialize_database
    initialize_database() # idempotent, creates tables if they don't exist

    run_all_migrations()
