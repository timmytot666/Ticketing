import json
import sqlite3
import sys # For stderr
from datetime import datetime, timezone
from typing import List, Optional, Dict, Any

try:
    from kb_article import KBArticle
except ModuleNotFoundError:
    print("Critical Error: kb_article.py not found. KB manager cannot function.", file=sys.stderr)
    class KBArticle: # Basic fallback
        article_id: str; title: str; content: str; author_user_id: str; keywords: List[str]; category: Optional[str]
        created_at: datetime; updated_at: datetime
        def __init__(self, title: str, content: str, author_user_id: str, **kwargs):
            self.article_id = kwargs.get("article_id", "fb_kb_id_" + uuid.uuid4().hex)
            self.title = title; self.content = content; self.author_user_id = author_user_id
            self.keywords = kwargs.get("keywords", [])
            self.category = kwargs.get("category")
            self.created_at = kwargs.get("created_at", datetime.now(timezone.utc))
            self.updated_at = kwargs.get("updated_at", self.created_at)
        def to_dict(self) -> Dict[str, Any]: return {k:v for k,v in self.__dict__.items() if not k.startswith('_')}
        @classmethod
        def from_dict(cls, data: Dict[str, Any]) -> 'KBArticle': return cls(**data)


try:
    from database_setup import get_db_connection
except ModuleNotFoundError:
    print("Critical Error: database_setup.py not found. KB manager cannot function.", file=sys.stderr)
    def get_db_connection(): raise ConnectionError("Database setup module not found.")

def _iso_to_datetime(iso_str: Optional[str]) -> Optional[datetime]:
    if not iso_str: return None
    try:
        dt = datetime.fromisoformat(iso_str)
        if dt.tzinfo is None:
            return dt.replace(tzinfo=timezone.utc)
        return dt.astimezone(timezone.utc)
    except ValueError:
        return None

def _row_to_kb_article(row: sqlite3.Row) -> Optional[KBArticle]:
    """Converts a sqlite3.Row to a KBArticle object."""
    if not row:
        return None

    keywords_list = json.loads(row["keywords"]) if row["keywords"] else []

    return KBArticle(
        article_id=row["article_id"],
        title=row["title"],
        content=row["content"],
        author_user_id=row["author_user_id"],
        keywords=keywords_list,
        category=row["category"],
        created_at=_iso_to_datetime(row["created_at"]),
        updated_at=_iso_to_datetime(row["updated_at"])
    )

def create_article(
    title: str,
    content: str,
    author_user_id: str,
    keywords: Optional[List[str]] = None,
    category: Optional[str] = None
) -> Optional[KBArticle]:

    try: # Validation is primarily handled by KBArticle constructor
        new_article = KBArticle(
            title=title, content=content, author_user_id=author_user_id,
            keywords=keywords, category=category
        )
    except ValueError as ve:
        print(f"Error creating article object: {ve}", file=sys.stderr)
        return None

    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        cursor.execute('''
            INSERT INTO kb_articles (
                article_id, title, content, author_user_id,
                keywords, category, created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        ''', (
            new_article.article_id, new_article.title, new_article.content,
            new_article.author_user_id, json.dumps(new_article.keywords),
            new_article.category, new_article.created_at.isoformat(),
            new_article.updated_at.isoformat()
        ))
        conn.commit()
        return new_article
    except sqlite3.Error as e:
        conn.rollback()
        print(f"Database error creating KB article '{new_article.title}': {e}", file=sys.stderr)
        return None # Or raise custom error
    finally:
        conn.close()

def get_article(article_id: str) -> Optional[KBArticle]:
    if not article_id: return None
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM kb_articles WHERE article_id = ?", (article_id,))
    row = cursor.fetchone()
    conn.close()
    return _row_to_kb_article(row)

def list_articles(sort_by: str = 'updated_at', reverse: bool = True) -> List[KBArticle]:
    conn = get_db_connection()
    cursor = conn.cursor()

    allowed_sort_columns = ['article_id', 'title', 'category', 'created_at', 'updated_at', 'author_user_id']
    if sort_by not in allowed_sort_columns:
        sort_by = 'updated_at' # Default to a safe column
        print(f"Warning: Invalid sort_by column for articles '{sort_by}'. Defaulting to 'updated_at'.", file=sys.stderr)

    order = "DESC" if reverse else "ASC"
    query = f"SELECT * FROM kb_articles ORDER BY {sort_by} {order}" # sort_by is from whitelist

    try:
        cursor.execute(query)
        rows = cursor.fetchall()
        articles = [_row_to_kb_article(row) for row in rows if row]
        return [art for art in articles if art is not None]
    except sqlite3.Error as e:
        print(f"Database error listing KB articles: {e}", file=sys.stderr)
        return []
    finally:
        conn.close()

