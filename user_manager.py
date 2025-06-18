import sqlite3
import sys # For stderr
from typing import List, Optional, Dict, Any

try:
    from models import User
    # This will try to import werkzeug.security from models.py
    # If not found, models.py has a fallback, but a warning will be printed.
except ModuleNotFoundError:
    print("Critical Error: models.py not found. User manager cannot function.", file=sys.stderr)
    # Fallback User class if models.py is missing, to allow some basic parsing of this file
    # but operations will largely fail.
    class User:
        ROLES = None
        username: str; role: Any; user_id: str; _password_hash: Optional[str]
        is_active: bool; force_password_reset: bool; phone: Optional[str]; email: Optional[str]; department: Optional[str]
        def __init__(self, username: str, role: Any, user_id: Optional[str]=None, password_hash: Optional[str]=None,
                     is_active: bool = True, force_password_reset: bool = False,
                     phone: Optional[str] = None, email: Optional[str] = None, department: Optional[str] = None,
                     *args, **kwargs):
            self.user_id = user_id or "fb_user_id"
            self.username = username
            self._password_hash = password_hash
            self.role = role
            self.is_active = is_active
            self.force_password_reset = force_password_reset
            self.phone = phone
            self.email = email
            self.department = department
        def set_password(self, p): self._password_hash = f"fb_hashed_{p}"
        def check_password(self, p) -> bool: return self._password_hash == f"fb_hashed_{p}" if self._password_hash else False
        @property
        def password_hash(self): return self._password_hash
        # to_dict and from_dict are not strictly needed by user_manager after DB migration
        # but a User instance still needs these for other parts (like migration script)
        def to_dict(self) -> dict: return {**self.__dict__, '_password_hash': self._password_hash}
        @classmethod
        def from_dict(cls, data: Dict[str, Any]) -> 'User':
            return cls(
                username=data["username"], role=data["role"], user_id=data.get("user_id"),
                password_hash=data.get("password_hash"),is_active=data.get("is_active", True),
                force_password_reset=data.get("force_password_reset", False), phone=data.get("phone"),
                email=data.get("email"), department=data.get("department")
            )

try:
    from database_setup import get_db_connection
except ModuleNotFoundError:
    print("Critical Error: database_setup.py not found. User manager cannot function.", file=sys.stderr)
    # Fallback get_db_connection
    def get_db_connection():
        print("Fallback get_db_connection called: Database operations will fail.", file=sys.stderr)
        raise ConnectionError("Database setup module not found.")

def _row_to_user(row: sqlite3.Row) -> Optional[User]:
    """Converts a sqlite3.Row to a User object."""
    if not row:
        return None
    return User(
        user_id=row["user_id"],
        username=row["username"],
        password_hash=row["password_hash"], # Direct hash from DB
        role=row["role"],
        is_active=bool(row["is_active"]),
        force_password_reset=bool(row["force_password_reset"]),
        phone=row["phone"],
        email=row["email"],
        department=row["department"]
    )

