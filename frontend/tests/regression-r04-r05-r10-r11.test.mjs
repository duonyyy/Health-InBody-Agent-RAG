// Comprehensive regression test suite for R04, R05, R10, R11
import test from 'node:test';
import assert from 'node:assert/strict';

// Helper to mock global fetch
function mockFetch(handler) {
  const originalFetch = globalThis.fetch;
  globalThis.fetch = async (url, options) => {
    return handler(url.toString(), options);
  };
  return () => {
    globalThis.fetch = originalFetch;
  };
}

function jsonResponse(body, status = 200) {
  return new Response(JSON.stringify(body), {
    status,
    headers: { 'Content-Type': 'application/json' },
  });
}

// =================================================================
// R04: Dữ liệu thiếu vs Dữ liệu thật & PBF Sex Classification
// =================================================================
test('R04 - classifyPbf handles sex_at_birth without hardcoded male', async () => {
  const { classifyPbf } = await import('../src/lib/classifiers.ts');

  // Female
  const femaleRes = classifyPbf(22, 'female');
  assert.equal(femaleRes.label, 'Lý tưởng (18 - 28%)');
  assert.equal(femaleRes.status, 'safe');

  // Male
  const maleRes = classifyPbf(15, 'male');
  assert.equal(maleRes.label, 'Lý tưởng (10 - 20%)');
  assert.equal(maleRes.status, 'safe');

  // Undefined / null / intersex / prefer_not_to_say should NOT default to male!
  const undefinedRes = classifyPbf(22, undefined);
  assert.equal(undefinedRes.status, 'unknown', 'Undefined sex must return unknown status');
  assert.equal(undefinedRes.label, 'Chưa xác định chuẩn giới tính');

  const intersexRes = classifyPbf(22, 'intersex');
  assert.equal(intersexRes.status, 'unknown', 'Intersex must return unknown status');

  const preferNotToSayRes = classifyPbf(22, 'prefer_not_to_say');
  assert.equal(preferNotToSayRes.status, 'unknown');
});

test('R04 - classifyVisceralFat distinguishes null/missing from level 0', async () => {
  const { classifyVisceralFat } = await import('../src/lib/classifiers.ts');

  const nullRes = classifyVisceralFat(null);
  assert.equal(nullRes.label, 'Chưa có số đo');
  assert.equal(nullRes.status, 'unknown');

  const undefRes = classifyVisceralFat(undefined);
  assert.equal(undefRes.label, 'Chưa có số đo');
  assert.equal(undefRes.status, 'unknown');

  const zeroRes = classifyVisceralFat(0);
  assert.equal(zeroRes.label, 'Mức an toàn (0/9)');
  assert.equal(zeroRes.status, 'safe');
});

test('R04 - fetchInBodyMeasurements preserves nulls and retains partial records', async () => {
  const { fetchInBodyMeasurements } = await import('../src/lib/api.ts');

  const restore = mockFetch((url) => {
    if (url.includes('/me/measurements')) {
      return jsonResponse({
        items: [
          // Record 1: has SMM/BFM/PBF/VFL as null, weight and height present
          {
            id: 'meas-nulls',
            measured_at: '2026-11-17T08:00:00Z',
            weight_kg: 72.5,
            height_cm: 170.0,
            smm_kg: null,
            bfm_kg: null,
            pbf_percent: null,
            visceral_fat_level: null,
            body_water_l: null,
          },
          // Record 2: partial record (weight and height missing, but smm and pbf present)
          {
            id: 'meas-partial',
            measured_at: '2026-11-17T09:00:00Z',
            weight_kg: null,
            height_cm: null,
            smm_kg: 32.5,
            pbf_percent: 18.2,
          },
        ],
      });
    }
    return jsonResponse({}, 404);
  });

  try {
    const list = await fetchInBodyMeasurements();
    assert.equal(list.length, 2, 'Should keep both records including partial record');

    const rec1 = list.find((m) => m.id === 'meas-nulls');
    assert.ok(rec1, 'meas-nulls should be present');
    assert.equal(rec1.weight_kg, 72.5);
    assert.equal(rec1.height_cm, 170.0);
    assert.equal(rec1.smm_kg, undefined, 'Null smm_kg must not become 0');
    assert.equal(rec1.bfm_kg, undefined, 'Null bfm_kg must not become 0');
    assert.equal(rec1.pbf_percent, undefined, 'Null pbf_percent must not become 0');
    assert.equal(rec1.visceral_fat_level, undefined, 'Null visceral_fat_level must not become 0');

    const rec2 = list.find((m) => m.id === 'meas-partial');
    assert.ok(rec2, 'meas-partial should not be dropped');
    assert.equal(rec2.weight_kg, undefined);
    assert.equal(rec2.height_cm, undefined);
    assert.equal(rec2.smm_kg, 32.5);
    assert.equal(rec2.pbf_percent, 18.2);
  } finally {
    restore();
  }
});

