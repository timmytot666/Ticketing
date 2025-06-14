import unittest
import uuid
from datetime import datetime, timezone
from typing import List # Required for Ticket.comments
from models import Ticket, User, Notification # Import new models

# It's good practice to ensure werkzeug is available if User model relies on it.
# Models.py has a fallback, but tests for hashing should ideally use real hashing.
try:
    from werkzeug.security import generate_password_hash, check_password_hash
    WERKZEUG_AVAILABLE = True
except ImportError:
    WERKZEUG_AVAILABLE = False
    # Use the placeholder functions from models.py if werkzeug is not installed
    from models import generate_password_hash, check_password_hash


class TestUserModel(unittest.TestCase):
    def test_user_creation_success(self):
        user = User(username="testuser", role="EndUser")
        user.set_password("password123")

        self.assertIsInstance(user.user_id, str)
        self.assertEqual(user.username, "testuser")
        self.assertEqual(user.role, "EndUser")
        self.assertIsNotNone(user.password_hash)
        self.assertTrue(user.is_active) # Default
        self.assertFalse(user.force_password_reset) # Default
        self.assertTrue(user.check_password("password123"))
        self.assertFalse(user.check_password("wrongpassword"))

    def test_user_creation_with_active_reset_flags(self):
        user1 = User(username="activeuser", role="EndUser", is_active=True, force_password_reset=False)
        self.assertTrue(user1.is_active)
        self.assertFalse(user1.force_password_reset)

        user2 = User(username="inactiveuser", role="Technician", is_active=False, force_password_reset=True)
        self.assertFalse(user2.is_active)
        self.assertTrue(user2.force_password_reset)

    def test_user_creation_invalid_username(self):
        with self.assertRaisesRegex(ValueError, "Username cannot be empty."):
            User(username="", role="EndUser")

    def test_user_creation_invalid_role(self):
        with self.assertRaisesRegex(ValueError, "Invalid role: Guest."):
            User(username="testuser", role="Guest") # type: ignore

    def test_user_set_empty_password(self):
        user = User(username="testuser", role="Technician")
        with self.assertRaisesRegex(ValueError, "Password cannot be empty."):
            user.set_password("")

    def test_user_check_password_no_password_set(self):
        user = User(username="nouser", role="EndUser") # Password not set
        self.assertFalse(user.check_password("anypassword"))

    def test_user_check_password_empty_password_to_check(self):
        user = User(username="testuser", role="Engineer")
        user.set_password("securepass")
        self.assertFalse(user.check_password(""))


    def test_user_to_dict_from_dict_roundtrip(self):
        original_user = User(username="dictuser", role="TechManager", is_active=False, force_password_reset=True)
        original_user.set_password("dictpass")
        original_user.user_id = "fixed_user_id_for_dict_test" # Fixed for predictability

        user_dict = original_user.to_dict()

        expected_dict = {
            "user_id": "fixed_user_id_for_dict_test",
            "username": "dictuser",
            "password_hash": original_user.password_hash,
            "role": "TechManager",
            "is_active": False,
            "force_password_reset": True
        }
        self.assertEqual(user_dict, expected_dict)

        reconstructed_user = User.from_dict(user_dict)
        self.assertEqual(reconstructed_user.user_id, original_user.user_id)
        self.assertEqual(reconstructed_user.username, original_user.username)
        self.assertEqual(reconstructed_user.role, original_user.role)
        self.assertEqual(reconstructed_user.password_hash, original_user.password_hash)
        self.assertEqual(reconstructed_user.is_active, False)
        self.assertEqual(reconstructed_user.force_password_reset, True)

        # Check password still works after reconstruction
        self.assertTrue(reconstructed_user.check_password("dictpass"))
        self.assertFalse(reconstructed_user.check_password("wrongpass"))

    def test_user_from_dict_defaults_for_missing_flags(self):
        # Data that might come from an older version without the new flags
        old_user_data = {
            "user_id": "old_user_id",
            "username": "olduser",
            "password_hash": generate_password_hash("oldpass"),
            "role": "EndUser"
        }
        reconstructed_user = User.from_dict(old_user_data)
        self.assertEqual(reconstructed_user.username, "olduser")
        self.assertTrue(reconstructed_user.is_active) # Should default to True
        self.assertFalse(reconstructed_user.force_password_reset) # Should default to False

