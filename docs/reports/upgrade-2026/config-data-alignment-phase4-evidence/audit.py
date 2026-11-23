import collections, datetime, gzip, hashlib, json, os, pathlib, subprocess, sys, urllib.request

ROOT = pathlib.Path.cwd()
sys.dont_write_bytecode = True
sys.path.insert(0, str(ROOT / 'backend/src'))
from rag.corpus_lifecycle import compute_chunk_set_fingerprint, compute_embedding_fingerprint

out = {'timestamp': datetime.datetime.now(datetime.timezone.utc).isoformat(), 'method': 'Qdrant GET collections/aliases/info and POST exact count/scroll with metadata allowlist; local artifact SHA256 and project fingerprint functions; no vectors or content output'}
def request(path, body=None):
    data = None if body is None else json.dumps(body).encode()
    req = urllib.request.Request('http://127.0.0.1:6333' + path, data=data, headers={'Content-Type': 'application/json'})
    with urllib.request.urlopen(req, timeout=15) as resp:
        return json.load(resp)['result']

out['collections'] = request('/collections')
out['aliases'] = request('/aliases')
out['candidates'] = {}
fields = ['document_id', 'doc_id', 'chunk_id', 'content_hash', 'corpus_version', 'release_id', 'embedding_fingerprint', 'vector_size', 'embedding_dimension']
for name in ['health_knowledge_e5_v1', 'nmk_chatbot_e5small_v20261118']:
    item = {'info': request('/collections/' + name), 'count_before': request('/collections/' + name + '/points/count', {'exact': True})['count']}
    records, offset = [], None
    while True:
        body = {'limit': 256, 'with_payload': fields, 'with_vector': False}
        if offset is not None: body['offset'] = offset
        page = request('/collections/' + name + '/points/scroll', body)
        for p in page['points']:
            records.append({'qdrant_point_id': str(p['id']), **(p.get('payload') or {})})
        offset = page.get('next_page_offset')
        if offset is None: break
    item['count_after'] = request('/collections/' + name + '/points/count', {'exact': True})['count']
    item['scrolled'] = len(records)
    item['fingerprint'] = compute_chunk_set_fingerprint(records)
    item['missing'] = {f: sum(1 for x in records if x.get(f) is None or str(x.get(f)).strip() == '') for f in fields}
    item['distribution'] = {f: dict(collections.Counter(str(x.get(f) if x.get(f) is not None else '<missing>') for x in records)) for f in ['corpus_version', 'release_id', 'embedding_fingerprint', 'vector_size', 'embedding_dimension']}
    pairs = [(r.get('document_id'), r.get('chunk_id')) for r in records]
    item['duplicate_document_chunk_pairs'] = len(pairs) - len(set(pairs))
    if records:
        changed = [dict(x) for x in records]
        changed[0]['content_hash'] = '0' * 64 if changed[0].get('content_hash') != '0' * 64 else '1' * 64
        item['same_count_changed_hash_changes_fingerprint'] = compute_chunk_set_fingerprint(changed)['chunk_set_fingerprint'] != item['fingerprint']['chunk_set_fingerprint']
    item['stable_counts_during_scroll'] = item['count_before'] == item['count_after'] == len(records)
    out['candidates'][name] = item

out['artifacts'] = {}
for folder in ['health_knowledge_e5_v1', 'e5small-2026-11-18-v1']:
    base = ROOT / 'backend/artifacts' / folder
    manifest = json.loads((base / 'release.json').read_text(encoding='utf-8'))
    path = base / 'bm25_snapshot.json.gz'
    sha = hashlib.sha256(path.read_bytes()).hexdigest()
    with gzip.open(path, 'rt', encoding='utf-8') as f: snapshot = json.load(f)
    source = ROOT / pathlib.Path(manifest['source_manifest']['path'])
    out['artifacts'][folder] = {'manifest': manifest, 'source_exists': source.exists(), 'source_sha_actual': hashlib.sha256(source.read_bytes()).hexdigest() if source.exists() else None, 'snapshot_sha_actual': sha, 'snapshot_header': {k: v for k, v in snapshot.items() if k != 'documents'}, 'snapshot_fingerprint_actual': compute_chunk_set_fingerprint(snapshot['documents']), 'embedding_fingerprint_actual': compute_embedding_fingerprint(manifest['embedding_config'])}

