import json
import os
from datetime import datetime, timezone
from typing import List, Optional, Dict, Any

try:
    from kb_article import KBArticle # Assuming kb_article.py is in the same directory or PYTHONPATH
except ModuleNotFoundError:
    print("Error: kb_article.py not found. Ensure it's accessible.", file=sys.stderr)
    # Basic fallback for KBArticle to allow parsing of this file
    class KBArticle:
        def __init__(self, title: str, content: str, author_user_id: str, **kwargs):
            self.article_id = kwargs.get("article_id", "fb_kb_id")
            self.title = title; self.content = content; self.author_user_id = author_user_id
            self.keywords = kwargs.get("keywords", [])
            self.category = kwargs.get("category")
            self.created_at = kwargs.get("created_at", datetime.now(timezone.utc))
            self.updated_at = kwargs.get("updated_at", self.created_at)
        def to_dict(self) -> Dict[str, Any]: return self.__dict__ # Simplified
        @classmethod
        def from_dict(cls, data: Dict[str, Any]) -> 'KBArticle':
             # This simplified from_dict might miss datetime parsing if not careful
             return cls(**data)


KB_FILE = "knowledge_base.json"
DEFAULT_KB_DATA: List[Dict[str, Any]] = [] # Default to an empty list

# --- Helper Functions ---

def _load_articles() -> List[KBArticle]:
    """Loads articles from KB_FILE, returns list of KBArticle objects."""
    if not os.path.exists(KB_FILE):
        # If file doesn't exist, create it with empty list to avoid load errors on first run
        _save_articles([]) # Save an empty list to create the file
        return []

    try:
        with open(KB_FILE, 'r', encoding='utf-8') as f:
            if os.fstat(f.fileno()).st_size == 0: # File is empty
                return []
            data = json.load(f)
            if not isinstance(data, list): # Ensure top level is a list
                print(f"Warning: {KB_FILE} does not contain a JSON list. Initializing with empty list.", file=sys.stderr)
                _save_articles([])
                return []
            return [KBArticle.from_dict(article_data) for article_data in data]
    except json.JSONDecodeError:
        print(f"Error decoding JSON from {KB_FILE}. Returning empty list.", file=sys.stderr)
        return [] # Or raise an error / return default
    except Exception as e:
        print(f"An unexpected error occurred loading KB articles: {e}", file=sys.stderr)
        return []


def _save_articles(articles: List[KBArticle]) -> bool:
    """Saves list of KBArticle objects to KB_FILE. Returns True on success."""
    try:
        with open(KB_FILE, 'w', encoding='utf-8') as f:
            json.dump([article.to_dict() for article in articles], f, indent=4, ensure_ascii=False)
        return True
    except IOError as e:
        print(f"Error saving KB articles to {KB_FILE}: {e}", file=sys.stderr)
    except Exception as e:
        print(f"An unexpected error occurred while saving KB articles: {e}", file=sys.stderr)
    return False

# --- CRUD Functions ---

def create_article(
    title: str,
    content: str,
    author_user_id: str,
    keywords: Optional[List[str]] = None,
    category: Optional[str] = None
) -> Optional[KBArticle]:
    """Creates a new KBArticle instance, saves it, and returns the article."""
    try:
        new_article = KBArticle(
            title=title,
            content=content,
            author_user_id=author_user_id,
            keywords=keywords,
            category=category
        )
    except ValueError as ve: # Catch validation errors from KBArticle model
        print(f"Error creating article: {ve}", file=sys.stderr)
        # raise # Or return None if preferred for manager layer
        return None

    articles = _load_articles()
    articles.append(new_article)
    if _save_articles(articles):
        return new_article
    return None # Save failed

def get_article(article_id: str) -> Optional[KBArticle]:
    """Finds and returns a KBArticle by its ID."""
    if not article_id: return None
    articles = _load_articles()
    for article in articles:
        if article.article_id == article_id:
            return article
    return None

def list_articles(sort_by: str = 'updated_at', reverse: bool = True) -> List[KBArticle]:
    """Returns all articles, sorted by a given field."""
    articles = _load_articles()
    # Basic sort, ensure attribute exists. More robust sorting might handle missing attrs.
    try:
        articles.sort(key=lambda x: getattr(x, sort_by, datetime.min.replace(tzinfo=timezone.utc) if 'at' in sort_by else ""), reverse=reverse)
    except TypeError as e:
        print(f"Warning: Could not sort articles by '{sort_by}': {e}. Returning unsorted.", file=sys.stderr)
    return articles

