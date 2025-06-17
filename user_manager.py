import json
import os
from typing import List, Optional, Dict, Any

try:
    from models import User
except ModuleNotFoundError:
    print("Error: models.py not found. Ensure it's in the same directory or PYTHONPATH.", file=sys.stderr)
    class User:
        ROLES = None # type: ignore
        username: str; role: Any; user_id: str; _password_hash: Optional[str]
        is_active: bool; force_password_reset: bool; # Add new fields to fallback
        def __init__(self, username: str, role: Any, user_id: Optional[str]=None, password_hash: Optional[str]=None,
                     is_active: bool = True, force_password_reset: bool = False, *args, **kwargs):
            self.username=username; self.role=role; self.user_id=user_id or "fb_id"; self._password_hash=password_hash
            self.is_active=is_active; self.force_password_reset=force_password_reset
        def set_password(self, p): self._password_hash = f"fb_hashed_{p}"
        def check_password(self, p) -> bool: return self._password_hash == f"fb_hashed_{p}" if self._password_hash else False
        def to_dict(self) -> dict: return self.__dict__
        @classmethod
        def from_dict(cls, d) -> 'User': return cls(**d)


USERS_FILE = "users.json"

def _load_users() -> List[User]:
    try:
        if not os.path.exists(USERS_FILE) or os.path.getsize(USERS_FILE) == 0: return []
        with open(USERS_FILE, 'r', encoding='utf-8') as f: data = json.load(f)
        return [User.from_dict(user_data) for user_data in data]
    except FileNotFoundError: return []
    except json.JSONDecodeError:
        print(f"Error decoding JSON from {USERS_FILE}. Ret empty list.", file=sys.stderr); return []
    except Exception as e: print(f"Unexpected error loading users: {e}", file=sys.stderr); return []

def _save_users(users: List[User]) -> bool: # Changed to return bool for success/failure
    try:
        with open(USERS_FILE, 'w', encoding='utf-8') as f:
            json.dump([user.to_dict() for user in users], f, indent=4, ensure_ascii=False)
        return True
    except IOError as e: print(f"Error saving users to {USERS_FILE}: {e}", file=sys.stderr); return False
    except Exception as e: print(f"Unexpected error saving users: {e}", file=sys.stderr); return False


def create_user(
    username: str,
    password: str,
    role: User.ROLES, # type: ignore
    is_active: bool = True,
    force_password_reset: bool = False,
    phone: Optional[str] = None,
    email: Optional[str] = None,
    department: Optional[str] = None
) -> User: # Changed to raise ValueError on failure, so User is always returned on success
    if not username: raise ValueError("Username cannot be empty.")
    if not password: raise ValueError("Password cannot be empty.")
    if User.ROLES and hasattr(User.ROLES, '__args__') and role not in User.ROLES.__args__: # type: ignore
         raise ValueError(f"Invalid role: {role}. Must be one of {User.ROLES.__args__}") # type: ignore

    users = _load_users()
    if any(hasattr(u, 'username') and u.username == username for u in users):
        raise ValueError("Username already exists.")

    user = User(
        username=username,
        role=role,
        is_active=is_active,
        force_password_reset=force_password_reset,
        phone=phone,
        email=email,
        department=department
    )
    user.set_password(password)

    users.append(user)
    if not _save_users(users):
        # This case should ideally not happen if pre-checks are done or if _save_users raises.
        # If _save_users can fail silently (other than printing), this indicates an issue.
        raise Exception("Failed to save user data after creating user.")
    return user

def get_user_by_username(username: str) -> Optional[User]:
    if not username: return None
    users = _load_users()
    return next((user for user in users if hasattr(user, 'username') and user.username == username), None)

def get_user_by_id(user_id: str) -> Optional[User]:
    if not user_id: return None
    users = _load_users()
    return next((user for user in users if hasattr(user, 'user_id') and user.user_id == user_id), None)

