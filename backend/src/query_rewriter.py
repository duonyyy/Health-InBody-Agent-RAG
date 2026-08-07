"""Compatibility module alias for :mod:`rag.query_rewriter`."""

import sys

from rag import query_rewriter as _query_rewriter

sys.modules[__name__] = _query_rewriter