// =================================================================
// R05: Check-in Safety Result & Contract Alignment
// =================================================================
test('R05 - fetchCheckIns reads items array and retains safety_result and proper fields', async () => {
  const { fetchCheckIns } = await import('../src/lib/api.ts');

  const restore = mockFetch((url) => {
    if (url.includes('/me/check-ins')) {
      return jsonResponse({
        items: [
          {
            id: 'chk-urgent-1',
            checked_at: '2026-11-17T07:30:00Z',
            adherence: 85,
            energy_level: 4,
            sleep_quality: 3,
            soreness: 2,
            symptoms: ['đau ngực', 'khó thở'],
            note: 'Cảm thấy tức ngực khi chạy bộ',
            safety_result: {
              risk_level: 'urgent',
              is_urgent: true,
              recommended_action: 'Đến cơ sở y tế gần nhất hoặc gọi 115 ngay lập tức.',
              emergency_hotline: '115',
            },
          },
        ],
      });
    }
    return jsonResponse({}, 404);
  });

  try {
    const checkIns = await fetchCheckIns();
    assert.equal(checkIns.length, 1, 'Should parse 1 check-in from items');
    const chk = checkIns[0];
    assert.equal(chk.id, 'chk-urgent-1');
    assert.equal(chk.adherence, 85);
    assert.equal(chk.energy_level, 4);
    assert.equal(chk.sleep_quality, 3);
    assert.equal(chk.soreness, 2);
    assert.deepEqual(chk.symptoms, ['đau ngực', 'khó thở']);
    assert.ok(chk.safety_result, 'safety_result must be retained');
    assert.equal(chk.safety_result.risk_level, 'urgent');
    assert.equal(chk.safety_result.recommended_action, 'Đến cơ sở y tế gần nhất hoặc gọi 115 ngay lập tức.');
  } finally {
    restore();
  }
});

test('R05 - saveCheckIn sends proper fields and retains safety_result from response', async () => {
  const { saveCheckIn } = await import('../src/lib/api.ts');

  let sentBody = null;
  const restore = mockFetch((url, options) => {
    if (url.includes('/me/check-ins') && options?.method === 'POST') {
      sentBody = JSON.parse(options.body);
      return jsonResponse({
        id: 'chk-new-99',
        checked_at: sentBody.checked_at,
        adherence: sentBody.adherence,
        energy_level: sentBody.energy_level,
        sleep_quality: sentBody.sleep_quality,
        soreness: sentBody.soreness,
        symptoms: sentBody.symptoms,
        note: sentBody.note,
        safety_result: {
          risk_level: 'urgent',
          is_urgent: true,
          recommended_action: 'Cần đến bệnh viện kiểm tra ngay.',
        },
      }, 201);
    }
    return jsonResponse({}, 404);
  });

  try {
    const result = await saveCheckIn({
      adherence: 90,
      energy_level: 5,
      sleep_quality: 4,
      soreness: 1,
      symptoms: ['chóng mặt'],
      note: 'Tập bài chân',
    });

    assert.ok(sentBody, 'Body must have been sent');
    assert.equal(sentBody.adherence, 90);
    assert.equal(sentBody.energy_level, 5);
    assert.equal(sentBody.sleep_quality, 4);
    assert.equal(sentBody.soreness, 1);
    assert.deepEqual(sentBody.symptoms, ['chóng mặt']);
    assert.equal(sentBody.note, 'Tập bài chân');

    assert.ok(result.safety_result, 'Returned result must keep safety_result');
    assert.equal(result.safety_result.risk_level, 'urgent');
  } finally {
    restore();
  }
});