class TestNotificationModel(unittest.TestCase):
    def test_notification_creation_success(self):
        now = datetime.now(timezone.utc)
        notification = Notification(
            user_id="user123",
            message="Test notification message",
            ticket_id="ticket_abc"
        )
        self.assertIsInstance(notification.notification_id, str)
        self.assertEqual(notification.user_id, "user123")
        self.assertEqual(notification.message, "Test notification message")
        self.assertEqual(notification.ticket_id, "ticket_abc")
        self.assertIsInstance(notification.timestamp, datetime)
        self.assertGreaterEqual(notification.timestamp, now)
        self.assertFalse(notification.is_read)

    def test_notification_creation_defaults(self):
        notification = Notification(user_id="user456", message="Another message")
        self.assertIsNotNone(notification.notification_id)
        self.assertIsNone(notification.ticket_id) # Default
        self.assertIsNotNone(notification.timestamp) # Default
        self.assertFalse(notification.is_read) # Default

    def test_notification_creation_invalid_user_id(self):
        with self.assertRaisesRegex(ValueError, "User ID cannot be empty for a notification."):
            Notification(user_id="", message="Test message")

    def test_notification_creation_invalid_message(self):
        with self.assertRaisesRegex(ValueError, "Notification message cannot be empty."):
            Notification(user_id="user123", message="")

    def test_notification_to_dict_from_dict_roundtrip(self):
        ts = datetime(2023, 10, 26, 12, 0, 0, tzinfo=timezone.utc)
        original_notification = Notification(
            user_id="user_dict_test",
            message="Notification for dict test",
            ticket_id="t_dict_123",
            notification_id="notif_fixed_id", # Fixed for predictability
            timestamp=ts,
            is_read=True
        )

        notif_dict = original_notification.to_dict()
        expected_dict = {
            "notification_id": "notif_fixed_id",
            "user_id": "user_dict_test",
            "ticket_id": "t_dict_123",
            "message": "Notification for dict test",
            "timestamp": ts.isoformat(),
            "is_read": True
        }
        self.assertEqual(notif_dict, expected_dict)

        reconstructed_notification = Notification.from_dict(notif_dict)
        self.assertEqual(reconstructed_notification.notification_id, original_notification.notification_id)
        self.assertEqual(reconstructed_notification.user_id, original_notification.user_id)
        self.assertEqual(reconstructed_notification.ticket_id, original_notification.ticket_id)
        self.assertEqual(reconstructed_notification.message, original_notification.message)
        self.assertEqual(reconstructed_notification.timestamp, original_notification.timestamp)
        self.assertEqual(reconstructed_notification.is_read, original_notification.is_read)


