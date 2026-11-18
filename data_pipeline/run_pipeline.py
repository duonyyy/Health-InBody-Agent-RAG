"""Master Data Pipeline Orchestrator for Health/InBody Agent RAG.

Stages:
1. Extract (PyMuPDF with smart kerning & TCVN3 decoding to Markdown)
2. Build (Clean normalization, RAG gatekeeping, Medical seed integration — no fabricated approvals)
3. Chunk (Structure-aware Markdown & contextual breadcrumb injection)
4. Index BM25 (Versioned, fingerprinted, atomic gzip BM25 snapshot — requires explicit corpus_version)
5. Index Qdrant (Staging-only, fail-closed admission, write lease, honest WriteReceipt)
6. Verify (Chunk + BM25 fingerprint verification + versioned release manifest output)

Usage:
    python data_pipeline/run_pipeline.py --all --corpus-version 2026-11-18-v1 --staging-collection nmk_chatbot_staging_20261118
    python data_pipeline/run_pipeline.py --index-bm25 --corpus-version 2026-11-18-v1 --staging-collection nmk_chatbot_staging_20261118
    python data_pipeline/run_pipeline.py --index-qdrant --corpus-version 2026-11-18-v1 --staging-collection nmk_chatbot_staging_20261118 [--dry-run]
"""

from __future__ import annotations

import argparse
import gzip
import hashlib
import json
import logging
import sys
import time
from pathlib import Path
from typing import Any, Dict, List, Optional

# Add parent directory to sys.path so configs and src can be imported cleanly
PIPELINE_ROOT = Path(__file__).resolve().parent
if str(PIPELINE_ROOT) not in sys.path:
    sys.path.insert(0, str(PIPELINE_ROOT))

from configs.pipeline_config import (
    ALL_RAW_SOURCES_PATH,
    ALLOWED_CONTENT_TYPES,
    BACKEND_BM25_SNAPSHOT_PATH,
    CHUNK_OVERLAP,
    CHUNK_SIZE,
    CHUNKS_PATH,
    DEFAULT_BATCH_SIZE,
    DEFAULT_COLLECTION_ALIAS,
    DEFAULT_CORPUS_VERSION,
    DEFAULT_QDRANT_URL,
    DEFAULT_RELEASE_MANIFEST_PATH,
    DEFAULT_STAGING_COLLECTION,
    DEFAULT_VECTOR_SIZE,
    EMBEDDING_API_URL,
    EMBEDDING_DOCUMENTS_PATH,
    EXTRACTED_TEXT_DIR,
    MIN_CHUNK_LENGTH,
    PIPELINE_REPORT_PATH,
    RAG_CORPUS_PATH,
    RAW_DIR,
)
from src.chunkers.markdown_chunker import chunk_document
from src.embedder.client import EmbeddingClient
from src.extractors.pdf_extractor import extract_pdf_to_markdown
from src.indexers.bm25_indexer import export_bm25_snapshot
from src.indexers.qdrant_indexer import QdrantIndexer
from src.ingestion.raw_loader import merge_all
from src.processors.corpus_processor import prepare_dataset
from src.processors.lifecycle_bridge import (
    atomic_write_json,
    build_release_manifest,
    compute_chunk_set_fingerprint,
    current_embedding_config,
    make_release_id,
    save_release_manifest,
    validate_corpus_version,
    verify_staging_write_target,
)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("data_pipeline")


