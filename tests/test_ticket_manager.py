import unittest
import json
import os
import shutil
import tempfile # Added for managing temporary attachment directory
import uuid # For mocking uuid.uuid4
import mimetypes # For mocking mimetypes.guess_type
from datetime import datetime, date, time, timedelta, timezone
from unittest.mock import patch, MagicMock, call, mock_open # Added mock_open
from typing import Optional, List, Dict, Any

from models import Ticket
import ticket_manager

TEST_TICKETS_FILE = "test_tickets.json" # For main ticket data

DUMMY_REQUESTER_USER_ID = "req_user_001"
DUMMY_UPLOADER_USER_ID = "uploader_user_007"
DUMMY_COMMENTER_USER_ID = "comment_user_002"
DUMMY_ASSIGNEE_USER_ID_ORIGINAL = "assign_user_003"
DUMMY_ASSIGNEE_USER_ID_NEW = "assign_user_004"


MOCK_BUSINESS_SCHEDULE = {day: (time(9,0), time(17,0)) for day in ["monday", "tuesday", "wednesday", "thursday", "friday"]}
MOCK_BUSINESS_SCHEDULE.update({"saturday": None, "sunday": None})
MOCK_PUBLIC_HOLIDAYS = [date(2024,1,1)]
MOCK_SLA_POLICY_HIGH = {"policy_id": "sla_high", "response_time_hours": 4.0, "resolution_time_hours": 24.0}
MOCK_SLA_POLICY_MEDIUM = {"policy_id": "sla_med", "response_time_hours": 8.0, "resolution_time_hours": 48.0}


