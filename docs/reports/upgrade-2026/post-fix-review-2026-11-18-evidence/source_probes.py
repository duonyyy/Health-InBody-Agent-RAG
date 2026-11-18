"""Read-only/synthetic audit probes. No production services or corpus writes."""
import ast
import gzip
import hashlib
import json
import os
import socket
import sys
from pathlib import Path
from types import SimpleNamespace

ROOT = Path(__file__).resolve().parents[4]
OUT = Path(__file__).resolve().parent
sys.path[:0] = [str(ROOT / 'backend/src'), str(ROOT / 'ocr-paddle-services/src')]
os.environ.update(DATABASE_URL='sqlite://', LLM_PROVIDER='none', OPENAI_API_KEY='', BM25_AUTOLOAD='false')

from harness.guards import verify_answer_claims_detailed
from harness.layers.citation_checker import prepare_composer_context
from rag.provenance import empty_review_registry

cases = [
    ('drop_not', 'BMI không đủ để chẩn đoán sức khỏe.', 'BMI đủ để chẩn đoán sức khỏe [1].', False),
    ('add_not', 'BMI là chỉ số khối cơ thể.', 'BMI không là chỉ số khối cơ thể [1].', False),
    ('other_sentence_negation', 'BMI là chỉ số khối cơ thể. BMI không thay thế bác sĩ.', 'BMI là chỉ số khối cơ thể [1].', True),
    ('exact', 'PBF là tỷ lệ phần trăm mỡ cơ thể.', 'PBF là tỷ lệ phần trăm mỡ cơ thể [1].', True),
    ('paraphrase', 'PBF là tỷ lệ phần trăm mỡ cơ thể.', 'PBF phản ánh tỷ lệ phần trăm mỡ cơ thể [1].', True),
    ('wrong_unit', 'PBF ở nam là 25%.', 'PBF ở nam là 25 kg [1].', False),
    ('wrong_number', 'Cân nặng là 72 kg.', 'Cân nặng là 82 kg [1].', False),
    ('wrong_subject', 'PBF ở nam là 25%.', 'PBF ở nữ là 25% [1].', False),
    ('drop_condition', 'Nếu có bệnh thận, cần tham khảo bác sĩ trước khi tăng protein.', 'Cần tham khảo bác sĩ trước khi tăng protein [1].', False),
    ('unrelated_id', 'BMI là chỉ số khối cơ thể.', 'Uống nước chữa khỏi bệnh thận [1].', False),
    ('swap_population_values', 'PBF ở nam là 20% và ở nữ là 30%.', 'PBF ở nam là 30% và ở nữ là 20% [1].', False),
    ('swap_metric_values', 'SMM là 30 kg và BFM là 20 kg.', 'SMM là 20 kg và BFM là 30 kg [1].', False),
    ('swap_relationship', 'Tập luyện giúp cải thiện sức khỏe.', 'Sức khỏe giúp cải thiện tập luyện [1].', False),
    ('valid_unlisted_paraphrase', 'BMI là chỉ số khối cơ thể.', 'Chỉ số khối cơ thể được viết tắt là BMI [1].', True),
]
results = []
for name, source, answer, expected in cases:
    verdict = verify_answer_claims_detailed(answer, [{'id': 1, 'document_id': 'synthetic', 'chunk_id': 'synthetic-1', 'excerpt': source}])
    results.append(dict(name=name, source=source, answer=answer, expected_supported=expected,
                        actual_supported=verdict['supported'], status=verdict['status'], reasons=verdict['reasons']))

# A fabricated verified stamp must not be accepted by an empty authoritative registry.
forged = dict(document_id='synthetic-unregistered', chunk_id='s1', content='BMI là chỉ số khối cơ thể.',
              review_verification_status='verified', medical_review_status='approved', review_id='invented-review',
              reviewer_id='invented-reviewer', review_scope='whole_document', reviewed_at='2026-11-18T00:00:00Z',
              reviewed_content_hash='a' * 64, document_content_hash='a' * 64,
              source_tier='guideline', source_tier_verified=True)
admitted, evidence, rejected = prepare_composer_context([forged], max_docs=3, max_chars=1000,
    require_verified_medical_review=True, review_registry=empty_review_registry())

from inbody_ocr.clients.paddle import OcrLine
from inbody_ocr.imaging.preprocess import PreparedImage
from inbody_ocr.inbody.extractor import InBodyOcrService
class Paddle:
    def __init__(self, text): self.text = text
    def read(self, _): return [OcrLine(self.text, .98, [[0, 0], [100, 0], [100, 20], [0, 20]])]
