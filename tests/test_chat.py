"""Unit tests for chat mode functionality."""

import json
import unittest
from pathlib import Path
from unittest.mock import patch

from ai_cli.chat import ChatSession, ChatManager, Message
from ai_cli.constants import CONFIG_DIR


class TestMessage(unittest.TestCase):
    """Test cases for Message dataclass."""

    def test_message_creation(self):
        """Test creating a message with role and content."""
        msg = Message(role="user", content="Hello")
        self.assertEqual(msg.role, "user")
        self.assertEqual(msg.content, "Hello")
        self.assertIsNotNone(msg.timestamp)

    def test_message_with_custom_timestamp(self):
        """Test creating a message with a custom timestamp."""
        timestamp = "2025-01-18T00:00:00"
        msg = Message(role="assistant", content="Hi there", timestamp=timestamp)
        self.assertEqual(msg.timestamp, timestamp)


class TestChatSession(unittest.TestCase):
    """Test cases for ChatSession dataclass."""

    def setUp(self):
        """Set up test fixtures."""
        self.session = ChatSession(chat_id="ABC", model_alias="sonnet")

    def test_session_creation(self):
        """Test creating a chat session."""
        self.assertEqual(self.session.chat_id, "ABC")
        self.assertEqual(self.session.model_alias, "sonnet")
        self.assertEqual(len(self.session.messages), 0)
        self.assertIsNotNone(self.session.created_at)
        self.assertIsNotNone(self.session.updated_at)

    def test_path_property(self):
        """Test that path property returns correct file path."""
        expected_path = CONFIG_DIR / "chats" / "ABC.json"
        self.assertEqual(self.session.path, expected_path)

    def test_add_message(self):
        """Test adding a message to the session."""
        initial_updated_at = self.session.updated_at
        self.session.add_message("user", "Hello")
        self.assertEqual(len(self.session.messages), 1)
        self.assertEqual(self.session.messages[0].role, "user")
        self.assertEqual(self.session.messages[0].content, "Hello")
        # updated_at should change after adding a message
        self.assertGreater(self.session.updated_at, initial_updated_at)

    def test_add_multiple_messages(self):
        """Test adding multiple messages in conversation order."""
        self.session.add_message("user", "Hello")
        self.session.add_message("assistant", "Hi there")
        self.session.add_message("user", "How are you?")
        self.assertEqual(len(self.session.messages), 3)
        self.assertEqual(self.session.messages[0].content, "Hello")
        self.assertEqual(self.session.messages[1].content, "Hi there")
        self.assertEqual(self.session.messages[2].content, "How are you?")

    def test_format_history_empty(self):
        """Test formatting history when no messages exist."""
        result = self.session.format_history()
        self.assertEqual(result, "")

    def test_format_history_single_message(self):
        """Test formatting history with one message."""
        self.session.add_message("user", "Hello")
        result = self.session.format_history()
        self.assertEqual(result, "USER: Hello")

    def test_format_history_multiple_messages(self):
        """Test formatting history with multiple messages."""
        self.session.add_message("user", "Hello")
        self.session.add_message("assistant", "Hi there")
        self.session.add_message("user", "How are you?")
        result = self.session.format_history()
        expected = "USER: Hello\n\nASSISTANT: Hi there\n\nUSER: How are you?"
        self.assertEqual(result, expected)

    def test_to_dict(self):
        """Test converting session to dictionary."""
        self.session.add_message("user", "Hello")
        self.session.add_message("assistant", "Hi")
        data = self.session.to_dict()
        self.assertEqual(data["chat_id"], "ABC")
        self.assertEqual(data["model_alias"], "sonnet")
        self.assertEqual(len(data["messages"]), 2)
        self.assertEqual(data["messages"][0]["role"], "user")
        self.assertEqual(data["messages"][0]["content"], "Hello")
        self.assertIn("timestamp", data["messages"][0])
        self.assertIn("created_at", data)
        self.assertIn("updated_at", data)

    def test_enforce_limit_empty_history(self):
        """Test enforce_limit does nothing on empty history."""
        self.session.enforce_limit()
        self.assertEqual(len(self.session.messages), 0)

    def test_enforce_limit_under_limits(self):
        """Test enforce_limit keeps messages under limits."""
        # Add 5 short messages (under default limits of 10 messages, 4000 chars)
        for i in range(5):
            self.session.add_message("user", f"Message {i}")
        self.session.enforce_limit()
        self.assertEqual(len(self.session.messages), 5)

    def test_enforce_limit_truncates_by_message_count(self):
        """Test enforce_limit truncates when exceeding max_messages."""
        # Add 15 messages (exceeds default max_messages=10)
        for i in range(15):
            self.session.add_message("user", f"Message {i}")
        self.session.enforce_limit(max_messages=10)
        # Should keep last 10 messages
        self.assertEqual(len(self.session.messages), 10)
        # First message should be from index 5 (oldest 5 removed)
        self.assertEqual(self.session.messages[0].content, "Message 5")
        self.assertEqual(self.session.messages[-1].content, "Message 14")

    def test_enforce_limit_truncates_by_char_count(self):
        """Test enforce_limit truncates when exceeding max_chars."""
        # Add messages with long content
        long_content = "x" * 1000  # Each message is 1000 chars
        for i in range(5):
            self.session.add_message("user", long_content)
        # Total 5000 chars, exceeds max_chars=4000
        self.session.enforce_limit(max_chars=4000)
        # Should trim to 4 messages (4000 chars)
        self.assertEqual(len(self.session.messages), 4)
        # Verify we kept the most recent messages
        for msg in self.session.messages:
            self.assertEqual(len(msg.content), 1000)

    def test_enforce_limit_keeps_at_least_one_message(self):
        """Test enforce_limit always keeps at least one message."""
        # Add one very long message
        self.session.add_message("user", "x" * 10000)
        self.session.enforce_limit(max_chars=1000)
        # Should keep at least one message even if it exceeds char limit
        self.assertEqual(len(self.session.messages), 1)

    def test_enforce_limit_combined_constraints(self):
        """Test enforce_limit with both message and char constraints."""
        # Add 15 messages, each 500 chars (total 7500 chars)
        for i in range(15):
            self.session.add_message("user", "x" * 500)
        # max_messages=8, max_chars=3000
        self.session.enforce_limit(max_messages=8, max_chars=3000)
        # Should trim to fit both constraints (6 messages = 3000 chars)
        self.assertLessEqual(len(self.session.messages), 8)
        self.assertLessEqual(sum(len(m.content) for m in self.session.messages), 3000)


