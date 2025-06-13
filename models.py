import uuid
from datetime import datetime, timezone
from typing import Dict, Any, Type

class Ticket:
    def __init__(
        self,
        title: str,
        description: str,
        type: str,
        requester_email: str,
        status: str = 'Open',
        priority: str = 'Medium',
    ):
        if type not in ('IT', 'Facilities'):
            raise ValueError("Type must be 'IT' or 'Facilities'")
        if status not in ('Open', 'In Progress', 'Closed'):
            raise ValueError("Status must be 'Open', 'In Progress', or 'Closed'")
        if priority not in ('Low', 'Medium', 'High'):
            raise ValueError("Priority must be 'Low', 'Medium', or 'High'")

        self.id: str = uuid.uuid4().hex
        self.title: str = title
        self.description: str = description
        self.type: str = type
        self.status: str = status
        self.priority: str = priority
        self.requester_email: str = requester_email
        self.created_at: datetime = datetime.now(timezone.utc)
        self.updated_at: datetime = datetime.now(timezone.utc)

    def to_dict(self) -> Dict[str, Any]:
        return {
            'id': self.id,
            'title': self.title,
            'description': self.description,
            'type': self.type,
            'status': self.status,
            'priority': self.priority,
            'requester_email': self.requester_email,
            'created_at': self.created_at.isoformat(),
            'updated_at': self.updated_at.isoformat(),
        }

    @classmethod
    def from_dict(cls: Type['Ticket'], data: Dict[str, Any]) -> 'Ticket':
        ticket = cls(
            title=data['title'],
            description=data['description'],
            type=data['type'],
            requester_email=data['requester_email'],
            status=data.get('status', 'Open'),
            priority=data.get('priority', 'Medium'),
        )
        ticket.id = data['id']
        ticket.created_at = datetime.fromisoformat(data['created_at'])
        ticket.updated_at = datetime.fromisoformat(data['updated_at'])
        return ticket

    def __repr__(self) -> str:
        return f"<Ticket {self.id} - {self.title}>"