def create_user(
    username: str,
    password: str,
    role: User.ROLES, # type: ignore
    is_active: bool = True,
    force_password_reset: bool = False,
    phone: Optional[str] = None,
    email: Optional[str] = None,
    department: Optional[str] = None
) -> User:
    if not username: raise ValueError("Username cannot be empty.")
    if not password: raise ValueError("Password cannot be empty.")

    # Role validation using Literal's __args__ if available
    if User.ROLES and hasattr(User.ROLES, '__args__'): # type: ignore
        if role not in User.ROLES.__args__: # type: ignore
             raise ValueError(f"Invalid role: {role}. Must be one of {User.ROLES.__args__}") # type: ignore
    elif User.ROLES and hasattr(User.ROLES, '__values__'): # Fallback for older Literal
        if role not in User.ROLES.__values__: # type: ignore
             raise ValueError(f"Invalid role: {role}. Must be one of {User.ROLES.__values__}") # type: ignore


    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        # Check for existing username
        cursor.execute("SELECT username FROM users WHERE username = ?", (username,))
        if cursor.fetchone():
            raise ValueError("Username already exists.")

        user = User(
            username=username, role=role, is_active=is_active,
            force_password_reset=force_password_reset,
            phone=phone, email=email, department=department
        )
        user.set_password(password) # Hashes the password

        cursor.execute('''
            INSERT INTO users (user_id, username, password_hash, role, is_active,
                               force_password_reset, phone, email, department)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (user.user_id, user.username, user.password_hash, user.role, user.is_active,
              user.force_password_reset, user.phone, user.email, user.department))
        conn.commit()
        return user
    except sqlite3.Error as e:
        conn.rollback() # Rollback on any SQLite error
        print(f"Database error creating user {username}: {e}", file=sys.stderr)
        # Could raise a custom DB error or re-raise
        raise Exception(f"Failed to save user data for {username} due to database error.") from e
    finally:
        conn.close()


def get_user_by_username(username: str) -> Optional[User]:
    if not username: return None
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM users WHERE username = ?", (username,))
    row = cursor.fetchone()
    conn.close()
    return _row_to_user(row)

def get_user_by_id(user_id: str) -> Optional[User]:
    if not user_id: return None
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM users WHERE user_id = ?", (user_id,))
    row = cursor.fetchone()
    conn.close()
    return _row_to_user(row)

def verify_user(username: str, password: str) -> Optional[User]:
    if not username or not password: return None
    user = get_user_by_username(username)
    if user and not user.is_active:
        print(f"Login attempt for inactive user: {username}", file=sys.stderr)
        return None
    if user and user.check_password(password): # check_password is part of User model
        return user
    return None

def update_user_profile(
    user_id: str,
    role: Optional[User.ROLES] = None, # type: ignore
    is_active: Optional[bool] = None,
    force_password_reset: Optional[bool] = None,
    phone: Optional[str] = None,
    email: Optional[str] = None,
    department: Optional[str] = None
) -> Optional[User]:
    if not user_id: raise ValueError("User ID is required to update profile.")

    conn = get_db_connection()
    cursor = conn.cursor()

    user_to_update = get_user_by_id(user_id) # Fetch current state first
    if not user_to_update:
        conn.close()
        return None

    fields_to_update: Dict[str, Any] = {}
    if role is not None:
        if User.ROLES and hasattr(User.ROLES, '__args__') and role not in User.ROLES.__args__: # type: ignore
            conn.close()
            raise ValueError(f"Invalid role: {role}. Must be one of {User.ROLES.__args__}") # type: ignore
        if user_to_update.role != role: fields_to_update['role'] = role

    if is_active is not None and user_to_update.is_active != is_active:
        fields_to_update['is_active'] = is_active
    if force_password_reset is not None and user_to_update.force_password_reset != force_password_reset:
        fields_to_update['force_password_reset'] = force_password_reset
    if phone is not None and user_to_update.phone != phone:
        fields_to_update['phone'] = phone
    if email is not None and user_to_update.email != email:
        fields_to_update['email'] = email
    if department is not None and user_to_update.department != department:
        fields_to_update['department'] = department

    if not fields_to_update:
        conn.close()
        return user_to_update # No changes

    set_clause = ", ".join([f"{key} = ?" for key in fields_to_update.keys()])
    values = list(fields_to_update.values())
    values.append(user_id)

    try:
        cursor.execute(f"UPDATE users SET {set_clause} WHERE user_id = ?", tuple(values))
        conn.commit()
    except sqlite3.Error as e:
        conn.rollback()
        print(f"Database error updating user profile {user_id}: {e}", file=sys.stderr)
        conn.close()
        return None # Or raise error
    finally:
        if conn: conn.close()

    return get_user_by_id(user_id) # Return the updated user object


def set_user_password(user_id: str, new_password: str) -> bool:
    if not user_id: raise ValueError("User ID is required.")
    if not new_password: raise ValueError("New password cannot be empty.")

    user = get_user_by_id(user_id)
    if not user:
        return False

    user.set_password(new_password) # Hashes the new password

    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        cursor.execute('''
            UPDATE users
            SET password_hash = ?, force_password_reset = ?
            WHERE user_id = ?
        ''', (user.password_hash, False, user_id)) # Reset force_password_reset flag
        conn.commit()
        return True
    except sqlite3.Error as e:
        conn.rollback()
        print(f"Database error setting password for user {user_id}: {e}", file=sys.stderr)
        return False
    finally:
        conn.close()

def list_all_users(
    filters: Optional[Dict[str, Any]] = None,
    sort_by: str = 'username', # Default sort column
    reverse_sort: bool = False
) -> List[User]:
    conn = get_db_connection()
    cursor = conn.cursor()

    query = "SELECT * FROM users"
    filter_values = []

    if filters:
        conditions = []
        for key, value in filters.items():
            # Ensure key is a valid column to prevent SQL injection if keys were less controlled
            # For this internal use, we assume keys are from a known set.
            if key == 'username': # Partial match for username
                conditions.append(f"LOWER(username) LIKE ?")
                filter_values.append(f"%{str(value).lower()}%")
            elif key in ['role', 'is_active', 'force_password_reset', 'department', 'email', 'phone']: # Exact match
                conditions.append(f"{key} = ?")
                filter_values.append(value)
            # else: ignore unknown filter keys
        if conditions:
            query += " WHERE " + " AND ".join(conditions)

    # Validate sort_by against a list of allowed column names to prevent SQL injection
    allowed_sort_columns = ['user_id', 'username', 'role', 'is_active', 'email', 'department']
    if sort_by not in allowed_sort_columns:
        sort_by = 'username' # Default to a safe column if invalid sort_by is provided
        print(f"Warning: Invalid sort_by column '{sort_by}'. Defaulting to 'username'.", file=sys.stderr)

    query += f" ORDER BY {sort_by}" # sort_by is now from a whitelist
    if reverse_sort:
        query += " DESC"
    else:
        query += " ASC"

    try:
        cursor.execute(query, tuple(filter_values))
        rows = cursor.fetchall()
        users = [_row_to_user(row) for row in rows if row] # Filter out None if _row_to_user returns it
        return [u for u in users if u is not None] # Ensure no None User objects in list
    except sqlite3.Error as e:
        print(f"Database error listing users: {e}", file=sys.stderr)
        return []
    finally:
        conn.close()

def get_users_by_role(roles: List[str]) -> List[User]:
    if not roles: return []

    conn = get_db_connection()
    cursor = conn.cursor()

    # Create a string of placeholders for the IN clause, e.g., (?, ?, ?)
    placeholders = ', '.join(['?'] * len(roles))
    query = f"SELECT * FROM users WHERE role IN ({placeholders})"

    try:
        cursor.execute(query, tuple(roles))
        rows = cursor.fetchall()
        users = [_row_to_user(row) for row in rows if row]
        return [u for u in users if u is not None]
    except sqlite3.Error as e:
        print(f"Database error getting users by role: {e}", file=sys.stderr)
        return []
    finally:
        conn.close()