def update_article(article_id: str, **kwargs: Any) -> Optional[KBArticle]:
    if not article_id: return None

    conn = get_db_connection()
    cursor = conn.cursor()

    current_article = get_article(article_id) # Fetch current state
    if not current_article:
        conn.close()
        return None

    fields_to_update: Dict[str, Any] = {}
    allowed_fields = ['title', 'content', 'keywords', 'category']

    for key, value in kwargs.items():
        if key in allowed_fields:
            # Perform basic validation similar to the old manager if necessary
            if key in ['title', 'content'] and (not value or not str(value).strip()):
                print(f"Warning: Update for '{key}' for article '{article_id}' is empty. Skipping.", file=sys.stderr)
                continue
            if key == 'keywords' and not isinstance(value, list):
                print(f"Warning: Keywords must be a list for article '{article_id}'. Skipping.", file=sys.stderr)
                continue
            if key == 'category' and value is not None and not str(value).strip():
                value = None

            if getattr(current_article, key) != value:
                setattr(current_article, key, value) # Update model instance
                if key == 'keywords':
                    fields_to_update[key] = json.dumps(value)
                else:
                    fields_to_update[key] = value

    if not fields_to_update:
        conn.close()
        return current_article # No valid fields were changed

    current_article.updated_at = datetime.now(timezone.utc)
    fields_to_update['updated_at'] = current_article.updated_at.isoformat()

    set_clause = ", ".join([f"{key} = ?" for key in fields_to_update.keys()])
    sql_values = list(fields_to_update.values())
    sql_values.append(article_id)

    try:
        cursor.execute(f"UPDATE kb_articles SET {set_clause} WHERE article_id = ?", tuple(sql_values))
        conn.commit()
    except sqlite3.Error as e:
        conn.rollback()
        print(f"Database error updating KB article {article_id}: {e}", file=sys.stderr)
        conn.close()
        return get_article(article_id) # Return potentially unchanged or partially updated object state from before error
    finally:
        if conn: conn.close()

    return get_article(article_id) # Re-fetch the updated article

def delete_article(article_id: str) -> bool:
    if not article_id: return False
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        cursor.execute("DELETE FROM kb_articles WHERE article_id = ?", (article_id,))
        conn.commit()
        return cursor.rowcount > 0 # Returns true if a row was deleted
    except sqlite3.Error as e:
        conn.rollback()
        print(f"Database error deleting KB article {article_id}: {e}", file=sys.stderr)
        return False
    finally:
        conn.close()

