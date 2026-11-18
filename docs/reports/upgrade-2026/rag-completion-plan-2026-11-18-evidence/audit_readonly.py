"""Planning evidence: read-only Qdrant scroll, artifact hashes, synthetic probes.

No corpus writes, alias changes, LLM calls, or application deployment.
Run from repository root: python -B <this file>
"""
import collections
import gzip
import hashlib
import json
import os
from pathlib import Path
import sys
import urllib.request

ROOT = Path(__file__).resolve().parents[4]
OUT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT / 'backend/src'))
os.environ.update(LLM_PROVIDER='none', OPENAI_API_KEY='', COHERE_API_KEY='',
                  BM25_AUTOLOAD='false', DATABASE_URL='sqlite://',
                  QDRANT_URL='http://localhost:6333')
from rag.corpus_lifecycle import compute_chunk_set_fingerprint, check_existing_point_conflict
from harness.guards import verify_answer_claims_detailed
from harness.layers.citation_checker import prepare_composer_context
from rag.provenance import empty_review_registry
from rag import search


def sha(data):
    return hashlib.sha256(data).hexdigest()


def request(path, payload=None):
    data = json.dumps(payload).encode() if payload is not None else None
    req = urllib.request.Request('http://localhost:6333/' + path, data=data,
                                 headers={'Content-Type': 'application/json'})
    with urllib.request.urlopen(req, timeout=10) as response:
        return json.load(response)['result']


def rows(path):
    return [json.loads(line) for line in path.read_text(encoding='utf-8').splitlines() if line.strip()]


report = {'scope': 'read_only_runtime_and_synthetic_in_process; no quality metrics'}
artifact = ROOT / 'backend/artifacts/health_knowledge_e5_v1'
manifest = json.loads((artifact / 'release.json').read_text(encoding='utf-8'))
snapshot_path = artifact / 'bm25_snapshot.json.gz'
snapshot = json.load(gzip.open(snapshot_path, 'rt', encoding='utf-8'))
points = []
offset = None
while True:
    args = dict(limit=256, with_payload=True, with_vector=False)
    if offset is not None:
        args['offset'] = offset
    batch = request('collections/health_knowledge_e5_v1/points/scroll', args)
    points.extend(batch['points'])
    offset = batch.get('next_page_offset')
    if offset is None:
        break
