"""Compatibility entrypoint for the relocated Qdrant admin CLI."""

from rag.qdrant.collection_admin import *  # noqa: F401,F403
from rag.qdrant.collection_admin import main


if __name__ == "__main__":
    main()