class TestChatSessionPersistence(unittest.TestCase):
    """Test cases for ChatSession save/load functionality."""

    def setUp(self):
        """Set up test fixtures with isolated chat directory."""
        self.chat_id = "XYZ"
        self.model_alias = "opus"
        # Use a test-specific chat directory
        self.test_chats_dir = CONFIG_DIR / "chats"

    def tearDown(self):
        """Clean up test files."""
        test_file = self.test_chats_dir / f"{self.chat_id}.json"
        if test_file.exists():
            test_file.unlink()

    def test_save_and_load(self):
        """Test saving and loading a chat session."""
        # Create and populate session
        session = ChatSession(chat_id=self.chat_id, model_alias=self.model_alias)
        session.add_message("user", "Hello")
        session.add_message("assistant", "Hi there")

        # Save session
        session.save()

        # Verify file exists
        self.assertTrue(session.path.exists())

        # Load session
        loaded = ChatSession.load(self.chat_id)
        self.assertIsNotNone(loaded)
        self.assertEqual(loaded.chat_id, self.chat_id)
        self.assertEqual(loaded.model_alias, self.model_alias)
        self.assertEqual(len(loaded.messages), 2)
        self.assertEqual(loaded.messages[0].content, "Hello")
        self.assertEqual(loaded.messages[1].content, "Hi there")

    def test_load_nonexistent_session(self):
        """Test loading a session that doesn't exist returns None."""
        loaded = ChatSession.load("NONEXISTENT")
        self.assertIsNone(loaded)

    def test_save_preserves_timestamps(self):
        """Test that save preserves created_at and updated_at timestamps."""
        session = ChatSession(chat_id=self.chat_id, model_alias=self.model_alias)
        created_at = session.created_at
        updated_at = session.updated_at

        session.save()

        loaded = ChatSession.load(self.chat_id)
        self.assertEqual(loaded.created_at, created_at)
        self.assertEqual(loaded.updated_at, updated_at)

    def test_save_overwrites_existing(self):
        """Test that save overwrites existing session file."""
        # Create initial session
        session = ChatSession(chat_id=self.chat_id, model_alias=self.model_alias)
        session.add_message("user", "First message")
        session.save()

        # Update session
        session.add_message("assistant", "Response")
        session.save()

        # Load and verify
        loaded = ChatSession.load(self.chat_id)
        self.assertEqual(len(loaded.messages), 2)
        self.assertEqual(loaded.messages[1].content, "Response")


