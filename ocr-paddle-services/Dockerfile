FROM python:3.10-slim AS builder

WORKDIR /build
RUN python -m venv /opt/venv
COPY pyproject.toml .
COPY src ./src
RUN /opt/venv/bin/pip install --no-cache-dir .

FROM python:3.10-slim

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    poppler-utils \
    libgl1 \
    libglib2.0-0 \
    libgomp1 \
    libsm6 \
    libxext6 \
    libxrender1 \
    && rm -rf /var/lib/apt/lists/*
COPY --from=builder /opt/venv /opt/venv
RUN useradd --create-home --uid 10001 ocr
ENV PATH="/opt/venv/bin:${PATH}" \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

USER ocr

EXPOSE 18100

CMD ["uvicorn", "inbody_ocr.main:app", "--host", "0.0.0.0", "--port", "18100"]
