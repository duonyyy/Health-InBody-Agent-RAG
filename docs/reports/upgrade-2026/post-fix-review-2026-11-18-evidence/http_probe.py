"""Real loopback HTTP, actual API/SQLite; synthetic slow upstream, no paid calls."""
import asyncio
import json
import logging
import math
import os
import socket
import sys
import threading
import time
from collections import Counter
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

ROOT = Path(__file__).resolve().parents[4]
OUT = Path(__file__).resolve().parent
TMP = ROOT / '.audit-post-fix-tmp'
TMP.mkdir(exist_ok=True)
sys.path.insert(0, str(ROOT / 'backend/src'))
os.environ.update(DATABASE_URL='sqlite:///' + (TMP / 'http-synthetic.sqlite').as_posix(),
    AUTH_MODE='development', BM25_AUTOLOAD='false', API_RATE_LIMIT_ENABLED='false',
    LLM_PROVIDER='ollama', OLLAMA_MODEL='synthetic-test-model', OPENAI_API_KEY='',
    COHERE_API_KEY='', TAVILY_API_KEY='', FEATURE_OCR_UPLOAD='true',
    SUMMARIZE_TIMEOUT_SECONDS='0.45', SEARCH_TIMEOUT_SECONDS='0.45',
    SEARCH_MAX_CONCURRENCY='2', SEARCH_MAX_QUEUE='1', SEARCH_QUEUE_TIMEOUT_SECONDS='0.12',
    SUMMARIZE_MAX_CONCURRENCY='1', SUMMARIZE_MAX_QUEUE='0',
    AGENT_REQUEST_TIMEOUT_SECONDS='2', REDIS_HOST='127.0.0.1', REDIS_PORT='1',
    QDRANT_URL='http://127.0.0.1:1', CUSTOM_EMBEDDING_API_URL='http://127.0.0.1:1',
    LLM_RESPONSE_CACHE_ENABLED='false')
logging.disable(logging.CRITICAL)

state = dict(delay=0.8, mode='ok', calls=Counter(), active=Counter(), maximum=Counter())
lock = threading.Lock()
class Upstream(BaseHTTPRequestHandler):
    def log_message(self, *args): pass
    def do_POST(self):
        self.rfile.read(int(self.headers.get('Content-Length', '0')))
        path = self.path
        with lock:
            state['calls'][path] += 1
            state['active'][path] += 1
            state['maximum'][path] = max(state['maximum'][path], state['active'][path])
            delay, mode = state['delay'], state['mode']
        try:
            time.sleep(delay)
            if path == '/ocr/inbody':
                payload = dict(document_type='inbody_result', parser_version='synthetic-http', status='needs_confirmation',
                    extracted_fields={'weight_kg': dict(value=72.5, raw_text='72.5 kg', page_number=1, confidence=None)},
                    unresolved_fields=['height_cm'], warnings=[])
            elif path == '/search': payload = []
            else: payload = {'message': {'content': 'Mình cần thêm thông tin để hỗ trợ bạn.'}}
            raw = json.dumps(payload).encode()
            self.send_response(503 if mode == 'error' and path == '/api/chat' else 200)
            self.send_header('Content-Type', 'application/json')
            self.send_header('Content-Length', str(len(raw)))
            self.end_headers()
            self.wfile.write(raw)
        except (BrokenPipeError, ConnectionResetError, ConnectionAbortedError): pass
        finally:
            with lock: state['active'][path] -= 1

upstream = ThreadingHTTPServer(('127.0.0.1', 0), Upstream)
threading.Thread(target=upstream.serve_forever, daemon=True).start()
upstream_url = f'http://127.0.0.1:{upstream.server_port}'
os.environ['OLLAMA_BASE_URL'] = upstream_url
os.environ['OCR_SERVICE_URL'] = upstream_url

import httpx
import requests
import uvicorn
import api.app as api
from core.execution import get_all_lane_stats, reset_lanes
from persistence.database import init_db, engine
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.ext.compiler import compiles
@compiles(JSONB, 'sqlite')
def jsonb_sqlite(type_, compiler, **kw):
    return 'JSON'
init_db()

# Inject only search transport; actual lane/deadline/endpoint remain unmodified.
def slow_search(query, timeout=None, **kwargs):
    return requests.post(upstream_url + '/search', json={'synthetic': True}, timeout=timeout).json()
