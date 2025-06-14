import unittest
import json
import os
import shutil
from datetime import datetime, timezone, timedelta
from unittest.mock import patch, MagicMock
from typing import Optional, List

from models import Ticket
import ticket_manager

TEST_TICKETS_FILE = "test_tickets.json"

DUMMY_REQUESTER_USER_ID = "req_user_001"
DUMMY_COMMENTER_USER_ID = "comment_user_002"
DUMMY_ASSIGNEE_USER_ID_ORIGINAL = "assign_user_003"
DUMMY_ASSIGNEE_USER_ID_NEW = "assign_user_004"


class TestTicketManager(unittest.TestCase):

    def setUp(self):
        self.patcher = patch('ticket_manager.TICKETS_FILE', TEST_TICKETS_FILE)
        self.mock_tickets_file = self.patcher.start()
        if os.path.exists(TEST_TICKETS_FILE): os.remove(TEST_TICKETS_FILE)
        # Create an empty file for each test to ensure clean state for _load_tickets
        with open(TEST_TICKETS_FILE, 'w') as f: json.dump([], f)

    def tearDown(self):
        self.patcher.stop()
        if os.path.exists(TEST_TICKETS_FILE): os.remove(TEST_TICKETS_FILE)

    def _add_ticket_to_file_for_test(self, ticket: Ticket):
        current_tickets = ticket_manager._load_tickets()
        # Remove if ticket with same ID exists, to simulate overwriting for setup
        current_tickets = [t for t in current_tickets if t.id != ticket.id]
        current_tickets.append(ticket)
        ticket_manager._save_tickets(current_tickets)

    # --- Existing tests for create, get, list, basic update (ensure they are fine) ---
    def test_create_ticket_success(self):
        t = ticket_manager.create_ticket("Title", "Desc", "IT", DUMMY_REQUESTER_USER_ID)
        self.assertIsNotNone(t)
        loaded = ticket_manager._load_tickets()
        self.assertEqual(len(loaded), 1)

    # --- Tests for add_comment_to_ticket ---
    @patch('ticket_manager.create_notification')
    def test_add_comment_success(self, mock_create_notification: MagicMock):
        ticket = Ticket(title="Comment Test", description=".", type="IT",
                        requester_user_id=DUMMY_REQUESTER_USER_ID,
                        created_by_user_id=DUMMY_REQUESTER_USER_ID,
                        assignee_user_id=DUMMY_ASSIGNEE_USER_ID_ORIGINAL)
        ticket.id = "cmt_ticket_001"
        self._add_ticket_to_file_for_test(ticket)

        original_updated_at = ticket.updated_at

        updated_ticket = ticket_manager.add_comment_to_ticket(
            ticket_id=ticket.id,
            user_id=DUMMY_COMMENTER_USER_ID,
            comment_text="This is a test comment."
        )

        self.assertIsNotNone(updated_ticket)
        self.assertEqual(len(updated_ticket.comments), 1)
        comment = updated_ticket.comments[0]
        self.assertEqual(comment['user_id'], DUMMY_COMMENTER_USER_ID)
        self.assertEqual(comment['text'], "This is a test comment.")
        self.assertTrue(updated_ticket.updated_at > original_updated_at) # Check timestamp updated

        # Check notifications (commenter is not requester or assignee)
        self.assertEqual(mock_create_notification.call_count, 2)
        # Call 1: Notify Requester
        args_requester, _ = mock_create_notification.call_args_list[0]
        self.assertEqual(args_requester[0]['user_id'], DUMMY_REQUESTER_USER_ID)
        self.assertIn(f"new comment from user {DUMMY_COMMENTER_USER_ID}", args_requester[0]['message'])
        # Call 2: Notify Assignee
        args_assignee, _ = mock_create_notification.call_args_list[1]
        self.assertEqual(args_assignee[0]['user_id'], DUMMY_ASSIGNEE_USER_ID_ORIGINAL)
        self.assertIn(f"new comment from user {DUMMY_COMMENTER_USER_ID}", args_assignee[0]['message'])


    def test_add_comment_empty_text_raises_value_error(self):
        with self.assertRaisesRegex(ValueError, "Comment text cannot be empty."):
            ticket_manager.add_comment_to_ticket("tid", "uid", "  ")

    def test_add_comment_empty_user_id_raises_value_error(self):
        with self.assertRaisesRegex(ValueError, "User ID for comment cannot be empty."):
            ticket_manager.add_comment_to_ticket("tid", "  ", "comment")

    def test_add_comment_ticket_not_found(self):
        result = ticket_manager.add_comment_to_ticket("non_existent_id", "uid", "comment")
        self.assertIsNone(result)

    @patch('ticket_manager.create_notification')
    def test_add_comment_notification_logic_scenarios(self, mock_create_notification: MagicMock):
        # Scenario 1: Requester adds a comment (notify assignee if different)
        ticket1 = Ticket(title="S1", description=".", type="IT",
                         requester_user_id=DUMMY_REQUESTER_USER_ID,
                         created_by_user_id=DUMMY_REQUESTER_USER_ID,
                         assignee_user_id=DUMMY_ASSIGNEE_USER_ID_ORIGINAL)
        ticket1.id = "cmt_s1_001"
        self._add_ticket_to_file_for_test(ticket1)
        ticket_manager.add_comment_to_ticket(ticket1.id, DUMMY_REQUESTER_USER_ID, "Requester comment")
        mock_create_notification.assert_called_once() # Only assignee notified
        args_s1, _ = mock_create_notification.call_args
        self.assertEqual(args_s1[0]['user_id'], DUMMY_ASSIGNEE_USER_ID_ORIGINAL)
        mock_create_notification.reset_mock()

        # Scenario 2: Assignee adds a comment (notify requester)
        ticket2 = Ticket(title="S2", description=".", type="IT",
                         requester_user_id=DUMMY_REQUESTER_USER_ID,
                         created_by_user_id=DUMMY_REQUESTER_USER_ID,
                         assignee_user_id=DUMMY_ASSIGNEE_USER_ID_ORIGINAL)
        ticket2.id = "cmt_s2_001"
        self._add_ticket_to_file_for_test(ticket2)
        ticket_manager.add_comment_to_ticket(ticket2.id, DUMMY_ASSIGNEE_USER_ID_ORIGINAL, "Assignee comment")
        mock_create_notification.assert_called_once() # Only requester notified
        args_s2, _ = mock_create_notification.call_args
        self.assertEqual(args_s2[0]['user_id'], DUMMY_REQUESTER_USER_ID)
        mock_create_notification.reset_mock()

        # Scenario 3: Requester is also Assignee, adds comment (no notifications)
        ticket3 = Ticket(title="S3", description=".", type="IT",
                         requester_user_id=DUMMY_REQUESTER_USER_ID,
                         created_by_user_id=DUMMY_REQUESTER_USER_ID,
                         assignee_user_id=DUMMY_REQUESTER_USER_ID) # Requester is assignee
        ticket3.id = "cmt_s3_001"
        self._add_ticket_to_file_for_test(ticket3)
        ticket_manager.add_comment_to_ticket(ticket3.id, DUMMY_REQUESTER_USER_ID, "Self comment")
        mock_create_notification.assert_not_called()


    # --- Tests for update_ticket notification logic (status and assignment) ---
    @patch('ticket_manager.create_notification')
    def test_update_ticket_status_change_notification(self, mock_cn: MagicMock):
        t = Ticket("T", "D", "IT", DUMMY_REQUESTER_USER_ID, DUMMY_REQUESTER_USER_ID, status="Open")
        t.id = "status_notify_001"
        self._add_ticket_to_file_for_test(t)
        ticket_manager.update_ticket(t.id, status="Closed")
        mock_cn.assert_called_once()
        args, _ = mock_cn.call_args
        self.assertEqual(args[0]['user_id'], DUMMY_REQUESTER_USER_ID)
        self.assertIn("status changed from 'Open' to 'Closed'", args[0]['message'])

    @patch('ticket_manager.create_notification')
    def test_update_ticket_assignment_notifications(self, mock_cn: MagicMock):
        t = Ticket("Assign Test", ".", "IT", DUMMY_REQUESTER_USER_ID, DUMMY_REQUESTER_USER_ID,
                   assignee_user_id=DUMMY_ASSIGNEE_USER_ID_ORIGINAL)
        t.id = "assign_notify_001"
        self._add_ticket_to_file_for_test(t)

        ticket_manager.update_ticket(t.id, assignee_user_id=DUMMY_ASSIGNEE_USER_ID_NEW)
        self.assertEqual(mock_cn.call_count, 3)

        # Check calls (order might vary depending on dict iteration, so check content)
        notifications_sent_to = {call[0][0]['user_id'] for call in mock_cn.call_args_list}
        self.assertIn(DUMMY_ASSIGNEE_USER_ID_NEW, notifications_sent_to) # New assignee
        self.assertIn(DUMMY_ASSIGNEE_USER_ID_ORIGINAL, notifications_sent_to) # Old assignee
        self.assertIn(DUMMY_REQUESTER_USER_ID, notifications_sent_to) # Requester

        # More specific checks on messages if needed by iterating call_args_list

    @patch('ticket_manager.create_notification')
    def test_update_ticket_assign_to_new_no_old_assignee(self, mock_cn: MagicMock):
        t = Ticket("Assign New", ".", "IT", DUMMY_REQUESTER_USER_ID, DUMMY_REQUESTER_USER_ID, assignee_user_id=None)
        t.id = "assign_new_001"
        self._add_ticket_to_file_for_test(t)
        ticket_manager.update_ticket(t.id, assignee_user_id=DUMMY_ASSIGNEE_USER_ID_NEW)
        self.assertEqual(mock_cn.call_count, 2) # New assignee and Requester
        notifications_sent_to = {call[0][0]['user_id'] for call in mock_cn.call_args_list}
        self.assertIn(DUMMY_ASSIGNEE_USER_ID_NEW, notifications_sent_to)
        self.assertIn(DUMMY_REQUESTER_USER_ID, notifications_sent_to)

    @patch('ticket_manager.create_notification')
    def test_update_ticket_unassign_ticket(self, mock_cn: MagicMock):
        t = Ticket("Unassign Test", ".", "IT", DUMMY_REQUESTER_USER_ID, DUMMY_REQUESTER_USER_ID,
                   assignee_user_id=DUMMY_ASSIGNEE_USER_ID_ORIGINAL)
        t.id = "unassign_001"
        self._add_ticket_to_file_for_test(t)
        ticket_manager.update_ticket(t.id, assignee_user_id=None) # Unassign
        self.assertEqual(mock_cn.call_count, 2) # Old assignee and Requester
        notifications_sent_to = {call[0][0]['user_id'] for call in mock_cn.call_args_list}
        self.assertIn(DUMMY_ASSIGNEE_USER_ID_ORIGINAL, notifications_sent_to)
        self.assertIn(DUMMY_REQUESTER_USER_ID, notifications_sent_to)
        # Check message for requester contains "...now unassigned."
        requester_notif = next(call for call in mock_cn.call_args_list if call[0][0]['user_id'] == DUMMY_REQUESTER_USER_ID)
        self.assertIn("is now unassigned", requester_notif[0][0]['message'])


    @patch('ticket_manager.create_notification')
    def test_update_ticket_no_assignment_notification_if_not_changed(self, mock_cn: MagicMock):
        t = Ticket("No Assign Change", ".", "IT", DUMMY_REQUESTER_USER_ID, DUMMY_REQUESTER_USER_ID,
                   assignee_user_id=DUMMY_ASSIGNEE_USER_ID_ORIGINAL)
        t.id = "no_assign_change_001"
        self._add_ticket_to_file_for_test(t)
        ticket_manager.update_ticket(t.id, title="New Title") # Assignee not in kwargs
        mock_cn.assert_not_called()

        ticket_manager.update_ticket(t.id, assignee_user_id=DUMMY_ASSIGNEE_USER_ID_ORIGINAL) # Assignee same
        mock_cn.assert_not_called()

    @patch('ticket_manager.create_notification')
    def test_update_ticket_handles_notification_creation_error(self, mock_cn: MagicMock):
        t = Ticket("Notify Error", ".", "IT", DUMMY_REQUESTER_USER_ID, DUMMY_REQUESTER_USER_ID, status="Open")
        t.id = "notify_err_001"
        self._add_ticket_to_file_for_test(t)
        mock_cn.side_effect = Exception("SMTP boom")
        with patch('builtins.print') as mock_print:
            updated_ticket = ticket_manager.update_ticket(t.id, status='Closed')
        self.assertIsNotNone(updated_ticket)
        self.assertEqual(updated_ticket.status, 'Closed')
        mock_cn.assert_called_once()
        self.assertTrue(any("Error creating status update notification" in call[0][0] for call in mock_print.call_args_list))

if __name__ == '__main__':
    unittest.main()
