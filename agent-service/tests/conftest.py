"""Pytest fixtures for agent-service tests."""

import os
import pytest

# Disable external service connections during unit tests
os.environ["BM25_AUTOLOAD"] = "false"
os.environ["REDIS_HOST"] = ""
os.environ["LLM_PROVIDER"] = "none"
