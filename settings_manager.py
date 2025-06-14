import json
import os
from datetime import date, time as dt_time # Renamed to avoid conflict with time module if used
from typing import Dict, List, Any, Optional, Tuple

SETTINGS_FILE = "app_settings.json"
DEFAULT_SETTINGS: Dict[str, Any] = {
    "business_hours": {},
    "public_holidays": [],
    "sla_policies": []
}

# --- Loading Functions ---

def _load_settings() -> Dict[str, Any]:
    """
    Loads the entire JSON settings file.
    Handles FileNotFoundError and json.JSONDecodeError by returning default settings.
    """
    if not os.path.exists(SETTINGS_FILE):
        print(f"Warning: Settings file '{SETTINGS_FILE}' not found. Returning default settings.")
        # Optionally, create a default file here: _save_settings(DEFAULT_SETTINGS)
        return DEFAULT_SETTINGS.copy() # Return a copy to prevent modification of defaults

    try:
        with open(SETTINGS_FILE, 'r') as f:
            settings = json.load(f)
            # Basic validation for top-level keys
            if not all(key in settings for key in DEFAULT_SETTINGS.keys()):
                print(f"Warning: Settings file '{SETTINGS_FILE}' is missing some top-level keys. Merging with defaults.")
                # Merge loaded settings with defaults, loaded taking precedence for existing keys
                loaded_settings = settings.copy()
                settings = DEFAULT_SETTINGS.copy()
                settings.update(loaded_settings)

            return settings
    except json.JSONDecodeError as e:
        print(f"Error decoding JSON from '{SETTINGS_FILE}': {e}. Returning default settings.")
        return DEFAULT_SETTINGS.copy()
    except Exception as e:
        print(f"An unexpected error occurred loading settings: {e}. Returning default settings.")
        return DEFAULT_SETTINGS.copy()

def get_business_schedule() -> Dict[str, Optional[Tuple[dt_time, dt_time]]]:
    """
    Loads and returns the business hours schedule.
    Times are converted to datetime.time objects.
    Returns a dictionary mapping day of the week (lowercase string) to a tuple of
    (start_time, end_time) as datetime.time objects, or None if non-operational.
    """
    settings = _load_settings()
    raw_schedule = settings.get("business_hours", {})
    schedule: Dict[str, Optional[Tuple[dt_time, dt_time]]] = {}

    valid_days = ["monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday"]

    for day, times in raw_schedule.items():
        day_lower = day.lower()
        if day_lower not in valid_days:
            print(f"Warning: Invalid day '{day}' in business_hours. Skipping.")
            continue

        if times is None: # Non-operational day
            schedule[day_lower] = None
        elif isinstance(times, list) and len(times) == 2 and \
             all(isinstance(t_str, str) for t_str in times):
            try:
                start_time_obj = dt_time.fromisoformat(times[0]) # Expects HH:MM or HH:MM:SS
                end_time_obj = dt_time.fromisoformat(times[1])
                if end_time_obj <= start_time_obj: # Basic validation
                     print(f"Warning: End time must be after start time for '{day}'. Setting as non-operational.")
                     schedule[day_lower] = None
                else:
                    schedule[day_lower] = (start_time_obj, end_time_obj)
            except ValueError as e:
                print(f"Warning: Invalid time format for '{day}' in business_hours: {times}. Error: {e}. Setting as non-operational.")
                schedule[day_lower] = None
        else:
            print(f"Warning: Invalid format for business_hours on '{day}': {times}. Expected ['HH:MM', 'HH:MM'] or null. Setting as non-operational.")
            schedule[day_lower] = None

    # Ensure all days are present in the returned schedule, even if not in JSON
    for valid_day in valid_days:
        if valid_day not in schedule:
            schedule[valid_day] = None # Default to non-operational if missing

    return schedule

def get_public_holidays() -> List[date]:
    """
    Loads and returns the list of public holidays as datetime.date objects.
    Invalid date strings are skipped with a warning.
    """
    settings = _load_settings()
    raw_holidays = settings.get("public_holidays", [])
    holidays: List[date] = []
    if not isinstance(raw_holidays, list):
        print(f"Warning: 'public_holidays' is not a list in settings. Returning empty list.")
        return []

    for date_str in raw_holidays:
        if not isinstance(date_str, str):
            print(f"Warning: Non-string value '{date_str}' found in public_holidays. Skipping.")
            continue
        try:
            holidays.append(date.fromisoformat(date_str)) # Expects YYYY-MM-DD
        except ValueError:
            print(f"Warning: Invalid date format '{date_str}' in public_holidays. Skipping.")
    return holidays

def get_sla_policies() -> List[Dict[str, Any]]:
    """
    Loads and returns the list of SLA policy dictionaries.
    Performs basic validation for required keys in each policy.
    """
    settings = _load_settings()
    raw_policies = settings.get("sla_policies", [])
    policies: List[Dict[str, Any]] = []
    if not isinstance(raw_policies, list):
        print(f"Warning: 'sla_policies' is not a list in settings. Returning empty list.")
        return []

    required_keys = ["policy_id", "name", "priority", "ticket_type", "response_time_hours", "resolution_time_hours"]
    for policy_dict in raw_policies:
        if not isinstance(policy_dict, dict):
            print(f"Warning: Non-dictionary item found in sla_policies: {policy_dict}. Skipping.")
            continue
        if all(key in policy_dict for key in required_keys):
            # Further type validation can be added here (e.g., hours are numbers)
            try:
                policy_dict['response_time_hours'] = float(policy_dict['response_time_hours'])
                policy_dict['resolution_time_hours'] = float(policy_dict['resolution_time_hours'])
                if policy_dict['response_time_hours'] < 0 or policy_dict['resolution_time_hours'] < 0:
                    raise ValueError("SLA times cannot be negative.")
                policies.append(policy_dict)
            except (ValueError, TypeError) as e:
                 print(f"Warning: Invalid numeric value for response/resolution time in SLA policy '{policy_dict.get('policy_id')}': {e}. Skipping.")
        else:
            missing_keys = [key for key in required_keys if key not in policy_dict]
            print(f"Warning: SLA policy '{policy_dict.get('policy_id', 'Unknown Policy')}' is missing required keys: {missing_keys}. Skipping.")
    return policies

