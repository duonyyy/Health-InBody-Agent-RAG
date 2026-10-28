"""Production WSGI entrypoint that fails fast when the model cannot load."""

from serve_model import app, load_model


if not load_model():
    raise RuntimeError("Embedding model failed to load")
