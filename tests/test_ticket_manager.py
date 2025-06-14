import unittest
import json
import os
import shutil
from datetime import datetime, date, time, timedelta, timezone # Added date, time
from unittest.mock import patch, MagicMock, call # Added call
from typing import Optional, List, Dict, Any # Added Dict, Any

from models import Ticket
import ticket_manager

TEST_TICKETS_FILE = "test_tickets.json"

DUMMY_REQUESTER_USER_ID = "req_user_001"
DUMMY_COMMENTER_USER_ID = "comment_user_002"
DUMMY_ASSIGNEE_USER_ID_ORIGINAL = "assign_user_003"
DUMMY_ASSIGNEE_USER_ID_NEW = "assign_user_004"

# Mock data for settings and SLA calculations
MOCK_BUSINESS_SCHEDULE = {day: (time(9,0), time(17,0)) for day in ["monday", "tuesday", "wednesday", "thursday", "friday"]}
MOCK_BUSINESS_SCHEDULE.update({"saturday": None, "sunday": None})
MOCK_PUBLIC_HOLIDAYS = [date(2024,1,1)]
MOCK_SLA_POLICY_HIGH = {"policy_id": "sla_high", "response_time_hours": 4.0, "resolution_time_hours": 24.0}
MOCK_SLA_POLICY_MEDIUM = {"policy_id": "sla_med", "response_time_hours": 8.0, "resolution_time_hours": 48.0}