// =================================================================
// R10: Đọc đúng danh sách và xử lý đúng lỗi phiên
// =================================================================
test('R10 - fetchCheckIns: empty items is valid [], error codes throw ApiError', async () => {
  const { fetchCheckIns, ApiError } = await import('../src/lib/api.ts');

  // Empty items -> []
  const restore1 = mockFetch(() => jsonResponse({ items: [] }));
  try {
    const list = await fetchCheckIns();
    assert.deepEqual(list, []);
  } finally {
    restore1();
  }

  // 401 must throw ApiError with status 401
  const restore2 = mockFetch(() => jsonResponse({ detail: 'Token expired' }, 401));
  try {
    await assert.rejects(
      async () => {
        await fetchCheckIns();
      },
      (err) => {
        assert.ok(err instanceof ApiError);
        assert.equal(err.status, 401);
        return true;
      }
    );
  } finally {
    restore2();
  }

  // 403 must throw ApiError with status 403
  const restore3 = mockFetch(() => jsonResponse({ detail: 'Forbidden' }, 403));
  try {
    await assert.rejects(
      async () => {
        await fetchCheckIns();
      },
      (err) => {
        assert.ok(err instanceof ApiError);
        assert.equal(err.status, 403);
        return true;
      }
    );
  } finally {
    restore3();
  }

  // Malformed response must throw ApiError 502
  const restore4 = mockFetch(() => jsonResponse({ invalid_structure: true }));
  try {
    await assert.rejects(
      async () => {
        await fetchCheckIns();
      },
      (err) => {
        assert.ok(err instanceof ApiError);
        assert.equal(err.status, 502);
        return true;
      }
    );
  } finally {
    restore4();
  }
});

test('R10 - fetchMemoryFacts: reads items, empty items is [], 401/403/malformed throw ApiError', async () => {
  const { fetchMemoryFacts, ApiError } = await import('../src/lib/api.ts');

  // Normal items
  const restore1 = mockFetch(() => jsonResponse({
    items: [
      {
        id: 'fact-1',
        kind: 'dietary_preference',
        text: 'Kiêng đường sữa',
        status: 'confirmed',
        created_at: '2026-11-01T00:00:00Z',
      },
    ],
    external_memory: false,
    sync_pending: false,
  }));
  try {
    const facts = await fetchMemoryFacts();
    assert.equal(facts.length, 1);
    assert.equal(facts[0].id, 'fact-1');
    assert.equal(facts[0].fact, 'Kiêng đường sữa');
    assert.equal(facts[0].category, 'dietary_preference');
    assert.equal(facts[0].status, 'confirmed');
  } finally {
    restore1();
  }

  // 401 must throw ApiError
  const restore2 = mockFetch(() => jsonResponse({ detail: 'Token expired' }, 401));
  try {
    await assert.rejects(
      async () => {
        await fetchMemoryFacts();
      },
      (err) => {
        assert.ok(err instanceof ApiError);
        assert.equal(err.status, 401);
        return true;
      }
    );
  } finally {
    restore2();
  }

  // Malformed response must throw ApiError 502
  const restore3 = mockFetch(() => jsonResponse({ bad_data: 123 }));
  try {
    await assert.rejects(
      async () => {
        await fetchMemoryFacts();
      },
      (err) => {
        assert.ok(err instanceof ApiError);
        assert.equal(err.status, 502);
        return true;
      }
    );
  } finally {
    restore3();
  }
});

