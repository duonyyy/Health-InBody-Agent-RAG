"""Compatibility module alias for the relocated :mod:`llm.client` module."""

import sys

from llm import client as _client

# Preserve private helpers and module-level dependencies used by legacy callers
# and tests (for example ``brain._chat_with_ollama`` and ``brain.requests``).
sys.modules[__name__] = _client
