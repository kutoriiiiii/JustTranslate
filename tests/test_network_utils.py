# -*- coding: utf-8 -*-
"""Unit tests for network utilities, loopback detection, and proxy routing."""

import unittest
from unittest.mock import MagicMock
from core.network_utils import is_loopback_url, create_httpx_client, open_url_respecting_proxy, StreamController

class TestNetworkUtils(unittest.TestCase):
    """Verifies loopback URL detection and proxy-bypass logic."""

    def test_is_loopback_url_ipv4(self):
        self.assertTrue(is_loopback_url("http://127.0.0.1:8001/v1"))
        self.assertTrue(is_loopback_url("http://127.0.0.1:11434/v1"))
        self.assertTrue(is_loopback_url("http://127.0.0.2:8080/v1"))
        self.assertTrue(is_loopback_url("http://127.255.255.254:8000"))
        self.assertTrue(is_loopback_url("127.0.0.1:8000"))

    def test_is_loopback_url_localhost_and_ipv6(self):
        self.assertTrue(is_loopback_url("http://localhost:8080/v1"))
        self.assertTrue(is_loopback_url("http://localhost:11434"))
        self.assertTrue(is_loopback_url("http://test.localhost:8000"))
        self.assertTrue(is_loopback_url("http://[::1]:8000/v1"))
        self.assertTrue(is_loopback_url("http://0.0.0.0:8000"))

    def test_is_not_loopback_url(self):
        self.assertFalse(is_loopback_url("https://api.deepseek.com/v1"))
        self.assertFalse(is_loopback_url("https://api.openai.com/v1"))
        self.assertFalse(is_loopback_url("http://192.168.1.100:8000"))
        self.assertFalse(is_loopback_url("http://10.0.0.1:8000"))
        self.assertFalse(is_loopback_url("http://example.com"))

    def test_is_loopback_url_empty_or_malformed(self):
        self.assertFalse(is_loopback_url(""))
        self.assertFalse(is_loopback_url(None))
        self.assertFalse(is_loopback_url("   "))
        self.assertFalse(is_loopback_url("://malformed"))

    def test_create_httpx_client_trust_env_routing(self):
        # Loopback URL must have trust_env=False to bypass environment proxy
        client_local = create_httpx_client("http://127.0.0.1:8001/v1")
        self.assertFalse(client_local._trust_env)
        client_local.close()

        # Remote URL must preserve trust_env=True to respect environment proxy
        client_remote = create_httpx_client("https://api.deepseek.com/v1")
        self.assertTrue(client_remote._trust_env)
        client_remote.close()

    def test_stream_controller_abort(self):
        controller = StreamController()
        mock_resp = MagicMock()
        mock_client = MagicMock()

        controller.active_response = mock_resp
        controller.active_client = mock_client
        self.assertFalse(controller.is_aborted)

        controller.abort()
        self.assertTrue(controller.is_aborted)
        mock_resp.close.assert_called_once()
        mock_client.close.assert_called_once()

if __name__ == "__main__":
    unittest.main()
