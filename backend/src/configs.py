"""Shared runtime defaults for the Health/InBody backend.

Keep common service names and collection defaults here so API, tasks, search,
and import scripts do not silently drift apart.
"""

import os

DEFAULT_COLLECTION_NAME = os.getenv("QDRANT_COLLECTION_NAME", "nmk_chatbot_active")
DEFAULT_COLLECTION_ALIAS = os.getenv(
    "QDRANT_COLLECTION_ALIAS",
    "nmk_chatbot_active",
)
DEFAULT_CORPUS_VERSION = os.getenv("CORPUS_VERSION", "").strip()
DEFAULT_VECTOR_SIZE = int(os.getenv("VECTOR_SIZE", "1024"))
DEFAULT_QDRANT_URL = os.getenv("QDRANT_URL", "http://qdrant-db:6333")
DEFAULT_QDRANT_TIMEOUT = float(
    os.getenv("QDRANT_TIMEOUT_SECONDS", "30")
)
DEFAULT_QDRANT_SEARCH_TIMEOUT = float(
    os.getenv("QDRANT_SEARCH_TIMEOUT_SECONDS", "5")
)

DEFAULT_DATABASE_URL = os.getenv(
    "DATABASE_URL",
    "postgresql+psycopg2://health_user:change-me@localhost:5432/health_inbody",
)

DEFAULT_CELERY_BROKER_URL = os.getenv("CELERY_BROKER_URL", "redis://valkey-db:6379/0")
DEFAULT_CELERY_RESULT_BACKEND = os.getenv(
    "CELERY_RESULT_BACKEND",
    DEFAULT_CELERY_BROKER_URL,
)