class TestTicketManagerWithSLA(unittest.TestCase): # Renamed for clarity

    def setUp(self):
        self.patcher_file = patch('ticket_manager.TICKETS_FILE', TEST_TICKETS_FILE)
        self.mock_tickets_file = self.patcher_file.start()

        # Patch dependencies from settings_manager and sla_calculator
        self.patcher_get_policy = patch('ticket_manager.get_matching_sla_policy')
        self.mock_get_policy = self.patcher_get_policy.start()

        self.patcher_get_schedule = patch('ticket_manager.get_business_schedule')
        self.mock_get_schedule = self.patcher_get_schedule.start()

        self.patcher_get_holidays = patch('ticket_manager.get_public_holidays')
        self.mock_get_holidays = self.patcher_get_holidays.start()

        self.patcher_calc_due = patch('ticket_manager.calculate_due_date')
        self.mock_calc_due = self.patcher_calc_due.start()

        # Set default return values for mocks
        self.mock_get_policy.return_value = MOCK_SLA_POLICY_MEDIUM # Default policy for tests
        self.mock_get_schedule.return_value = MOCK_BUSINESS_SCHEDULE
        self.mock_get_holidays.return_value = MOCK_PUBLIC_HOLIDAYS
        # mock_calc_due will be configured per test or return a simple offset
        self.mock_calc_due.side_effect = lambda start, hours, sched, hols: start + timedelta(hours=hours)


        if os.path.exists(TEST_TICKETS_FILE): os.remove(TEST_TICKETS_FILE)
        with open(TEST_TICKETS_FILE, 'w') as f: json.dump([], f)

    def tearDown(self):
        self.patcher_file.stop()
        self.patcher_get_policy.stop()
        self.patcher_get_schedule.stop()
        self.patcher_get_holidays.stop()
        self.patcher_calc_due.stop()
        if os.path.exists(TEST_TICKETS_FILE): os.remove(TEST_TICKETS_FILE)

    def _add_ticket_to_file_for_test(self, ticket: Ticket):
        current_tickets = ticket_manager._load_tickets()
        current_tickets = [t for t in current_tickets if t.id != ticket.id]
        current_tickets.append(ticket)
        ticket_manager._save_tickets(current_tickets)

    # --- Tests for create_ticket SLA fields ---
    def test_create_ticket_sets_sla_fields_from_policy(self):
        self.mock_get_policy.return_value = MOCK_SLA_POLICY_HIGH

        # Define what calculate_due_date should return for specific calls
        # Response: created_at + 4 business hours
        # Resolution: created_at + 24 business hours
        def side_effect_calc_due(start_time, hours, sched, hols):
            if hours == 4.0: return start_time + timedelta(hours=4) # Mocked business hours
            if hours == 24.0: return start_time + timedelta(hours=24)
            return start_time + timedelta(hours=hours) # Default fallback
        self.mock_calc_due.side_effect = side_effect_calc_due

        ticket = ticket_manager.create_ticket("SLA Test", "Desc", "IT", DUMMY_REQUESTER_USER_ID, priority="High")

        self.assertIsNotNone(ticket)
        self.assertEqual(ticket.sla_policy_id, "sla_high")
        self.mock_get_policy.assert_called_once_with("High", "IT")
        self.mock_get_schedule.assert_called_once()
        self.mock_get_holidays.assert_called_once()

        # Check calculate_due_date calls
        expected_calls_calc_due = [
            call(ticket.created_at, 4.0, MOCK_BUSINESS_SCHEDULE, MOCK_PUBLIC_HOLIDAYS),
            call(ticket.created_at, 24.0, MOCK_BUSINESS_SCHEDULE, MOCK_PUBLIC_HOLIDAYS)
        ]
        self.mock_calc_due.assert_has_calls(expected_calls_calc_due, any_order=False)

        self.assertIsNotNone(ticket.response_due_at)
        self.assertIsNotNone(ticket.resolution_due_at)
        self.assertEqual(ticket.response_due_at, ticket.created_at + timedelta(hours=4))
        self.assertEqual(ticket.resolution_due_at, ticket.created_at + timedelta(hours=24))

    def test_create_ticket_no_sla_policy_found(self):
        self.mock_get_policy.return_value = None # No policy matches
        ticket = ticket_manager.create_ticket("No SLA", "Desc", "IT", DUMMY_REQUESTER_USER_ID, priority="Low")
        self.assertIsNone(ticket.sla_policy_id)
        self.assertIsNone(ticket.response_due_at)
        self.assertIsNone(ticket.resolution_due_at)
        self.mock_calc_due.assert_not_called()


    # --- Tests for update_ticket SLA logic ---
    def test_update_ticket_recalculates_sla_on_priority_change(self):
        initial_created_at = datetime.now(timezone.utc) - timedelta(days=1)
        ticket = Ticket(id="sla_update_1", title="Priority Change", requester_user_id=DUMMY_REQUESTER_USER_ID,
                        created_by_user_id=DUMMY_REQUESTER_USER_ID, type="IT", priority="Medium",
                        created_at=initial_created_at, response_due_at=initial_created_at + timedelta(hours=8),
                        resolution_due_at=initial_created_at + timedelta(hours=48), sla_policy_id="sla_med")
        self._add_ticket_to_file_for_test(ticket)

        self.mock_get_policy.return_value = MOCK_SLA_POLICY_HIGH # New policy for "High"
        self.mock_calc_due.side_effect = lambda st, hrs, sch, hol: st + timedelta(hours=hrs) # Simplified calc

        updated_ticket = ticket_manager.update_ticket(ticket.id, priority="High")

        self.assertIsNotNone(updated_ticket)
        self.assertEqual(updated_ticket.priority, "High")
        self.assertEqual(updated_ticket.sla_policy_id, "sla_high")
        # Due dates should be recalculated from original created_at
        self.assertEqual(updated_ticket.response_due_at, initial_created_at + timedelta(hours=MOCK_SLA_POLICY_HIGH['response_time_hours']))
        self.assertEqual(updated_ticket.resolution_due_at, initial_created_at + timedelta(hours=MOCK_SLA_POLICY_HIGH['resolution_time_hours']))

    def test_update_ticket_handles_sla_pause_on_hold(self):
        ticket = Ticket(id="sla_pause_1", title="Pause Test", requester_user_id=DUMMY_REQUESTER_USER_ID,
                        created_by_user_id=DUMMY_REQUESTER_USER_ID, status="Open")
        self._add_ticket_to_file_for_test(ticket)

        now_before_pause = datetime.now(timezone.utc)
        with patch('ticket_manager.datetime') as mock_datetime: # Patch datetime used in ticket_manager
            mock_datetime.now.return_value = now_before_pause
            updated_ticket = ticket_manager.update_ticket(ticket.id, status="On Hold")

        self.assertIsNotNone(updated_ticket)
        self.assertEqual(updated_ticket.status, "On Hold")
        self.assertIsNotNone(updated_ticket.sla_paused_at)
        # sla_paused_at should be close to now_before_pause
        self.assertAlmostEqual(updated_ticket.sla_paused_at, now_before_pause, delta=timedelta(seconds=5))


    def test_update_ticket_handles_sla_resume_from_hold(self):
        pause_start_time = datetime.now(timezone.utc) - timedelta(hours=2)
        ticket = Ticket(id="sla_resume_1", title="Resume Test", requester_user_id=DUMMY_REQUESTER_USER_ID,
                        created_by_user_id=DUMMY_REQUESTER_USER_ID, status="On Hold",
                        sla_paused_at=pause_start_time, total_paused_duration_seconds=0.0)
        self._add_ticket_to_file_for_test(ticket)

        now_resume_time = datetime.now(timezone.utc)
        with patch('ticket_manager.datetime') as mock_datetime:
            mock_datetime.now.return_value = now_resume_time
            updated_ticket = ticket_manager.update_ticket(ticket.id, status="In Progress")

        self.assertIsNotNone(updated_ticket)
        self.assertEqual(updated_ticket.status, "In Progress")
        self.assertIsNone(updated_ticket.sla_paused_at)
        expected_paused_seconds = (now_resume_time - pause_start_time).total_seconds()
        self.assertAlmostEqual(updated_ticket.total_paused_duration_seconds, expected_paused_seconds, delta=1)


    def test_update_ticket_sets_responded_at(self):
        ticket = Ticket(id="sla_resp_1", title="Respond Test", requester_user_id=DUMMY_REQUESTER_USER_ID,
                        created_by_user_id=DUMMY_REQUESTER_USER_ID, status="Open", responded_at=None)
        self._add_ticket_to_file_for_test(ticket)

        now_response_time = datetime.now(timezone.utc)
        with patch('ticket_manager.datetime') as mock_datetime:
            mock_datetime.now.return_value = now_response_time # This will be ticket.updated_at
            updated_ticket = ticket_manager.update_ticket(ticket.id, status="In Progress")

        self.assertIsNotNone(updated_ticket)
        self.assertEqual(updated_ticket.status, "In Progress")
        self.assertIsNotNone(updated_ticket.responded_at)
        self.assertAlmostEqual(updated_ticket.responded_at, now_response_time, delta=timedelta(seconds=5))


    # --- Tests for add_comment_to_ticket responded_at logic ---
    @patch('ticket_manager.create_notification') # Still need to mock this for add_comment
    def test_add_comment_sets_responded_at_for_first_non_requester_comment_on_open_ticket(self, mock_create_notification):
        ticket = Ticket(id="comment_resp_1", title="Comment Response Test",
                        requester_user_id=DUMMY_REQUESTER_USER_ID,
                        created_by_user_id=DUMMY_REQUESTER_USER_ID,
                        status="Open", responded_at=None)
        self._add_ticket_to_file_for_test(ticket)

        comment_time = datetime.now(timezone.utc)
        with patch('ticket_manager.datetime') as mock_datetime: # Patch datetime used in add_comment
             # Ticket.add_comment also uses datetime.now(), so this mock affects it too.
            mock_datetime.now.return_value = comment_time
            updated_ticket = ticket_manager.add_comment_to_ticket(
                ticket.id, DUMMY_COMMENTER_USER_ID, "First helpful comment"
            )

        self.assertIsNotNone(updated_ticket)
        self.assertIsNotNone(updated_ticket.responded_at)
        # responded_at is set to ticket.updated_at, which is set by Ticket.add_comment using datetime.now()
        self.assertAlmostEqual(updated_ticket.responded_at, comment_time, delta=timedelta(seconds=5))

    @patch('ticket_manager.create_notification')
    def test_add_comment_does_not_set_responded_at_if_already_set(self, mock_create_notification):
        initial_response_time = datetime.now(timezone.utc) - timedelta(hours=1)
        ticket = Ticket(id="comment_resp_2", title="Already Responded",
                        requester_user_id=DUMMY_REQUESTER_USER_ID,
                        created_by_user_id=DUMMY_REQUESTER_USER_ID,
                        status="In Progress", responded_at=initial_response_time)
        self._add_ticket_to_file_for_test(ticket)

        updated_ticket = ticket_manager.add_comment_to_ticket(
            ticket.id, DUMMY_COMMENTER_USER_ID, "Another comment"
        )
        self.assertIsNotNone(updated_ticket)
        self.assertEqual(updated_ticket.responded_at, initial_response_time) # Should not change

    @patch('ticket_manager.create_notification')
    def test_add_comment_does_not_set_responded_at_if_requester_comments(self, mock_create_notification):
        ticket = Ticket(id="comment_resp_3", title="Requester Comment",
                        requester_user_id=DUMMY_REQUESTER_USER_ID,
                        created_by_user_id=DUMMY_REQUESTER_USER_ID,
                        status="Open", responded_at=None)
        self._add_ticket_to_file_for_test(ticket)

        updated_ticket = ticket_manager.add_comment_to_ticket(
            ticket.id, DUMMY_REQUESTER_USER_ID, "I have more info" # Requester is commenting
        )
        self.assertIsNotNone(updated_ticket)
        self.assertIsNone(updated_ticket.responded_at) # Should not be set

    # Keep other existing tests (status change notifications, assignment notifications, etc.)
    # For brevity, they are not repeated here but should be maintained.

if __name__ == '__main__':
    unittest.main()
