# -*- coding: utf-8 -*-
"""Network utility functions for proxy routing, loopback detection, and safe client construction."""

import ipaddress
import urllib.parse
import urllib.request
from typing import Optional, Any
import httpx

LOOPBACK_HOSTNAMES = {"localhost", "127.0.0.1", "::1", "0.0.0.0"}

def is_loopback_url(url: str) -> bool:
    """Returns True if the URL points to a loopback address (e.g. 127.0.0.1, localhost, ::1).
    
    Covers IPv4 127.0.0.0/8, IPv6 ::1, localhost, and *.localhost domains.
    """
    if not url:
        return False
    try:
        url_str = str(url).strip()
        if "://" not in url_str:
            url_str = "http://" + url_str
        parsed = urllib.parse.urlparse(url_str)
        hostname = parsed.hostname
        if not hostname:
            return False
        hostname = hostname.lower().strip()
        if hostname in LOOPBACK_HOSTNAMES or hostname.endswith(".localhost"):
            return True
        try:
            ip = ipaddress.ip_address(hostname)
            return ip.is_loopback
        except ValueError:
            return False
    except Exception:
        return False

def create_httpx_client(url: str, timeout: Optional[httpx.Timeout] = None, **kwargs) -> httpx.Client:
    """Creates an httpx.Client configured with proxy bypass for loopback targets, 
    while preserving environment proxy support (trust_env=True) for remote targets.
    """
    if is_loopback_url(url):
        # Explicitly bypass system/environment proxies for loopback endpoints
        return httpx.Client(timeout=timeout, proxy=None, trust_env=False, **kwargs)
    else:
        # Respect system/environment proxies for remote endpoints
        return httpx.Client(timeout=timeout, trust_env=True, **kwargs)

def open_url_respecting_proxy(req_or_url: Any, timeout: float = 3.0):
    """Urllib helper that bypasses proxy for loopback URLs and respects proxy for remote URLs."""
    url = req_or_url.full_url if hasattr(req_or_url, "full_url") else str(req_or_url)
    if is_loopback_url(url):
        opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
        return opener.open(req_or_url, timeout=timeout)
    else:
        return urllib.request.urlopen(req_or_url, timeout=timeout)

class StreamController:
    """Thread-safe cancellation controller that can forcibly close active HTTP streaming connections."""

    def __init__(self):
        self.is_aborted = False
        self.active_response: Optional[httpx.Response] = None
        self.active_client: Optional[httpx.Client] = None

    def abort(self):
        """Immediately sets abort flag and closes the active response and client socket."""
        self.is_aborted = True
        if self.active_response is not None:
            try:
                self.active_response.close()
            except Exception:
                pass
        if self.active_client is not None:
            try:
                self.active_client.close()
            except Exception:
                pass
