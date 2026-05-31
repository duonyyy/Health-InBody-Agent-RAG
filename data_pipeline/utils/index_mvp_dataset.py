"""Send the embedding dataset to the backend indexing API in batches."""

from __future__ import annotations

import argparse
import json
import time
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any


def load_jsonl(path: Path):
    with path.open("r", encoding="utf-8") as file:
        for line in file:
            line = line.strip()
            if line:
                yield json.loads(line)


def post_json(url: str, payload: dict[str, Any], timeout: int = 120) -> dict[str, Any]:
    data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    request = urllib.request.Request(
        url,
        data=data,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            body = response.read().decode("utf-8")
            return json.loads(body) if body else {}
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"POST {url} failed with {exc.code}: {detail}") from exc


def batched(items, batch_size: int):
    batch = []
    for item in items:
        batch.append(item)
        if len(batch) >= batch_size:
            yield batch
            batch = []
    if batch:
        yield batch


def index_dataset(
    input_path: Path,
    api_url: str,
    collection_name: str,
    vector_size: int,
    batch_size: int,
    limit: int | None,
    skip_create: bool,
    sleep_seconds: float,
) -> None:
    api_url = api_url.rstrip("/")

    if not skip_create:
        try:
            post_json(
                f"{api_url}/collection/create",
                {
                    "collection_name": collection_name,
                    "vector_size": vector_size,
                },
            )
            print(f"Created collection: {collection_name}")
        except RuntimeError as exc:
            print(f"Collection create skipped/failed: {exc}")

    documents = load_jsonl(input_path)
    if limit is not None:
        documents = (doc for index, doc in enumerate(documents) if index < limit)

    total = 0
    for batch_index, batch in enumerate(batched(documents, batch_size), start=1):
        result = post_json(
            f"{api_url}/documents/index",
            {
                "collection_name": collection_name,
                "documents": batch,
            },
            timeout=600,
        )
        total += len(batch)
        print(f"Indexed batch {batch_index}: {len(batch)} docs, total={total}")
        if result.get("status") is not True:
            print(f"Backend response: {result}")
        if sleep_seconds:
            time.sleep(sleep_seconds)

    print(f"Done. Sent {total} documents to {collection_name}.")


def parse_args() -> argparse.Namespace:
    default_root = Path(__file__).resolve().parents[1]
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--input",
        type=Path,
        default=default_root / "dataset" / "processed" / "embedding_documents.jsonl",
    )
    parser.add_argument("--api-url", default="http://localhost:8000")
    parser.add_argument("--collection-name", default="nmk_chatbot_collection")
    parser.add_argument("--vector-size", type=int, default=1024)
    parser.add_argument("--batch-size", type=int, default=50)
    parser.add_argument("--limit", type=int, default=None)
    parser.add_argument("--skip-create", action="store_true")
    parser.add_argument("--sleep-seconds", type=float, default=0.0)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    index_dataset(
        input_path=args.input,
        api_url=args.api_url,
        collection_name=args.collection_name,
        vector_size=args.vector_size,
        batch_size=args.batch_size,
        limit=args.limit,
        skip_create=args.skip_create,
        sleep_seconds=args.sleep_seconds,
    )


if __name__ == "__main__":
    main()