# --- SLA Policy Matching Function ---

def get_matching_sla_policy(
    priority: str,
    ticket_type: str,
    policies: Optional[List[Dict[str, Any]]] = None
) -> Optional[Dict[str, Any]]:
    """
    Finds the best matching SLA policy for a given priority and ticket type.
    Priority:
    1. Exact match for `priority` AND `ticket_type`.
    2. Match for `priority` AND `ticket_type == "All"`.
    Returns the matched policy dictionary or None.
    """
    if policies is None:
        policies = get_sla_policies()

    if not policies:
        return None

    # Try for specific match first (e.g., "High" and "IT")
    for policy in policies:
        if policy.get("priority") == priority and policy.get("ticket_type") == ticket_type:
            return policy

    # If no specific match, try for "All" ticket_type with the same priority
    for policy in policies:
        if policy.get("priority") == priority and policy.get("ticket_type") == "All":
            return policy

    return None


# --- (Optional) Saving Functions ---
# These can be implemented later if settings are editable via UI.

def _save_settings(settings: Dict[str, Any]) -> bool:
    """Saves the entire settings dictionary back to SETTINGS_FILE."""
    try:
        with open(SETTINGS_FILE, 'w') as f:
            json.dump(settings, f, indent=4)
        return True
    except IOError as e:
        print(f"Error saving settings to '{SETTINGS_FILE}': {e}")
        return False
    except Exception as e:
        print(f"An unexpected error occurred while saving settings: {e}")
        return False

# Example of how an update function might look:
# def update_public_holidays(new_holidays: List[date]) -> bool:
#     settings = _load_settings()
#     settings["public_holidays"] = [h.isoformat() for h in new_holidays]
#     return _save_settings(settings)

def save_sla_policies(sla_policies: List[Dict[str, Any]]) -> bool:
    """
    Saves the provided list of SLA policies to the settings file.
    Overwrites existing SLA policies.
    """
    if not isinstance(sla_policies, list):
        # Basic type check, could be more granular for dicts inside
        print("Error: save_sla_policies expects a list of dictionaries.")
        return False

    all_settings = _load_settings()
    all_settings["sla_policies"] = sla_policies # Update the policies section
    return _save_settings(all_settings)


if __name__ == '__main__':
    # Test loading and processing
    print("--- Business Schedule ---")
    schedule = get_business_schedule()
    for day, times in schedule.items():
        if times:
            print(f"{day.capitalize()}: {times[0].strftime('%H:%M')} - {times[1].strftime('%H:%M')}")
        else:
            print(f"{day.capitalize()}: Closed")

    print("\n--- Public Holidays ---")
    holidays = get_public_holidays()
    if holidays:
        for hol_date in holidays:
            print(hol_date.isoformat())
    else:
        print("No public holidays loaded or defined.")

    print("\n--- SLA Policies ---")
    sla_policies = get_sla_policies()
    if sla_policies:
        for policy in sla_policies:
            print(f"- {policy['name']} (Priority: {policy['priority']}, Type: {policy['ticket_type']}): "
                  f"Response: {policy['response_time_hours']}h, Resolution: {policy['resolution_time_hours']}h")
    else:
        print("No SLA policies loaded or defined.")

    print("\n--- SLA Matching Examples ---")
    # Assuming 'sla_it_high' and 'sla_high_priority_default' exist from app_settings.json
    it_high_sla = get_matching_sla_policy(priority="High", ticket_type="IT", policies=sla_policies)
    if it_high_sla: print(f"Match for IT/High: {it_high_sla['name']}")
    else: print("No match for IT/High")

    facilities_high_sla = get_matching_sla_policy(priority="High", ticket_type="Facilities", policies=sla_policies)
    if facilities_high_sla: print(f"Match for Facilities/High: {facilities_high_sla['name']}") # Should pick default High
    else: print("No match for Facilities/High")

    facilities_medium_sla = get_matching_sla_policy(priority="Medium", ticket_type="Facilities", policies=sla_policies)
    if facilities_medium_sla: print(f"Match for Facilities/Medium: {facilities_medium_sla['name']}")
    else: print("No match for Facilities/Medium")

    unknown_low_sla = get_matching_sla_policy(priority="Low", ticket_type="UnknownType", policies=sla_policies)
    if unknown_low_sla: print(f"Match for UnknownType/Low: {unknown_low_sla['name']}") # Should pick default Low
    else: print("No match for UnknownType/Low")

    # Example of handling a case where settings file might be missing initially
    # if os.path.exists(SETTINGS_FILE): os.remove(SETTINGS_FILE) # Simulate missing file
    # print("\n--- Testing with missing file (should use defaults or report error) ---")
    # schedule_default = get_business_schedule()
    # print(f"Default schedule loaded: {bool(schedule_default)}")
    # if not os.path.exists(SETTINGS_FILE): # If _load_settings created a default file
    #      _save_settings(DEFAULT_SETTINGS) # Or save the initial example content back
    #      print(f"Created a default settings file at {SETTINGS_FILE}")
