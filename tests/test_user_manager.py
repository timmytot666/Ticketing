import unittest
import json
import os
import shutil
from unittest.mock import patch

# Assuming models.py and user_manager.py are accessible
from models import User
import user_manager

# Global for this test module
TEST_USERS_FILE = "test_users.json"

# It's good practice to ensure werkzeug is available if User model relies on it.
# Models.py has a fallback, but tests for hashing should ideally use real hashing.
try:
    from werkzeug.security import generate_password_hash, check_password_hash
    WERKZEUG_AVAILABLE = True
except ImportError:
    WERKZEUG_AVAILABLE = False


class TestUserManager(unittest.TestCase):

    def setUp(self):
        """Set up for test methods."""
        self.patcher = patch('user_manager.USERS_FILE', TEST_USERS_FILE)
        self.mock_users_file = self.patcher.start()

        if os.path.exists(TEST_USERS_FILE):
            if os.path.isdir(TEST_USERS_FILE):
                 shutil.rmtree(TEST_USERS_FILE)
            else:
                os.remove(TEST_USERS_FILE)

    def tearDown(self):
        """Tear down after test methods."""
        self.patcher.stop()
        if os.path.exists(TEST_USERS_FILE):
            if os.path.isdir(TEST_USERS_FILE):
                 shutil.rmtree(TEST_USERS_FILE)
            else:
                os.remove(TEST_USERS_FILE)

    def test_load_users_file_not_exist(self):
        self.assertEqual(user_manager._load_users(), [])

    def test_load_users_empty_file(self):
        with open(TEST_USERS_FILE, 'w') as f:
            f.write("")
        self.assertEqual(user_manager._load_users(), [])

    def test_load_users_invalid_json(self):
        with open(TEST_USERS_FILE, 'w') as f:
            f.write("{invalid_json_")
        with patch('builtins.print') as mock_print: # user_manager prints error
            self.assertEqual(user_manager._load_users(), [])
            mock_print.assert_any_call(f"Error: Could not decode JSON from {TEST_USERS_FILE}. Returning empty list.")

    def test_save_and_load_users(self):
        user1 = User(username="user1", role="EndUser")
        user1.set_password("pass1")
        user1.user_id = "fixed_id_1" # for predictable test

        user2 = User(username="user2", role="Technician")
        user2.set_password("pass2")
        user2.user_id = "fixed_id_2"

        users_to_save = [user1, user2]
        user_manager._save_users(users_to_save)

        loaded_users = user_manager._load_users()
        self.assertEqual(len(loaded_users), 2)
        loaded_usernames = {u.username for u in loaded_users}
        self.assertIn("user1", loaded_usernames)
        self.assertIn("user2", loaded_usernames)

        # Verify details of one user
        loaded_user1 = next(u for u in loaded_users if u.username == "user1")
        self.assertEqual(loaded_user1.user_id, user1.user_id)
        self.assertEqual(loaded_user1.role, user1.role)
        self.assertEqual(loaded_user1.password_hash, user1.password_hash) # Check hash directly
        self.assertTrue(loaded_user1.check_password("pass1"))


    def test_create_user_success(self):
        created_user = user_manager.create_user("newuser", "newpass123", "Engineer")
        self.assertIsInstance(created_user, User)
        self.assertEqual(created_user.username, "newuser")
        self.assertEqual(created_user.role, "Engineer")
        self.assertTrue(created_user.check_password("newpass123"))
        self.assertIsNotNone(created_user.password_hash) # Ensure hash is set

        loaded_users = user_manager._load_users()
        self.assertEqual(len(loaded_users), 1)
        self.assertEqual(loaded_users[0].username, "newuser")
        self.assertTrue(loaded_users[0].check_password("newpass123"))


    def test_create_user_duplicate_username(self):
        user_manager.create_user("existinguser", "pass1", "EndUser")
        with self.assertRaisesRegex(ValueError, "Username already exists."):
            user_manager.create_user("existinguser", "pass2", "Technician")

    def test_create_user_invalid_role(self):
        with self.assertRaisesRegex(ValueError, "Invalid role: BadRole."):
            user_manager.create_user("test", "testpass", "BadRole") # type: ignore

    def test_create_user_empty_password(self):
        # This check is now primarily in User.set_password, but create_user calls it.
        # user_manager.create_user itself also has a basic check.
        with self.assertRaisesRegex(ValueError, "Password cannot be empty."):
            user_manager.create_user("testuser", "", "EndUser")

    def test_get_user_by_username(self):
        user_manager.create_user("getme", "getpass", "TechManager")

        found_user = user_manager.get_user_by_username("getme")
        self.assertIsNotNone(found_user)
        self.assertEqual(found_user.username, "getme")

        not_found_user = user_manager.get_user_by_username("nosuchuser")
        self.assertIsNone(not_found_user)

        self.assertIsNone(user_manager.get_user_by_username(""), "Empty username should return None")


    def test_get_user_by_id(self):
        created_user = user_manager.create_user("byid_user", "idpass", "EngManager")

        found_user = user_manager.get_user_by_id(created_user.user_id)
        self.assertIsNotNone(found_user)
        self.assertEqual(found_user.user_id, created_user.user_id)

        not_found_user = user_manager.get_user_by_id("non_existent_id")
        self.assertIsNone(not_found_user)

        self.assertIsNone(user_manager.get_user_by_id(""), "Empty ID should return None")


    def test_verify_user_success(self):
        username = "verify_user_success"
        password = "verifypass"
        user_manager.create_user(username, password, "EndUser")

        verified_user = user_manager.verify_user(username, password)
        self.assertIsNotNone(verified_user)
        self.assertEqual(verified_user.username, username)

    def test_verify_user_wrong_password(self):
        username = "verify_user_wrong_pass"
        password = "correct_password"
        user_manager.create_user(username, password, "Technician")

        verified_user = user_manager.verify_user(username, "wrong_password")
        self.assertIsNone(verified_user)

    def test_verify_user_non_existent_user(self):
        verified_user = user_manager.verify_user("ghost_user", "any_pass")
        self.assertIsNone(verified_user)

    def test_verify_user_empty_credentials(self):
        self.assertIsNone(user_manager.verify_user("", "password"))
        self.assertIsNone(user_manager.verify_user("username", ""))
        self.assertIsNone(user_manager.verify_user("", ""))


if __name__ == '__main__':
    unittest.main()
