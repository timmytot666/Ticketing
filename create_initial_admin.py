#!/usr/bin/env python3

import sys
import os

# Ensure project root is in sys.path if running script directly from root.
# This helps locate user_manager and models if they are not installed as a package.
# current_dir = os.path.dirname(os.path.abspath(__file__))
# if current_dir not in sys.path:
#     sys.path.append(current_dir)
# For this project structure, if all .py files are in the root, direct imports usually work.

try:
    from user_manager import get_user_by_username, create_user
    from models import User
except ModuleNotFoundError as e:
    print(f"Error: Could not import necessary modules (user_manager, models). {e}", file=sys.stderr)
    print("Please ensure that user_manager.py and models.py are in the same directory as this script,", file=sys.stderr)
    print("or that the project root directory is in your PYTHONPATH.", file=sys.stderr)
    sys.exit(1)

# Default Admin Credentials
DEFAULT_ADMIN_USERNAME = "admin"
DEFAULT_ADMIN_PASSWORD = "password"  # IMPORTANT: Change this in a production environment!
DEFAULT_ADMIN_ROLE = "TechManager"    # Ensure this role is valid (e.g., 'EngManager' or 'TechManager')

def main():
    """Main function to create the initial admin user."""
    print("Attempting to create initial admin user...")

    # Validate the default admin role
    if not hasattr(User, 'ROLES') or not hasattr(User.ROLES, '__args__'):
        print(f"Error: User.ROLES not defined or not structured as expected in models.py.", file=sys.stderr)
        sys.exit(1)

    if DEFAULT_ADMIN_ROLE not in User.ROLES.__args__:
        print(f"Error: Role '{DEFAULT_ADMIN_ROLE}' is not a valid role.", file=sys.stderr)
        print(f"Available roles are: {User.ROLES.__args__}", file=sys.stderr)
        sys.exit(1)

    # Check if the admin user already exists
    try:
        existing_user = get_user_by_username(DEFAULT_ADMIN_USERNAME)
    except Exception as e:
        print(f"Error while checking for existing user: {e}", file=sys.stderr)
        print("This might indicate an issue with the user data store (e.g., users.json).", file=sys.stderr)
        sys.exit(1)

    if existing_user:
        print(f"User '{DEFAULT_ADMIN_USERNAME}' with role '{existing_user.role}' already exists. No action taken.")
    else:
        print(f"User '{DEFAULT_ADMIN_USERNAME}' not found. Creating new admin user...")
        try:
            # create_user from user_manager is expected to handle is_active and force_password_reset defaults
            new_admin = create_user(
                username=DEFAULT_ADMIN_USERNAME,
                password=DEFAULT_ADMIN_PASSWORD,
                role=DEFAULT_ADMIN_ROLE,
                force_password_reset=True # Ensure user must change password on first login
                # is_active will use its default from user_manager.create_user (typically True)
            )
            if new_admin:
                print(f"Successfully created user '{new_admin.username}' with role '{new_admin.role}'.")
                print(f"  ID: {new_admin.user_id}")
                # The force_password_reset value will now reflect the explicit setting
                print(f"  Status: is_active={new_admin.is_active}, force_password_reset={new_admin.force_password_reset}")
                print(f"\nIMPORTANT: User '{new_admin.username}' will be required to change the default password ('{DEFAULT_ADMIN_PASSWORD}') on first login.")
                print("This is because 'force_password_reset' has been set to True for this initial admin account.")

            else:
                # This case might occur if create_user returns None without raising an exception
                print(f"Failed to create user '{DEFAULT_ADMIN_USERNAME}'.", file=sys.stderr)
                print("The create_user function returned None but did not raise an error.", file=sys.stderr)
        except ValueError as ve:
            print(f"Error creating user '{DEFAULT_ADMIN_USERNAME}': {ve}", file=sys.stderr)
        except Exception as e:
            print(f"An unexpected error occurred while creating user '{DEFAULT_ADMIN_USERNAME}': {e}", file=sys.stderr)
            print("Check for issues with file permissions or data integrity (e.g., users.json).", file=sys.stderr)

if __name__ == "__main__":
    main()
