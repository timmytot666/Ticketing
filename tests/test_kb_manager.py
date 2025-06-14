import unittest
from unittest.mock import patch, mock_open, MagicMock, call
import json
import os
from datetime import datetime, timezone, timedelta
import sys

# Adjust path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

import kb_manager # The module to test
from kb_article import KBArticle # For creating instances and type checks

class TestKBManager(unittest.TestCase):

    def setUp(self):
        self.test_kb_file_path = "test_knowledge_base.json"
        self.kb_file_patcher = patch('kb_manager.KB_FILE', self.test_kb_file_path)
        self.mock_kb_file_path = self.kb_file_patcher.start()

        # Ensure a clean slate for each test for file operations
        if os.path.exists(self.test_kb_file_path):
            os.remove(self.test_kb_file_path)

    def tearDown(self):
        self.kb_file_patcher.stop()
        if os.path.exists(self.test_kb_file_path):
            os.remove(self.test_kb_file_path)

    @patch('builtins.open', new_callable=mock_open)
    @patch('json.load')
    @patch('kb_manager._save_articles') # Prevent _load_articles from creating file on first call
    def test_load_articles_success(self, mock_save, mock_json_load, mock_file_open):
        mock_data = [
            {"article_id": "kb1", "title": "T1", "content": "C1", "author_user_id": "u1",
             "created_at": datetime.now(timezone.utc).isoformat(),
             "updated_at": datetime.now(timezone.utc).isoformat()}
        ]
        mock_json_load.return_value = mock_data
        with patch('os.path.exists', return_value=True):
             with patch('os.fstat') as mock_fstat: # Mock fstat for file size check
                mock_fstat.return_value.st_size = 100 # Non-empty
                articles = kb_manager._load_articles()

        mock_file_open.assert_called_once_with(self.test_kb_file_path, 'r', encoding='utf-8')
        self.assertEqual(len(articles), 1)
        self.assertIsInstance(articles[0], KBArticle)
        self.assertEqual(articles[0].title, "T1")

    @patch('os.path.exists', return_value=False)
    @patch('kb_manager._save_articles') # Mock save to check if it's called to create empty file
    def test_load_articles_file_not_found_creates_empty(self, mock_save_articles, mock_os_exists):
        articles = kb_manager._load_articles()
        self.assertEqual(articles, [])
        mock_save_articles.assert_called_once_with([]) # Should create an empty file

    @patch('builtins.open', new_callable=mock_open, read_data="") # Empty file content
    @patch('os.path.exists', return_value=True)
    @patch('os.fstat')
    def test_load_articles_empty_file(self, mock_fstat, mock_os_exists, mock_file_open):
        mock_fstat.return_value.st_size = 0 # Empty file
        articles = kb_manager._load_articles()
        self.assertEqual(articles, [])

    @patch('builtins.open', new_callable=mock_open, read_data="invalid json")
    @patch('os.path.exists', return_value=True)
    @patch('os.fstat')
    @patch('builtins.print')
    def test_load_articles_json_decode_error(self, mock_print, mock_fstat, mock_os_exists, mock_file_open):
        mock_fstat.return_value.st_size = 100 # Non-empty
        with patch('json.load', side_effect=json.JSONDecodeError("e","d",0)):
            articles = kb_manager._load_articles()
        self.assertEqual(articles, [])
        mock_print.assert_any_call(unittest.mock.string_containing("Error decoding JSON"))

    @patch('builtins.open', new_callable=mock_open)
    @patch('json.dump')
    def test_save_articles_success(self, mock_json_dump, mock_file_open):
        articles = [KBArticle(title="T1", content="C1", author_user_id="u1")]
        result = kb_manager._save_articles(articles)
        self.assertTrue(result)
        mock_file_open.assert_called_once_with(self.test_kb_file_path, 'w', encoding='utf-8')
        # json.dump is called with a list of dicts
        mock_json_dump.assert_called_once_with([articles[0].to_dict()], mock_file_open.return_value, indent=4, ensure_ascii=False)

    @patch('builtins.open', side_effect=IOError("Disk full"))
    def test_save_articles_io_error(self, mock_file_open):
        articles = [KBArticle(title="T1", content="C1", author_user_id="u1")]
        result = kb_manager._save_articles(articles)
        self.assertFalse(result)

    @patch('kb_manager._load_articles', return_value=[])
    @patch('kb_manager._save_articles', return_value=True)
    def test_create_article_success(self, mock_save, mock_load):
        article = kb_manager.create_article("New Title", "New Content", "author1", ["key"], "Cat1")
        self.assertIsNotNone(article)
        self.assertEqual(article.title, "New Title")
        mock_load.assert_called_once()
        # _save_articles is called with a list containing the new article
        self.assertTrue(mock_save.call_args[0][0][0].title == "New Title")

    def test_create_article_validation_error_from_model(self):
        # KBArticle model validates title, content, author_user_id are non-empty
        with patch('builtins.print') as mock_print: # Suppress error print from manager
             article = kb_manager.create_article("", "Content", "author")
        self.assertIsNone(article)


    @patch('kb_manager._load_articles')
    def test_get_article(self, mock_load):
        a1 = KBArticle(article_id="kb1", title="T1", content="C1", author_user_id="u1")
        a2 = KBArticle(article_id="kb2", title="T2", content="C2", author_user_id="u2")
        mock_load.return_value = [a1, a2]

        self.assertEqual(kb_manager.get_article("kb1"), a1)
        self.assertIsNone(kb_manager.get_article("kb3"))

    @patch('kb_manager._load_articles')
    def test_list_articles(self, mock_load):
        a1_time = datetime.now(timezone.utc) - timedelta(hours=1)
        a2_time = datetime.now(timezone.utc)
        a1 = KBArticle(article_id="kb1", title="Alpha", content="C1", author_user_id="u1", updated_at=a1_time)
        a2 = KBArticle(article_id="kb2", title="Beta", content="C2", author_user_id="u2", updated_at=a2_time)
        mock_load.return_value = [a1, a2]

        # Default sort (updated_at desc)
        articles = kb_manager.list_articles()
        self.assertEqual(articles, [a2, a1])

        # Sort by title asc
        articles_title = kb_manager.list_articles(sort_by='title', reverse=False)
        self.assertEqual(articles_title, [a1, a2])

        # Empty list
        mock_load.return_value = []
        self.assertEqual(kb_manager.list_articles(), [])


    @patch('kb_manager._load_articles')
    @patch('kb_manager._save_articles', return_value=True)
    @patch('kb_manager.datetime') # Mock datetime.now for updated_at
    def test_update_article_success(self, mock_datetime, mock_save, mock_load):
        fixed_now = datetime.now(timezone.utc)
        mock_datetime.now.return_value = fixed_now

        a1 = KBArticle(article_id="kb1", title="Old Title", content="Old Content", author_user_id="u1")
        mock_load.return_value = [a1]

        updated_article = kb_manager.update_article("kb1", title="New Title", category="Updated Cat")
        self.assertIsNotNone(updated_article)
        self.assertEqual(updated_article.title, "New Title")
        self.assertEqual(updated_article.category, "Updated Cat")
        self.assertEqual(updated_article.content, "Old Content") # Unchanged
        self.assertEqual(updated_article.updated_at, fixed_now)
        mock_save.assert_called_once()
        # Check that the saved article is the updated one
        self.assertEqual(mock_save.call_args[0][0][0].title, "New Title")

    def test_update_article_not_found(self):
        with patch('kb_manager._load_articles', return_value=[]):
            updated = kb_manager.update_article("kb_nonexistent", title="New")
        self.assertIsNone(updated)

    @patch('kb_manager._load_articles')
    @patch('kb_manager._save_articles', return_value=True)
    def test_delete_article_success(self, mock_save, mock_load):
        a1 = KBArticle(article_id="kb_del1", title="To Delete", content="C", author_user_id="u")
        mock_load.return_value = [a1]

        result = kb_manager.delete_article("kb_del1")
        self.assertTrue(result)
        mock_save.assert_called_once_with([]) # Called with empty list

    def test_delete_article_not_found(self):
        with patch('kb_manager._load_articles', return_value=[]):
            result = kb_manager.delete_article("kb_del_nonexistent")
        self.assertFalse(result)

    @patch('kb_manager._load_articles')
    def test_search_articles(self, mock_load):
        articles_data = [
            KBArticle(title="VPN Guide", content="Setup remote access", keywords=["vpn", "network"], author_user_id="u1"),
            KBArticle(title="Printer Fix", content="How to fix paper jams", keywords=["printer", "hardware"], author_user_id="u2"),
            KBArticle(title="Remote Desktop", content="Using RDP for access", keywords=["remote", "desktop"], author_user_id="u1")
        ]
        mock_load.return_value = articles_data

        # Match title
        results = kb_manager.search_articles("VPN")
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0].title, "VPN Guide")

        # Match content
        results = kb_manager.search_articles("paper jams")
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0].title, "Printer Fix")

        # Match keyword
        results = kb_manager.search_articles("remote")
        self.assertEqual(len(results), 2) # VPN Guide, Remote Desktop
        titles = {r.title for r in results}
        self.assertIn("VPN Guide", titles)
        self.assertIn("Remote Desktop", titles)

        # Case-insensitive
        results = kb_manager.search_articles("vpn guide")
        self.assertEqual(len(results), 1)

        # No match
        results = kb_manager.search_articles("nonexistentXYZ")
        self.assertEqual(len(results), 0)

        # Empty query
        results = kb_manager.search_articles("")
        self.assertEqual(len(results), 0)
        results = kb_manager.search_articles("   ")
        self.assertEqual(len(results), 0)

        # Specific search fields
        results = kb_manager.search_articles("VPN", search_fields=['title'])
        self.assertEqual(len(results), 1)
        results = kb_manager.search_articles("VPN", search_fields=['content']) # VPN not in content of "VPN Guide"
        self.assertEqual(len(results), 0)
        results = kb_manager.search_articles("vpn", search_fields=['keywords'])
        self.assertEqual(len(results), 1)


if __name__ == '__main__':
    unittest.main()