class LLM:
    settings = SimpleNamespace(ocr_num_predict=800)
    def __init__(self, fields): self.fields = fields
    def generate(self, **_): return json.dumps(self.fields)
ocr_results = []
for name, text, fields in [
    ('fabricated_value_and_raw', 'Cân nặng 72.5 kg', {'weight_kg': {'value': 82.5, 'raw_text': '82.5 kg'}}),
    ('wrong_metric', 'SMM 30 kg', {'weight_kg': {'value': 30, 'raw_text': '30 kg'}}),
    ('wrong_unit', 'PBF 25%', {'weight_kg': {'value': 25, 'raw_text': '25%'}}),
    ('nonexistent_span', 'Cân nặng 72.5 kg', {'weight_kg': {'value': 72.5, 'raw_text': '72.5 kg', 'page_number': 99, 'line_id': 'does-not-exist'}}),
]:
    response = InBodyOcrService(Paddle(text), LLM(fields)).extract([PreparedImage(1, 'a', b'synthetic')])
    ocr_results.append(dict(name=name, accepted='weight_kg' in response.extracted_fields,
                            status=response.status, warnings=response.warnings))

# Two synthetic releases: real BM25 code, injected dense adapter. No Qdrant network.
from rag import search
search.initialize_search_index([{'doc_id': 'old', 'content': 'BMI chỉ số khối cơ thể bản cũ', 'corpus_version': 'old'}])
search._search_index_metadata.pop('physical_collection', None)
search._search_index_metadata.pop('snapshot_error', None)
search._resolve_alias_target = lambda *a, **kw: 'physical-new'
search.vector_search_fallback = lambda *a, **kw: [{'doc_id': 'new', 'content': 'BMI chỉ số khối cơ thể bản mới', 'corpus_version': 'new', 'similarity_score': .9}]
sync = search.verify_runtime_release_sync(qdrant_client=object())
mixed = search.hybrid_search('BMI chỉ số khối cơ thể', use_rerank=False, expand_parents=False, qdrant_client=object())

syntax = []
syntax_errors = []
for group in ('backend/src', 'backend/scripts', 'data_pipeline', 'ocr-paddle-services/src', 'infra/embed_serving', 'contracts'):
    for path in (ROOT / group).rglob('*.py'):
        if any(p in {'.venv', '__pycache__', 'node_modules'} for p in path.parts): continue
        try:
            text = path.read_text(encoding='utf-8-sig')
            ast.parse(text, filename=str(path), feature_version=(3, 10))
            compile(text, str(path), 'exec')
            syntax.append(str(path.relative_to(ROOT)))
        except Exception as exc:
            syntax_errors.append(dict(file=str(path.relative_to(ROOT)), error=type(exc).__name__, detail=str(exc)))

snapshot_path = ROOT / 'backend/data/generated/bm25_snapshot.json.gz'
snapshot = {}
if snapshot_path.exists():
    data = json.loads(gzip.decompress(snapshot_path.read_bytes()))
    snapshot = {'sha256': hashlib.sha256(snapshot_path.read_bytes()).hexdigest(),
                'keys': sorted(data), 'metadata': data.get('metadata'),
                'document_count': len(data.get('documents', []))}
    # Metadata contains corpus descriptors only; never emit document contents.

report = dict(scope='synthetic_in_process_no_network', claims=results,
    claim_counts=dict(false_acceptances=sum(not r['expected_supported'] and r['actual_supported'] for r in results),
                      false_rejections=sum(r['expected_supported'] and not r['actual_supported'] for r in results)),
    forged_provenance=dict(registry_reviews=0, admitted=len(admitted), rejected=rejected,
                          statuses=[e['review_verification_status'] for e in evidence]),
    ocr=ocr_results, corpus_mixing=dict(sync=sync, result_versions=sorted(set(d.get('corpus_version', '') for d in mixed)),
                                      retrieval_modes=sorted(set(d.get('retrieval_mode', '') for d in mixed))),
    syntax=dict(count=len(syntax), errors=syntax_errors, runtime='host 3.13; grammar 3.10, not image execution'),
    snapshot=snapshot)
(OUT / 'source-probes.json').write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
print(json.dumps({k: v for k, v in report.items() if k not in {'claims', 'snapshot'}}, ensure_ascii=False, indent=2))