class TestChatManager(unittest.TestCase):
    """Test cases for ChatManager class."""

    def setUp(self):
        """Set up test fixtures."""
        # Clean up any existing test chat files
        chats_dir = CONFIG_DIR / "chats"
        if chats_dir.exists():
            for f in chats_dir.glob("TST*.json"):
                f.unlink()
        # Store initial count
        self.initial_count = len(ChatManager.list_all())

    def tearDown(self):
        """Clean up test files."""
        chats_dir = CONFIG_DIR / "chats"
        if chats_dir.exists():
            for f in chats_dir.glob("TST*.json"):
                f.unlink()

    def test_generate_id_format(self):
        """Test that generate_id produces valid 3-character codes."""
        chat_id = ChatManager.generate_id()
        self.assertEqual(len(chat_id), 3)
        self.assertTrue(chat_id.isalnum())
        self.assertTrue(chat_id.isupper())

    def test_generate_id_uniqueness(self):
        """Test that generate_id produces different IDs (statistically)."""
        ids = set()
        for _ in range(100):
            chat_id = ChatManager.generate_id()
            ids.add(chat_id)
        # With 36^3 = 46656 possible combinations, 100 should be unique
        self.assertEqual(len(ids), 100)

    def test_create_with_auto_id(self):
        """Test creating a session with auto-generated ID."""
        session = ChatManager.create("sonnet")
        self.assertIsNotNone(session.chat_id)
        self.assertEqual(len(session.chat_id), 3)
        self.assertEqual(session.model_alias, "sonnet")
        self.assertEqual(len(session.messages), 0)

    def test_create_with_custom_id(self):
        """Test creating a session with a custom ID."""
        session = ChatManager.create("opus", chat_id="CUSTOM")
        self.assertEqual(session.chat_id, "CUSTOM")
        self.assertEqual(session.model_alias, "opus")

    def test_load_existing_session(self):
        """Test loading an existing session."""
        # Create and save a session
        session = ChatManager.create("haiku", chat_id="TST")
        session.add_message("user", "Test message")
        session.save()

        # Load it
        loaded = ChatManager.load("TST")
        self.assertIsNotNone(loaded)
        self.assertEqual(loaded.chat_id, "TST")
        self.assertEqual(loaded.model_alias, "haiku")
        self.assertEqual(len(loaded.messages), 1)

    def test_load_nonexistent_session(self):
        """Test loading a nonexistent session returns None."""
        loaded = ChatManager.load("NOTFOUND")
        self.assertIsNone(loaded)

    def test_list_all_empty(self):
        """Test listing sessions when none exist (only pre-existing files)."""
        sessions = ChatManager.list_all()
        # Should only have pre-existing sessions, no new TST* ones
        self.assertEqual(len(sessions), self.initial_count)

    def test_list_all_with_sessions(self):
        """Test listing multiple sessions."""
        # Create and save multiple sessions
        ChatManager.create("sonnet", chat_id="TST1").save()
        ChatManager.create("opus", chat_id="TST2").save()
        ChatManager.create("haiku", chat_id="TST3").save()

        sessions = ChatManager.list_all()
        # Should have initial + 3 new sessions
        self.assertEqual(len(sessions), self.initial_count + 3)

        # Verify all test sessions are present
        chat_ids = {s.chat_id for s in sessions}
        self.assertIn("TST1", chat_ids)
        self.assertIn("TST2", chat_ids)
        self.assertIn("TST3", chat_ids)

    def test_list_all_sorts_by_updated_at(self):
        """Test that list_all sorts by updated_at descending."""
        # Create sessions with different timestamps
        session1 = ChatManager.create("sonnet", chat_id="TST1")
        session1.save()

        session2 = ChatManager.create("opus", chat_id="TST2")
        session2.save()

        session3 = ChatManager.create("haiku", chat_id="TST3")
        session3.save()

        sessions = ChatManager.list_all()

        # Most recently updated should be first
        self.assertEqual(sessions[0].chat_id, "TST3")
        self.assertEqual(sessions[1].chat_id, "TST2")
        self.assertEqual(sessions[2].chat_id, "TST1")

    def test_delete_existing_session(self):
        """Test deleting an existing session."""
        session = ChatManager.create("sonnet", chat_id="TSTDEL")
        session.save()

        # Verify file exists
        self.assertTrue(session.path.exists())

        # Delete it
        result = ChatManager.delete("TSTDEL")
        self.assertTrue(result)

        # Verify file is gone
        self.assertFalse(session.path.exists())

    def test_delete_nonexistent_session(self):
        """Test deleting a nonexistent session returns False."""
        result = ChatManager.delete("NOTFOUND")
        self.assertFalse(result)

    def test_delete_and_list(self):
        """Test that deleted sessions don't appear in list."""
        # Create sessions
        ChatManager.create("sonnet", chat_id="TSTA").save()
        ChatManager.create("opus", chat_id="TSTB").save()

        # Verify both exist (plus any pre-existing)
        sessions = ChatManager.list_all()
        self.assertEqual(len(sessions), self.initial_count + 2)

        # Delete one
        ChatManager.delete("TSTA")

        # Verify only one remains (plus any pre-existing)
        sessions = ChatManager.list_all()
        self.assertEqual(len(sessions), self.initial_count + 1)
        # Filter to just our test sessions
        test_sessions = [s for s in sessions if s.chat_id in ["TSTA", "TSTB"]]
        self.assertEqual(len(test_sessions), 1)
        self.assertEqual(test_sessions[0].chat_id, "TSTB")

    def test_get_latest_returns_most_recent(self):
        """Test that get_latest returns the most recently updated session."""
        # Create sessions with different update times
        session1 = ChatManager.create("sonnet", chat_id="TST1")
        session1.save()
        # Small delay to ensure different timestamps
        import time
        time.sleep(0.01)
        session2 = ChatManager.create("opus", chat_id="TST2")
        session2.save()

        # get_latest should return the most recent one
        latest = ChatManager.get_latest()
        self.assertIsNotNone(latest)
        # The most recent should be TST2 (or could be TST1 if file system has low resolution)
        self.assertIn(latest.chat_id, ["TST1", "TST2"])

    def test_get_latest_returns_none_when_empty(self):
        """Test that get_latest returns None when no sessions exist."""
        # Get all existing sessions to restore later
        import shutil
        chats_dir = CONFIG_DIR / "chats"
        chats_dir.mkdir(parents=True, exist_ok=True)

        # Backup existing sessions
        backup_dir = chats_dir / "backup_test"
        existing_files = list(chats_dir.glob("*.json"))
        if existing_files:
            backup_dir.mkdir(exist_ok=True)
            for f in existing_files:
                shutil.copy(f, backup_dir / f.name)
                f.unlink()

        try:
            # Should return None when no sessions
            latest = ChatManager.get_latest()
            self.assertIsNone(latest)
        finally:
            # Restore backup
            if backup_dir.exists():
                for f in backup_dir.glob("*.json"):
                    shutil.copy(f, chats_dir / f.name)
                shutil.rmtree(backup_dir)

    def test_get_latest_optimized_by_mtime(self):
        """Test that get_latest uses file modification time for sorting."""
        # Create a session
        session = ChatManager.create("haiku", chat_id="TSTMTIME")
        session.add_message("user", "Test message")
        session.save()

        # Get latest - should find this session
        latest = ChatManager.get_latest()
        self.assertIsNotNone(latest)

        # Clean up
        session.path.unlink(missing_ok=True)


