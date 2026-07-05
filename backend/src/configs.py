"""Shared runtime defaults for the Health/InBody backend.

Keep common service names and collection defaults here so API, tasks, search,
and import scripts do not silently drift apart.
"""

import os

DEFAULT_COLLECTION_NAME = os.getenv("QDRANT_COLLECTION_NAME", "nmk_chatbot_collection")
DEFAULT_VECTOR_SIZE = int(os.getenv("VECTOR_SIZE", "1024"))
DEFAULT_QDRANT_URL = os.getenv("QDRANT_URL", "http://qdrant-db:6333")

DEFAULT_DATABASE_URL = os.getenv(
    "DATABASE_URL",
    "postgresql+psycopg2://health_user:health_password@postgres-db:5432/health_inbody",
)

DEFAULT_CELERY_BROKER_URL = os.getenv("CELERY_BROKER_URL", "redis://valkey-db:6379/0")
DEFAULT_CELERY_RESULT_BACKEND = os.getenv(
    "CELERY_RESULT_BACKEND",
    DEFAULT_CELERY_BROKER_URL,
)