// =================================================================
// R11: Citations backend mapping & excerpt preservation
// =================================================================
test('R11 - sendChatMessageApi maps backend citations preserving excerpt, scores and IDs', async () => {
  const { sendChatMessageApi } = await import('../src/lib/api.ts');

  const restore = mockFetch((url) => {
    if (url.includes('/agent/answer')) {
      return jsonResponse({
        answer: 'Theo WHO Châu Á, BMI từ 18.5 đến 22.9 là mức lý tưởng [1].',
        latency_ms: 120,
        status: 'ok',
        citations: [
          {
            id: 1,
            document_id: 'doc-who-bmi',
            chunk_id: 'chunk-101',
            title: 'WHO Asian BMI Guidelines',
            source: 'who.int',
            source_url: 'https://who.int/bmi-asian',
            publisher: 'WHO WPRO',
            content_type: 'medical_safety',
            excerpt: 'Chỉ số BMI người Châu Á có điểm cắt 23.0 cho thừa cân và 25.0 cho béo phì.',
            retrieval_score: 0.88,
            source_version: '2026.1',
          },
        ],
      });
    }
    return jsonResponse({}, 404);
  });

  try {
    const msg = await sendChatMessageApi('Chỉ số BMI chuẩn cho người Châu Á?');
    assert.ok(msg.citations, 'Citations must be present in response message');
    assert.equal(msg.citations.length, 1);

    const cite = msg.citations[0];
    assert.equal(cite.id, 1, 'Citation id must be preserved for [1] cross-referencing');
    assert.equal(cite.excerpt, 'Chỉ số BMI người Châu Á có điểm cắt 23.0 cho thừa cân và 25.0 cho béo phì.');
    assert.equal(cite.content, 'Chỉ số BMI người Châu Á có điểm cắt 23.0 cho thừa cân và 25.0 cho béo phì.', 'content must match excerpt');
    assert.equal(cite.retrieval_score, 0.88);
    assert.equal(cite.source_url, 'https://who.int/bmi-asian');
    assert.equal(cite.title, 'WHO Asian BMI Guidelines');
    assert.equal(cite.source, 'who.int');
  } finally {
    restore();
  }
});

// =================================================================
// Bổ sung các case biên: số 0 thực, chuỗi rỗng, 409/503 status
// =================================================================
test('R04 - Edge cases: real zero is preserved, string numeric parsed, invalid/empty is undefined', async () => {
  const { fetchInBodyMeasurements } = await import('../src/lib/api.ts');

  const restore = mockFetch(() =>
    jsonResponse({
      items: [
        {
          id: 'meas-zero-and-strings',
          measured_at: '2026-11-17T10:00:00Z',
          weight_kg: '68.5',
          height_cm: 165,
          visceral_fat_level: 0, // Real 0
          smm_kg: '', // Empty string -> undefined, NOT 0
          bfm_kg: 'invalid_number', // NaN -> undefined, NOT 0
          pbf_percent: 0, // Real 0 (boundary)
        },
      ],
    })
  );

  try {
    const [rec] = await fetchInBodyMeasurements();
    assert.equal(rec.weight_kg, 68.5, 'String numeric "68.5" parsed to 68.5');
    assert.equal(rec.visceral_fat_level, 0, 'Real level 0 must be preserved');
    assert.equal(rec.pbf_percent, 0, 'Real percent 0 must be preserved');
    assert.equal(rec.smm_kg, undefined, 'Empty string must not become 0');
    assert.equal(rec.bfm_kg, undefined, 'Invalid string must not become 0');
  } finally {
    restore();
  }
});