payloads = [p['payload'] for p in points]
fingerprint = compute_chunk_set_fingerprint(payloads)
snap_fp = compute_chunk_set_fingerprint(snapshot['documents'])
source = ROOT / manifest['source_manifest']['path']
source_rows = rows(source)
original_rows = rows(ROOT / 'data_pipeline/dataset/processed/embedding_documents.jsonl')
original_by_id = {r['doc_id']: r for r in original_rows}
source_ids = {r['doc_id'] for r in source_rows}
old_chunks = rows(ROOT / 'data_pipeline/dataset/chunks/chunks.jsonl')
report['release'] = {
    'physical_collection': manifest['physical_collection'],
    'release_id': manifest['release_id'], 'qdrant': fingerprint, 'bm25': snap_fp,
    'fingerprints_match_manifest': fingerprint['chunk_set_fingerprint'] == snap_fp['chunk_set_fingerprint'] == manifest['chunk_manifest']['chunk_set_fingerprint'],
    'snapshot_sha_matches': sha(snapshot_path.read_bytes()) == manifest['bm25_artifact']['sha256'],
    'source_sha_matches': sha(source.read_bytes()) == manifest['source_manifest']['sha256'],
    'chunk_content_hash_mismatches': sum(sha(p['content'].encode()) != p['content_hash'] for p in payloads),
    'point_id_mismatches': sum(str(p['id']) != p['payload'].get('qdrant_point_id') for p in points),
    'embedding_fingerprints': dict(collections.Counter(p.get('embedding_fingerprint') for p in payloads)),
    'corpus_versions': dict(collections.Counter(p.get('corpus_version') for p in payloads)),
    'release_ids': dict(collections.Counter(p.get('release_id') for p in payloads)),
    'parent_content_present': sum(bool(p.get('parent_content')) for p in payloads),
    'review_status_counts': dict(collections.Counter(p.get('review_verification_status') for p in payloads)),
    'source_document_counts': dict(collections.Counter(p.get('source') for p in source_rows)),
    'source_document_count': len(source_rows), 'prior_document_count': len(original_rows),
    'prior_chunks_count': len(old_chunks),
    'retained_source_records_equal': all(p == original_by_id.get(p['doc_id']) for p in source_rows),
    'excluded_document_ids': sorted(set(original_by_id) - source_ids),
    'missing_payload_metadata_counts': {k: sum(not p.get(k) for p in payloads) for k in ['source_url','publisher','published_at','reviewed_at','review_id','source_tier','document_content_hash']},
}
cases = [
    ('swap_metric', 'SMM là 30 kg và BFM là 20 kg.', 'SMM là 20 kg và BFM là 30 kg [1].', False),
    ('swap_population', 'PBF ở nam là 20% và ở nữ là 30%.', 'PBF ở nam là 30% và ở nữ là 20% [1].', False),
    ('valid_paraphrase', 'BMI là chỉ số khối cơ thể.', 'Chỉ số khối cơ thể được viết tắt là BMI [1].', True),
    ('valid_exact', 'BMI là chỉ số khối cơ thể.', 'BMI là chỉ số khối cơ thể [1].', True),
]
report['claims'] = []
for name, excerpt, answer, expected in cases:
    v = verify_answer_claims_detailed(answer, [{'id':1,'document_id':'synthetic','chunk_id':'s1','excerpt':excerpt}])
    report['claims'].append(dict(case=name,expected=expected,actual=v['supported'],reasons=v['reasons']))
forged = dict(document_id='synthetic-unregistered',chunk_id='s1',content='BMI là chỉ số khối cơ thể.',
              review_verification_status='verified',medical_review_status='approved',review_id='invented',
              reviewer_id='invented',review_scope='whole_document',reviewed_at='2026-11-18T00:00:00Z',
              reviewed_content_hash='a'*64,document_content_hash='a'*64)
admitted, evidence, rejected = prepare_composer_context([forged],max_docs=3,max_chars=1000,
    require_verified_medical_review=True,review_registry=empty_review_registry())
report['forged_stamp_empty_registry'] = dict(admitted=len(admitted), rejected=rejected)
report['resume_missing_embedding_fingerprint'] = check_existing_point_conflict('p',
    {'content_hash':'a'*64,'corpus_version':'v1','embedding_fingerprint':'expected'},
    {'p':{'content_hash':'a'*64,'corpus_version':'v1'}})
report['bm25_loaded'] = search.load_search_snapshot(snapshot_path,
    expected_physical_collection=manifest['physical_collection'],expected_release_id=manifest['release_id'],
    expected_corpus_version=manifest['corpus_version'],expected_chunk_set_fingerprint=fingerprint['chunk_set_fingerprint'])
report['live_release_sync_no_alias'] = search.verify_runtime_release_sync(release_manifest_path=artifact/'release.json')
report['bm25_smoke_not_eval'] = []
for query, filters in [('BMI là gì?',{'content_type':'inbody_metric'}),('Vai trò protein',{'content_type':'nutrition'}),('đau ngực khó thở',{'content_type':'medical_safety'})]:
    results = search.bm25_search(query,limit=5,filters=filters)
    report['bm25_smoke_not_eval'].append({'query':query,'filters':filters,'top5':[{'document_id':p.get('document_id'),'chunk_id':p.get('chunk_id'),'content_type':p.get('content_type')} for p in results]})
(OUT/'audit-results.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
print(json.dumps(report,ensure_ascii=False,indent=2))
