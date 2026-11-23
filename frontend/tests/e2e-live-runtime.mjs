import assert from 'node:assert';
import fs from 'node:fs';
import path from 'node:path';

const FRONTEND_URL = 'http://localhost:3000';
const BACKEND_URL = 'http://localhost:8000';
const EVIDENCE_DIR = path.resolve('docs/reports/upgrade-2026/real-runtime-completion-evidence');

async function main() {
  console.log('=== BẮT ĐẦU KIỂM THỬ RUNTIME THẬT 100% ===');
  const results = {
    timestamp: new Date().toISOString(),
    frontend: {},
    backend_health: {},
    auth: {},
    fastpath_bmi: {},
    fastpath_urgent: {},
    rag_inbody: {},
  };

  // 1. Kiểm tra Frontend Next.js 16 container
  console.log('\n[1/6] Kiểm tra Frontend Next.js container...');
  const feRes = await fetch(FRONTEND_URL);
  assert.strictEqual(feRes.status, 200, `Frontend trả status ${feRes.status}`);
  const feHtml = await feRes.text();
  assert.ok(feHtml.includes('<!DOCTYPE html>') || feHtml.includes('<html'), 'Frontend không trả về HTML');
  results.frontend = {
    url: FRONTEND_URL,
    status: feRes.status,
    content_length: feHtml.length,
    ok: true,
  };
  console.log(`✓ Frontend HTTP 200 OK (${feHtml.length} bytes)`);

  // 2. Kiểm tra Backend readiness
  console.log('\n[2/6] Kiểm tra Backend /health/ready...');
  const healthRes = await fetch(`${BACKEND_URL}/health/ready`);
  assert.strictEqual(healthRes.status, 200, `Backend health trả status ${healthRes.status}`);
  const healthData = await healthRes.json();
  assert.strictEqual(healthData.status, 'ready', 'Backend status không phải ready');
  assert.strictEqual(healthData.dependencies.postgres, true, 'Postgres không ready');
  assert.strictEqual(healthData.dependencies.qdrant, true, 'Qdrant không ready');
  assert.strictEqual(healthData.dependencies.valkey, true, 'Valkey không ready');
  assert.strictEqual(healthData.dependencies.embedding_api, true, 'Embedding API không ready');
  assert.strictEqual(healthData.dependencies.corpus_release_sync, true, 'Corpus release sync không ready');
  results.backend_health = healthData;
  console.log('✓ Backend dependencies 100% READY:', healthData.dependencies);

  // 3. Auth: Register / Login tài khoản người dùng thật vào PostgreSQL
  console.log('\n[3/6] Xác thực người dùng thực (PostgreSQL Auth)...');
  const testUser = {
    username: `e2e_user_${Date.now()}`,
    password: 'SecurePassword123!',
  };
  const regRes = await fetch(`${BACKEND_URL}/auth/register`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(testUser),
  });
  let token = null;
  if (regRes.status === 200 || regRes.status === 201) {
    const regData = await regRes.json();
    token = regData.access_token;
    console.log(`✓ Đăng ký thành công người dùng mới: ${testUser.username}`);
  } else {
    console.log(`Đăng ký trả ${regRes.status}, tiến hành đăng nhập...`);
    const loginRes = await fetch(`${BACKEND_URL}/auth/login`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(testUser),
    });
    assert.strictEqual(loginRes.status, 200, `Login thất bại: ${loginRes.status}`);
    const loginData = await loginRes.json();
    token = loginData.access_token;
    console.log('✓ Đăng nhập thành công');
  }
  assert.ok(token, 'Không lấy được access_token');
  results.auth = {
    username: testUser.username,
    token_type: 'Bearer',
    token_length: token.length,
    authenticated: true,
  };

  const authHeaders = {
    'Content-Type': 'application/json',
    'Authorization': `Bearer ${token}`,
  };

  // 4. Fast-path BMI
  console.log('\n[4/6] Kiểm tra Fast-path BMI qua Agent...');
  const bmiStart = performance.now();
  const bmiRes = await fetch(`${BACKEND_URL}/agent/answer`, {
    method: 'POST',
    headers: authHeaders,
    body: JSON.stringify({ question: 'Tôi nặng 70kg, cao 170cm, tính BMI giúp tôi' }),
  });
  const bmiDuration = Math.round(performance.now() - bmiStart);
  assert.strictEqual(bmiRes.status, 200, `BMI request trả status ${bmiRes.status}`);
  const bmiData = await bmiRes.json();
  assert.ok(bmiData.answer.includes('24.2') || bmiData.answer.includes('BMI'), 'BMI answer thiếu chỉ số');
  assert.strictEqual(bmiData.fast_path, 'inbody_tools', 'Không trúng fast-path BMI');
  assert.ok(bmiDuration < 500, `Fast-path BMI vượt ngưỡng 500ms (${bmiDuration}ms)`);
  results.fastpath_bmi = {
    duration_ms: bmiDuration,
    fast_path: bmiData.fast_path,
    answer: bmiData.answer,
  };
  console.log(`✓ Fast-path BMI thành công trong ${bmiDuration}ms (< 500ms):`, bmiData.answer.substring(0, 80) + '...');

  // 5. Fast-path Urgent Safety
  console.log('\n[5/6] Kiểm tra Fast-path Urgent Safety qua Agent...');
  const urgentStart = performance.now();
  const urgentRes = await fetch(`${BACKEND_URL}/agent/answer`, {
    method: 'POST',
    headers: authHeaders,
    body: JSON.stringify({ question: 'Tôi bị đau ngực và khó thở dữ dội' }),
  });
  const urgentDuration = Math.round(performance.now() - urgentStart);
  assert.strictEqual(urgentRes.status, 200, `Urgent request trả status ${urgentRes.status}`);
  const urgentData = await urgentRes.json();
  assert.strictEqual(urgentData.fast_path, 'urgent_safety', 'Không trúng urgent safety');
  assert.strictEqual(urgentData.safety_result?.risk_level, 'urgent', 'Safety không trigger urgent');
  assert.ok(urgentDuration < 500, `Urgent safety vượt ngưỡng 500ms (${urgentDuration}ms)`);
  results.fastpath_urgent = {
    duration_ms: urgentDuration,
    fast_path: urgentData.fast_path,
    safety_result: urgentData.safety_result,
    answer: urgentData.answer,
  };
  console.log(`✓ Fast-path Urgent Safety thành công trong ${urgentDuration}ms (< 500ms)`);

  // 6. RAG InBody + E5 Retrieval + Ollama qwen2.5:3b + Citations
  console.log('\n[6/6] Kiểm tra Luồng RAG InBody đầy đủ (Embedding + Qdrant/BM25 + LLM Ollama qwen2.5:3b + Citation)...');
  const ragStart = performance.now();
  const ragRes = await fetch(`${BACKEND_URL}/agent/answer`, {
    method: 'POST',
    headers: authHeaders,
    body: JSON.stringify({ question: 'Chỉ số PBF là gì?' }),
  });
  const ragDuration = Math.round(performance.now() - ragStart);
  assert.strictEqual(ragRes.status, 200, `RAG request trả status ${ragRes.status}`);
  const ragData = await ragRes.json();
  assert.ok(ragData.answer && ragData.answer.length > 20, 'RAG answer quá ngắn hoặc rỗng');
  assert.ok(ragData.citations && ragData.citations.length > 0, 'Thiếu citations từ retrieval');
  assert.strictEqual(ragData.status, 'ok', 'Agent status không ok');
  assert.ok(ragData.claim_evidence_links && ragData.claim_evidence_links.length > 0, 'Thiếu claim_evidence_links');

  results.rag_inbody = {
    duration_ms: ragDuration,
    status: ragData.status,
    selected_agents: ragData.selected_agents,
    answer: ragData.answer,
    claim_evidence_links: ragData.claim_evidence_links,
    citation_count: ragData.citations.length,
    citations: ragData.citations.map((c) => ({
      id: c.id,
      title: c.title,
      source: c.source,
      source_url: c.source_url,
      excerpt: c.excerpt?.substring(0, 100),
      score: c.retrieval_score || c.score,
    })),
  };
  console.log(`✓ RAG InBody hoàn thành trong ${ragDuration}ms:`);
  console.log('  Agents:', ragData.selected_agents);
  console.log('  Câu trả lời:', ragData.answer);
  console.log('  Claim Evidence Links:', JSON.stringify(ragData.claim_evidence_links));
  console.log(`  Số lượng Citation: ${ragData.citations.length}`);
  ragData.citations.forEach((c, idx) => {
    console.log(`    [${idx + 1}] ${c.title || c.source} (URL: ${c.source_url || 'N/A'})`);
  });

  // Lưu file bằng chứng
  fs.mkdirSync(EVIDENCE_DIR, { recursive: true });
  const evidenceFile = path.join(EVIDENCE_DIR, 'e2e_live_runtime_result.json');
  fs.writeFileSync(evidenceFile, JSON.stringify(results, null, 2), 'utf8');
  console.log(`\n✓ Đã lưu file bằng chứng: ${evidenceFile}`);
  console.log('=== TẤT CẢ CÁC BƯỚC ĐÃ ĐẠT 100% TRÊN MÔI TRƯỜNG THẬT ===');
}

main().catch((err) => {
  console.error('LỖI KIỂM THỬ RUNTIME:', err);
  process.exit(1);
});