default_snapshot = ROOT / 'backend/data/generated/bm25_snapshot.json.gz'
out['default_snapshot'] = {'exists': default_snapshot.exists()}
if default_snapshot.exists():
    with gzip.open(default_snapshot, 'rt', encoding='utf-8') as f: snap = json.load(f)
    out['default_snapshot'].update({'sha256': hashlib.sha256(default_snapshot.read_bytes()).hexdigest(), 'header': {k:v for k,v in snap.items() if k != 'documents'}, 'computed': compute_chunk_set_fingerprint(snap.get('documents', []))})
allow = {'VECTOR_SIZE','CUSTOM_EMBEDDING_API_URL','EMBEDDING_MODEL_ID','EMBEDDING_MODEL_NAME','OPENAI_EMBEDDING_MODEL','EMBEDDING_MODEL_REVISION','EMBEDDING_QUERY_PREFIX','EMBEDDING_PASSAGE_PREFIX','EMBEDDING_NORMALIZE','EMBEDDING_MAX_LENGTH','QDRANT_COLLECTION_NAME','QDRANT_COLLECTION_ALIAS','CORPUS_VERSION','BM25_SNAPSHOT_PATH','BM25_AUTOLOAD','CORPUS_RELEASE_MANIFEST_PATH','MODEL_PATH','EMBEDDING_DEVICE','EMBEDDING_DTYPE'}
def safe(k,v):
    if 'URL' in k and ('@' in v or '?' in v or '#' in v): return '<redacted URL>'
    return v
out['env_files'] = {}
for name in ['backend/.env', 'infra/embed_serving/.env.serving']:
    path = ROOT / name
    found = {}
    if path.exists():
        for line in path.read_text(encoding='utf-8-sig').splitlines():
            line=line.strip()
            if not line or line.startswith('#') or '=' not in line: continue
            k,v=line.split('=',1); k=k.strip().removeprefix('export ').strip()
            if k in allow: found[k]=safe(k,v.strip().strip('"\''))
    out['env_files'][name] = {'exists': path.exists(), 'allowlisted': found}
out['shell_allowlisted'] = {k:safe(k, v) for k,v in os.environ.items() if k in allow}
out['compose'] = {}
for name,args,service in [('backend',['docker','compose','--env-file','backend/.env','-f','backend/docker-compose.yml','config','--format','json'],'chatbot-api'),('infra',['docker','compose','--env-file','backend/.env','-f','infra/docker-compose.infra.yml','config','--format','json'],'embedding-api'),('serving',['docker','compose','--env-file','infra/embed_serving/.env.serving','-f','infra/embed_serving/docker-compose.serving.yml','config','--format','json'],'embedding-api')]:
    p=subprocess.run(args,capture_output=True,text=True,encoding='utf-8',errors='replace')
    if p.returncode == 0:
        c=json.loads(p.stdout); env=c['services'][service].get('environment',{})
        out['compose'][name]={'status':'resolved', 'allowlisted':{k:safe(k,str(v)) for k,v in env.items() if k in allow}, 'networks':list(c['services'][service].get('networks',{})), 'volumes':c['services'][service].get('volumes',[])}
    else: out['compose'][name]={'status':'blocked', 'exit_code':p.returncode, 'error':'config failed; details withheld to avoid secrets'}
path = ROOT / 'docs/reports/upgrade-2026/config-data-alignment-phase4-evidence/inspection.json'
path.write_text(json.dumps(out,ensure_ascii=False,indent=2), encoding='utf-8')
print('Wrote', path)
for k,v in out['candidates'].items(): print(k, 'count',v['count_before'],v['scrolled'],v['count_after'],'fp',v['fingerprint'], 'missing',v['missing'],'distribution',v['distribution'])
for k,v in out['artifacts'].items(): print(k,'source SHA',v['source_sha_actual'],'snapshot SHA',v['snapshot_sha_actual'],'snapshot fp',v['snapshot_fingerprint_actual'],'embedding fp',v['embedding_fingerprint_actual'])
print('env',out['env_files'],'shell',out['shell_allowlisted'],'compose',out['compose'])
print('default snapshot', out['default_snapshot'])
