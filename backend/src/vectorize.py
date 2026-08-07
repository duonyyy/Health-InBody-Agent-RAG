"""Compatibility module alias for :mod:`rag.qdrant.client`."""

import sys

from rag.qdrant import client as _client

sys.modules[__name__] = _client