test('R10 - 409 Consent and 503 Service Unavailable propagate descriptive errors', async () => {
  const { fetchCheckIns, fetchMemoryFacts, ApiError } = await import('../src/lib/api.ts');

  // Check 409
  const restore409 = mockFetch(() => jsonResponse({ detail: 'Chưa đồng ý xử lý dữ liệu sức khỏe' }, 409));
  try {
    await assert.rejects(
      () => fetchCheckIns(),
      (err) => {
        assert.ok(err instanceof ApiError);
        assert.equal(err.status, 409);
        assert.match(err.message, /đồng ý xử lý dữ liệu/i);
        return true;
      }
    );
  } finally {
    restore409();
  }

  // Check 503 fallback message
  const restore503 = mockFetch(() => jsonResponse({}, 503));
  try {
    await assert.rejects(
      () => fetchMemoryFacts(),
      (err) => {
        assert.ok(err instanceof ApiError);
        assert.equal(err.status, 503);
        assert.match(err.message, /gián đoạn/i);
        return true;
      }
    );
  } finally {
    restore503();
  }
});

// =================================================================
// R10 Session Expiration: 401 clears token & dispatches event
// =================================================================
test('R10 - HTTP 401 clears access token and dispatches bodywise-auth-expired event', async () => {
  const { authenticateAccount, hasAccessToken, fetchCheckIns, ApiError } = await import('../src/lib/api.ts');

  let authExpiredEvents = 0;
  const originalWindow = globalThis.window;
  globalThis.window = {
    dispatchEvent: (ev) => {
      if (ev && ev.type === 'bodywise-auth-expired') {
        authExpiredEvents += 1;
      }
      return true;
    },
  };

  const restoreLogin = mockFetch((url) => {
    if (url.includes('/auth/login')) {
      return jsonResponse({ token_type: 'bearer', access_token: 'mock-valid-jwt' });
    }
    if (url.includes('/me/check-ins')) {
      return jsonResponse({ detail: 'Token expired' }, 401);
    }
    return jsonResponse({}, 404);
  });

  try {
    await authenticateAccount('tester', 'secret123');
    assert.equal(hasAccessToken(), true, 'Access token should be set after login');

    await assert.rejects(
      () => fetchCheckIns(),
      (err) => {
        assert.ok(err instanceof ApiError);
        assert.equal(err.status, 401);
        return true;
      }
    );

    assert.equal(hasAccessToken(), false, '401 must clear access token');
    assert.equal(authExpiredEvents, 1, '401 must dispatch bodywise-auth-expired event');
  } finally {
    restoreLogin();
    if (originalWindow === undefined) {
      delete globalThis.window;
    } else {
      globalThis.window = originalWindow;
    }
  }
});

// =================================================================
// Component-level Consumer Tests (React SSR renderToStaticMarkup)
// =================================================================
test('R05 Component - SafetyBanner renders urgent (alert) and medical_caution (status) properly', async () => {
  const React = await import('react');
  const { renderToStaticMarkup } = await import('react-dom/server');
  const { default: SafetyBanner } = await import('../src/components/chat/SafetyBanner.tsx');

  const urgentHtml = renderToStaticMarkup(
    React.createElement(SafetyBanner, {
      safety: {
        risk_level: 'urgent',
        is_urgent: true,
        recommended_action: 'Gọi 115 hoặc đến phòng cấp cứu gần nhất.',
        emergency_hotline: '115',
      },
    })
  );
  assert.match(urgentHtml, /role="alert"/);
  assert.match(urgentHtml, /aria-live="assertive"/);
  assert.match(urgentHtml, /Gọi 115 hoặc đến phòng cấp cứu gần nhất\./);
  assert.match(urgentHtml, /tel:115/);

  const cautionHtml = renderToStaticMarkup(
    React.createElement(SafetyBanner, {
      safety: {
        risk_level: 'medical_caution',
        is_caution: true,
        recommended_action: 'Tham khảo ý kiến bác sĩ chuyên khoa trước khi tập nặng.',
      },
    })
  );
  assert.match(cautionHtml, /role="status"/);
  assert.match(cautionHtml, /aria-live="polite"/);
  assert.match(cautionHtml, /Tham khảo ý kiến bác sĩ chuyên khoa trước khi tập nặng\./);
});

