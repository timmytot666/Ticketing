import unittest
import json
import os
import shutil
from datetime import datetime, timezone, timedelta
from unittest.mock import patch

from models import Notification # Assuming models.py is accessible
import notification_manager # Assuming notification_manager.py is accessible

# Global for this test module
TEST_NOTIFICATIONS_FILE = "test_notifications.json"

class TestNotificationManager(unittest.TestCase):

    USER_ID_1 = "user_test_1"
    USER_ID_2 = "user_test_2"
    TICKET_ID_1 = "ticket_test_1"

    def setUp(self):
        """Set up for test methods."""
        self.patcher = patch('notification_manager.NOTIFICATIONS_FILE', TEST_NOTIFICATIONS_FILE)
        self.mock_notifications_file = self.patcher.start()

        if os.path.exists(TEST_NOTIFICATIONS_FILE):
            if os.path.isdir(TEST_NOTIFICATIONS_FILE): # Should not happen
                 shutil.rmtree(TEST_NOTIFICATIONS_FILE)
            else:
                os.remove(TEST_NOTIFICATIONS_FILE)

    def tearDown(self):
        """Tear down after test methods."""
        self.patcher.stop()
        if os.path.exists(TEST_NOTIFICATIONS_FILE):
            if os.path.isdir(TEST_NOTIFICATIONS_FILE):
                 shutil.rmtree(TEST_NOTIFICATIONS_FILE)
            else:
                os.remove(TEST_NOTIFICATIONS_FILE)

    def test_load_notifications_file_not_exist(self):
        self.assertEqual(notification_manager._load_notifications(), [])

    def test_load_notifications_empty_file(self):
        with open(TEST_NOTIFICATIONS_FILE, 'w') as f:
            f.write("")
        self.assertEqual(notification_manager._load_notifications(), [])

    def test_load_notifications_invalid_json(self):
        with open(TEST_NOTIFICATIONS_FILE, 'w') as f:
            f.write("{invalid_json_")
        # notification_manager prints error message to console
        with patch('builtins.print') as mock_print:
            self.assertEqual(notification_manager._load_notifications(), [])
            mock_print.assert_any_call(f"Error: Could not decode JSON from {TEST_NOTIFICATIONS_FILE}. Returning empty list.")

    def test_save_and_load_notifications(self):
        ts1 = datetime.now(timezone.utc) - timedelta(minutes=10)
        ts2 = datetime.now(timezone.utc)

        # Create Notification instances directly for saving
        notif1 = Notification(user_id=self.USER_ID_1, message="MSG1", ticket_id=self.TICKET_ID_1, timestamp=ts1)
        notif1.notification_id = "fixed_notif_id_1" # For predictable testing
        notif2 = Notification(user_id=self.USER_ID_2, message="MSG2", timestamp=ts2, is_read=True)
        notif2.notification_id = "fixed_notif_id_2"

        notifications_to_save = [notif1, notif2]
        notification_manager._save_notifications(notifications_to_save)

        loaded_notifications = notification_manager._load_notifications()
        self.assertEqual(len(loaded_notifications), 2)

        loaded_ids = {n.notification_id for n in loaded_notifications}
        self.assertIn(notif1.notification_id, loaded_ids)
        self.assertIn(notif2.notification_id, loaded_ids)

        # Verify details
        loaded_notif1 = next(n for n in loaded_notifications if n.notification_id == notif1.notification_id)
        self.assertEqual(loaded_notif1.message, "MSG1")
        self.assertEqual(loaded_notif1.timestamp, ts1)
        self.assertFalse(loaded_notif1.is_read)


    def test_create_notification_success(self):
        created_notif = notification_manager.create_notification(
            user_id=self.USER_ID_1,
            message="Your ticket has been updated.",
            ticket_id=self.TICKET_ID_1
        )
        self.assertIsInstance(created_notif, Notification)
        self.assertEqual(created_notif.user_id, self.USER_ID_1)
        self.assertEqual(created_notif.message, "Your ticket has been updated.")
        self.assertEqual(created_notif.ticket_id, self.TICKET_ID_1)
        self.assertFalse(created_notif.is_read)

        loaded_notifications = notification_manager._load_notifications()
        self.assertEqual(len(loaded_notifications), 1)
        self.assertEqual(loaded_notifications[0].notification_id, created_notif.notification_id)

    def test_create_notification_validation_error(self):
        with self.assertRaisesRegex(ValueError, "User ID cannot be empty"):
            notification_manager.create_notification(user_id="", message="Test")
        with self.assertRaisesRegex(ValueError, "Notification message cannot be empty"):
            notification_manager.create_notification(user_id=self.USER_ID_1, message="")


    def test_get_notifications_for_user(self):
        # Create some notifications with controlled timestamps for sorting verification
        now = datetime.now(timezone.utc)
        n1 = notification_manager.create_notification(self.USER_ID_1, "Old message", self.TICKET_ID_1)
        n1.timestamp = now - timedelta(hours=1) # Manually adjust for test
        n2 = notification_manager.create_notification(self.USER_ID_1, "New message", self.TICKET_ID_1)
        n2.timestamp = now
        n3 = notification_manager.create_notification(self.USER_ID_1, "Unread message", self.TICKET_ID_1)
        n3.timestamp = now - timedelta(minutes=30)
        n4 = notification_manager.create_notification(self.USER_ID_2, "Other user message") # Different user

        # Manually mark one as read for testing unread_only
        n1.is_read = True
        notification_manager._save_notifications([n1, n2, n3, n4]) # Resave with modifications

        # Test get all for USER_ID_1
        user1_notifs = notification_manager.get_notifications_for_user(self.USER_ID_1)
        self.assertEqual(len(user1_notifs), 3)
        # Check sorting (n2 newest, then n3, then n1)
        self.assertEqual(user1_notifs[0].notification_id, n2.notification_id)
        self.assertEqual(user1_notifs[1].notification_id, n3.notification_id)
        self.assertEqual(user1_notifs[2].notification_id, n1.notification_id)

        # Test unread_only for USER_ID_1
        user1_unread_notifs = notification_manager.get_notifications_for_user(self.USER_ID_1, unread_only=True)
        self.assertEqual(len(user1_unread_notifs), 2)
        unread_ids = {n.notification_id for n in user1_unread_notifs}
        self.assertIn(n2.notification_id, unread_ids)
        self.assertIn(n3.notification_id, unread_ids)
        self.assertNotIn(n1.notification_id, unread_ids) # n1 is read

        # Test for USER_ID_2
        user2_notifs = notification_manager.get_notifications_for_user(self.USER_ID_2)
        self.assertEqual(len(user2_notifs), 1)
        self.assertEqual(user2_notifs[0].notification_id, n4.notification_id)

        # Test for user with no notifications
        self.assertEqual(notification_manager.get_notifications_for_user("non_existent_user"), [])


    def test_get_notification_by_id(self):
        notif = notification_manager.create_notification(self.USER_ID_1, "Find this notification")

        found_notif = notification_manager.get_notification_by_id(notif.notification_id)
        self.assertIsNotNone(found_notif)
        self.assertEqual(found_notif.notification_id, notif.notification_id)

        not_found_notif = notification_manager.get_notification_by_id("non_existent_notif_id")
        self.assertIsNone(not_found_notif)

        self.assertIsNone(notification_manager.get_notification_by_id(""), "Empty ID should return None")


    def test_mark_notification_as_read(self):
        notif = notification_manager.create_notification(self.USER_ID_1, "Mark me as read")
        self.assertFalse(notif.is_read)

        # Mark as read
        result = notification_manager.mark_notification_as_read(notif.notification_id)
        self.assertTrue(result)

        updated_notif = notification_manager.get_notification_by_id(notif.notification_id)
        self.assertIsNotNone(updated_notif)
        self.assertTrue(updated_notif.is_read)

        # Try to mark already read notification
        result_already_read = notification_manager.mark_notification_as_read(notif.notification_id)
        self.assertFalse(result_already_read, "Should return False if already read")

        # Try to mark non-existent notification
        result_not_found = notification_manager.mark_notification_as_read("non_existent_id")
        self.assertFalse(result_not_found, "Should return False if not found")

        self.assertFalse(notification_manager.mark_notification_as_read(""), "Empty ID should return False")

    def test_mark_multiple_notifications_as_read(self):
        n1 = notification_manager.create_notification(self.USER_ID_1, "Multi 1") # unread
        n2 = notification_manager.create_notification(self.USER_ID_1, "Multi 2") # unread
        n3 = notification_manager.create_notification(self.USER_ID_1, "Multi 3", ticket_id=self.TICKET_ID_1) # unread
        n4_read = notification_manager.create_notification(self.USER_ID_1, "Multi 4 Read")
        n4_read.is_read = True # Mark one as already read
        notification_manager._save_notifications([n1, n2, n3, n4_read])


        ids_to_mark = [n1.notification_id, n3.notification_id, "non_existent_id", n4_read.notification_id]

        marked_count = notification_manager.mark_multiple_notifications_as_read(ids_to_mark)
        self.assertEqual(marked_count, 2, "Should only count n1 and n3 as newly marked read")

        # Verify n1 and n3 are read
        self.assertTrue(notification_manager.get_notification_by_id(n1.notification_id).is_read)
        self.assertTrue(notification_manager.get_notification_by_id(n3.notification_id).is_read)
        # Verify n2 is still unread
        self.assertFalse(notification_manager.get_notification_by_id(n2.notification_id).is_read)
        # Verify n4_read is still read
        self.assertTrue(notification_manager.get_notification_by_id(n4_read.notification_id).is_read)

        # Test with empty list
        self.assertEqual(notification_manager.mark_multiple_notifications_as_read([]), 0)


if __name__ == '__main__':
    unittest.main()
