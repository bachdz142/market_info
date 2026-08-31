"""Import this module first, before anything else, in every real entry
point (service.py, conftest.py, and this package's own agent/crawler.py).

This machine's Python 3.11 (built from source via Homebrew, no bottle for
this old Intel Mac/macOS 13.2.1) doesn't wire OpenSSL up to any trust
store, so ssl.create_default_context() loads zero CA certs by default.
aiohttp (which crawl4ai uses) caches its default verified SSL context as a
module-level global at aiohttp's OWN import time
(aiohttp/connector.py: _SSL_CONTEXT_VERIFIED = _make_ssl_context(True)) —
so setting SSL_CERT_FILE after anything has transitively imported aiohttp
(e.g. langchain_groq/langchain_tavily, both imported by agent.graph) is
too late and has no effect. Without this, every HTTPS request through
aiohttp fails with a misleading "self-signed certificate in certificate
chain" error, even though requests/urllib3 (which bundle certifi
explicitly) work fine against the same host.

A single shared module — imported first, everywhere — is the only way to
guarantee this runs before that first aiohttp import, regardless of which
entry point starts the process or what import order it uses.
"""

import os

import certifi

os.environ.setdefault("SSL_CERT_FILE", certifi.where())