test('R11 Component - CitationsView renders excerpt, keeps [id], escapes HTML, blocks unsafe URLs', async () => {
  const React = await import('react');
  const { renderToStaticMarkup } = await import('react-dom/server');
  const { sendChatMessageApi } = await import('../src/lib/api.ts');
  const { default: CitationsView } = await import('../src/components/chat/CitationsView.tsx');

  const restore = mockFetch(() =>
    jsonResponse({
      answer: 'Chỉ số tham chiếu theo [2].',
      latency_ms: 85,
      status: 'ok',
      citations: [
        {
          id: 2,
          document_id: 'doc-safe-1',
          chunk_id: 'chunk-2',
          title: '<b>WHO WPRO</b> Guidelines',
          source: 'who.int',
          source_url: 'javascript:alert(1)',
          excerpt: 'Ngưỡng BMI <script>alert("xss")</script> là 23.0 kg/m².',
          retrieval_score: 0.87,
          source_version: '2026.2',
        },
      ],
    })
  );

  try {
    const msg = await sendChatMessageApi('BMI chuẩn?');
    const html = renderToStaticMarkup(
      React.createElement(CitationsView, {
        citations: msg.citations,
        defaultExpandedIdx: 0,
      })
    );

    // Must keep original citation id [2]
    assert.match(html, /\[2\]/);
    // Must render excerpt content
    assert.match(html, /Ngưỡng BMI/);
    // Must escape HTML tags in title and excerpt
    assert.doesNotMatch(html, /<script>/i);
    assert.match(html, /&lt;script&gt;alert\(&quot;xss&quot;\)&lt;\/script&gt;/);
    assert.doesNotMatch(html, /<b>WHO WPRO<\/b>/);
    assert.match(html, /&lt;b&gt;WHO WPRO&lt;\/b&gt;/);
    // Must NOT render javascript: link
    assert.doesNotMatch(html, /href="javascript:/i);
    // Must display raw retrieval score, not coerced to percentage
    assert.match(html, /Điểm: 0\.87/);
    assert.doesNotMatch(html, /87%/);
    // Must include version metadata
    assert.match(html, /v2026\.2/);
  } finally {
    restore();
  }
});

test('R04 Component - MeasurementHistoryTable handles partial record, real zero, and sexAtBirth PBF', async () => {
  const React = await import('react');
  const { renderToStaticMarkup } = await import('react-dom/server');
  const { default: MeasurementHistoryTable } = await import(
    '../src/components/inbody/MeasurementHistoryTable.tsx'
  );

  const partialRecord = {
    id: 'm-partial-1',
    measured_at: '2026-11-17T08:00:00Z',
    weight_kg: undefined,
    height_cm: undefined,
    pbf_percent: 22,
    visceral_fat_level: 0,
  };

  // Female profile -> 22% PBF is Lý tưởng (18 - 28%)
  const femaleHtml = renderToStaticMarkup(
    React.createElement(MeasurementHistoryTable, {
      measurements: [partialRecord],
      onDelete: async () => {},
      sexAtBirth: 'female',
    })
  );
  assert.doesNotMatch(femaleHtml, /undefined kg/);
  assert.match(femaleHtml, /Lý tưởng \(18 - 28%\)/);
  assert.match(femaleHtml, /Cấp 0/);

  // Unknown sex -> must NOT default to male (10 - 20%)
  const unknownHtml = renderToStaticMarkup(
    React.createElement(MeasurementHistoryTable, {
      measurements: [partialRecord],
      onDelete: async () => {},
      sexAtBirth: null,
    })
  );
  assert.doesNotMatch(unknownHtml, /10 - 20%/);
  assert.match(unknownHtml, /Chưa xác định chuẩn giới tính/);
});
