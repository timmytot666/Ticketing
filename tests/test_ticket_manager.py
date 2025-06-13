import unittest
import json
import os
import shutil # For robustly removing test_tickets.json if it's a directory by mistake
from datetime import datetime, timezone
from unittest.mock import patch, MagicMock

# Assuming models.py is in the parent directory or accessible via PYTHONPATH
from models import Ticket

# Import functions from ticket_manager
# Assuming ticket_manager.py is in the parent directory or accessible via PYTHONPATH
import ticket_manager

# Global for this test module
TEST_TICKETS_FILE = "test_tickets.json"

class TestTicketManager(unittest.TestCase):

    def setUp(self):
        """Set up for test methods."""
        # Ensure ticket_manager uses the test file
        self.patcher = patch('ticket_manager.TICKETS_FILE', TEST_TICKETS_FILE)
        self.mock_tickets_file = self.patcher.start()

        # Clean up any existing test file before each test
        if os.path.exists(TEST_TICKETS_FILE):
            if os.path.isdir(TEST_TICKETS_FILE): # Should not happen, but good to be safe
                 shutil.rmtree(TEST_TICKETS_FILE)
            else:
                os.remove(TEST_TICKETS_FILE)

    def tearDown(self):
        """Tear down after test methods."""
        self.patcher.stop() # Stop patching
        # Clean up the test file after each test
        if os.path.exists(TEST_TICKETS_FILE):
            if os.path.isdir(TEST_TICKETS_FILE):
                 shutil.rmtree(TEST_TICKETS_FILE)
            else:
                os.remove(TEST_TICKETS_FILE)

    def test_load_tickets_file_not_exist(self):
        """Test _load_tickets when the tickets file does not exist."""
        self.assertEqual(ticket_manager._load_tickets(), [])

    def test_load_tickets_empty_file(self):
        """Test _load_tickets when the tickets file is empty."""
        with open(TEST_TICKETS_FILE, 'w') as f:
            f.write("") # Create an empty file
        self.assertEqual(ticket_manager._load_tickets(), [])

    def test_load_tickets_invalid_json(self):
        """Test _load_tickets when the tickets file contains invalid JSON."""
        with open(TEST_TICKETS_FILE, 'w') as f:
            f.write("{invalid_json_") # Write malformed JSON
        # Capture print output to check error message (optional)
        with patch('builtins.print') as mock_print:
            loaded_tickets = ticket_manager._load_tickets()
            self.assertEqual(loaded_tickets, [])
            mock_print.assert_any_call(f"Error: Could not decode JSON from {TEST_TICKETS_FILE}. Returning empty list.")


    def test_save_and_load_tickets(self):
        """Test saving tickets with _save_tickets and then loading with _load_tickets."""
        ticket1_data = {
            "title": "Save Test 1", "description": "Desc 1",
            "type": "IT", "requester_email": "save1@example.com"
        }
        ticket2_data = {
            "title": "Save Test 2", "description": "Desc 2",
            "type": "Facilities", "requester_email": "save2@example.com", "priority": "High"
        }

        ticket1 = Ticket(**ticket1_data)
        ticket2 = Ticket(**ticket2_data)

        # Manually set dynamic fields for predictable comparison after loading
        # This makes comparison much simpler than trying to mock datetime.now precisely everywhere
        # For this test, we can set them to known values *before* saving.
        # When Ticket.from_dict reconstructs them, they will be identical.
        ts1 = datetime(2023, 1, 1, 10, 0, 0, tzinfo=timezone.utc)
        ts2 = datetime(2023, 1, 1, 11, 0, 0, tzinfo=timezone.utc)
        ticket1.id, ticket1.created_at, ticket1.updated_at = "id_save1", ts1, ts1
        ticket2.id, ticket2.created_at, ticket2.updated_at = "id_save2", ts2, ts2

        tickets_to_save = [ticket1, ticket2]
        ticket_manager._save_tickets(tickets_to_save)

        loaded_tickets = ticket_manager._load_tickets()
        self.assertEqual(len(loaded_tickets), 2)

        # Compare based on to_dict() for simplicity if order is not guaranteed
        # or field by field if order is guaranteed (json.dump preserves order of list)
        loaded_ids = {t.id for t in loaded_tickets}
        self.assertIn(ticket1.id, loaded_ids)
        self.assertIn(ticket2.id, loaded_ids)

        for loaded_ticket in loaded_tickets:
            original_ticket = ticket1 if loaded_ticket.id == ticket1.id else ticket2
            self.assertEqual(loaded_ticket.title, original_ticket.title)
            self.assertEqual(loaded_ticket.description, original_ticket.description)
            self.assertEqual(loaded_ticket.type, original_ticket.type)
            self.assertEqual(loaded_ticket.requester_email, original_ticket.requester_email)
            self.assertEqual(loaded_ticket.status, original_ticket.status)
            self.assertEqual(loaded_ticket.priority, original_ticket.priority)
            self.assertEqual(loaded_ticket.created_at, original_ticket.created_at)
            self.assertEqual(loaded_ticket.updated_at, original_ticket.updated_at)


    def test_create_ticket_success(self):
        """Test successful ticket creation."""
        with patch('uuid.uuid4') as mock_uuid:
            mock_uuid.return_value.hex = "test_id_create_success"
            created_ticket = ticket_manager.create_ticket(
                title="New PC Setup",
                description="Setup new PC for intern.",
                type="IT",
                requester_email="intern_setup@example.com",
                priority="Low"
            )

        self.assertIsInstance(created_ticket, Ticket)
        self.assertEqual(created_ticket.title, "New PC Setup")
        self.assertEqual(created_ticket.id, "test_id_create_success")

        loaded_tickets = ticket_manager._load_tickets()
        self.assertEqual(len(loaded_tickets), 1)
        self.assertEqual(loaded_tickets[0].id, created_ticket.id)
        self.assertEqual(loaded_tickets[0].title, "New PC Setup")

    def test_create_ticket_validation_errors(self):
        """Test create_ticket with various validation errors from ticket_manager and Ticket model."""
        with self.assertRaisesRegex(ValueError, "Title is required and must be a non-empty string."):
            ticket_manager.create_ticket("", "Desc", "IT", "user@example.com")

        with self.assertRaisesRegex(ValueError, "Description is required and must be a non-empty string."):
            ticket_manager.create_ticket("Title", "", "IT", "user@example.com")

        with self.assertRaisesRegex(ValueError, "Requester email must contain an '@' symbol."):
            ticket_manager.create_ticket("Title", "Desc", "IT", "userexample.com")

        # This one comes from the Ticket model via create_ticket
        with self.assertRaisesRegex(ValueError, "Type must be 'IT' or 'Facilities'"):
            ticket_manager.create_ticket("Title", "Desc", "WRONG_TYPE", "user@example.com")

        # Ensure no tickets were saved due to errors
        self.assertEqual(ticket_manager._load_tickets(), [])


    def test_get_ticket_found(self):
        """Test get_ticket when the ticket exists."""
        ticket = ticket_manager.create_ticket("Find Me", "Desc", "Facilities", "find@example.com")
        found_ticket = ticket_manager.get_ticket(ticket.id)
        self.assertIsNotNone(found_ticket)
        self.assertEqual(found_ticket.id, ticket.id)
        self.assertEqual(found_ticket.title, "Find Me")

    def test_get_ticket_not_found(self):
        """Test get_ticket when the ticket does not exist."""
        ticket_manager.create_ticket("Another Ticket", "Desc", "IT", "another@example.com")
        found_ticket = ticket_manager.get_ticket("non_existent_id")
        self.assertIsNone(found_ticket)

    def test_update_ticket_success(self):
        """Test successful ticket update."""
        initial_ticket = ticket_manager.create_ticket(
            "Initial Title", "Initial Desc", "IT", "update@example.com", "Medium"
        )
        initial_created_at = initial_ticket.created_at
        initial_updated_at = initial_ticket.updated_at

        # Make sure some time passes for updated_at to be different
        # A more robust way would be to mock datetime.now used in update_ticket
        # For now, a small sleep or assuming execution time difference is usually enough
        # import time; time.sleep(0.001)

        update_data = {"title": "Updated Title", "status": "In Progress", "priority": "High"}

        with patch('ticket_manager.datetime') as mock_datetime:
            # Mock datetime.now() within the scope of update_ticket call
            # Ensure it's the one from datetime module imported in ticket_manager
            mock_now = datetime.now(timezone.utc) # Use a fixed "now"
            mock_datetime.now.return_value = mock_now

            updated_ticket = ticket_manager.update_ticket(initial_ticket.id, **update_data)

        self.assertIsNotNone(updated_ticket)
        self.assertEqual(updated_ticket.id, initial_ticket.id)
        self.assertEqual(updated_ticket.title, "Updated Title")
        self.assertEqual(updated_ticket.status, "In Progress")
        self.assertEqual(updated_ticket.priority, "High")
        self.assertEqual(updated_ticket.description, "Initial Desc") # Unchanged

        self.assertEqual(updated_ticket.created_at, initial_created_at) # Should not change
        self.assertEqual(updated_ticket.updated_at, mock_now) # Should be the mocked time
        self.assertNotEqual(updated_ticket.updated_at, initial_updated_at) # Verify it changed


        # Verify persistence
        reloaded_ticket = ticket_manager.get_ticket(initial_ticket.id)
        self.assertIsNotNone(reloaded_ticket)
        self.assertEqual(reloaded_ticket.title, "Updated Title")
        self.assertEqual(reloaded_ticket.updated_at, mock_now)


    def test_update_ticket_not_found(self):
        """Test updating a non-existent ticket."""
        updated_ticket = ticket_manager.update_ticket("non_existent_id", title="New Title")
        self.assertIsNone(updated_ticket)

    def test_update_ticket_validation_errors(self):
        """Test update_ticket with invalid data."""
        ticket = ticket_manager.create_ticket("Valid Ticket", "Desc", "IT", "valid@example.com")

        with self.assertRaisesRegex(ValueError, "Status must be a string and 'Open', 'In Progress', or 'Closed'."):
            ticket_manager.update_ticket(ticket.id, status="InvalidStatus")

        with self.assertRaisesRegex(ValueError, "Priority must be a string and 'Low', 'Medium', or 'High'."):
            ticket_manager.update_ticket(ticket.id, priority=123) # Not a string

        with self.assertRaisesRegex(ValueError, "Title cannot be empty."):
            ticket_manager.update_ticket(ticket.id, title="")

        # Check that the ticket was not actually updated with invalid data
        reloaded_ticket = ticket_manager.get_ticket(ticket.id)
        self.assertEqual(reloaded_ticket.status, "Open") # Should remain original
        self.assertEqual(reloaded_ticket.title, "Valid Ticket")


    def test_list_tickets_empty(self):
        """Test listing tickets when no tickets exist."""
        self.assertEqual(ticket_manager.list_tickets(), [])

    def test_list_tickets_all(self):
        """Test listing all tickets without filters."""
        ticket_manager.create_ticket("T1", "D1", "IT", "t1@example.com", "Low")
        ticket_manager.create_ticket("T2", "D2", "Facilities", "t2@example.com", "High", status="In Progress")

        tickets = ticket_manager.list_tickets()
        self.assertEqual(len(tickets), 2)
        # You could add more specific checks on the content if needed

    def test_list_tickets_filtered(self):
        """Test listing tickets with various filters."""
        t1 = ticket_manager.create_ticket("IT Open Low", "D1", "IT", "t1@example.com", "Low", status="Open")
        t2 = ticket_manager.create_ticket("IT Closed High", "D2", "IT", "t2@example.com", "High", status="Closed")
        t3 = ticket_manager.create_ticket("Facilities Open Low", "D3", "Facilities", "t3@example.com", "Low", status="Open")
        t4 = ticket_manager.create_ticket("IT In Progress Medium", "D4", "IT", "t4@example.com", "Medium", status="In Progress")

        # Filter by status
        open_tickets = ticket_manager.list_tickets(filters={"status": "Open"})
        self.assertEqual(len(open_tickets), 2)
        self.assertTrue(all(t.status == "Open" for t in open_tickets))
        open_ids = {t.id for t in open_tickets}
        self.assertIn(t1.id, open_ids)
        self.assertIn(t3.id, open_ids)


        # Filter by type
        it_tickets = ticket_manager.list_tickets(filters={"type": "IT"})
        self.assertEqual(len(it_tickets), 3)
        self.assertTrue(all(t.type == "IT" for t in it_tickets))

        # Filter by priority
        low_priority_tickets = ticket_manager.list_tickets(filters={"priority": "Low"})
        self.assertEqual(len(low_priority_tickets), 2)
        self.assertTrue(all(t.priority == "Low" for t in low_priority_tickets))

        # Combined filters
        it_open_tickets = ticket_manager.list_tickets(filters={"type": "IT", "status": "Open"})
        self.assertEqual(len(it_open_tickets), 1)
        self.assertEqual(it_open_tickets[0].id, t1.id)

        # Filter resulting in empty list
        no_match_tickets = ticket_manager.list_tickets(filters={"type": "Facilities", "priority": "High"})
        self.assertEqual(len(no_match_tickets), 0)

if __name__ == '__main__':
    unittest.main()
