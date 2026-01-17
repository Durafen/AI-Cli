"""Unit tests for GLM provider."""

import json
import os
import unittest
import urllib.error
from unittest.mock import Mock, patch

from ai_cli.providers.glm import GLMProvider
from ai_cli.exceptions import ProviderError


class TestGLMProvider(unittest.TestCase):
    """Test cases for GLMProvider."""

    def setUp(self):
        """Set up test fixtures."""
        self.provider = GLMProvider()

    def tearDown(self):
        """Clean up environment variables."""
        for key in ["ZHIPU_API_KEY", "GLM_API_KEY"]:
            os.environ.pop(key, None)

    def test_is_available_with_zhipu_key(self):
        """Test is_available returns True when ZHIPU_API_KEY is set."""
        os.environ["ZHIPU_API_KEY"] = "test-key"
        self.assertTrue(self.provider.is_available())

    def test_is_available_with_glm_key(self):
        """Test is_available returns True when GLM_API_KEY is set."""
        os.environ["GLM_API_KEY"] = "test-key"
        self.assertTrue(self.provider.is_available())

    def test_is_available_without_key(self):
        """Test is_available returns False when no API key is set."""
        self.assertFalse(self.provider.is_available())

    def test_api_key_property_zhipu_takes_precedence(self):
        """Test that ZHIPU_API_KEY takes precedence over GLM_API_KEY."""
        os.environ["ZHIPU_API_KEY"] = "zhipu-key"
        os.environ["GLM_API_KEY"] = "glm-key"
        self.assertEqual(self.provider.api_key, "zhipu-key")

    def test_api_key_property_fallback_to_glm(self):
        """Test that GLM_API_KEY is used when ZHIPU_API_KEY is not set."""
        os.environ["GLM_API_KEY"] = "glm-key"
        self.assertEqual(self.provider.api_key, "glm-key")

    def test_api_key_from_init(self):
        """Test that API key can be set via init parameter."""
        provider = GLMProvider(api_key="init-key")
        self.assertEqual(provider.api_key, "init-key")

    @patch("ai_cli.providers.glm.urllib.request.urlopen")
    def test_call_success(self, mock_urlopen):
        """Test successful API call returns content."""
        os.environ["ZHIPU_API_KEY"] = "test-key"

        mock_response = Mock()
        mock_response.read.return_value = json.dumps({
            "choices": [{"message": {"content": "Test response"}}]
        }).encode()
        mock_response.__enter__ = Mock(return_value=mock_response)
        mock_response.__exit__ = Mock(return_value=False)
        mock_urlopen.return_value = mock_response

        result = self.provider.call("glm-4.7", "Hello")
        self.assertEqual(result, "Test response")

        # Verify request was made correctly
        call_args = mock_urlopen.call_args
        req = call_args[0][0]
        self.assertEqual(req.full_url, GLMProvider.API_URL)
        self.assertIn("Authorization", req.headers)
        self.assertTrue(req.headers["Authorization"].startswith("Bearer "))

    @patch("ai_cli.providers.glm.urllib.request.urlopen")
    def test_call_with_json_output(self, mock_urlopen):
        """Test that json_output adds response_format to payload."""
        os.environ["ZHIPU_API_KEY"] = "test-key"

        mock_response = Mock()
        mock_response.read.return_value = json.dumps({
            "choices": [{"message": {"content": '{"result": "ok"}'}}]
        }).encode()
        mock_response.__enter__ = Mock(return_value=mock_response)
        mock_response.__exit__ = Mock(return_value=False)
        mock_urlopen.return_value = mock_response

        self.provider.call("glm-4.7", "Return JSON", json_output=True)

        # Verify payload includes response_format
        call_args = mock_urlopen.call_args
        req = call_args[0][0]
        payload = json.loads(req.data)
        self.assertEqual(payload["response_format"], {"type": "json_object"})

    @patch("ai_cli.providers.glm.urllib.request.urlopen")
    def test_call_http_error(self, mock_urlopen):
        """Test that HTTP errors raise ProviderError."""
        os.environ["ZHIPU_API_KEY"] = "test-key"

        error = urllib.error.HTTPError(
            GLMProvider.API_URL,
            401,
            "Unauthorized",
            {},
            None
        )
        mock_urlopen.side_effect = error

        with self.assertRaises(ProviderError) as cm:
            self.provider.call("glm-4.7", "Hello")

        self.assertIn("401", str(cm.exception))

    @patch("ai_cli.providers.glm.urllib.request.urlopen")
    def test_call_url_error(self, mock_urlopen):
        """Test that URL errors raise ProviderError."""
        os.environ["ZHIPU_API_KEY"] = "test-key"

        error = urllib.error.URLError("Connection refused")
        mock_urlopen.side_effect = error

        with self.assertRaises(ProviderError) as cm:
            self.provider.call("glm-4.7", "Hello")

        self.assertIn("Connection error", str(cm.exception))

    def test_call_no_api_key(self):
        """Test that calling without API key raises ProviderError."""
        with self.assertRaises(ProviderError) as cm:
            self.provider.call("glm-4.7", "Hello")

        self.assertIn("not set", str(cm.exception))

    @patch("ai_cli.providers.glm.urllib.request.urlopen")
    def test_call_api_error_response(self, mock_urlopen):
        """Test that API error in response body raises ProviderError."""
        os.environ["ZHIPU_API_KEY"] = "test-key"

        mock_response = Mock()
        mock_response.read.return_value = json.dumps({
            "error": {"message": "Invalid model"}
        }).encode()
        mock_response.__enter__ = Mock(return_value=mock_response)
        mock_response.__exit__ = Mock(return_value=False)
        mock_urlopen.return_value = mock_response

        with self.assertRaises(ProviderError) as cm:
            self.provider.call("glm-4.7", "Hello")

        self.assertIn("Invalid model", str(cm.exception))

    @patch("ai_cli.providers.glm.urllib.request.urlopen")
    def test_call_malformed_response_missing_choices(self, mock_urlopen):
        """Test that missing choices raises ProviderError."""
        os.environ["ZHIPU_API_KEY"] = "test-key"

        mock_response = Mock()
        mock_response.read.return_value = json.dumps({}).encode()
        mock_response.__enter__ = Mock(return_value=mock_response)
        mock_response.__exit__ = Mock(return_value=False)
        mock_urlopen.return_value = mock_response

        with self.assertRaises(ProviderError) as cm:
            self.provider.call("glm-4.7", "Hello")

        self.assertIn("missing 'choices'", str(cm.exception))


if __name__ == "__main__":
    unittest.main()
