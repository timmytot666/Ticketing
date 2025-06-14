import json
import os
from typing import List, Optional, Dict, Any

try:
    from models import User
except ModuleNotFoundError:
    # This might happen if models.py is not in PYTHONPATH during some execution context
    # For this task, we assume models.py is accessible.
    print("Error: models.py not found. Ensure it's in the same directory or PYTHONPATH.")
    # Fallback User class for type hinting if models cannot be imported.
    # This allows the rest of the file to be parsed for tool validation,
    # but actual execution would fail if models.py is truly missing.
    class User:
        ROLES = None # Placeholder
        def __init__(self, *args, **kwargs): pass
        def set_password(self, p): pass
        def check_password(self, p) -> bool: return False
        def to_dict(self) -> dict: return {}
        @classmethod
        def from_dict(cls, d) -> 'User': return cls()


USERS_FILE = "users.json"

def _load_users() -> List[User]:
    """
    Reads users from USERS_FILE.
    If the file doesn't exist or is empty, returns an empty list.
    Otherwise, parses the JSON content and returns a list of User objects.
    Handles potential FileNotFoundError and json.JSONDecodeError.
    """
    try:
        if not os.path.exists(USERS_FILE) or os.path.getsize(USERS_FILE) == 0:
            return []
        with open(USERS_FILE, 'r') as f:
            data = json.load(f)
            return [User.from_dict(user_data) for user_data in data]
    except FileNotFoundError:
        return []
    except json.JSONDecodeError:
        print(f"Error: Could not decode JSON from {USERS_FILE}. Returning empty list.")
        return []
    except Exception as e: # Catch other potential errors during loading
        print(f"An unexpected error occurred while loading users: {e}")
        return []

def _save_users(users: List[User]) -> None:
    """
    Takes a list of User objects.
    Converts each User object to its dictionary representation.
    Writes the list of dictionaries to USERS_FILE as JSON.
    """
    try:
        with open(USERS_FILE, 'w') as f:
            json.dump([user.to_dict() for user in users], f, indent=4)
    except IOError as e:
        print(f"Error saving users to {USERS_FILE}: {e}")
    except Exception as e:
        print(f"An unexpected error occurred while saving users: {e}")


def create_user(username: str, password: str, role: User.ROLES) -> User:
    """
    Creates a new User, hashes their password, and saves them.
    Checks for existing username and valid role.
    """
    if not username: # Basic check, User class also validates
        raise ValueError("Username cannot be empty.")
    if not password: # Basic check, User.set_password also validates
        raise ValueError("Password cannot be empty.")

    # Validate role against User.ROLES
    # The User class __init__ also validates this, but good to have an early check.
    # ROLES might be None if the fallback User class is used due to import error.
    if User.ROLES and hasattr(User.ROLES, '__args__') and role not in User.ROLES.__args__:
         raise ValueError(f"Invalid role: {role}. Must be one of {User.ROLES.__args__}")


    users = _load_users()

    if any(user.username == username for user in users):
        raise ValueError("Username already exists.")

    # Create user instance (this will also validate role if User model is correctly imported)
    try:
        user = User(username=username, role=role)
        user.set_password(password) # Hashes password
    except ValueError as e: # Catch validation errors from User class or set_password
        raise ValueError(f"Error during user creation: {e}")


    users.append(user)
    _save_users(users)
    return user

def get_user_by_username(username: str) -> Optional[User]:
    """
    Retrieves a user by their username.
    """
    if not username:
        return None
    users = _load_users()
    for user in users:
        if user.username == username:
            return user
    return None

def get_user_by_id(user_id: str) -> Optional[User]:
    """
    Retrieves a user by their ID.
    """
    if not user_id:
        return None
    users = _load_users()
    for user in users:
        if user.user_id == user_id:
            return user
    return None

def verify_user(username: str, password: str) -> Optional[User]:
    """
    Verifies a user's credentials.
    Returns the User object if verification is successful, otherwise None.
    """
    if not username or not password:
        return None

    user = get_user_by_username(username)
    if user and user.check_password(password):
        return user
    return None
