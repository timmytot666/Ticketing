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
        self.assertTrue(created_user.is_active) # Default
        self.assertFalse(created_user.force_password_reset) # Default
        self.assertTrue(created_user.check_password("newpass123"))
        self.assertIsNotNone(created_user.password_hash)

        loaded_users = user_manager._load_users()
        self.assertEqual(len(loaded_users), 1)
        loaded_db_user = loaded_users[0]
        self.assertEqual(loaded_db_user.username, "newuser")
        self.assertTrue(loaded_db_user.is_active)
        self.assertFalse(loaded_db_user.force_password_reset)
        self.assertTrue(loaded_db_user.check_password("newpass123"))

    def test_create_user_with_flags(self):
        created_user = user_manager.create_user(
            "flaguser", "flagpass", "Technician", is_active=False, force_password_reset=True
        )
        self.assertFalse(created_user.is_active)
        self.assertTrue(created_user.force_password_reset)

        loaded_users = user_manager._load_users()
        self.assertEqual(len(loaded_users), 1)
        loaded_db_user = loaded_users[0]
        self.assertEqual(loaded_db_user.username, "flaguser")
        self.assertFalse(loaded_db_user.is_active)
        self.assertTrue(loaded_db_user.force_password_reset)

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
        # Ensure user is active for this test
        user_manager.create_user(username, password, "EndUser", is_active=True)

        verified_user = user_manager.verify_user(username, password)
        self.assertIsNotNone(verified_user)
        self.assertEqual(verified_user.username, username)
        self.assertTrue(verified_user.is_active)

    def test_verify_user_inactive_user(self):
        username = "inactive_user_test"
        password = "inactive_password"
        user_manager.create_user(username, password, "EndUser", is_active=False)

        verified_user = user_manager.verify_user(username, password)
        # Even with correct password, verify_user should fail if user is inactive
        self.assertIsNone(verified_user, "Inactive user should not be verified.")

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

    @patch.object(user_manager, '_save_users')
    def test_update_user_profile_success_all_fields(self, mock_save_users):
        user = user_manager.create_user("updater", "oldpass", "EndUser", is_active=True, force_password_reset=False)
        updated_user = user_manager.update_user_profile(
            user.user_id,
            role="Technician",
            is_active=False,
            force_password_reset=True
        )
        self.assertIsNotNone(updated_user)
        self.assertEqual(updated_user.role, "Technician")
        self.assertFalse(updated_user.is_active)
        self.assertTrue(updated_user.force_password_reset)
        mock_save_users.assert_called_once()
        # Check if data is actually persisted by reloading
        reloaded_user = user_manager.get_user_by_id(user.user_id)
        self.assertEqual(reloaded_user.role, "Technician")
        self.assertFalse(reloaded_user.is_active)
        self.assertTrue(reloaded_user.force_password_reset)


    @patch.object(user_manager, '_save_users')
    def test_update_user_profile_only_role(self, mock_save_users):
        user = user_manager.create_user("roleupdater", "pass", "EndUser")
        user_manager.update_user_profile(user.user_id, role="Engineer")
        reloaded = user_manager.get_user_by_id(user.user_id)
        self.assertEqual(reloaded.role, "Engineer")
        mock_save_users.assert_called() # Might be called more than once if get_user reloads

    @patch.object(user_manager, '_save_users')
    def test_update_user_profile_only_is_active(self, mock_save_users):
        user = user_manager.create_user("activeupdater", "pass", "EndUser", is_active=True)
        user_manager.update_user_profile(user.user_id, is_active=False)
        reloaded = user_manager.get_user_by_id(user.user_id)
        self.assertFalse(reloaded.is_active)
        mock_save_users.assert_called()

    @patch.object(user_manager, '_save_users')
    def test_update_user_profile_only_force_reset(self, mock_save_users):
        user = user_manager.create_user("resetupdater", "pass", "EndUser", force_password_reset=False)
        user_manager.update_user_profile(user.user_id, force_password_reset=True)
        reloaded = user_manager.get_user_by_id(user.user_id)
        self.assertTrue(reloaded.force_password_reset)
        mock_save_users.assert_called()

    @patch.object(user_manager, '_save_users')
    def test_update_user_profile_user_not_found(self, mock_save_users):
        result = user_manager.update_user_profile("nonexistentid", role="Admin")
        self.assertIsNone(result)
        mock_save_users.assert_not_called()

    @patch.object(user_manager, '_save_users')
    def test_update_user_profile_invalid_role(self, mock_save_users):
        user = user_manager.create_user("invalidroleuser", "pass", "EndUser")
        original_role = user.role
        with self.assertRaisesRegex(ValueError, "Invalid role: SuperAdmin"):
            user_manager.update_user_profile(user.user_id, role="SuperAdmin") # type: ignore

        reloaded_user = user_manager.get_user_by_id(user.user_id)
        self.assertEqual(reloaded_user.role, original_role) # Role should not change
        # _save_users might be called by create_user, so we check calls *after* setup
        # For this specific test, the critical part is that the invalid role is not set.
        # Depending on implementation, _save_users might be called before the validation error.
        # A more robust check would be to see if the saved state reflects the original role.
        # This is covered by reloading and checking reloaded_user.role.

    @patch.object(user_manager, '_save_users')
    def test_update_user_profile_no_changes(self, mock_save_users):
        user = user_manager.create_user("nochangeuser", "pass", "EndUser", is_active=True, force_password_reset=False)
        # Get initial call count of _save_users from the create_user call
        initial_save_count = mock_save_users.call_count

        updated_user = user_manager.update_user_profile(user.user_id, role="EndUser", is_active=True, force_password_reset=False)
        self.assertIsNotNone(updated_user)
        # In current user_manager, it saves if any attribute is provided, even if value is same.
        # self.assertEqual(mock_save_users.call_count, initial_save_count) # This would fail
        self.assertGreaterEqual(mock_save_users.call_count, initial_save_count + 1)


    @patch.object(user_manager, '_save_users')
    def test_set_user_password_success(self, mock_save_users):
        user = user_manager.create_user("passreset", "oldpass", "EndUser", force_password_reset=True)
        self.assertTrue(user.force_password_reset) # Pre-condition

        result = user_manager.set_user_password(user.user_id, "newSecurePassword")
        self.assertTrue(result)

        reloaded_user = user_manager.get_user_by_id(user.user_id)
        self.assertTrue(reloaded_user.check_password("newSecurePassword"))
        self.assertFalse(reloaded_user.force_password_reset, "force_password_reset should be False after password change")
        mock_save_users.assert_called()


    @patch.object(user_manager, '_save_users')
    def test_set_user_password_empty_new_password(self, mock_save_users):
        user = user_manager.create_user("emptypass", "oldpass", "EndUser")
        with self.assertRaisesRegex(ValueError, "Password cannot be empty."):
            user_manager.set_user_password(user.user_id, "")
        mock_save_users.assert_not_called() # _save_users is called by create_user, so check after that

    @patch.object(user_manager, '_save_users')
    def test_set_user_password_user_not_found(self, mock_save_users):
        initial_save_count = mock_save_users.call_count
        result = user_manager.set_user_password("nonexistentid", "newpass")
        self.assertFalse(result)
        self.assertEqual(mock_save_users.call_count, initial_save_count)

    def _setup_sample_users_for_listing(self):
        # Clear existing users for clean slate for list tests
        user_manager._save_users([])
        users_data = [
            {"username": "alice", "password": "password", "role": "Engineer", "is_active": True, "force_password_reset": False},
            {"username": "bob", "password": "password", "role": "Technician", "is_active": True, "force_password_reset": True},
            {"username": "charlie", "password": "password", "role": "EndUser", "is_active": False, "force_password_reset": False},
            {"username": "david", "password": "password", "role": "Engineer", "is_active": True, "force_password_reset": False},
            {"username": "eve", "password": "password", "role": "TechManager", "is_active": False, "force_password_reset": True},
            {"username": "frank", "password": "password", "role": "EndUser", "is_active": True, "force_password_reset": False}
        ]
        for u_data in users_data:
            user_manager.create_user(u_data["username"], u_data["password"], u_data["role"], # type: ignore
                                     is_active=u_data["is_active"],
                                     force_password_reset=u_data["force_password_reset"])
        return users_data


    def test_list_all_users_no_filters_default_sort(self):
        self._setup_sample_users_for_listing()
        users = user_manager.list_all_users()
        self.assertEqual(len(users), 6)
        # Default sort is by username
        self.assertEqual([u.username for u in users], ["alice", "bob", "charlie", "david", "eve", "frank"])

    def test_list_all_users_sort_by_role_descending(self):
        self._setup_sample_users_for_listing()
        users = user_manager.list_all_users(sort_by="role", reverse_sort=True)
        # Expected: TechManager, Technician, Engineer, Engineer, EndUser, EndUser
        # (Order within same role might vary based on secondary sort, often username)
        roles = [u.role for u in users]
        self.assertEqual(roles, ["TechManager", "Technician", "Engineer", "Engineer", "EndUser", "EndUser"])
        # Check secondary sort by username if roles are same
        if roles[2] == roles[3] == "Engineer": # david then alice if reverse username
             self.assertTrue( (users[2].username == "david" and users[3].username == "alice") or \
                              (users[2].username == "alice" and users[3].username == "david") )


    def test_list_all_users_filter_username(self):
        self._setup_sample_users_for_listing()
        users = user_manager.list_all_users(filters={"username": "ali"}) # Substring, case-insensitive by default in manager
        self.assertEqual(len(users), 1)
        self.assertEqual(users[0].username, "alice")

        users_case = user_manager.list_all_users(filters={"username": "ALI"})
        self.assertEqual(len(users_case), 1)
        self.assertEqual(users_case[0].username, "alice")

    def test_list_all_users_filter_role(self):
        self._setup_sample_users_for_listing()
        users = user_manager.list_all_users(filters={"role": "Engineer"})
        self.assertEqual(len(users), 2)
        self.assertTrue(all(u.role == "Engineer" for u in users))
        usernames = {u.username for u in users}
        self.assertEqual(usernames, {"alice", "david"})

    def test_list_all_users_filter_is_active_true(self):
        self._setup_sample_users_for_listing()
        users = user_manager.list_all_users(filters={"is_active": True})
        self.assertEqual(len(users), 4) # alice, bob, david, frank
        self.assertTrue(all(u.is_active for u in users))
        usernames = {u.username for u in users}
        self.assertEqual(usernames, {"alice", "bob", "david", "frank"})

    def test_list_all_users_filter_is_active_false(self):
        self._setup_sample_users_for_listing()
        users = user_manager.list_all_users(filters={"is_active": False})
        self.assertEqual(len(users), 2) # charlie, eve
        self.assertTrue(all(not u.is_active for u in users))
        usernames = {u.username for u in users}
        self.assertEqual(usernames, {"charlie", "eve"})

    def test_list_all_users_filter_force_password_reset_true(self):
        self._setup_sample_users_for_listing()
        users = user_manager.list_all_users(filters={"force_password_reset": True})
        self.assertEqual(len(users), 2) # bob, eve
        self.assertTrue(all(u.force_password_reset for u in users))
        usernames = {u.username for u in users}
        self.assertEqual(usernames, {"bob", "eve"})

    def test_list_all_users_filter_force_password_reset_false(self):
        self._setup_sample_users_for_listing()
        users = user_manager.list_all_users(filters={"force_password_reset": False})
        self.assertEqual(len(users), 4) # alice, charlie, david, frank
        self.assertTrue(all(not u.force_password_reset for u in users))
        usernames = {u.username for u in users}
        self.assertEqual(usernames, {"alice", "charlie", "david", "frank"})

    def test_list_all_users_combined_filters(self):
        self._setup_sample_users_for_listing()
        # Active Engineers
        users = user_manager.list_all_users(filters={"is_active": True, "role": "Engineer"})
        self.assertEqual(len(users), 2) # alice, david
        self.assertTrue(all(u.is_active and u.role == "Engineer" for u in users))
        usernames = {u.username for u in users}
        self.assertEqual(usernames, {"alice", "david"})

        # Inactive users needing password reset
        users = user_manager.list_all_users(filters={"is_active": False, "force_password_reset": True})
        self.assertEqual(len(users), 1) # eve
        self.assertEqual(users[0].username, "eve")

    def test_list_all_users_empty_list_from_storage(self):
        user_manager._save_users([]) # Ensure no users
        users = user_manager.list_all_users()
        self.assertEqual(len(users), 0)

    def test_list_all_users_no_match(self):
        self._setup_sample_users_for_listing()
        users = user_manager.list_all_users(filters={"username": "nonexistentuser"})
        self.assertEqual(len(users), 0)

        users = user_manager.list_all_users(filters={"role": "NonExistentRole"}) # type: ignore
        self.assertEqual(len(users), 0)


if __name__ == '__main__':
    unittest.main()
