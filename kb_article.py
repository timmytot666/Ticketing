import uuid
from datetime import datetime, timezone
from typing import List, Optional, Dict, Any, Type

class KBArticle:
    def __init__(
        self,
        title: str,
        content: str,
        author_user_id: str,
        keywords: Optional[List[str]] = None,
        category: Optional[str] = None,
        article_id: Optional[str] = None,
        created_at: Optional[datetime] = None,
        updated_at: Optional[datetime] = None
    ):
        if not title or not title.strip():
            raise ValueError("Title cannot be empty.")
        if not content or not content.strip():
            raise ValueError("Content cannot be empty.")
        if not author_user_id or not author_user_id.strip():
            raise ValueError("Author User ID cannot be empty.")

        self.article_id: str = article_id or "kb_" + uuid.uuid4().hex
        self.title: str = title.strip()
        self.content: str = content # Keep original content formatting, strip handled by validation
        self.author_user_id: str = author_user_id
        self.keywords: List[str] = [kw.strip() for kw in keywords if kw.strip()] if keywords is not None else []
        self.category: Optional[str] = category.strip() if category and category.strip() else None

        now_utc = datetime.now(timezone.utc)
        self.created_at: datetime = created_at or now_utc
        self.updated_at: datetime = updated_at or self.created_at

        # Ensure created_at and updated_at are timezone-aware (UTC)
        if self.created_at.tzinfo is None:
            self.created_at = self.created_at.replace(tzinfo=timezone.utc)
        else:
            self.created_at = self.created_at.astimezone(timezone.utc)

        if self.updated_at.tzinfo is None:
            self.updated_at = self.updated_at.replace(tzinfo=timezone.utc)
        else:
            self.updated_at = self.updated_at.astimezone(timezone.utc)


    def to_dict(self) -> Dict[str, Any]:
        return {
            "article_id": self.article_id,
            "title": self.title,
            "content": self.content,
            "author_user_id": self.author_user_id,
            "keywords": self.keywords,
            "category": self.category,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
        }

    @classmethod
    def from_dict(cls: Type['KBArticle'], data: Dict[str, Any]) -> 'KBArticle':
        def parse_datetime_utc(dt_str: Optional[str]) -> Optional[datetime]:
            if dt_str is None: return None
            dt_obj = datetime.fromisoformat(dt_str)
            return dt_obj.astimezone(timezone.utc) if dt_obj.tzinfo else dt_obj.replace(tzinfo=timezone.utc)

        return cls(
            article_id=data.get("article_id"),
            title=data["title"],
            content=data["content"],
            author_user_id=data["author_user_id"],
            keywords=data.get("keywords", []),
            category=data.get("category"),
            created_at=parse_datetime_utc(data.get("created_at")),
            updated_at=parse_datetime_utc(data.get("updated_at"))
        )

    def __repr__(self) -> str:
        return f"<KBArticle {self.article_id} - '{self.title[:50]}...'>"
