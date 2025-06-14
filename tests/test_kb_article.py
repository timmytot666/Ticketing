import unittest
import uuid
from datetime import datetime, timezone, timedelta
import sys
import os

# Adjust path to import from parent directory
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from kb_article import KBArticle # The class to test

class TestKBArticleModel(unittest.TestCase):

    def test_kbarticle_creation_success_all_fields(self):
        """Test successful KBArticle creation with all fields provided."""
        article_id = "kb_" + uuid.uuid4().hex
        now = datetime.now(timezone.utc)
        keywords = ["test", "setup", "guide"]

        article = KBArticle(
            article_id=article_id,
            title="  Test Article Title  ", # Test stripping
            content="This is the main content of the article.",
            author_user_id="user123",
            keywords=keywords,
            category="  General  ", # Test stripping
            created_at=now - timedelta(minutes=1), # Ensure created_at can be different from updated_at
            updated_at=now
        )
        self.assertEqual(article.article_id, article_id)
        self.assertEqual(article.title, "Test Article Title")
        self.assertEqual(article.content, "This is the main content of the article.")
        self.assertEqual(article.author_user_id, "user123")
        self.assertEqual(article.keywords, keywords) # Assumes keywords in list are already stripped if needed
        self.assertEqual(article.category, "General")
        self.assertEqual(article.created_at, now - timedelta(minutes=1))
        self.assertEqual(article.updated_at, now)

    def test_kbarticle_creation_minimal_fields_and_defaults(self):
        """Test KBArticle creation with only mandatory fields and check defaults."""
        before_creation = datetime.now(timezone.utc) - timedelta(seconds=1)
        article = KBArticle(
            title="Minimal Article",
            content="Minimal content.",
            author_user_id="author456"
        )
        after_creation = datetime.now(timezone.utc) + timedelta(seconds=1)

        self.assertTrue(article.article_id.startswith("kb_"))
        self.assertEqual(len(article.article_id), 32 + 3) # "kb_" + 32 hex chars
        self.assertEqual(article.title, "Minimal Article")
        self.assertEqual(article.content, "Minimal content.")
        self.assertEqual(article.author_user_id, "author456")
        self.assertEqual(article.keywords, []) # Default
        self.assertIsNone(article.category) # Default

        self.assertIsInstance(article.created_at, datetime)
        self.assertIsInstance(article.updated_at, datetime)
        self.assertTrue(before_creation <= article.created_at <= after_creation)
        self.assertEqual(article.created_at, article.updated_at) # Default updated_at is created_at

    def test_kbarticle_creation_validates_empty_fields(self):
        with self.assertRaisesRegex(ValueError, "Title cannot be empty."):
            KBArticle(title="", content="Content", author_user_id="user")
        with self.assertRaisesRegex(ValueError, "Title cannot be empty."):
            KBArticle(title="   ", content="Content", author_user_id="user")

        with self.assertRaisesRegex(ValueError, "Content cannot be empty."):
            KBArticle(title="Title", content="", author_user_id="user")
        with self.assertRaisesRegex(ValueError, "Content cannot be empty."):
            KBArticle(title="Title", content="  ", author_user_id="user")

        with self.assertRaisesRegex(ValueError, "Author User ID cannot be empty."):
            KBArticle(title="Title", content="Content", author_user_id="")
        with self.assertRaisesRegex(ValueError, "Author User ID cannot be empty."):
            KBArticle(title="Title", content="Content", author_user_id="   ")

    def test_keywords_are_stripped_and_empty_ones_removed(self):
        article = KBArticle("T", "C", "A", keywords=["  key1  ", "key2", "  ", "key3  ,  key4 "]) # key4 has comma
        self.assertEqual(article.keywords, ["key1", "key2", "key3  ,  key4"]) # Stripping is per item

    def test_category_is_stripped_or_none(self):
        article1 = KBArticle("T", "C", "A", category="  My Category  ")
        self.assertEqual(article1.category, "My Category")
        article2 = KBArticle("T", "C", "A", category="   ")
        self.assertIsNone(article2.category)
        article3 = KBArticle("T", "C", "A", category=None)
        self.assertIsNone(article3.category)


    def test_to_dict_serialization(self):
        now = datetime.now(timezone.utc)
        article = KBArticle(
            article_id="kb_testdict1", title="To Dict Test", content="Content here",
            author_user_id="dict_author", keywords=["dict", "test"], category="Serialization",
            created_at=now, updated_at=now
        )
        data = article.to_dict()
        expected_data = {
            "article_id": "kb_testdict1", "title": "To Dict Test", "content": "Content here",
            "author_user_id": "dict_author", "keywords": ["dict", "test"], "category": "Serialization",
            "created_at": now.isoformat(), "updated_at": now.isoformat()
        }
        self.assertEqual(data, expected_data)

    def test_from_dict_deserialization(self):
        now_iso = datetime.now(timezone.utc).isoformat()
        data = {
            "article_id": "kb_fromdict1", "title": "From Dict Test", "content": "Content from dict",
            "author_user_id": "from_dict_author", "keywords": ["from", "dict"], "category": "Deserialization",
            "created_at": now_iso, "updated_at": now_iso
        }
        article = KBArticle.from_dict(data)
        self.assertEqual(article.article_id, "kb_fromdict1")
        self.assertEqual(article.title, "From Dict Test")
        self.assertEqual(article.keywords, ["from", "dict"])
        self.assertEqual(article.category, "Deserialization")
        self.assertEqual(article.created_at.isoformat(), now_iso) # Compare ISO strings for tz-aware check

        # Test with missing optional fields
        minimal_data = {
            "title": "Minimal From Dict", "content": "Minimal Content", "author_user_id": "min_author"
        }
        article_min = KBArticle.from_dict(minimal_data)
        self.assertTrue(article_min.article_id.startswith("kb_"))
        self.assertEqual(article_min.keywords, [])
        self.assertIsNone(article_min.category)
        self.assertIsNotNone(article_min.created_at)
        self.assertEqual(article_min.created_at, article_min.updated_at)

    def test_from_dict_parses_datetime_to_utc(self):
        # Test with timezone offset in string
        dt_with_offset_str = "2023-01-01T10:00:00+02:00" # Not UTC
        dt_utc_expected = datetime(2023,1,1,8,0,0, tzinfo=timezone.utc) # Equivalent UTC
        data = {"title":"T","content":"C","author_user_id":"A", "created_at": dt_with_offset_str}
        article = KBArticle.from_dict(data)
        self.assertEqual(article.created_at, dt_utc_expected)

        # Test with 'Z' (Zulu/UTC)
        dt_with_z_str = "2023-01-01T10:00:00Z"
        dt_utc_expected_z = datetime(2023,1,1,10,0,0, tzinfo=timezone.utc)
        data_z = {"title":"T","content":"C","author_user_id":"A", "created_at": dt_with_z_str}
        article_z = KBArticle.from_dict(data_z)
        self.assertEqual(article_z.created_at, dt_utc_expected_z)

        # Test naive datetime string (should assume UTC)
        dt_naive_str = "2023-01-01T10:00:00"
        dt_utc_expected_naive = datetime(2023,1,1,10,0,0, tzinfo=timezone.utc)
        data_naive = {"title":"T","content":"C","author_user_id":"A", "created_at": dt_naive_str}
        article_naive = KBArticle.from_dict(data_naive)
        self.assertEqual(article_naive.created_at, dt_utc_expected_naive)


    def test_repr_method(self):
        article = KBArticle(title="This is a Test Article for Repr", content="Content", author_user_id="user")
        self.assertTrue(repr(article).startswith(f"<KBArticle {article.article_id} - 'This is a Test Article for Repr"))

if __name__ == '__main__':
    unittest.main()