class TestTicketModel(unittest.TestCase):
    # Dummy user IDs for testing
    DUMMY_REQUESTER_USER_ID = "requester_user_001"
    DUMMY_CREATED_BY_USER_ID = "creator_user_002"
    DUMMY_ASSIGNEE_USER_ID = "assignee_user_003"

    def test_ticket_creation_success(self):
        now = datetime.now(timezone.utc)
        ticket = Ticket(
            title="Network Outage",
            description="The entire 3rd floor is offline.",
            type="IT",
            requester_user_id=self.DUMMY_REQUESTER_USER_ID, # Changed
            created_by_user_id=self.DUMMY_CREATED_BY_USER_ID, # Added
            status="Open",
            priority="High",
            assignee_user_id=self.DUMMY_ASSIGNEE_USER_ID, # Added
            comments=[] # Added
        )
        self.assertIsInstance(ticket.id, str)
        self.assertEqual(ticket.title, "Network Outage")
        self.assertEqual(ticket.requester_user_id, self.DUMMY_REQUESTER_USER_ID) # Changed
        self.assertEqual(ticket.created_by_user_id, self.DUMMY_CREATED_BY_USER_ID) # Added
        self.assertEqual(ticket.assignee_user_id, self.DUMMY_ASSIGNEE_USER_ID) # Added
        self.assertEqual(ticket.comments, []) # Added
        self.assertGreaterEqual(ticket.created_at, now)

    def test_ticket_creation_defaults(self):
        ticket = Ticket(
            title="Printer Issue",
            description="Printer on 2nd floor not working.",
            type="Facilities",
            requester_user_id=self.DUMMY_REQUESTER_USER_ID, # Changed
            created_by_user_id=self.DUMMY_CREATED_BY_USER_ID # Added
        )
        self.assertEqual(ticket.status, "Open") # Default
        self.assertEqual(ticket.priority, "Medium") # Default
        self.assertIsNone(ticket.assignee_user_id) # Default
        self.assertEqual(ticket.comments, []) # Default

    def test_ticket_creation_invalid_requester_user_id(self): # New test
        with self.assertRaisesRegex(ValueError, "Requester User ID cannot be empty"):
            Ticket("Title", "Desc", "IT", "", self.DUMMY_CREATED_BY_USER_ID)

    def test_ticket_creation_invalid_created_by_user_id(self): # New test
        with self.assertRaisesRegex(ValueError, "Created By User ID cannot be empty"):
            Ticket("Title", "Desc", "IT", self.DUMMY_REQUESTER_USER_ID, "")

    # Existing tests for title, description, type, status, priority remain largely the same
    # but need to include the new mandatory fields in Ticket creation
    def test_ticket_creation_invalid_type(self):
        with self.assertRaisesRegex(ValueError, "Type must be 'IT' or 'Facilities'"):
            Ticket("Test", "Test desc", "Billing", self.DUMMY_REQUESTER_USER_ID, self.DUMMY_CREATED_BY_USER_ID)

    def test_ticket_creation_empty_title(self):
        with self.assertRaisesRegex(ValueError, "Title cannot be empty"):
            Ticket("", "Description", "IT", self.DUMMY_REQUESTER_USER_ID, self.DUMMY_CREATED_BY_USER_ID)

    def test_id_auto_generation(self):
        ticket1 = Ticket("T1", "D1", "IT", self.DUMMY_REQUESTER_USER_ID, self.DUMMY_CREATED_BY_USER_ID)
        ticket2 = Ticket("T2", "D2", "Facilities", self.DUMMY_REQUESTER_USER_ID, self.DUMMY_CREATED_BY_USER_ID)
        self.assertNotEqual(ticket1.id, ticket2.id)

    def test_add_comment(self): # New test for comments
        ticket = Ticket("Comment Test", "Testing add_comment", "IT",
                        self.DUMMY_REQUESTER_USER_ID, self.DUMMY_CREATED_BY_USER_ID)
        initial_updated_at = ticket.updated_at

        # Allow a moment for timestamp to potentially change if not mocking datetime.now
        # import time; time.sleep(0.001)

        ticket.add_comment(user_id="commenter_001", text="This is the first comment.")
        self.assertEqual(len(ticket.comments), 1)
        comment1 = ticket.comments[0]
        self.assertEqual(comment1["user_id"], "commenter_001")
        self.assertEqual(comment1["text"], "This is the first comment.")
        self.assertIsInstance(comment1["timestamp"], str) # ISO Format
        self.assertNotEqual(ticket.updated_at, initial_updated_at) # updated_at should change

        initial_updated_at = ticket.updated_at # Reset for next check
        # import time; time.sleep(0.001)
        ticket.add_comment(user_id="commenter_002", text="Another comment.")
        self.assertEqual(len(ticket.comments), 2)
        self.assertNotEqual(ticket.updated_at, initial_updated_at)

    def test_to_dict_conversion(self):
        created_time = datetime.now(timezone.utc)
        ticket = Ticket(
            title="Dict Test", description="Testing to_dict", type="IT",
            requester_user_id=self.DUMMY_REQUESTER_USER_ID,
            created_by_user_id=self.DUMMY_CREATED_BY_USER_ID,
            assignee_user_id=self.DUMMY_ASSIGNEE_USER_ID,
            comments=[{"user_id": "u1", "timestamp": created_time.isoformat(), "text": "Hi"}]
        )
        ticket.created_at = created_time # Control timestamps for exact match
        ticket.updated_at = created_time

        ticket_dict = ticket.to_dict()
        expected_dict = {
            'id': ticket.id,
            'title': "Dict Test",
            'description': "Testing to_dict",
            'type': "IT",
            'status': "Open", # Default
            'priority': "Medium", # Default
            'requester_user_id': self.DUMMY_REQUESTER_USER_ID,
            'created_by_user_id': self.DUMMY_CREATED_BY_USER_ID,
            'assignee_user_id': self.DUMMY_ASSIGNEE_USER_ID,
            'comments': [{"user_id": "u1", "timestamp": created_time.isoformat(), "text": "Hi"}],
            'created_at': created_time.isoformat(),
            'updated_at': created_time.isoformat(),
        }
        self.assertEqual(ticket_dict, expected_dict)

    def test_from_dict_conversion(self):
        created_iso = datetime.now(timezone.utc).isoformat()
        ticket_data = {
            'id': uuid.uuid4().hex,
            'title': "From Dict Test",
            'description': "Testing from_dict",
            'type': "Facilities",
            'requester_user_id': self.DUMMY_REQUESTER_USER_ID, # Changed
            'created_by_user_id': self.DUMMY_CREATED_BY_USER_ID, # Added
            'assignee_user_id': self.DUMMY_ASSIGNEE_USER_ID, # Added
            'comments': [{"user_id": "u2", "timestamp": created_iso, "text": "Test comment"}], # Added
            'status': "In Progress",
            'priority': "Low",
            'created_at': created_iso,
            'updated_at': created_iso,
        }
        ticket = Ticket.from_dict(ticket_data)

        self.assertEqual(ticket.id, ticket_data['id'])
        self.assertEqual(ticket.title, ticket_data['title'])
        self.assertEqual(ticket.requester_user_id, ticket_data['requester_user_id']) # Changed
        self.assertEqual(ticket.created_by_user_id, ticket_data['created_by_user_id']) # Added
        self.assertEqual(ticket.assignee_user_id, ticket_data['assignee_user_id']) # Added
        self.assertEqual(len(ticket.comments), 1)
        self.assertEqual(ticket.comments[0]['text'], "Test comment")


if __name__ == '__main__':
    unittest.main()
