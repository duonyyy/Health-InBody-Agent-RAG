"""Compatibility module alias for :mod:`rag.search`."""

import sys

from rag import search as _search

sys.modules[__name__] = _search