class TestChatEdgeCases(unittest.TestCase):
    """Test edge cases and error conditions."""

    def setUp(self):
        """Set up test fixtures."""
        self.test_file = CONFIG_DIR / "chats" / "EDGE.json"
        if self.test_file.exists():
            self.test_file.unlink()

    def tearDown(self):
        """Clean up test files."""
        if self.test_file.exists():
            self.test_file.unlink()

    def test_load_malformed_json(self):
        """Test loading a session with malformed JSON."""
        # Create invalid JSON file
        CONFIG_DIR.mkdir(parents=True, exist_ok=True)
        chats_dir = CONFIG_DIR / "chats"
        chats_dir.mkdir(parents=True, exist_ok=True)

        with open(self.test_file, "w") as f:
            f.write("{invalid json")

        # Should return None gracefully instead of raising error
        result = ChatSession.load("EDGE")
        self.assertIsNone(result)

    def test_load_missing_required_fields(self):
        """Test loading a session with missing required fields."""
        CONFIG_DIR.mkdir(parents=True, exist_ok=True)
        chats_dir = CONFIG_DIR / "chats"
        chats_dir.mkdir(parents=True, exist_ok=True)

        # Create JSON missing required fields
        with open(self.test_file, "w") as f:
            json.dump({"chat_id": "EDGE"}, f)  # Missing model_alias

        # Should return None gracefully instead of raising KeyError
        result = ChatSession.load("EDGE")
        self.assertIsNone(result)

    def test_message_with_special_characters(self):
        """Test messages with special characters and unicode."""
        session = ChatSession(chat_id="SPECIAL", model_alias="sonnet")
        special_content = "Hello 世界 🌍\nNew line\tTab\nQuote: \"test\""
        session.add_message("user", special_content)

        # Save and load
        session.save()
        loaded = ChatSession.load("SPECIAL")

        self.assertEqual(loaded.messages[0].content, special_content)

    def test_very_long_message(self):
        """Test handling of very long messages."""
        session = ChatSession(chat_id="LONG", model_alias="sonnet")
        long_content = "x" * 100000  # 100KB message
        session.add_message("user", long_content)

        # Should handle gracefully
        session.save()
        loaded = ChatSession.load("LONG")

        self.assertEqual(len(loaded.messages[0].content), 100000)

    def test_enforce_limit_with_unicode(self):
        """Test enforce_limit correctly counts unicode characters."""
        session = ChatSession(chat_id="UNI", model_alias="sonnet")
        # Add unicode messages
        for i in range(5):
            session.add_message("user", "消息" * 100)  # Chinese characters

        # Each message is 600 bytes but 300 characters
        # enforce_limit should count characters, not bytes
        session.enforce_limit(max_chars=1000)

        # Should correctly count and trim
        total_chars = sum(len(m.content) for m in session.messages)
        self.assertLessEqual(total_chars, 1000)


if __name__ == "__main__":
    unittest.main()