def verify_user(username: str, password: str) -> Optional[User]:
    if not username or not password: return None
    user = get_user_by_username(username)
    if user and hasattr(user, 'is_active') and not user.is_active: # Check if user is active
        print(f"Login attempt for inactive user: {username}", file=sys.stderr)
        return None
    if user and user.check_password(password):
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

    users = _load_users()
    user_to_update: Optional[User] = None
    user_index: int = -1

    for i, u in enumerate(users):
        if hasattr(u, 'user_id') and u.user_id == user_id:
            user_to_update = u
            user_index = i
            break

    if not user_to_update: return None

    updated = False
    if role is not None:
        if User.ROLES and hasattr(User.ROLES, '__args__') and role not in User.ROLES.__args__: # type: ignore
            raise ValueError(f"Invalid role: {role}. Must be one of {User.ROLES.__args__}") # type: ignore
        if user_to_update.role != role: user_to_update.role = role; updated = True

    if is_active is not None and user_to_update.is_active != is_active:
        user_to_update.is_active = is_active; updated = True

    if force_password_reset is not None and user_to_update.force_password_reset != force_password_reset:
        user_to_update.force_password_reset = force_password_reset; updated = True

    if phone is not None and user_to_update.phone != phone:
        user_to_update.phone = phone; updated = True

    if email is not None and user_to_update.email != email:
        user_to_update.email = email; updated = True

    if department is not None and user_to_update.department != department:
        user_to_update.department = department; updated = True

    if updated:
        users[user_index] = user_to_update
        if not _save_users(users):
            # Consider how to handle save failure. Maybe raise an exception.
            print(f"Error: Failed to save user profile updates for {user_id}", file=sys.stderr)
            return None # Or re-raise

    return user_to_update


def set_user_password(user_id: str, new_password: str) -> bool:
    if not user_id: raise ValueError("User ID is required.")
    if not new_password: raise ValueError("New password cannot be empty.")

    users = _load_users()
    user_to_update: Optional[User] = None
    user_index: int = -1

    for i, u in enumerate(users):
        if hasattr(u, 'user_id') and u.user_id == user_id:
            user_to_update = u
            user_index = i
            break

    if not user_to_update: return False # User not found

    user_to_update.set_password(new_password)
    user_to_update.force_password_reset = False # Password has been reset

    users[user_index] = user_to_update
    return _save_users(users)


def list_all_users(
    filters: Optional[Dict[str, Any]] = None,
    sort_by: str = 'username',
    reverse_sort: bool = False
) -> List[User]:
    users = _load_users()

    if filters:
        filtered_users: List[User] = []
        for user in users:
            match = True
            for key, value in filters.items():
                if not hasattr(user, key): match = False; break
                attr_value = getattr(user, key)
                if key == 'username' and isinstance(value, str): # Case-insensitive substring for username
                    if value.lower() not in attr_value.lower(): match = False; break
                elif key == 'role' and isinstance(value, str): # Exact match for role
                    if attr_value != value: match = False; break
                elif key == 'is_active' and isinstance(value, bool):
                    if attr_value != value: match = False; break
                elif key == 'force_password_reset' and isinstance(value, bool):
                    if attr_value != value: match = False; break
                # else: # Unknown filter key for User model
                #     match = False; break
            if match: filtered_users.append(user)
        users = filtered_users

    # Sorting
    if hasattr(User, sort_by): # Check if sort_by is a valid attribute of User
        # Provide default for getattr in case an attribute could be None (e.g. for non-string sort keys)
        default_sort_val = "" if isinstance(getattr(users[0] if users else User, sort_by, ""), str) else 0
        try:
            users.sort(key=lambda u: getattr(u, sort_by, default_sort_val), reverse=reverse_sort)
        except TypeError as e:
            print(f"Warning: Could not sort users by '{sort_by}' due to type error: {e}. Returning unsorted by this key.", file=sys.stderr)
    elif sort_by != 'username': # Default was username, if it's something else and invalid, warn.
         print(f"Warning: Cannot sort by '{sort_by}', attribute not found. Defaulting to username sort.", file=sys.stderr)
         users.sort(key=lambda u: getattr(u, 'username', ""), reverse=reverse_sort)


    return users


def get_users_by_role(roles: List[str]) -> List[User]: # Unchanged from previous step
    if not roles: return []
    all_users = _load_users()
    matching_users: List[User] = []
    if User.ROLES and hasattr(User.ROLES, '__args__'):
        valid_system_roles = User.ROLES.__args__
        for role in roles:
            if role not in valid_system_roles:
                print(f"Warning: Role '{role}' in get_users_by_role is not a defined system role.", file=sys.stderr)
    for user in all_users:
        if hasattr(user, 'role') and user.role in roles: matching_users.append(user)
    return matching_users