def _sha256_file(path: Path) -> Optional[str]:
    if not path.exists():
        return None
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def load_jsonl(path: Path) -> List[Dict[str, Any]]:
    records = []
    if not path.exists():
        return records
    with path.open("r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                records.append(json.loads(line))
    return records


def save_jsonl(records: List[Dict[str, Any]], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="\n") as f:
        for r in records:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")


# ─────────────────────────────────────────────────────────────────────────────
# STAGE 1: EXTRACT PDF TO STRUCTURED MARKDOWN
# ─────────────────────────────────────────────────────────────────────────────
def run_extract_stage() -> Dict[str, Any]:
    logger.info("=== STAGE 1: Extracting PDFs to Structured Markdown ===")
    start_time = time.time()
    result = extract_pdf_to_markdown(RAW_DIR, EXTRACTED_TEXT_DIR)
    elapsed = round(time.time() - start_time, 2)
    logger.info("Extraction completed in %.2fs: %s", elapsed, result)
    return {"stage": "extract", "ok": True, "elapsed_seconds": elapsed, **result}


# ─────────────────────────────────────────────────────────────────────────────
# STAGE 2: BUILD & NORMALIZE RAG CORPUS
# ─────────────────────────────────────────────────────────────────────────────
def run_build_stage() -> Dict[str, Any]:
    logger.info("=== STAGE 2: Merging Raw Sources & Normalizing Corpus ===")
    start_time = time.time()
    merge_report = ALL_RAW_SOURCES_PATH.parent / "merge_report.json"
    embedding_report = EMBEDDING_DOCUMENTS_PATH.parent / "embedding_report.json"

    merge_all(RAW_DIR, ALL_RAW_SOURCES_PATH, merge_report)
    prepare_dataset(ALL_RAW_SOURCES_PATH, EMBEDDING_DOCUMENTS_PATH, embedding_report)

    RAG_CORPUS_PATH.parent.mkdir(parents=True, exist_ok=True)
    RAG_CORPUS_PATH.write_bytes(EMBEDDING_DOCUMENTS_PATH.read_bytes())

    docs = load_jsonl(EMBEDDING_DOCUMENTS_PATH)
    elapsed = round(time.time() - start_time, 2)
    logger.info(
        "Corpus build completed in %.2fs: %s documents",
        elapsed,
        len(docs),
    )
    return {
        "stage": "build",
        "ok": True,
        "elapsed_seconds": elapsed,
        "document_count": len(docs),
        "corpus_path": str(EMBEDDING_DOCUMENTS_PATH),
        "corpus_sha256": _sha256_file(EMBEDDING_DOCUMENTS_PATH),
    }


# ─────────────────────────────────────────────────────────────────────────────
# STAGE 3: STRUCTURE-AWARE CHUNKING WITH BREADCRUMBS
# ─────────────────────────────────────────────────────────────────────────────
def run_chunk_stage() -> Dict[str, Any]:
    logger.info("=== STAGE 3: Structure-Aware Chunking with Contextual Breadcrumbs ===")
    start_time = time.time()
    docs = load_jsonl(EMBEDDING_DOCUMENTS_PATH)
    if not docs:
        raise RuntimeError(f"Corpus {EMBEDDING_DOCUMENTS_PATH} is empty. Run build first.")

    all_chunks: List[Dict[str, Any]] = []
    type_counts: Dict[str, int] = {}

    for doc in docs:
        chunks = chunk_document(
            doc,
            chunk_size=CHUNK_SIZE,
            chunk_overlap=CHUNK_OVERLAP,
            min_chunk_length=MIN_CHUNK_LENGTH,
        )
        for c in chunks:
            all_chunks.append(c)
            ct = c.get("content_type", "unknown")
            type_counts[ct] = type_counts.get(ct, 0) + 1

    save_jsonl(all_chunks, CHUNKS_PATH)
    fp_info = compute_chunk_set_fingerprint(all_chunks)
    elapsed = round(time.time() - start_time, 2)
    logger.info(
        "Chunking completed in %.2fs: %s documents -> %s chunks (fp=%s)",
        elapsed,
        len(docs),
        len(all_chunks),
        fp_info["chunk_set_fingerprint"][:16],
    )
    return {
        "stage": "chunk",
        "ok": True,
        "elapsed_seconds": elapsed,
        "input_documents": len(docs),
        "total_chunks": len(all_chunks),
        "unique_document_count": fp_info["unique_document_count"],
        "unique_chunk_count": fp_info["unique_chunk_count"],
        "chunk_set_fingerprint": fp_info["chunk_set_fingerprint"],
        "type_counts": type_counts,
        "output_path": str(CHUNKS_PATH),
        "output_sha256": _sha256_file(CHUNKS_PATH),
    }


# ─────────────────────────────────────────────────────────────────────────────
# STAGE 4: EXPORT VERSIONED BM25 SNAPSHOT
# ─────────────────────────────────────────────────────────────────────────────
def run_bm25_stage(
    *,
    corpus_version: Optional[str] = None,
    staging_collection: Optional[str] = None,
    serving_alias: str = DEFAULT_COLLECTION_ALIAS,
    release_id: Optional[str] = None,
    output_path: Optional[Path] = None,
    chunks_path: Optional[Path] = None,
) -> Dict[str, Any]:
    """Xuất bản snapshot BM25 gắn đúng corpus_version, physical_collection và fingerprint."""
    logger.info("=== STAGE 4: Exporting Versioned BM25 Snapshot Artifact ===")
    start_time = time.time()
    verified_version = validate_corpus_version(corpus_version or DEFAULT_CORPUS_VERSION)
    resolved_staging = str(staging_collection or DEFAULT_STAGING_COLLECTION).strip()
    if not resolved_staging:
        raise ValueError(
            "staging_collection (--staging-collection / QDRANT_STAGING_COLLECTION) là bắt buộc "
            "để gắn BM25 snapshot đúng với physical collection phát hành."
        )
    # Offline name/policy validation to ensure staging_collection is not a protected serving alias.
    verify_staging_write_target(
        resolved_staging,
        corpus_version=verified_version,
        require_corpus_version=True,
        dry_run=True,
    )

    source_chunks = Path(chunks_path or CHUNKS_PATH)
    chunks = load_jsonl(source_chunks)
    if not chunks:
        raise RuntimeError(f"Chunks file {source_chunks} is empty. Run chunk first.")

    fp_info = compute_chunk_set_fingerprint(chunks)
    resolved_release_id = release_id or make_release_id(
        verified_version, fp_info["chunk_set_fingerprint"]
    )

    target_output = Path(output_path) if output_path else BACKEND_BM25_SNAPSHOT_PATH
    res_primary = export_bm25_snapshot(
        chunks=chunks,
        output_path=target_output,
        collection_name=serving_alias,
        corpus_version=verified_version,
        physical_collection=resolved_staging,
        release_id=resolved_release_id,
    )

    res_pipeline = None
    if output_path is None:
        pipeline_copy = source_chunks.parent.parent / "processed" / f"bm25_snapshot_{resolved_release_id}.json.gz"
        res_pipeline = export_bm25_snapshot(
            chunks=chunks,
            output_path=pipeline_copy,
            collection_name=serving_alias,
            corpus_version=verified_version,
            physical_collection=resolved_staging,
            release_id=resolved_release_id,
        )

    elapsed = round(time.time() - start_time, 2)
    logger.info("BM25 snapshot export completed in %.2fs", elapsed)
    return {
        "stage": "index_bm25",
        "ok": True,
        "elapsed_seconds": elapsed,
        "corpus_version": verified_version,
        "release_id": resolved_release_id,
        "physical_collection": resolved_staging,
        "backend_snapshot": res_primary,
        "pipeline_snapshot": res_pipeline,
    }


# ─────────────────────────────────────────────────────────────────────────────
# STAGE 5: DIRECT QDRANT STAGING INDEXING
# ─────────────────────────────────────────────────────────────────────────────
def run_qdrant_stage(
    dry_run: bool = False,
    *,
    corpus_version: Optional[str] = None,
    staging_collection: Optional[str] = None,
    release_id: Optional[str] = None,
    chunks_path: Optional[Path] = None,
    lock_dir: Optional[Path] = None,
    indexer: Optional[QdrantIndexer] = None,
    embedder: Optional[EmbeddingClient] = None,
) -> Dict[str, Any]:
    """Đưa vector và payload vào physical staging collection (fail-closed, không tự fallback dry-run)."""
    logger.info("=== STAGE 5: Direct Qdrant Staging Vector Indexing ===")
    start_time = time.time()
    resolved_version = str(corpus_version or DEFAULT_CORPUS_VERSION).strip()
    resolved_staging = str(staging_collection or DEFAULT_STAGING_COLLECTION).strip()

    source_chunks = Path(chunks_path or CHUNKS_PATH)
    chunks = load_jsonl(source_chunks)
    if not chunks:
        raise RuntimeError(f"Chunks file {source_chunks} is empty. Run chunk first.")

    active_embedder = embedder or EmbeddingClient(
        api_url=EMBEDDING_API_URL,
        vector_size=DEFAULT_VECTOR_SIZE,
    )
    active_indexer = indexer or QdrantIndexer(
        url=DEFAULT_QDRANT_URL,
        vector_size=DEFAULT_VECTOR_SIZE,
        lock_dir=lock_dir,
    )

    if dry_run:
        # Validate staging target name/policy offline without touching live Qdrant/Embedder.
        res = active_indexer.index_chunks(
            chunks=chunks,
            embedder=active_embedder,
            collection_name=resolved_staging,
            batch_size=DEFAULT_BATCH_SIZE,
            dry_run=True,
            corpus_version=resolved_version or None,
            release_id=release_id,
        )
        elapsed = round(time.time() - start_time, 2)
        return {
            "stage": "index_qdrant",
            "ok": bool(res.get("ok")),
            "elapsed_seconds": elapsed,
            "qdrant_online": None,
            "embedder_online": None,
            "dry_run": True,
            "result": res,
        }

    # Real write: fail closed! Never silently fall back to dry-run when services are offline.
    qdrant_online = active_indexer.is_available()
    embedder_online = active_embedder.is_available()
    logger.info("Service Status: Qdrant=%s, Embedder=%s", qdrant_online, embedder_online)
    if not qdrant_online or not embedder_online:
        raise RuntimeError(
            f"Từ chối ghi Qdrant thật vì dịch vụ chưa sẵn sàng "
            f"(qdrant_online={qdrant_online}, embedder_online={embedder_online}). "
            "Truyền tường minh --dry-run nếu chỉ muốn kiểm tra offline."
        )

    # Admission gate runs inside both create_collection_if_missing and index_chunks.
    active_indexer.create_collection_if_missing(resolved_staging)
    res = active_indexer.index_chunks(
        chunks=chunks,
        embedder=active_embedder,
        collection_name=resolved_staging,
        batch_size=DEFAULT_BATCH_SIZE,
        dry_run=False,
        corpus_version=resolved_version,
        release_id=release_id,
    )

    elapsed = round(time.time() - start_time, 2)
    logger.info("Qdrant indexing finished in %.2fs: ok=%s status=%s", elapsed, res.get("ok"), res.get("status"))
    return {
        "stage": "index_qdrant",
        "ok": bool(res.get("ok")),
        "elapsed_seconds": elapsed,
        "qdrant_online": qdrant_online,
        "embedder_online": embedder_online,
        "dry_run": False,
        "result": res,
    }


# ─────────────────────────────────────────────────────────────────────────────
# STAGE 6: AUTOMATED QUALITY GATE VERIFICATION & RELEASE MANIFEST
# ─────────────────────────────────────────────────────────────────────────────
def run_verify_stage(
    *,
    corpus_version: Optional[str] = None,
    staging_collection: Optional[str] = None,
    chunks_path: Optional[Path] = None,
    bm25_snapshot_path: Optional[Path] = None,
    release_manifest_path: Optional[Path] = None,
    qdrant_stage_result: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """Xác thực chất lượng chunk, fingerprint khớp với BM25 snapshot và tạo release manifest."""
    logger.info("=== STAGE 6: Automated Quality Gate Verification ===")
    start_time = time.time()
    source_chunks = Path(chunks_path or CHUNKS_PATH)
    snapshot_file = Path(bm25_snapshot_path or BACKEND_BM25_SNAPSHOT_PATH)
    chunks = load_jsonl(source_chunks)
    errors: List[str] = []

    if not chunks:
        errors.append(f"{source_chunks.name} is missing or empty")

    recipe_in_rag = 0
    missing_breadcrumbs = 0
    short_chunks = 0
    counts_by_type: Dict[str, int] = {}

    for idx, c in enumerate(chunks, start=1):
        ct = c.get("content_type")
        if ct not in ALLOWED_CONTENT_TYPES:
            errors.append(f"Chunk {idx}: invalid content_type {ct}")
        else:
            counts_by_type[ct] = counts_by_type.get(ct, 0) + 1
        if ct == "nutrition" and any(w in (c.get("content") or "").lower() for w in ["hầm 45 phút", "muỗng canh"]):
            recipe_in_rag += 1
        if not c.get("breadcrumb"):
            missing_breadcrumbs += 1
        if len(c.get("content") or "") < 40:
            short_chunks += 1

    if recipe_in_rag > 0:
        errors.append(f"Corpus pollution: found {recipe_in_rag} recipe chunks in RAG corpus")
    if missing_breadcrumbs > 0:
        errors.append(f"Found {missing_breadcrumbs} chunks without contextual breadcrumbs")
    if short_chunks > 0:
        errors.append(f"Found {short_chunks} chunks under minimum length threshold")

    chunk_fp = compute_chunk_set_fingerprint(chunks) if chunks else {}
    bm25_info: Dict[str, Any] = {}

    if not snapshot_file.exists():
        errors.append(f"BM25 snapshot not found at {snapshot_file}")
    else:
        try:
            with gzip.open(snapshot_file, "rt", encoding="utf-8") as f:
                snap = json.load(f)
            if snap.get("schema_version") != 1:
                errors.append("BM25 snapshot schema_version != 1")
            snap_docs = snap.get("documents", [])
            if len(snap_docs) != len(chunks):
                errors.append(
                    f"BM25 document count mismatch: {len(snap_docs)} vs {len(chunks)}"
                )
            snap_fp = compute_chunk_set_fingerprint(snap_docs)
            if chunk_fp and snap_fp["chunk_set_fingerprint"] != chunk_fp["chunk_set_fingerprint"]:
                errors.append(
                    "BM25 chunk_set_fingerprint mismatch with chunks.jsonl "
                    f"(bm25={snap_fp['chunk_set_fingerprint'][:16]} != chunks={chunk_fp['chunk_set_fingerprint'][:16]})"
                )
            snap_meta = snap.get("metadata") or {}
            if corpus_version and snap_meta.get("corpus_version") != corpus_version:
                errors.append(
                    f"BM25 corpus_version={snap_meta.get('corpus_version')!r} != expected {corpus_version!r}"
                )
            if staging_collection and snap_meta.get("physical_collection") not in (None, "", staging_collection):
                errors.append(
                    f"BM25 physical_collection={snap_meta.get('physical_collection')!r} != {staging_collection!r}"
                )
            bm25_info = {
                "path": str(snapshot_file),
                "sha256": _sha256_file(snapshot_file),
                "schema_version": snap.get("schema_version"),
                "tokenizer_version": snap_meta.get("tokenizer_version"),
                "document_count": len(snap_docs),
                "chunk_set_fingerprint": snap_fp["chunk_set_fingerprint"],
                "physical_collection": snap_meta.get("physical_collection") or staging_collection,
                "release_id": snap_meta.get("release_id") or snap.get("release_id"),
                "corpus_version": snap_meta.get("corpus_version") or snap.get("corpus_version"),
            }
        except Exception as exc:
            errors.append(f"Failed to read BM25 snapshot: {exc}")

    manifest_written: Optional[str] = None
    resolved_ver = str(corpus_version or bm25_info.get("corpus_version") or DEFAULT_CORPUS_VERSION).strip()
    resolved_col = str(staging_collection or bm25_info.get("physical_collection") or DEFAULT_STAGING_COLLECTION).strip()
    if release_manifest_path is not None and resolved_ver and resolved_col and chunk_fp:
        q_res = (qdrant_stage_result or {}).get("result") or {}
        q_ok = bool((qdrant_stage_result or {}).get("ok")) and not bool((qdrant_stage_result or {}).get("dry_run"))
        manifest = build_release_manifest(
            corpus_version=resolved_ver,
            physical_collection=resolved_col,
            serving_alias=DEFAULT_COLLECTION_ALIAS,
            release_id=bm25_info.get("release_id"),
            source_manifest={
                "path": str(EMBEDDING_DOCUMENTS_PATH),
                "sha256": _sha256_file(EMBEDDING_DOCUMENTS_PATH),
                "counts_by_content_type": counts_by_type,
            },
            chunk_manifest={
                "path": str(source_chunks),
                "sha256": _sha256_file(source_chunks),
                "expected_count": len(chunks),
                "unique_document_count": chunk_fp["unique_document_count"],
                "unique_chunk_count": chunk_fp["unique_chunk_count"],
                "chunk_set_fingerprint": chunk_fp["chunk_set_fingerprint"],
            },
            chunking_config={
                "chunk_size": CHUNK_SIZE,
                "chunk_overlap": CHUNK_OVERLAP,
                "min_chunk_length": MIN_CHUNK_LENGTH,
            },
            embedding_config=current_embedding_config(vector_size=DEFAULT_VECTOR_SIZE),
            bm25_artifact=bm25_info,
            write_receipt={
                key: q_res.get(key)
                for key in (
                    "ok",
                    "status",
                    "attempted_points",
                    "acknowledged_points",
                    "committed_points",
                    "failed_points",
                    "unconfirmed_points",
                    "skipped_points",
                    "conflict_points",
                    "partial_write",
                    "rollback_performed",
                )
                if key in q_res
            },
            build_status="imported" if (not errors and q_ok) else ("building" if not errors else "failed"),
            publication_status="staging",
            verification={
                "verified_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
                "qdrant_verified": False,
                "bm25_verified": not errors and bool(bm25_info),
                "count_matched": not errors,
                "fingerprint_matched": not errors and bool(bm25_info),
                "payload_indexes_verified": False,
                "errors": errors[:20],
            },
        )
        save_release_manifest(release_manifest_path, manifest)
        manifest_written = str(release_manifest_path)

    passed = len(errors) == 0
    elapsed = round(time.time() - start_time, 2)
    logger.info("Verification finished in %.2fs: passed=%s (errors=%s)", elapsed, passed, len(errors))

    return {
        "stage": "verify",
        "ok": passed,
        "passed": passed,
        "elapsed_seconds": elapsed,
        "total_chunks": len(chunks),
        "chunk_set_fingerprint": chunk_fp.get("chunk_set_fingerprint"),
        "recipe_chunks_in_rag": recipe_in_rag,
        "missing_breadcrumbs": missing_breadcrumbs,
        "release_manifest_path": manifest_written,
        "errors": errors[:20],
    }


# ─────────────────────────────────────────────────────────────────────────────
# CLI ENTRYPOINT
# ─────────────────────────────────────────────────────────────────────────────
def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="Health/InBody Data Pipeline Orchestrator")
    parser.add_argument("--all", action="store_true", help="Run the entire pipeline end-to-end")
    parser.add_argument("--extract", action="store_true", help="Extract PDFs to Markdown")
    parser.add_argument("--build", action="store_true", help="Merge and normalize raw sources")
    parser.add_argument("--chunk", action="store_true", help="Run structure-aware chunking")
    parser.add_argument("--index-bm25", action="store_true", help="Build and export versioned BM25 snapshot")
    parser.add_argument("--index-qdrant", action="store_true", help="Index chunks into a physical staging collection")
    parser.add_argument("--verify", action="store_true", help="Run quality gate verifications")
    parser.add_argument("--dry-run", action="store_true", help="Validate Qdrant payloads offline without writing")
    parser.add_argument("--corpus-version", default=DEFAULT_CORPUS_VERSION, help="Immutable corpus version (required for BM25/Qdrant)")
    parser.add_argument("--staging-collection", default=DEFAULT_STAGING_COLLECTION, help="Explicit physical staging Qdrant collection")
    parser.add_argument("--release-manifest", type=Path, default=DEFAULT_RELEASE_MANIFEST_PATH, help="Output path for versioned release manifest")
    parser.add_argument("--lock-dir", type=Path, default=None, help="Shared lock directory for staging write leases")

    args = parser.parse_args(argv)

    run_all = args.all or not (
        args.extract or args.build or args.chunk or args.index_bm25 or args.index_qdrant or args.verify
    )

    overall_start = time.time()
    report: Dict[str, Any] = {
        "corpus_version": args.corpus_version or None,
        "staging_collection": args.staging_collection or None,
        "started_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "ok": True,
        "stages": {},
    }

    try:
        if run_all or args.extract:
            report["stages"]["extract"] = run_extract_stage()

        if run_all or args.build:
            report["stages"]["build"] = run_build_stage()

        if run_all or args.chunk:
            report["stages"]["chunk"] = run_chunk_stage()

        if run_all or args.index_bm25:
            report["stages"]["index_bm25"] = run_bm25_stage(
                corpus_version=args.corpus_version,
                staging_collection=args.staging_collection,
            )

        qdrant_stage = None
        if run_all or args.index_qdrant:
            qdrant_stage = run_qdrant_stage(
                dry_run=args.dry_run,
                corpus_version=args.corpus_version,
                staging_collection=args.staging_collection,
                lock_dir=args.lock_dir,
            )
            report["stages"]["index_qdrant"] = qdrant_stage
            if not qdrant_stage.get("ok"):
                report["ok"] = False

        if run_all or args.verify:
            verify_stage = run_verify_stage(
                corpus_version=args.corpus_version,
                staging_collection=args.staging_collection,
                release_manifest_path=args.release_manifest,
                qdrant_stage_result=qdrant_stage,
            )
            report["stages"]["verify"] = verify_stage
            if not verify_stage.get("passed"):
                report["ok"] = False
    except Exception as exc:
        report["ok"] = False
        report["fatal_error"] = {"type": type(exc).__name__, "message": str(exc)}
        logger.error("Pipeline failed: %s", exc)

    report["total_elapsed_seconds"] = round(time.time() - overall_start, 2)
    atomic_write_json(PIPELINE_REPORT_PATH, report)

    logger.info("=== Pipeline Execution Finished in %.2fs (ok=%s) ===", report["total_elapsed_seconds"], report["ok"])
    logger.info("Report saved to %s", PIPELINE_REPORT_PATH)
    return 0 if report["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