def update_article(article_id: str, **kwargs: Any) -> Optional[KBArticle]:
    """Updates allowed fields of an existing article."""
    if not article_id: return None
    articles = _load_articles()
    article_to_update: Optional[KBArticle] = None
    article_index: int = -1

    for i, article in enumerate(articles):
        if article.article_id == article_id:
            article_to_update = article
            article_index = i
            break

    if not article_to_update:
        return None # Article not found

    allowed_fields = ['title', 'content', 'keywords', 'category']
    updated = False
    for key, value in kwargs.items():
        if key in allowed_fields and hasattr(article_to_update, key):
            # Basic validation, model might do more
            if key in ['title', 'content'] and (not value or not str(value).strip()):
                print(f"Warning: Update for '{key}' for article '{article_id}' is empty. Skipping update for this field.", file=sys.stderr)
                continue
            if key == 'keywords' and not isinstance(value, list):
                print(f"Warning: Keywords must be a list for article '{article_id}'. Skipping update for keywords.", file=sys.stderr)
                continue
            if key == 'category' and value is not None and not str(value).strip():
                value = None # Treat empty string category as None

            if getattr(article_to_update, key) != value:
                setattr(article_to_update, key, value)
                updated = True

    if updated:
        article_to_update.updated_at = datetime.now(timezone.utc)
        articles[article_index] = article_to_update
        if _save_articles(articles):
            return article_to_update
        else: # Save failed, should ideally indicate this more clearly or rollback
            return None

    return article_to_update # No fields were updated that are allowed

def delete_article(article_id: str) -> bool:
    """Deletes an article by its ID. Returns True if deleted, False otherwise."""
    if not article_id: return False
    articles = _load_articles()
    original_length = len(articles)
    articles = [article for article in articles if article.article_id != article_id]

    if len(articles) < original_length: # Article was found and removed from list
        return _save_articles(articles)
    return False # Article not found

# --- Search Function ---

def search_articles(query: str, search_fields: Optional[List[str]] = None) -> List[KBArticle]:
    """
    Searches articles for a query string in specified fields.
    Default fields: 'title', 'keywords', 'content'.
    Case-insensitive substring match.
    """
    if not query or not query.strip():
        return []

    articles = _load_articles()
    if not articles:
        return []

    if search_fields is None:
        search_fields = ['title', 'keywords', 'content']

    query_lower = query.lower()
    matched_articles: List[KBArticle] = []

    for article in articles:
        match_found = False
        for field in search_fields:
            if not hasattr(article, field):
                continue

            value = getattr(article, field)

            if isinstance(value, str):
                if query_lower in value.lower():
                    match_found = True
                    break
            elif isinstance(value, list) and field == 'keywords': # Special handling for keywords list
                if any(query_lower in str(kw).lower() for kw in value):
                    match_found = True
                    break

        if match_found:
            matched_articles.append(article)

    # Optional: Sort results by relevance or other criteria
    # For now, returning as found.
    return matched_articles


if __name__ == '__main__':
    # Basic test and usage examples
    print("KB Manager - Initializing...")
    # Ensure the JSON file is empty or has valid data for a clean test
    if os.path.exists(KB_FILE): os.remove(KB_FILE)
    _save_articles([])

    # Create
    print("\nCreating articles...")
    a1 = create_article("Setup VPN", "How to setup VPN access...", "user001", ["vpn", "network", "remote"], "Networking")
    a2 = create_article("Printer Fix", "Troubleshooting printer jams...", "user002", ["printer", "hardware", "fix"], "Hardware")
    a3 = create_article("Password Reset", "Steps to reset your password...", "user001", ["password", "account", "security"], "Security")
    if a1: print(f"Created: {a1.title}")
    if a2: print(f"Created: {a2.title}")
    if a3: print(f"Created: {a3.title}")

    # List
    print("\nListing articles (default sort - by updated_at desc):")
    all_arts = list_articles()
    for art in all_arts: print(f"- {art.title} (Updated: {art.updated_at.strftime('%Y-%m-%d %H:%M')})")

    # Get one
    if a1:
        print(f"\nGetting article: {a1.article_id}")
        fetched_a1 = get_article(a1.article_id)
        if fetched_a1: print(f"Found: {fetched_a1.title}")

    # Update
    if a2:
        print(f"\nUpdating article: {a2.title}")
        updated_a2 = update_article(a2.article_id, content="Updated content for printer jams.", category="General Hardware")
        if updated_a2: print(f"Updated: {updated_a2.title}, New Category: {updated_a2.category}, Updated At: {updated_a2.updated_at.strftime('%Y-%m-%d %H:%M')}")

    # Search
    print("\nSearching for 'vpn':")
    vpn_results = search_articles("vpn")
    for art in vpn_results: print(f"- Found in VPN search: {art.title}")

    print("\nSearching for 'password' in title only:")
    password_results = search_articles("Password", search_fields=['title'])
    for art in password_results: print(f"- Found in Password (title) search: {art.title}")

    print("\nSearching for 'nonexistentquery':")
    no_results = search_articles("nonexistentquery")
    print(f"Found {len(no_results)} articles for 'nonexistentquery'.")

    # Delete
    if a3:
        print(f"\nDeleting article: {a3.title}")
        deleted = delete_article(a3.article_id)
        print(f"Deleted successfully: {deleted}")
        print("Listing articles after delete:")
        all_arts_after_delete = list_articles()
        for art in all_arts_after_delete: print(f"- {art.title}")

    # Clean up test file
    # if os.path.exists(KB_FILE): os.remove(KB_FILE)
