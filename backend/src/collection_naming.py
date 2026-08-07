"""Compatibility module alias for :mod:`rag.qdrant.naming`."""

import sys

from rag.qdrant import naming as _naming

sys.modules[__name__] = _naming