def search_articles(query: str, search_fields: Optional[List[str]] = None) -> List[KBArticle]:
    if not query or not query.strip(): return []

    conn = get_db_connection()
    cursor = conn.cursor()

    # Default search fields for SQL LIKE - direct text fields
    sql_searchable_fields = ['title', 'content', 'category']
    # Fields that might need Python-side filtering (like JSON keywords)
    python_searchable_fields = ['keywords']

    if search_fields is None: # If user provides specific fields, respect them
        user_sql_fields = sql_searchable_fields
        user_python_fields = python_searchable_fields
    else:
        user_sql_fields = [f for f in search_fields if f in sql_searchable_fields]
        user_python_fields = [f for f in search_fields if f in python_searchable_fields]


    conditions = []
    sql_params: List[Any] = []

    if not user_sql_fields and not user_python_fields: # No valid fields to search
        conn.close()
        return []

    # Build SQL part of the query for direct text fields
    if user_sql_fields:
        for field in user_sql_fields:
            conditions.append(f"LOWER({field}) LIKE ?")
            sql_params.append(f"%{query.lower()}%")

    # If only python searchable fields are given, we fetch all and filter later
    # If both, sql conditions will pre-filter
    sql_query_string = "SELECT * FROM kb_articles"
    if conditions: # Only add WHERE if there are SQL conditions
        sql_query_string += " WHERE " + " OR ".join(conditions)

    articles_to_filter: List[KBArticle] = []
    try:
        cursor.execute(sql_query_string, tuple(sql_params))
        rows = cursor.fetchall()
        for row in rows:
            article = _row_to_kb_article(row)
            if article: articles_to_filter.append(article)
    except sqlite3.Error as e:
        print(f"Database error searching KB articles (SQL part): {e}", file=sys.stderr)
        conn.close()
        return []
    finally:
        conn.close() # Close connection after SQL query

    # Python-side filtering for fields like 'keywords' or if no SQL conditions were applied
    if not user_python_fields and conditions: # SQL filtering was done, no Python fields specified
        return articles_to_filter

    if not user_python_fields and not conditions: # No SQL and no Python fields, return all (edge case based on input)
        return articles_to_filter


    # Python side filtering for keywords (and other python_searchable_fields if any)
    query_lower = query.lower()
    matched_articles: List[KBArticle] = []

    # Determine effective fields for Python search
    # If user_sql_fields was empty, then user_python_fields must be the target.
    # If user_sql_fields was present, articles_to_filter is already pre-filtered.
    # We only need to check user_python_fields if they were specified.

    active_python_search_fields = user_python_fields
    if search_fields is None: # If no specific fields were given by caller, use defaults
         active_python_search_fields = python_searchable_fields


    for article in articles_to_filter:
        # If SQL conditions already matched this article, we might add it directly
        # OR if we need to check python fields exclusively or additionally
        # This logic can get complex based on wanting AND vs OR for combined SQL/Python field search
        # For simplicity: if an article was fetched by SQL, it's a candidate.
        # If SQL part was empty, all articles are candidates.
        # Then, if python_search_fields are active, we check them.

        # If SQL conditions were applied and matched, and no python fields to check, it's a match
        if conditions and article in matched_articles: # Already added by SQL match, if we put it there
             if not active_python_search_fields: continue # Already processed

        # If SQL conditions did not match it (i.e., it's not yet in matched_articles if conditions existed)
        # OR if there were no SQL conditions. Then we check Python fields.

        python_match_found = False
        if 'keywords' in active_python_search_fields:
            if any(query_lower in str(kw).lower() for kw in article.keywords):
                python_match_found = True

        # Add other python field checks here if any

        if python_match_found:
            if article not in matched_articles: # Avoid duplicates if SQL also matched
                 matched_articles.append(article)
        elif not conditions and not active_python_search_fields:
            # Edge case: no SQL condition, no python fields to check for this article, means it's a match by default
            # This branch is unlikely if active_python_search_fields is correctly managed
            if article not in matched_articles: matched_articles.append(article)
        elif conditions and article not in matched_articles and not active_python_search_fields:
            # If it was returned by SQL, and no python fields to check, it's a match
             matched_articles.append(article)


    # If SQL conditions were present, articles in matched_articles are already from the SQL filtered set.
    # If no SQL conditions, and python fields were checked, matched_articles contains those.
    # If SQL conditions were present AND python fields were checked, then we need to ensure results satisfy BOTH.
    # The current logic is more OR-like between SQL and Python fields.
    # For a simpler OR: if an article is in articles_to_filter (matched by SQL OR is everything)
    # AND it matches any python field condition, then it's a result.
    # Let's refine the final list:

    final_results = []
    if not user_sql_fields and user_python_fields: # Only python search
        # articles_to_filter is ALL articles. matched_articles has those matching python fields.
        final_results = matched_articles
    elif user_sql_fields and not user_python_fields: # Only SQL search
        # articles_to_filter is SQL-matched. matched_articles is not really used here.
        final_results = articles_to_filter
    elif user_sql_fields and user_python_fields: # Both SQL and Python fields used
        # We want articles that matched SQL *AND* (if specified) also match Python fields
        # The current 'matched_articles' list is more of an OR.
        # Let's re-filter 'articles_to_filter' (SQL results) for Python conditions.
        temp_results = []
        for article_sql_match in articles_to_filter:
            py_match = False
            if 'keywords' in user_python_fields:
                if any(query_lower in str(kw).lower() for kw in article_sql_match.keywords):
                    py_match = True
            # Add other python field checks if necessary
            if py_match:
                temp_results.append(article_sql_match)
        final_results = temp_results
    else: # No fields specified by user, default behavior (title, content, category for SQL, keywords for Python)
        # This path implies search_fields was None initially.
        # articles_to_filter contains matches from title, content, category.
        # We need to check keywords for these, OR any other articles for keywords.
        # This effectively becomes (SQL_default_fields LIKE query) OR (keywords HAS query)

        # Start with SQL matches
        final_results.extend(articles_to_filter)
        # Add articles that match keywords but weren't in SQL results yet
        all_db_articles = []
        if not conditions: # If SQL part was skipped (e.g. only keywords specified by default)
            conn_temp = get_db_connection()
            cursor_temp = conn_temp.cursor()
            cursor_temp.execute("SELECT * FROM kb_articles")
            rows_temp = cursor_temp.fetchall()
            conn_temp.close()
            all_db_articles = [_row_to_kb_article(r) for r in rows_temp if _row_to_kb_article(r)]
            all_db_articles = [art for art in all_db_articles if art] # filter None
        else: # SQL conditions were applied, articles_to_filter is pre-filtered by SQL
            all_db_articles = articles_to_filter # Only check keywords on these

        for article in all_db_articles: # Check all articles if SQL part was empty, else check pre-filtered
            if 'keywords' in python_searchable_fields: # Check against default python fields
                 if any(query_lower in str(kw).lower() for kw in article.keywords):
                    if article not in final_results:
                        final_results.append(article)

    # Remove duplicates that might have occurred if an article matched both SQL and Python parts
    # and was added twice by earlier logic.
    deduped_results = []
    seen_ids = set()
    for art in final_results:
        if art.article_id not in seen_ids:
            deduped_results.append(art)
            seen_ids.add(art.article_id)

    return deduped_results
