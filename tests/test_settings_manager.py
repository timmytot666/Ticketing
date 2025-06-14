import unittest
from unittest.mock import patch, mock_open, MagicMock
import json
import os
from datetime import date, time

# Adjust path to import from parent directory
import sys
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

import settings_manager # The module to test

class TestSettingsManager(unittest.TestCase):

    def setUp(self):
        # Default mock settings data
        self.mock_data = {
            "business_hours": {
                "monday": ["09:00", "17:00"],
                "tuesday": ["10:00", "16:00"],
                "saturday": None
            },
            "public_holidays": [
                "2024-01-01",
                "2024-12-25",
                "invalid-date-string"
            ],
            "sla_policies": [
                {
                    "policy_id": "p1", "name": "N1", "priority": "High", "ticket_type": "IT",
                    "response_time_hours": 1, "resolution_time_hours": 4
                },
                {
                    "policy_id": "p2", "name": "N2", "priority": "High", "ticket_type": "All",
                    "response_time_hours": 2, "resolution_time_hours": 8
                },
                { # Missing response_time_hours
                    "policy_id": "p3", "name": "N3", "priority": "Medium", "ticket_type": "Facilities",
                    "resolution_time_hours": 24
                },
                { # Invalid hour type
                    "policy_id": "p4", "name": "N4", "priority": "Low", "ticket_type": "All",
                    "response_time_hours": "invalid", "resolution_time_hours": 48
                }
            ]
        }
        # Patch SETTINGS_FILE path for tests
        self.test_settings_file_path = "test_app_settings.json"
        self.settings_file_patcher = patch('settings_manager.SETTINGS_FILE', self.test_settings_file_path)
        self.mock_settings_file_path = self.settings_file_patcher.start()

    def tearDown(self):
        self.settings_file_patcher.stop()
        if os.path.exists(self.test_settings_file_path):
            os.remove(self.test_settings_file_path)

    @patch('builtins.open', new_callable=mock_open)
    @patch('json.load')
    def test_load_settings_success(self, mock_json_load, mock_file_open):
        mock_json_load.return_value = self.mock_data
        with patch('os.path.exists', return_value=True): # Ensure file "exists"
            settings = settings_manager._load_settings()
        mock_file_open.assert_called_once_with(self.test_settings_file_path, 'r')
        self.assertEqual(settings, self.mock_data)

    @patch('os.path.exists', return_value=False) # File does not exist
    @patch('builtins.print') # To suppress "Warning: Settings file not found"
    def test_load_settings_file_not_found_returns_defaults(self, mock_print, mock_os_exists):
        settings = settings_manager._load_settings()
        self.assertEqual(settings, settings_manager.DEFAULT_SETTINGS)

    @patch('builtins.open', new_callable=mock_open, read_data="invalid json")
    @patch('os.path.exists', return_value=True)
    @patch('builtins.print')
    def test_load_settings_json_decode_error_returns_defaults(self, mock_print, mock_os_exists, mock_file_open):
        with patch('json.load', side_effect=json.JSONDecodeError("err", "doc", 0)):
            settings = settings_manager._load_settings()
        self.assertEqual(settings, settings_manager.DEFAULT_SETTINGS)
        mock_print.assert_any_call(unittest.mock.string_containing("Error decoding JSON"))


    @patch('settings_manager._load_settings')
    def test_get_business_schedule(self, mock_load_settings):
        mock_load_settings.return_value = self.mock_data
        schedule = settings_manager.get_business_schedule()
        self.assertEqual(schedule["monday"], (time(9,0), time(17,0)))
        self.assertEqual(schedule["tuesday"], (time(10,0), time(16,0)))
        self.assertIsNone(schedule["saturday"])
        self.assertIsNone(schedule["sunday"]) # Test default for missing day

        # Test invalid time string (should become None)
        bad_data = {"business_hours": {"wednesday": ["09:00", "bad-time"]}}
        mock_load_settings.return_value = bad_data
        schedule_bad = settings_manager.get_business_schedule()
        self.assertIsNone(schedule_bad["wednesday"])


    @patch('settings_manager._load_settings')
    def test_get_public_holidays(self, mock_load_settings):
        mock_load_settings.return_value = self.mock_data
        holidays = settings_manager.get_public_holidays()
        self.assertIn(date(2024, 1, 1), holidays)
        self.assertIn(date(2024, 12, 25), holidays)
        self.assertEqual(len(holidays), 2) # "invalid-date-string" should be skipped


    @patch('settings_manager._load_settings')
    def test_get_sla_policies(self, mock_load_settings):
        mock_load_settings.return_value = self.mock_data
        policies = settings_manager.get_sla_policies()
        self.assertEqual(len(policies), 2) # p3 and p4 should be skipped due to errors/missing fields
        self.assertEqual(policies[0]['policy_id'], 'p1')
        self.assertEqual(policies[1]['policy_id'], 'p2')
        self.assertIsInstance(policies[0]['response_time_hours'], float)

    @patch('settings_manager.get_sla_policies') # Mock the public getter
    def test_get_matching_sla_policy(self, mock_get_policies):
        # Use the valid policies from self.mock_data for this test
        valid_policies = [p for p in self.mock_data['sla_policies'] if 'response_time_hours' in p and isinstance(p['response_time_hours'], (int, float))]
        mock_get_policies.return_value = valid_policies

        # Exact match: IT, High
        policy = settings_manager.get_matching_sla_policy("High", "IT")
        self.assertIsNotNone(policy)
        self.assertEqual(policy['policy_id'], "p1")

        # Priority + "All" type match: Facilities, High (should match p2)
        policy = settings_manager.get_matching_sla_policy("High", "Facilities")
        self.assertIsNotNone(policy)
        self.assertEqual(policy['policy_id'], "p2")

        # No match
        policy = settings_manager.get_matching_sla_policy("Medium", "IT") # No Medium IT, no Medium All
        self.assertIsNone(policy)


    @patch('settings_manager._load_settings')
    @patch('settings_manager._save_settings')
    def test_save_sla_policies(self, mock_save_settings, mock_load_settings):
        mock_load_settings.return_value = {"business_hours": {}, "public_holidays": [], "sla_policies": []}
        mock_save_settings.return_value = True # Assume save is successful

        new_policies_to_save = [{"policy_id": "p_new", "name": "New Policy", "priority": "Low", "ticket_type": "All", "response_time_hours": 10, "resolution_time_hours": 50}]

        result = settings_manager.save_sla_policies(new_policies_to_save)
        self.assertTrue(result)

        mock_load_settings.assert_called_once()
        # Check that _save_settings was called with the updated full settings dict
        expected_saved_data = {"business_hours": {}, "public_holidays": [], "sla_policies": new_policies_to_save}
        mock_save_settings.assert_called_once_with(expected_saved_data)

    @patch('builtins.open', new_callable=mock_open)
    @patch('json.dump')
    def test_save_settings_success(self, mock_json_dump, mock_file_open):
        result = settings_manager._save_settings({"test": "data"})
        self.assertTrue(result)
        mock_file_open.assert_called_once_with(self.test_settings_file_path, 'w')
        mock_json_dump.assert_called_once_with({"test": "data"}, mock_file_open.return_value, indent=4)

    @patch('builtins.open', side_effect=IOError("Disk full"))
    def test_save_settings_io_error(self, mock_file_open):
        result = settings_manager._save_settings({"test": "data"})
        self.assertFalse(result)


if __name__ == '__main__':
    unittest.main()
