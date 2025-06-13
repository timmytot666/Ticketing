import unittest
import uuid
from datetime import datetime, timezone
from models import Ticket

class TestTicketModel(unittest.TestCase):

    def test_ticket_creation_success(self):
        """Test successful Ticket creation with valid data."""
        now = datetime.now(timezone.utc)
        ticket = Ticket(
            title="Network Outage",
            description="The entire 3rd floor is offline.",
            type="IT",
            requester_email="user@example.com",
            status="Open",
            priority="High"
        )
        self.assertIsInstance(ticket.id, str)
        self.assertEqual(len(ticket.id), 32) # UUID4 hex length
        self.assertEqual(ticket.title, "Network Outage")
        self.assertEqual(ticket.description, "The entire 3rd floor is offline.")
        self.assertEqual(ticket.type, "IT")
        self.assertEqual(ticket.requester_email, "user@example.com")
        self.assertEqual(ticket.status, "Open")
        self.assertEqual(ticket.priority, "High")
        self.assertIsInstance(ticket.created_at, datetime)
        self.assertIsInstance(ticket.updated_at, datetime)
        self.assertGreaterEqual(ticket.created_at, now)
        self.assertGreaterEqual(ticket.updated_at, now)
        self.assertEqual(ticket.created_at, ticket.updated_at)

    def test_ticket_creation_defaults(self):
        """Test Ticket creation with default status and priority."""
        ticket = Ticket(
            title="Printer Issue",
            description="Printer on 2nd floor not working.",
            type="Facilities",
            requester_email="another@example.com"
        )
        self.assertEqual(ticket.status, "Open")
        self.assertEqual(ticket.priority, "Medium")

    def test_ticket_creation_invalid_type(self):
        with self.assertRaisesRegex(ValueError, "Type must be 'IT' or 'Facilities'"):
            Ticket("Test", "Test desc", "Billing", "user@example.com")

    def test_ticket_creation_invalid_status(self):
        with self.assertRaisesRegex(ValueError, "Status must be 'Open', 'In Progress', or 'Closed'"):
            Ticket("Test", "Test desc", "IT", "user@example.com", status="Pending")

    def test_ticket_creation_invalid_priority(self):
        with self.assertRaisesRegex(ValueError, "Priority must be 'Low', 'Medium', or 'High'"):
            Ticket("Test", "Test desc", "IT", "user@example.com", priority="Urgent")

    def test_ticket_creation_empty_title(self):
        with self.assertRaisesRegex(ValueError, "Title cannot be empty and must be a string."):
            Ticket("", "Description", "IT", "user@example.com")

    def test_ticket_creation_empty_description(self):
        with self.assertRaisesRegex(ValueError, "Description cannot be empty and must be a string."):
            Ticket("Title", "", "IT", "user@example.com")

    def test_ticket_creation_empty_email(self):
        with self.assertRaisesRegex(ValueError, "Requester email cannot be empty and must be a string."):
            Ticket("Title", "Description", "IT", "")

    def test_ticket_creation_invalid_email_format(self):
        with self.assertRaisesRegex(ValueError, "Requester email must contain an '@' symbol."):
            Ticket("Title", "Description", "IT", "userexample.com")

    def test_id_auto_generation(self):
        """Test that IDs are auto-generated and unique."""
        ticket1 = Ticket("T1", "D1", "IT", "t1@example.com")
        ticket2 = Ticket("T2", "D2", "Facilities", "t2@example.com")
        self.assertNotEqual(ticket1.id, ticket2.id)
        self.assertTrue(uuid.UUID(ticket1.id, version=4)) # Check if it's a valid UUID4 hex

    def test_timestamps_auto_generation(self):
        """Test that created_at and updated_at are auto-generated datetime objects."""
        ticket = Ticket("T", "D", "IT", "t@example.com")
        self.assertIsInstance(ticket.created_at, datetime)
        self.assertIsInstance(ticket.updated_at, datetime)
        # Check if they are timezone-aware (assuming UTC)
        self.assertIsNotNone(ticket.created_at.tzinfo)
        self.assertEqual(ticket.created_at.tzinfo.utcoffset(ticket.created_at), timezone.utc.utcoffset(None))

    def test_to_dict_conversion(self):
        """Test conversion of Ticket object to dictionary."""
        created_time = datetime.now(timezone.utc) # Approximate time
        ticket = Ticket("Dict Test", "Testing to_dict", "IT", "dict@example.com")
        # Manually set created_at and updated_at for predictable ISO format string
        # This is a bit of a hack; ideally, we'd mock datetime.now for precise control
        ticket.created_at = created_time
        ticket.updated_at = created_time

        ticket_dict = ticket.to_dict()

        expected_dict = {
            'id': ticket.id,
            'title': "Dict Test",
            'description': "Testing to_dict",
            'type': "IT",
            'status': "Open",
            'priority': "Medium",
            'requester_email': "dict@example.com",
            'created_at': created_time.isoformat(),
            'updated_at': created_time.isoformat(),
        }
        self.assertEqual(ticket_dict, expected_dict)
        self.assertIsInstance(ticket_dict['created_at'], str)
        self.assertIsInstance(ticket_dict['updated_at'], str)

    def test_from_dict_conversion(self):
        """Test conversion from dictionary to Ticket object."""
        created_iso = datetime.now(timezone.utc).isoformat()
        updated_iso = datetime.now(timezone.utc).isoformat() # Can be same or different

        ticket_data = {
            'id': uuid.uuid4().hex,
            'title': "From Dict Test",
            'description': "Testing from_dict",
            'type': "Facilities",
            'status': "In Progress",
            'priority': "Low",
            'requester_email': "fromdict@example.com",
            'created_at': created_iso,
            'updated_at': updated_iso,
        }
        ticket = Ticket.from_dict(ticket_data)

        self.assertEqual(ticket.id, ticket_data['id'])
        self.assertEqual(ticket.title, ticket_data['title'])
        self.assertEqual(ticket.description, ticket_data['description'])
        self.assertEqual(ticket.type, ticket_data['type'])
        self.assertEqual(ticket.status, ticket_data['status'])
        self.assertEqual(ticket.priority, ticket_data['priority'])
        self.assertEqual(ticket.requester_email, ticket_data['requester_email'])

        # Check datetime objects
        self.assertIsInstance(ticket.created_at, datetime)
        self.assertIsInstance(ticket.updated_at, datetime)
        self.assertEqual(ticket.created_at, datetime.fromisoformat(created_iso))
        self.assertEqual(ticket.updated_at, datetime.fromisoformat(updated_iso))
        self.assertIsNotNone(ticket.created_at.tzinfo) # Ensure timezone aware
        self.assertIsNotNone(ticket.updated_at.tzinfo)

    def test_to_dict_from_dict_roundtrip(self):
        """Test a full cycle of to_dict then from_dict."""
        original_ticket = Ticket(
            title="Roundtrip",
            description="Testing full conversion cycle.",
            type="IT",
            requester_email="round@trip.com",
            priority="High"
        )
        # For a precise roundtrip, especially with microsecond precision,
        # it's best to control the initial timestamps if possible, or compare field by field.
        # The default datetime.now() might have microsecond differences if to_dict and from_dict
        # are called with slight delays.

        # Overwrite with specific values for stable comparison
        original_ticket.created_at = datetime(2023, 1, 1, 12, 0, 0, tzinfo=timezone.utc)
        original_ticket.updated_at = datetime(2023, 1, 1, 12, 30, 0, tzinfo=timezone.utc)


        ticket_dict = original_ticket.to_dict()
        reconstructed_ticket = Ticket.from_dict(ticket_dict)

        self.assertEqual(original_ticket.id, reconstructed_ticket.id)
        self.assertEqual(original_ticket.title, reconstructed_ticket.title)
        self.assertEqual(original_ticket.description, reconstructed_ticket.description)
        self.assertEqual(original_ticket.type, reconstructed_ticket.type)
        self.assertEqual(original_ticket.status, reconstructed_ticket.status)
        self.assertEqual(original_ticket.priority, reconstructed_ticket.priority)
        self.assertEqual(original_ticket.requester_email, reconstructed_ticket.requester_email)
        self.assertEqual(original_ticket.created_at, reconstructed_ticket.created_at)
        self.assertEqual(original_ticket.updated_at, reconstructed_ticket.updated_at)

if __name__ == '__main__':
    unittest.main()
