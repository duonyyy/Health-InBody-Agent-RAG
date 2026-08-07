"""Compatibility module alias for :mod:`rag.vector_metadata`."""

import sys

from rag import vector_metadata as _vector_metadata

sys.modules[__name__] = _vector_metadata