class TestTicketManagerFeatures(unittest.TestCase): # Renamed to be more general

    def setUp(self):
        self.patcher_file = patch('ticket_manager.TICKETS_FILE', TEST_TICKETS_FILE)
        self.mock_tickets_file = self.patcher_file.start()

        self.patcher_get_policy = patch('ticket_manager.get_matching_sla_policy')
        self.mock_get_policy = self.patcher_get_policy.start()
        self.patcher_get_schedule = patch('ticket_manager.get_business_schedule')
        self.mock_get_schedule = self.patcher_get_schedule.start()
        self.patcher_get_holidays = patch('ticket_manager.get_public_holidays')
        self.mock_get_holidays = self.patcher_get_holidays.start()
        self.patcher_calc_due = patch('ticket_manager.calculate_due_date')
        self.mock_calc_due = self.patcher_calc_due.start()

        self.mock_get_policy.return_value = MOCK_SLA_POLICY_MEDIUM
        self.mock_get_schedule.return_value = MOCK_BUSINESS_SCHEDULE
        self.mock_get_holidays.return_value = MOCK_PUBLIC_HOLIDAYS
        self.mock_calc_due.side_effect = lambda start, hours, sched, hols: start + timedelta(hours=hours)

        # Setup a temporary directory for attachments
        self.temp_attachment_dir_obj = tempfile.TemporaryDirectory()
        self.test_attachment_dir_path = self.temp_attachment_dir_obj.name
        self.patcher_attachment_dir = patch('ticket_manager.ATTACHMENT_DIR', self.test_attachment_dir_path)
        self.mock_attachment_dir = self.patcher_attachment_dir.start()

        # Common OS/file operation mocks for attachment tests
        self.patcher_os_path_exists = patch('ticket_manager.os.path.exists')
        self.mock_os_path_exists = self.patcher_os_path_exists.start()
        self.patcher_os_path_isfile = patch('ticket_manager.os.path.isfile') # For source_file_path check
        self.mock_os_path_isfile = self.patcher_os_path_isfile.start()
        self.patcher_os_makedirs = patch('ticket_manager.os.makedirs')
        self.mock_os_makedirs = self.patcher_os_makedirs.start()
        self.patcher_shutil_copy2 = patch('ticket_manager.shutil.copy2')
        self.mock_shutil_copy2 = self.patcher_shutil_copy2.start()
        self.patcher_os_getsize = patch('ticket_manager.os.path.getsize')
        self.mock_os_getsize = self.patcher_os_getsize.start()
        self.patcher_os_remove = patch('ticket_manager.os.remove')
        self.mock_os_remove = self.patcher_os_remove.start()
        self.patcher_uuid4 = patch('ticket_manager.uuid.uuid4')
        self.mock_uuid4 = self.patcher_uuid4.start()
        self.patcher_mimetypes = patch('ticket_manager.mimetypes.guess_type')
        self.mock_mimetypes_guess_type = self.patcher_mimetypes.start()
        self.patcher_datetime_now = patch('ticket_manager.datetime') # For updated_at and uploaded_at
        self.mock_datetime_now = self.patcher_datetime_now.start()
        self.fixed_now = datetime.now(timezone.utc) # A fixed 'now' for predictable timestamps
        self.mock_datetime_now.now.return_value = self.fixed_now


        if os.path.exists(TEST_TICKETS_FILE): os.remove(TEST_TICKETS_FILE)
        with open(TEST_TICKETS_FILE, 'w') as f: json.dump([], f)

    def tearDown(self):
        self.patcher_file.stop(); self.patcher_get_policy.stop(); self.patcher_get_schedule.stop()
        self.patcher_get_holidays.stop(); self.patcher_calc_due.stop()
        self.patcher_attachment_dir.stop(); self.temp_attachment_dir_obj.cleanup()
        self.patcher_os_path_exists.stop(); self.patcher_os_makedirs.stop(); self.patcher_shutil_copy2.stop()
        self.patcher_os_getsize.stop(); self.patcher_os_remove.stop(); self.patcher_uuid4.stop()
        self.patcher_mimetypes.stop(); self.patcher_os_path_isfile.stop(); self.patcher_datetime_now.stop()
        if os.path.exists(TEST_TICKETS_FILE): os.remove(TEST_TICKETS_FILE)

    def _add_ticket_to_file_for_test(self, ticket: Ticket):
        # ... (same as before)
        current_tickets = ticket_manager._load_tickets()
        current_tickets = [t for t in current_tickets if t.id != ticket.id]
        current_tickets.append(ticket)
        ticket_manager._save_tickets(current_tickets)

    # --- Tests for create_ticket and SLA fields (existing, ensure they pass with new setUp) ---
    # ... (test_create_ticket_sets_sla_fields_from_policy, test_create_ticket_no_sla_policy_found) ...

    # --- Tests for add_attachment_to_ticket ---
    def test_add_attachment_success(self):
        self.mock_uuid4.return_value.hex = "fixeduuid123"
        self.mock_mimetypes_guess_type.return_value = ("image/png", None)
        self.mock_os_getsize.return_value = 10240 # 10KB
        self.mock_os_path_exists.return_value = True # For source file
        self.mock_os_path_isfile.return_value = True # For source file

        ticket = Ticket(id="ticket_att_1", title="Attachment Test", requester_user_id=DUMMY_REQUESTER_USER_ID, created_by_user_id=DUMMY_REQUESTER_USER_ID)
        self._add_ticket_to_file_for_test(ticket)

        source_file = "/tmp/test_image.png" # Dummy path, copy2 is mocked
        original_name = "test_image.png"

        updated_ticket = ticket_manager.add_attachment_to_ticket(
            ticket.id, DUMMY_UPLOADER_USER_ID, source_file, original_name
        )

        self.mock_os_makedirs.assert_called_once_with(self.test_attachment_dir_path, exist_ok=True)
        expected_stored_filename = "att_fixeduuid123.png"
        expected_dest_path = os.path.join(self.test_attachment_dir_path, expected_stored_filename)
        self.mock_shutil_copy2.assert_called_once_with(source_file, expected_dest_path)

        self.assertIsNotNone(updated_ticket)
        self.assertEqual(len(updated_ticket.attachments), 1)
        att_meta = updated_ticket.attachments[0]
        self.assertEqual(att_meta['attachment_id'], "att_fixeduuid123")
        self.assertEqual(att_meta['original_filename'], original_name)
        self.assertEqual(att_meta['stored_filename'], expected_stored_filename)
        self.assertEqual(att_meta['uploader_user_id'], DUMMY_UPLOADER_USER_ID)
        self.assertEqual(att_meta['uploaded_at'], self.fixed_now.isoformat())
        self.assertEqual(att_meta['filesize'], 10240)
        self.assertEqual(att_meta['mimetype'], "image/png")
        self.assertEqual(updated_ticket.updated_at, self.fixed_now)

    def test_add_attachment_source_file_not_found(self):
        self.mock_os_path_exists.return_value = False # Source file does not exist
        self.mock_os_path_isfile.return_value = False
        with self.assertRaises(FileNotFoundError):
            ticket_manager.add_attachment_to_ticket("tid", "uid", "/tmp/fake.doc", "fake.doc")

    def test_add_attachment_ticket_not_found(self):
        self.mock_os_path_exists.return_value = True; self.mock_os_path_isfile.return_value = True
        result = ticket_manager.add_attachment_to_ticket("non_existent_ticket", "uid", "/tmp/file.txt", "file.txt")
        self.assertIsNone(result)
        self.mock_os_remove.assert_called_once() # Check if orphaned file cleanup was attempted

    def test_add_attachment_io_error_on_copy(self):
        self.mock_os_path_exists.return_value = True; self.mock_os_path_isfile.return_value = True
        self.mock_shutil_copy2.side_effect = IOError("Disk full")
        ticket = Ticket(id="ticket_io_err", title="Copy Error", requester_user_id=DUMMY_REQUESTER_USER_ID, created_by_user_id=DUMMY_REQUESTER_USER_ID)
        self._add_ticket_to_file_for_test(ticket)
        with self.assertRaises(IOError): # Expecting the IOError to be re-raised
            ticket_manager.add_attachment_to_ticket(ticket.id, "uid", "/tmp/file.txt", "file.txt")

    @patch('ticket_manager._save_tickets', side_effect=Exception("DB Save Failed"))
    def test_add_attachment_save_fails_rolls_back_file(self, mock_save_tickets_err):
        self.mock_os_path_exists.return_value = True; self.mock_os_path_isfile.return_value = True
        self.mock_uuid4.return_value.hex = "rollback_uuid"
        ticket = Ticket(id="ticket_save_fail", title="Save Fail", requester_user_id=DUMMY_REQUESTER_USER_ID, created_by_user_id=DUMMY_REQUESTER_USER_ID)
        self._add_ticket_to_file_for_test(ticket)

        result = ticket_manager.add_attachment_to_ticket(ticket.id, "uid", "/tmp/rollback.txt", "rollback.txt")
        self.assertIsNone(result)
        self.mock_shutil_copy2.assert_called_once() # Copy was attempted
        self.mock_os_remove.assert_called_once_with(os.path.join(self.test_attachment_dir_path, "att_rollback_uuid.txt")) # Rollback delete attempted


    # --- Tests for remove_attachment_from_ticket ---
    def test_remove_attachment_success(self):
        att_id_to_remove = "att_todelete"
        stored_filename = f"{att_id_to_remove}.txt"
        attachment_meta = {"attachment_id": att_id_to_remove, "stored_filename": stored_filename, "original_filename": "delete_me.txt"}
        ticket = Ticket(id="ticket_remove_att", title="Remove Att", requester_user_id=DUMMY_REQUESTER_USER_ID,
                        created_by_user_id=DUMMY_REQUESTER_USER_ID, attachments=[attachment_meta])
        self._add_ticket_to_file_for_test(ticket)

        # Simulate the file exists in the attachment directory
        # self.mock_os_path_exists needs to return True for the specific path
        def os_path_exists_side_effect(path):
            if path == os.path.join(self.test_attachment_dir_path, stored_filename): return True
            return False # Default for other calls if any
        self.mock_os_path_exists.side_effect = os_path_exists_side_effect

        updated_ticket = ticket_manager.remove_attachment_from_ticket(ticket.id, att_id_to_remove)

        self.assertIsNotNone(updated_ticket)
        self.assertEqual(len(updated_ticket.attachments), 0)
        self.mock_os_remove.assert_called_once_with(os.path.join(self.test_attachment_dir_path, stored_filename))
        self.assertEqual(updated_ticket.updated_at, self.fixed_now)

    def test_remove_attachment_metadata_only_if_file_missing(self):
        att_id_to_remove = "att_filegone"
        stored_filename = f"{att_id_to_remove}.txt"
        attachment_meta = {"attachment_id": att_id_to_remove, "stored_filename": stored_filename}
        ticket = Ticket(id="ticket_remove_meta", title="Remove Meta", attachments=[attachment_meta], requester_user_id="u", created_by_user_id="u")
        self._add_ticket_to_file_for_test(ticket)

        self.mock_os_path_exists.return_value = False # File does not exist

        updated_ticket = ticket_manager.remove_attachment_from_ticket(ticket.id, att_id_to_remove)
        self.assertIsNotNone(updated_ticket)
        self.assertEqual(len(updated_ticket.attachments), 0)
        self.mock_os_remove.assert_not_called() # Because os.path.exists was False for it

    def test_remove_attachment_id_not_found_in_ticket(self):
        attachment_meta = {"attachment_id": "att_existing", "stored_filename": "existing.txt"}
        ticket = Ticket(id="ticket_att_notfound", title="Att Not Found", attachments=[attachment_meta], requester_user_id="u", created_by_user_id="u")
        self._add_ticket_to_file_for_test(ticket)

        updated_ticket = ticket_manager.remove_attachment_from_ticket(ticket.id, "att_non_existent")
        self.assertIsNotNone(updated_ticket)
        self.assertEqual(len(updated_ticket.attachments), 1) # Unchanged
        self.mock_os_remove.assert_not_called()

    # ... (Other existing tests like add_comment, update_ticket for SLA and notifications should be kept) ...
    # For brevity, ensure that all previous tests for add_comment and update_ticket are still here and pass.
    # The setUp method has been significantly changed, so they might need slight adjustments if they relied on
    # unmocked os/datetime behavior that is now mocked.

if __name__ == '__main__':
    unittest.main()
