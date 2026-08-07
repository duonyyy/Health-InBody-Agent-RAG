"""Compatibility module alias for the relocated :mod:`llm.summarizer` module."""

import sys

from llm import summarizer as _summarizer

sys.modules[__name__] = _summarizer
