import uuid
from datetime import datetime, timezone
from typing import Dict, Any, Type, List, Optional, Literal

# Attempt to import werkzeug.security; tests will fail if not available
try:
    from werkzeug.security import generate_password_hash, check_password_hash
except ImportError:
    # Provide dummy implementations if werkzeug is not available
    # This allows the model file to be imported, but auth will not be secure.
    # Tests for User auth features should ideally mock these or ensure werkzeug is installed.
    print("Warning: werkzeug.security not found. Using placeholder password hashing.")
    def generate_password_hash(password: str) -> str:
        return f"hashed_{password}_placeholder"
    def check_password_hash(pwhash: str, password: str) -> bool:
        if pwhash is None: return False
        return pwhash == f"hashed_{password}_placeholder"

class User:
    ROLES = Literal['EndUser', 'Technician', 'Engineer', 'TechManager', 'EngManager']

    def __init__(self, username: str, role: ROLES, user_id: Optional[str] = None, password_hash: Optional[str] = None):
        if not username:
            raise ValueError("Username cannot be empty.")
        if role not in getattr(self.ROLES, '__args__', []): # Handle Literal for older Pythons if needed
             # For Python 3.8+, self.ROLES.__args__ works.
             # Fallback for older versions or if __args__ is not found on Literal type directly.
            args = []
            if hasattr(self.ROLES, '__args__'):
                args = self.ROLES.__args__
            elif hasattr(self.ROLES, '__values__'): # For older typing.Literal like constructs
                args = self.ROLES.__values__

            if role not in args:
                 raise ValueError(f"Invalid role: {role}. Must be one of {args}")


        self.user_id: str = user_id or uuid.uuid4().hex
        self.username: str = username
        # _password_hash stores the hash. If password_hash is provided during init (e.g. from_dict), store it directly.
        self._password_hash: Optional[str] = password_hash
        self.role: User.ROLES = role

    def set_password(self, password: str):
        if not password:
            raise ValueError("Password cannot be empty.")
        self._password_hash = generate_password_hash(password)

    def check_password(self, password: str) -> bool:
        if not self._password_hash: # No password set
            return False
        if not password: # No password provided to check
            return False
        return check_password_hash(self._password_hash, password)

    @property
    def password_hash(self) -> Optional[str]:
        """Provides access to the password hash, primarily for to_dict or storage."""
        return self._password_hash

    def to_dict(self) -> Dict[str, Any]:
        return {
            "user_id": self.user_id,
            "username": self.username,
            "password_hash": self._password_hash, # Store the hash
            "role": self.role,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'User':
        return cls(
            username=data["username"],
            role=data["role"],
            user_id=data.get("user_id"),
            password_hash=data.get("password_hash") # Retrieve the hash
        )

    def __repr__(self) -> str:
        return f"<User {self.user_id} - {self.username} ({self.role})>"


class Notification:
    def __init__(self, user_id: str, message: str, ticket_id: Optional[str] = None,
                 notification_id: Optional[str] = None, timestamp: Optional[datetime] = None,
                 is_read: bool = False):
        if not user_id:
            raise ValueError("User ID cannot be empty for a notification.")
        if not message:
            raise ValueError("Notification message cannot be empty.")

        self.notification_id: str = notification_id or uuid.uuid4().hex
        self.user_id: str = user_id
        self.ticket_id: Optional[str] = ticket_id
        self.message: str = message
        self.timestamp: datetime = timestamp or datetime.now(timezone.utc)
        self.is_read: bool = is_read

    def to_dict(self) -> Dict[str, Any]:
        return {
            "notification_id": self.notification_id,
            "user_id": self.user_id,
            "ticket_id": self.ticket_id,
            "message": self.message,
            "timestamp": self.timestamp.isoformat(),
            "is_read": self.is_read,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'Notification':
        return cls(
            user_id=data["user_id"],
            message=data["message"],
            ticket_id=data.get("ticket_id"),
            notification_id=data.get("notification_id"),
            timestamp=datetime.fromisoformat(data["timestamp"]) if data.get("timestamp") else None,
            is_read=data.get("is_read", False)
        )

    def __repr__(self) -> str:
        return f"<Notification {self.notification_id} for User {self.user_id} - Read: {self.is_read}>"


class Ticket:
    def __init__(
        self,
        title: str,
        description: str,
        type: str,
        requester_user_id: str, # Changed from requester_email
        created_by_user_id: str,
        status: str = 'Open',
        priority: str = 'Medium',
        assignee_user_id: Optional[str] = None, # Changed from assigned_to_user_id for clarity
        ticket_id: Optional[str] = None,
        created_at: Optional[datetime] = None,
        updated_at: Optional[datetime] = None,
        comments: Optional[List[Dict[str, str]]] = None,
        # New SLA fields
        sla_policy_id: Optional[str] = None,
        response_due_at: Optional[datetime] = None,
        resolution_due_at: Optional[datetime] = None,
        responded_at: Optional[datetime] = None,
        sla_paused_at: Optional[datetime] = None,
        total_paused_duration_seconds: float = 0.0,
        # New SLA notification tracking fields
        response_sla_breach_notified: bool = False,
        resolution_sla_breach_notified: bool = False,
        response_sla_nearing_breach_notified: bool = False,
        resolution_sla_nearing_breach_notified: bool = False,
        # New field for attachments
        attachments: Optional[List[Dict[str, Any]]] = None
    ):
        if not title or not isinstance(title, str):
            raise ValueError("Title cannot be empty and must be a string.")
        if not description or not isinstance(description, str):
            raise ValueError("Description cannot be empty and must be a string.")

        # Changed: requester_email validation removed, requester_user_id validation added
        if not requester_user_id or not isinstance(requester_user_id, str):
            raise ValueError("Requester User ID cannot be empty and must be a string.")

        if not created_by_user_id or not isinstance(created_by_user_id, str):
            raise ValueError("Created By User ID cannot be empty and must be a string.")

        if type not in ('IT', 'Facilities'):
            raise ValueError("Type must be 'IT' or 'Facilities'")
        if status not in ('Open', 'In Progress', 'Closed'):
            raise ValueError("Status must be 'Open', 'In Progress', or 'Closed'")
        if priority not in ('Low', 'Medium', 'High'):
            raise ValueError("Priority must be 'Low', 'Medium', or 'High'")

        if assignee_user_id is not None and not isinstance(assignee_user_id, str):
            raise ValueError("Assignee User ID must be a string if provided.")

        self.id: str = ticket_id or uuid.uuid4().hex
        self.title: str = title
        self.description: str = description
        self.type: str = type
        self.status: str = status
        self.priority: str = priority

        self.requester_user_id: str = requester_user_id # Changed
        self.created_by_user_id: str = created_by_user_id
        self.assignee_user_id: Optional[str] = assignee_user_id # Changed

        self.comments: List[Dict[str, str]] = comments if comments is not None else []
        self.created_at: datetime = created_at or datetime.now(timezone.utc)
        self.updated_at: datetime = updated_at or datetime.now(timezone.utc)

        # Initialize new SLA fields
        self.sla_policy_id: Optional[str] = sla_policy_id
        self.response_due_at: Optional[datetime] = response_due_at
        self.resolution_due_at: Optional[datetime] = resolution_due_at
        self.responded_at: Optional[datetime] = responded_at
        self.sla_paused_at: Optional[datetime] = sla_paused_at
        self.total_paused_duration_seconds: float = total_paused_duration_seconds if total_paused_duration_seconds is not None else 0.0

        # Initialize new SLA notification tracking fields
        self.response_sla_breach_notified: bool = response_sla_breach_notified
        self.resolution_sla_breach_notified: bool = resolution_sla_breach_notified
        self.response_sla_nearing_breach_notified: bool = response_sla_nearing_breach_notified
        self.resolution_sla_nearing_breach_notified: bool = resolution_sla_nearing_breach_notified

        # Initialize attachments
        self.attachments: List[Dict[str, Any]] = attachments if attachments is not None else []


    def to_dict(self) -> Dict[str, Any]:
        return {
            'id': self.id,
            'title': self.title,
            'description': self.description,
            'type': self.type,
            'status': self.status,
            'priority': self.priority,
            'requester_user_id': self.requester_user_id, # Changed
            'created_by_user_id': self.created_by_user_id,
            'assignee_user_id': self.assignee_user_id, # Changed
            'comments': self.comments,
            'created_at': self.created_at.isoformat(),
            'updated_at': self.updated_at.isoformat(),
            # SLA fields serialization
            'sla_policy_id': self.sla_policy_id,
            'response_due_at': self.response_due_at.isoformat() if self.response_due_at else None,
            'resolution_due_at': self.resolution_due_at.isoformat() if self.resolution_due_at else None,
            'responded_at': self.responded_at.isoformat() if self.responded_at else None,
            'sla_paused_at': self.sla_paused_at.isoformat() if self.sla_paused_at else None,
            'total_paused_duration_seconds': self.total_paused_duration_seconds,
            # SLA notification tracking fields serialization
            'response_sla_breach_notified': self.response_sla_breach_notified,
            'resolution_sla_breach_notified': self.resolution_sla_breach_notified,
            'response_sla_nearing_breach_notified': self.response_sla_nearing_breach_notified,
            'resolution_sla_nearing_breach_notified': self.resolution_sla_nearing_breach_notified,
            # Add attachments to dict
            "attachments": self.attachments,
        }

    @classmethod
    def from_dict(cls: Type['Ticket'], data: Dict[str, Any]) -> 'Ticket':
        # Helper to parse ISO datetime strings, ensuring they become offset-aware (UTC)
        def parse_datetime_utc(dt_str: Optional[str]) -> Optional[datetime]:
            if dt_str is None:
                return None
            dt_obj = datetime.fromisoformat(dt_str)
            # If fromisoformat results in naive datetime (no tz info in string), assume UTC.
            # If string has 'Z' or offset, it's already aware.
            if dt_obj.tzinfo is None:
                return dt_obj.replace(tzinfo=timezone.utc)
            return dt_obj.astimezone(timezone.utc) # Ensure it's UTC if it had other offset

        return cls(
            ticket_id=data.get('id'),
            title=data['title'],
            description=data['description'],
            type=data['type'],
            requester_user_id=data['requester_user_id'], # Changed
            created_by_user_id=data['created_by_user_id'],
            status=data.get('status', 'Open'),
            priority=data.get('priority', 'Medium'),
            assignee_user_id=data.get('assignee_user_id'),
            comments=data.get('comments', []),
            created_at=parse_datetime_utc(data.get('created_at')),
            updated_at=parse_datetime_utc(data.get('updated_at')),
            # SLA fields deserialization
            sla_policy_id=data.get('sla_policy_id'),
            response_due_at=parse_datetime_utc(data.get('response_due_at')),
            resolution_due_at=parse_datetime_utc(data.get('resolution_due_at')),
            responded_at=parse_datetime_utc(data.get('responded_at')),
            sla_paused_at=parse_datetime_utc(data.get('sla_paused_at')),
            total_paused_duration_seconds=float(data.get('total_paused_duration_seconds', 0.0)),
            # SLA notification tracking fields deserialization
            response_sla_breach_notified=data.get('response_sla_breach_notified', False),
            resolution_sla_breach_notified=data.get('resolution_sla_breach_notified', False),
            response_sla_nearing_breach_notified=data.get('response_sla_nearing_breach_notified', False),
            resolution_sla_nearing_breach_notified=data.get('resolution_sla_nearing_breach_notified', False),
            # Add attachments from dict
            attachments=data.get('attachments', []) # Default to empty list if not present
        )

    def __repr__(self) -> str:
        return f"<Ticket {self.id} - {self.title} (Status: {self.status})>"

    def add_comment(self, user_id: str, text: str) -> None:
        if not user_id or not isinstance(user_id, str):
            raise ValueError("User ID for comment cannot be empty and must be a string.")
        if not text or not isinstance(text, str):
            raise ValueError("Comment text cannot be empty and must be a string.")

        comment = {
            'user_id': user_id,
            'timestamp': datetime.now(timezone.utc).isoformat(),
            'text': text
        }
        self.comments.append(comment)
        self.updated_at = datetime.now(timezone.utc)
