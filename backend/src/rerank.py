"""Compatibility module alias for :mod:`rag.rerank`."""

import sys

from rag import rerank as _rerank

sys.modules[__name__] = _rerank
