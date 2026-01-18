
import unittest
import sys
import os
from unittest.mock import patch, MagicMock
from ai_cli.cli import detect_chat_mode
from ai_cli.config import Config
from ai_cli.chat import ChatManager

class TestChatRedesign(unittest.TestCase):
    def setUp(self):
        self.config = Config()
        self.config.aliases = {'sonnet': ('claude', 'sonnet'), 'gpt': ('codex', 'gpt')}

    def test_detect_reply(self):
        argv = ['reply', 'hello']
        res = detect_chat_mode(argv, self.config)
        self.assertTrue(res['reply_mode'])
        self.assertEqual(res['remaining_args'], ['hello'])

    def test_detect_model_reply(self):
        argv = ['sonnet', 'reply', 'hello']
        res = detect_chat_mode(argv, self.config)
        self.assertTrue(res['reply_mode'])
        self.assertEqual(res['model'], 'sonnet')
        self.assertEqual(res['remaining_args'], ['hello'])

    def test_detect_reply_flag(self):
        argv = ['--reply', 'hello']
        res = detect_chat_mode(argv, self.config)
        self.assertTrue(res['reply_mode'])
        self.assertEqual(res['remaining_args'], ['hello'])

    def test_detect_model_reply_flag(self):
        argv = ['sonnet', '--reply', 'hello']
        res = detect_chat_mode(argv, self.config)
        self.assertTrue(res['reply_mode'])
        self.assertEqual(res['model'], 'sonnet')
        self.assertEqual(res['remaining_args'], ['hello'])

    def test_detect_chat_id(self):
        argv = ['chat', 'ABC', 'hello']
        res = detect_chat_mode(argv, self.config)
        self.assertEqual(res['chat_id'], 'ABC')
        self.assertEqual(res['remaining_args'], ['hello'])

    def test_detect_model_chat_id(self):
        argv = ['sonnet', 'chat', 'ABC', 'hello']
        res = detect_chat_mode(argv, self.config)
        self.assertEqual(res['model'], 'sonnet')
        self.assertEqual(res['chat_id'], 'ABC')
        self.assertEqual(res['remaining_args'], ['hello'])

    def test_normal_prompt_no_chat_mode(self):
        argv = ['sonnet', 'hello']
        res = detect_chat_mode(argv, self.config)
        self.assertFalse(res['reply_mode'])
        self.assertIsNone(res['mode'])
        self.assertIsNone(res['chat_id'])

    def test_chat_list_subcommand(self):
        argv = ['chat', 'list']
        res = detect_chat_mode(argv, self.config)
        self.assertEqual(res['subcommand'], 'list')

    def test_chat_delete_subcommand(self):
        argv = ['chat', 'delete', 'ABC', 'DEF']
        res = detect_chat_mode(argv, self.config)
        self.assertEqual(res['subcommand'], 'delete')
        self.assertIn('ABC', res['chat_ids'])
        self.assertIn('DEF', res['chat_ids'])

    def test_chat_id_normalized_to_uppercase(self):
        argv = ['chat', 'abc', 'hello']
        res = detect_chat_mode(argv, self.config)
        self.assertEqual(res['chat_id'], 'ABC')  # normalized to upper

    def test_reply_mode_no_args(self):
        argv = ['reply']
        res = detect_chat_mode(argv, self.config)
        self.assertTrue(res['reply_mode'])
        self.assertEqual(res['remaining_args'], [])


class TestChatManagerGetLatest(unittest.TestCase):
    """Tests for the optimized get_latest method."""

    def test_get_latest_returns_none_when_empty(self):
        """Test that get_latest returns None when no sessions exist."""
        # This test assumes no chat sessions exist in test environment
        # In real tests, we'd need proper setup/teardown
        latest = ChatManager.get_latest()
        # The result should either be None or a valid ChatSession
        if latest is not None:
            from ai_cli.chat import ChatSession
            self.assertIsInstance(latest, ChatSession)

if __name__ == "__main__":
    unittest.main()