api.hybrid_search = slow_search

sock = socket.socket()
sock.bind(('127.0.0.1', 18791 if '--serve' in sys.argv else 0))
port = sock.getsockname()[1]
config = uvicorn.Config(api.app, host='127.0.0.1', port=port, log_level='critical', access_log=False)
server = uvicorn.Server(config)
thread = threading.Thread(target=lambda: server.run(sockets=[sock]), daemon=True)
thread.start()
for _ in range(200):
    if server.started: break
    time.sleep(.05)
if not server.started: raise RuntimeError('isolated server did not start')

def summary(samples):
    values = sorted(x['ms'] for x in samples)
    return dict(n=len(values), p50_ms=values[math.ceil(.5 * len(values))-1],
                p95_ms=values[math.ceil(.95 * len(values))-1], max_ms=max(values),
                statuses=dict(Counter(str(x['status']) for x in samples)))

async def main():
    report = dict(scope='real_loopback_HTTP_actual_API_SQLite_synthetic_search_Ollama_OCR_upstream',
                  config=dict(search_concurrency=2, search_queue=1, search_timeout=.45,
                              summarize_concurrency=1, summarize_queue=0, summarize_timeout=.45))
    async with httpx.AsyncClient(base_url=f'http://127.0.0.1:{port}', trust_env=False,
                                headers={'X-Dev-User-Id': 'audit-synthetic-a'}, timeout=10,
                                limits=httpx.Limits(max_connections=100)) as client:
        async def req(path, body=None, method='POST', **kwargs):
            start = time.perf_counter()
            response = await client.request(method, path, json=body, **kwargs)
            return dict(status=response.status_code, ms=round((time.perf_counter()-start)*1000, 3)), response

        # Authoritative readbacks through real persistence, SQLite test schema only.
        _, profile = await req('/me/profile', method='PATCH', body={'consent_flags': {'health_data_processing': True, 'personalization': True}, 'sex_at_birth': 'female'})
        measurement_body = {'measured_at': '2026-11-17T00:00:00Z', 'weight_kg': 72.5, 'source_type': 'manual_confirmed', 'confirmed_by_user': True}
        _, saved = await req('/me/measurements', body=measurement_body)
        measurement = saved.json()
        _, readback = await req('/me/measurements/' + measurement.get('id', 'missing'), method='GET')
        _, other = await req('/me/measurements/' + measurement.get('id', 'missing'), method='GET', headers={'X-Dev-User-Id': 'audit-synthetic-b'})
        _, checkin = await req('/me/check-ins', body={'checked_at': '2026-11-17T00:00:00Z', 'adherence': 50, 'energy_level': 3, 'sleep_quality': 2, 'soreness': 1, 'symptoms': ['đau ngực', 'khó thở']})
        _, history = await req('/me/check-ins', method='GET')
        report['persistence'] = dict(profile_status=profile.status_code, create_status=saved.status_code,
            readback_status=readback.status_code, readback_weight=readback.json().get('weight_kg'),
            other_owner_status=other.status_code, checkin_status=checkin.status_code,
            checkin_risk=(checkin.json().get('safety_result') or {}).get('risk_level'),
            readback_checkin_risk=[(i.get('safety_result') or {}).get('risk_level') for i in history.json().get('items', [])])

        # Warm-up excludes import/first-use time from measured fast-path samples.
        await req('/agent/answer', {'question': 'Tôi đau ngực và khó thở'})
        await req('/agent/answer', {'question': 'Tính BMI 72 kg 170 cm'})
        with lock: before = dict(state['calls'])
        loads = [asyncio.create_task(req('/search', {'query': 'synthetic search', 'use_rerank': False})) for _ in range(3)]
        loads.append(asyncio.create_task(req('/summarize', {'text': 'synthetic report'})))
        await asyncio.sleep(.08)
        urgent, bmi = [], []
        for _ in range(30):
            sample, _ = await req('/agent/answer', {'question': 'Tôi đau ngực và khó thở'})
            urgent.append(sample)
            sample, _ = await req('/agent/answer', {'question': 'Tính BMI 72 kg 170 cm'})
            bmi.append(sample)
        load_results = await asyncio.gather(*loads)
        report['under_search_summarize_load'] = dict(urgent=summary(urgent), bmi=summary(bmi),
            loads=[r[0] for r in load_results], lane_stats=get_all_lane_stats())
        await asyncio.sleep(.9)
        with lock: report['under_search_summarize_load']['upstream_calls'] = {k: v-before.get(k, 0) for k,v in state['calls'].items()}

        # Admission and timeout recovery.
        state['delay'] = .7
        samples = await asyncio.gather(*[req('/search', {'query': 'synthetic admission', 'use_rerank': False}) for _ in range(8)])
        report['admission'] = dict(summary=summary([r[0] for r in samples]), lane_stats=get_all_lane_stats())
        await asyncio.sleep(.8)
        state['delay'] = .02
        report['after_timeout'], _ = await req('/search', {'query': 'synthetic recovery', 'use_rerank': False})

        # Actual client disconnect: inspect server accounting, then recovery.
        os.environ['SUMMARIZE_TIMEOUT_SECONDS'] = '1.5'
        state['delay'] = .65
        before_completed = get_all_lane_stats()['summarize']['completed_total']
        try: await client.post('/summarize', json={'text': 'synthetic disconnect'}, timeout=.08)
        except httpx.ReadTimeout: pass
        await asyncio.sleep(.05)
        report['disconnect'] = dict(during=get_all_lane_stats()['summarize'])
        report['disconnect']['immediate_followup'], _ = await req('/summarize', {'text': 'synthetic followup'})
        await asyncio.sleep(.75)
        report['disconnect']['after'] = get_all_lane_stats()['summarize']
        report['disconnect']['completed_delta'] = report['disconnect']['after']['completed_total'] - before_completed
        state['delay'] = .02
        report['disconnect']['recovered'], _ = await req('/summarize', {'text': 'synthetic recovered'})

        # Retry uses real Composer/requests with controlled HTTP 503 (no paid provider).
        state['delay'], state['mode'] = .15, 'error'
        with lock: calls_before = state['calls']['/api/chat']
        retry_sample, retry_res = await req('/agent/answer', {'question': 'Bạn có thể giới thiệu cách sử dụng trợ lý này không?'})
        with lock: retry_calls = state['calls']['/api/chat'] - calls_before
        report['retry'] = dict(sample=retry_sample, upstream_calls=retry_calls,
                               response_status=retry_res.json().get('status'), errors=retry_res.json().get('errors'))
        state['mode'] = 'ok'

        # OCR uses the shared AnyIO pool. Forty slow OCR requests can starve auth.
        state['delay'] = 2.0
        ocr_jobs = [asyncio.create_task(client.post('/me/inbody-ocr', files={'file': ('synthetic.png', b'fixture', 'image/png')})) for _ in range(40)]
        for _ in range(100):
            with lock: active = state['active']['/ocr/inbody']
            if active >= 40: break
            await asyncio.sleep(.01)
        report['ocr_pool_saturation'] = dict(active_ocr_at_urgent=active)
        report['ocr_pool_saturation']['urgent'], _ = await req('/agent/answer', {'question': 'Tôi đau ngực và khó thở'})
        ocr_responses = await asyncio.gather(*ocr_jobs)
        report['ocr_pool_saturation']['ocr_statuses'] = dict(Counter(str(r.status_code) for r in ocr_responses))
        _, after_ocr = await req('/me/measurements', method='GET')
        report['ocr_pool_saturation']['measurements_after_extraction'] = len(after_ocr.json().get('items', []))

        report['negative_input'], _ = await req('/agent/answer', {'question': 'Tính BMI -72 kg 170 cm'})
        report['health'], _ = await req('/health', method='GET')
        report['final_lanes'] = get_all_lane_stats()
        with lock:
            report['upstream_final'] = {k: dict(state[k]) for k in ('calls', 'active', 'maximum')}
    (OUT / 'http-probes.json').write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
    print(json.dumps(report, ensure_ascii=False, indent=2))

try:
    if '--serve' in sys.argv:
        state['delay'] = .02
        print('Isolated synthetic browser backend ready on port 18791', flush=True)
        stop = TMP / 'stop-browser-backend'
        deadline = time.monotonic() + 900
        while not stop.exists() and time.monotonic() < deadline:
            time.sleep(.2)
    else:
        asyncio.run(main())
finally:
    server.should_exit = True
    thread.join(timeout=5)
    reset_lanes(wait=True)
    upstream.shutdown()
    upstream.server_close()
    engine.dispose()
    sock.close()
