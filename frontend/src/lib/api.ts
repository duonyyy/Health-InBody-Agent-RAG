import {
  ChatMessage,
  UserProfile,
  InBodyMeasurement,
  CheckInLog,
  MemoryProposal,
  BackendHealth,
  Citation,
  OcrResult,
  SourceType,
} from '@/types';
import {
  INITIAL_PROFILE,
  INITIAL_MEASUREMENTS,
  INITIAL_CHECKINS,
  INITIAL_MEMORY_FACTS,
  INITIAL_CORPUS_DOCS,
} from './mockData';

// -------------------------------------------------------------
// Configuration & Environment Helpers
// -------------------------------------------------------------
const DEMO_MODE_STORAGE_KEY = 'bodywise_explicit_demo_mode';
const BASE_URL_STORAGE_KEY = 'api_base_url';
const DEV_USER_STORAGE_KEY = 'active_user_id';

export class ApiError extends Error {
  status: number;
  data?: unknown;

  constructor(message: string, status: number = 500, data?: unknown) {
    super(message);
    this.name = 'ApiError';
    this.status = status;
    this.data = data;
  }
}

export function getApiBaseUrl(): string {
  if (typeof window !== 'undefined') {
    const saved = localStorage.getItem(BASE_URL_STORAGE_KEY);
    if (saved) return saved.replace(/\/$/, '');
  }
  return (process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000').replace(/\/$/, '');
}

export function setApiBaseUrl(url: string): void {
  if (typeof window !== 'undefined') {
    localStorage.setItem(BASE_URL_STORAGE_KEY, url.trim().replace(/\/$/, ''));
  }
}

export function getAuthMode(): 'development' | 'production' {
  const mode = process.env.NEXT_PUBLIC_AUTH_MODE || 'development';
  return mode.toLowerCase() === 'production' ? 'production' : 'development';
}

export function getActiveUserId(): string {
  if (typeof window !== 'undefined') {
    const saved = localStorage.getItem(DEV_USER_STORAGE_KEY);
    if (saved) return saved.trim();
  }
  return process.env.NEXT_PUBLIC_DEV_USER_ID || 'demo-user';
}

export function setActiveUserId(userId: string): void {
  if (typeof window !== 'undefined') {
    localStorage.setItem(DEV_USER_STORAGE_KEY, userId.trim());
  }
}

/**
 * Chế độ Demo tường minh (Explicit Demo Mode):
 * Mặc định tắt (false). Chỉ kích hoạt khi người dùng chủ động bật công tắc demo để xem mẫu UI.
 */
export function isExplicitDemoMode(): boolean {
  if (typeof window !== 'undefined') {
    return localStorage.getItem(DEMO_MODE_STORAGE_KEY) === 'true';
  }
  return false;
}

export function setExplicitDemoMode(enabled: boolean): void {
  if (typeof window !== 'undefined') {
    localStorage.setItem(DEMO_MODE_STORAGE_KEY, enabled ? 'true' : 'false');
  }
}

function getRequestHeaders(extraHeaders: Record<string, string> = {}): Record<string, string> {
  const headers: Record<string, string> = {
    Accept: 'application/json',
    ...extraHeaders,
  };

  // Chỉ gắn X-Dev-User-Id khi ở chế độ development được cấu hình tường minh
  if (getAuthMode() === 'development') {
    headers['X-Dev-User-Id'] = getActiveUserId();
  }
  return headers;
}

// -------------------------------------------------------------
// Health Check (SCR-01, SCR-07)
// -------------------------------------------------------------
export async function checkBackendHealth(): Promise<BackendHealth> {
  const url = `${getApiBaseUrl()}/health`;
  const start = performance.now();
  try {
    const controller = new AbortController();
    const timer = setTimeout(() => controller.abort(), 5000);

    const res = await fetch(url, {
      signal: controller.signal,
      headers: { Accept: 'application/json' },
    });
    clearTimeout(timer);

    const latency = Math.round(performance.now() - start);
    if (res.ok) {
      const data = await res.json();
      const isHealthy = data.status === 'healthy' || data.platform_state === 'READY';
      return {
        status: isHealthy ? 'healthy' : 'degraded',
        platform_state: data.platform_state || 'READY',
        can_serve_traffic: data.can_serve_traffic ?? true,
        latency_ms: latency,
        timestamp: new Date().toISOString(),
        dependencies: {
          postgres: Boolean(data.dependencies?.postgres ?? data.cache?.connected ?? true),
          qdrant: Boolean(data.dependencies?.qdrant ?? data.search?.vector_active ?? true),
          valkey: Boolean(data.dependencies?.valkey ?? data.cache?.connected ?? true),
          embedding_api: Boolean(data.dependencies?.embedding_api ?? true),
          llm_provider: data.llm?.provider || data.dependencies?.llm_provider || 'system_default',
        },
      };
    }
    return {
      status: 'degraded',
      latency_ms: latency,
      timestamp: new Date().toISOString(),
    };
  } catch {
    return {
      status: 'offline',
      latency_ms: Math.round(performance.now() - start),
      timestamp: new Date().toISOString(),
    };
  }
}

// -------------------------------------------------------------
// Chat Completion (SCR-02)
// -------------------------------------------------------------
export async function sendChatMessageApi(
  message: string,
  conversationId?: string
): Promise<ChatMessage> {
  // Nếu người dùng chủ động bật chế độ Demo thì nạp câu trả lời giả lập có cảnh báo
  if (isExplicitDemoMode()) {
    return generateDemoAgentResponse(message);
  }

  const baseUrl = getApiBaseUrl();
  const start = performance.now();

  try {
    const controller = new AbortController();
    // Frontend timeout 65s (lớn hơn hard timeout 60s của backend theo WP-04)
    const timer = setTimeout(() => controller.abort(), 65000);

    const res = await fetch(`${baseUrl}/agent/answer`, {
      method: 'POST',
      headers: getRequestHeaders({ 'Content-Type': 'application/json' }),
      body: JSON.stringify({
        question: message,
        conversation_id: conversationId || undefined,
      }),
      signal: controller.signal,
    });
    clearTimeout(timer);

    const latency = Math.round(performance.now() - start);

    if (res.ok) {
      const data = await res.json();
      return {
        id: `msg-${Date.now()}`,
        role: 'assistant',
        content: data.answer || data.content || '',
        timestamp: new Date().toLocaleTimeString('vi-VN', { hour: '2-digit', minute: '2-digit' }),
        latency_ms: data.latency_ms || latency,
        fast_path: data.fast_path || null,
        status: data.status || 'ok',
        selected_agents: data.selected_agents || [],
        agent_trace: data.agent_trace || [],
        citations: data.citations || [],
        safety_result: data.safety_result || {},
        personalization_used: data.personalization_used || {},
        errors: data.errors || [],
        request_id: data.request_id,
        conversation_id: data.conversation_id,
        evidence_status: data.evidence_status,
        limitations: data.limitations || [],
      };
    }

    let errorDetail = `Lỗi máy chủ (${res.status})`;
    try {
      const errJson = await res.json();
      if (errJson.detail) {
        errorDetail = typeof errJson.detail === 'string' ? errJson.detail : JSON.stringify(errJson.detail);
      }
    } catch {
      // ignore
    }
    throw new ApiError(errorDetail, res.status);
  } catch (err: unknown) {
    if (err instanceof ApiError) throw err;
    const isAbort = err instanceof Error && err.name === 'AbortError';
    throw new ApiError(
      isAbort
        ? 'Yêu cầu vượt quá thời gian xử lý (quá 65 giây). Vui lòng thử lại.'
        : 'Không thể kết nối đến máy chủ BodyWise Backend. Vui lòng kiểm tra cổng dịch vụ.',
      isAbort ? 504 : 503
    );
  }
}

// -------------------------------------------------------------
// Profile & Personalization (SCR-05)
// -------------------------------------------------------------
export async function fetchUserProfile(): Promise<UserProfile> {
  if (isExplicitDemoMode()) {
    return INITIAL_PROFILE;
  }

  const baseUrl = getApiBaseUrl();
  try {
    const res = await fetch(`${baseUrl}/me/profile`, {
      headers: getRequestHeaders(),
    });

    if (res.ok) {
      const data = await res.json();
      return {
        user_id: data.user_id || getActiveUserId(),
        display_name: data.display_name || 'Người dùng BodyWise',
        age: data.age,
        age_range: data.age_range,
        birth_date: data.birth_date,
        sex: data.sex_at_birth === 'female' ? 'female' : 'male',
        sex_at_birth: data.sex_at_birth,
        height_cm: Number(data.height_cm) || 170,
        activity_level: data.activity_level || 'moderate',
        goal: data.goal,
        health_conditions: data.medical_conditions || data.health_conditions || [],
        medical_conditions: data.medical_conditions || [],
        dietary_restrictions: data.dietary_preferences || data.dietary_restrictions || [],
        dietary_preferences: data.dietary_preferences || [],
        exercise_constraints: data.exercise_constraints || [],
        consent_flags: data.consent_flags || { health_data_processing: true, personalization: true },
        acknowledged_disclaimer: true,
        created_at: data.created_at,
        updated_at: data.updated_at,
      };
    }

    let detail = `Không thể tải hồ sơ (${res.status})`;
    try {
      const errJson = await res.json();
      if (errJson.detail) detail = errJson.detail;
    } catch {
      // ignore
    }
    throw new ApiError(detail, res.status);
  } catch (err: unknown) {
    if (err instanceof ApiError) throw err;
    throw new ApiError('Không thể kết nối tới máy chủ để tải hồ sơ cá nhân.', 503);
  }
}

export async function saveUserProfile(profile: Partial<UserProfile>): Promise<UserProfile> {
  if (isExplicitDemoMode()) {
    return { ...INITIAL_PROFILE, ...profile };
  }

  const baseUrl = getApiBaseUrl();
  const payload: Record<string, unknown> = {
    display_name: profile.display_name,
    height_cm: profile.height_cm ? Number(profile.height_cm) : undefined,
    sex_at_birth: profile.sex_at_birth || profile.sex,
    activity_level: profile.activity_level,
    goal: profile.goal,
    dietary_preferences: profile.dietary_preferences || profile.dietary_restrictions,
    exercise_constraints: profile.exercise_constraints,
    medical_conditions: profile.medical_conditions || profile.health_conditions,
    consent_flags: profile.consent_flags || { health_data_processing: true, personalization: true },
  };

  if (profile.age_range) {
    payload.age_range = profile.age_range;
  } else if (profile.birth_date) {
    payload.birth_date = profile.birth_date;
  }

  try {
    const res = await fetch(`${baseUrl}/me/profile`, {
      method: 'PUT',
      headers: getRequestHeaders({ 'Content-Type': 'application/json' }),
      body: JSON.stringify(payload),
    });

    if (res.ok) {
      return await fetchUserProfile();
    }

    let detail = `Không thể cập nhật hồ sơ (${res.status})`;
    try {
      const errJson = await res.json();
      if (errJson.detail) detail = errJson.detail;
    } catch {
      // ignore
    }
    throw new ApiError(detail, res.status);
  } catch (err: unknown) {
    if (err instanceof ApiError) throw err;
    throw new ApiError('Lỗi kết nối khi cập nhật hồ sơ cá nhân.', 503);
  }
}

// -------------------------------------------------------------
// InBody Measurements (SCR-03)
// -------------------------------------------------------------
export async function fetchInBodyMeasurements(): Promise<InBodyMeasurement[]> {
  if (isExplicitDemoMode()) {
    return INITIAL_MEASUREMENTS;
  }

  const baseUrl = getApiBaseUrl();
  try {
    const res = await fetch(`${baseUrl}/me/measurements?limit=50`, {
      headers: getRequestHeaders(),
    });

    if (res.ok) {
      const data = await res.json();
      const rawItems: unknown[] = Array.isArray(data)
        ? data
        : Array.isArray(data.measurements)
        ? data.measurements
        : Array.isArray(data.items)
        ? data.items
        : [];

      return rawItems.map((rawItem: unknown, idx: number): InBodyMeasurement => {
        const item = (rawItem || {}) as Record<string, unknown>;
        const smm = item.smm_kg !== undefined ? Number(item.smm_kg) : (item.skeletal_muscle_mass_kg as number | undefined);
        const bfm = item.bfm_kg !== undefined ? Number(item.bfm_kg) : (item.body_fat_mass_kg as number | undefined);
        const pbf = item.pbf_percent !== undefined ? Number(item.pbf_percent) : (item.percent_body_fat as number | undefined);

        return {
          id: String(item.id || `meas-${idx}`),
          user_id: item.user_id as string | undefined,
          measured_at: (item.measured_at as string) || new Date().toISOString(),
          weight_kg: Number(item.weight_kg) || 0,
          height_cm: Number(item.height_cm) || 170,
          smm_kg: smm,
          bfm_kg: bfm,
          pbf_percent: pbf,
          visceral_fat_level: item.visceral_fat_level !== undefined ? Number(item.visceral_fat_level) : undefined,
          body_water_l: item.body_water_l !== undefined ? Number(item.body_water_l) : undefined,
          source_type: (item.source_type as SourceType) || 'manual_confirmed',
          confirmed_by_user: (item.confirmed_by_user as boolean) ?? true,
          confidence: item.confidence as number | undefined,
          // Backward compatibility mappings
          skeletal_muscle_mass_kg: smm,
          body_fat_mass_kg: bfm,
          percent_body_fat: pbf,
          bmi: item.bmi ? Number(item.bmi) : undefined,
          bmr_kcal: item.bmr_kcal ? Number(item.bmr_kcal) : undefined,
          notes: (item.notes as string) || '',
          source: item.source_type === 'ocr_confirmed' ? 'ocr' : 'manual',
        };
      });
    }

    let detail = `Không thể tải danh sách số đo InBody (${res.status})`;
    try {
      const errJson = await res.json();
      if (errJson.detail) detail = errJson.detail;
    } catch {
      // ignore
    }
    throw new ApiError(detail, res.status);
  } catch (err: unknown) {
    if (err instanceof ApiError) throw err;
    throw new ApiError('Không thể kết nối đến máy chủ để lấy lịch sử đo InBody.', 503);
  }
}

export async function saveInBodyMeasurement(
  measurement: Partial<InBodyMeasurement>
): Promise<InBodyMeasurement> {
  if (isExplicitDemoMode()) {
    const entry: InBodyMeasurement = {
      id: `meas-${Date.now()}`,
      measured_at: measurement.measured_at || new Date().toISOString(),
      weight_kg: Number(measurement.weight_kg) || 70,
      height_cm: Number(measurement.height_cm) || 170,
      smm_kg: measurement.smm_kg ?? measurement.skeletal_muscle_mass_kg,
      bfm_kg: measurement.bfm_kg ?? measurement.body_fat_mass_kg,
      pbf_percent: measurement.pbf_percent ?? measurement.percent_body_fat,
      visceral_fat_level: measurement.visceral_fat_level,
      source_type: measurement.source_type || 'manual_confirmed',
      confirmed_by_user: true,
      skeletal_muscle_mass_kg: measurement.smm_kg ?? measurement.skeletal_muscle_mass_kg,
      body_fat_mass_kg: measurement.bfm_kg ?? measurement.body_fat_mass_kg,
      percent_body_fat: measurement.pbf_percent ?? measurement.percent_body_fat,
      bmi: measurement.bmi,
    };
    return entry;
  }

  const baseUrl = getApiBaseUrl();

  // Đảm bảo measured_at có timezone offset hợp lệ chuẩn ISO
  let measuredAt = measurement.measured_at;
  if (!measuredAt || !measuredAt.includes('T')) {
    measuredAt = new Date().toISOString();
  } else if (!measuredAt.endsWith('Z') && !measuredAt.includes('+')) {
    measuredAt = new Date(measuredAt).toISOString();
  }

  const payload = {
    measured_at: measuredAt,
    weight_kg: Number(measurement.weight_kg) || undefined,
    height_cm: Number(measurement.height_cm) || undefined,
    smm_kg: (measurement.smm_kg ?? measurement.skeletal_muscle_mass_kg) ? Number(measurement.smm_kg ?? measurement.skeletal_muscle_mass_kg) : undefined,
    bfm_kg: (measurement.bfm_kg ?? measurement.body_fat_mass_kg) ? Number(measurement.bfm_kg ?? measurement.body_fat_mass_kg) : undefined,
    pbf_percent: (measurement.pbf_percent ?? measurement.percent_body_fat) ? Number(measurement.pbf_percent ?? measurement.percent_body_fat) : undefined,
    visceral_fat_level: measurement.visceral_fat_level !== undefined ? Number(measurement.visceral_fat_level) : undefined,
    body_water_l: measurement.body_water_l !== undefined ? Number(measurement.body_water_l) : undefined,
    source_type: measurement.source_type || (measurement.source === 'ocr' ? 'ocr_confirmed' : 'manual_confirmed'),
    confirmed_by_user: measurement.confirmed_by_user ?? true,
    confidence: measurement.confidence,
  };

  try {
    const res = await fetch(`${baseUrl}/me/measurements`, {
      method: 'POST',
      headers: getRequestHeaders({ 'Content-Type': 'application/json' }),
      body: JSON.stringify(payload),
    });

    if (res.ok) {
      const data = await res.json();
      return {
        id: String(data.id || `meas-${Date.now()}`),
        measured_at: data.measured_at || measuredAt,
        weight_kg: Number(data.weight_kg) || 0,
        height_cm: Number(data.height_cm) || 170,
        smm_kg: data.smm_kg,
        bfm_kg: data.bfm_kg,
        pbf_percent: data.pbf_percent,
        visceral_fat_level: data.visceral_fat_level,
        bmi: data.bmi,
        source_type: data.source_type,
        confirmed_by_user: data.confirmed_by_user,
        skeletal_muscle_mass_kg: data.smm_kg,
        body_fat_mass_kg: data.bfm_kg,
        percent_body_fat: data.pbf_percent,
      };
    }

    let detail = `Không thể lưu số đo (${res.status})`;
    try {
      const errJson = await res.json();
      if (errJson.detail) detail = errJson.detail;
    } catch {
      // ignore
    }
    throw new ApiError(detail, res.status);
  } catch (err: unknown) {
    if (err instanceof ApiError) throw err;
    throw new ApiError('Lỗi kết nối khi gửi số đo InBody lên máy chủ.', 503);
  }
}

export async function deleteInBodyMeasurement(id: string): Promise<boolean> {
  if (isExplicitDemoMode()) return true;

  const baseUrl = getApiBaseUrl();
  try {
    const res = await fetch(`${baseUrl}/me/measurements/${encodeURIComponent(id)}`, {
      method: 'DELETE',
      headers: getRequestHeaders(),
    });
    if (res.ok || res.status === 204) return true;

    let detail = `Không thể xóa số đo (${res.status})`;
    try {
      const errJson = await res.json();
      if (errJson.detail) detail = errJson.detail;
    } catch {
      // ignore
    }
    throw new ApiError(detail, res.status);
  } catch (err: unknown) {
    if (err instanceof ApiError) throw err;
    throw new ApiError('Lỗi kết nối khi xóa bản ghi đo.', 503);
  }
}

// -------------------------------------------------------------
// InBody OCR Upload (SCR-04)
// Không tự sinh số đo giả! Trả về bản nháp để người dùng xác nhận
// -------------------------------------------------------------
export async function uploadInBodyOcrFile(file: File): Promise<Partial<InBodyMeasurement>> {
  if (isExplicitDemoMode()) {
    // Chỉ chạy trong demo mode được kích hoạt rõ ràng
    return {
      weight_kg: 72.4,
      height_cm: 172,
      smm_kg: 33.8,
      skeletal_muscle_mass_kg: 33.8,
      bfm_kg: 14.1,
      body_fat_mass_kg: 14.1,
      pbf_percent: 19.5,
      percent_body_fat: 19.5,
      visceral_fat_level: 6,
      bmi: 24.47,
      source: 'ocr',
      source_type: 'ocr_unconfirmed',
      confirmed_by_user: false,
      notes: `[DEMO MẪU] Trích xuất thử nghiệm từ tệp: ${file.name}`,
    };
  }

  const baseUrl = getApiBaseUrl();
  const formData = new FormData();
  formData.append('file', file);

  try {
    const controller = new AbortController();
    const timer = setTimeout(() => controller.abort(), 65000);

    const res = await fetch(`${baseUrl}/me/inbody-ocr`, {
      method: 'POST',
      headers: getRequestHeaders(),
      body: formData,
      signal: controller.signal,
    });
    clearTimeout(timer);

    if (res.ok) {
      const data: OcrResult = await res.json();
      const fields = data.extracted_fields || {};

      const draft: Partial<InBodyMeasurement> = {
        weight_kg: fields.weight_kg?.value,
        height_cm: fields.height_cm?.value,
        smm_kg: fields.smm_kg?.value,
        skeletal_muscle_mass_kg: fields.smm_kg?.value,
        bfm_kg: fields.bfm_kg?.value,
        body_fat_mass_kg: fields.bfm_kg?.value,
        pbf_percent: fields.pbf_percent?.value,
        percent_body_fat: fields.pbf_percent?.value,
        visceral_fat_level: fields.visceral_fat_level?.value,
        bmi: fields.bmi?.value,
        source: 'ocr',
        source_type: 'ocr_unconfirmed',
        confirmed_by_user: false,
        confidence: fields.weight_kg?.confidence ?? undefined,
        notes: `Bản nháp OCR từ tệp: ${file.name} (Chờ người dùng kiểm tra & xác nhận)`,
      };
      return draft;
    }

    if (res.status === 404) {
      throw new ApiError(
        'Dịch vụ OCR chưa được kích hoạt trên máy chủ backend (FEATURE_OCR_UPLOAD đang tắt). Bạn vui lòng nhập thủ công qua tab "Ghi nhận chỉ số".',
        404
      );
    }
    if (res.status === 409) {
      throw new ApiError(
        'Bạn cần chấp thuận điều khoản xử lý dữ liệu sức khỏe trong mục Hồ Sơ trước khi quét OCR.',
        409
      );
    }
    if (res.status === 503 || res.status === 504 || res.status === 502) {
      throw new ApiError(
        'Dịch vụ AI OCR hiện đang ngoại tuyến hoặc quá tải. Vui lòng thử lại sau hoặc nhập số liệu thủ công.',
        res.status
      );
    }

    let detail = `Lỗi xử lý OCR (${res.status})`;
    try {
      const errJson = await res.json();
      if (errJson.detail) detail = errJson.detail;
    } catch {
      // ignore
    }
    throw new ApiError(detail, res.status);
  } catch (err: unknown) {
    if (err instanceof ApiError) throw err;
    throw new ApiError(
      'Không thể kết nối đến cổng dịch vụ OCR. Vui lòng kiểm tra trạng thái máy chủ.',
      503
    );
  }
}

// -------------------------------------------------------------
// Check-In Logs (SCR-05)
// -------------------------------------------------------------
export async function fetchCheckIns(): Promise<CheckInLog[]> {
  if (isExplicitDemoMode()) return INITIAL_CHECKINS;

  const baseUrl = getApiBaseUrl();
  try {
    const res = await fetch(`${baseUrl}/me/check-ins`, {
      headers: getRequestHeaders(),
    });

    if (res.ok) {
      const data = await res.json();
      const rawItems: unknown[] = Array.isArray(data) ? data : data.check_ins || [];
      return rawItems.map((rawCheckIn: unknown, idx: number) => {
        const c = (rawCheckIn || {}) as Record<string, unknown>;
        const symptomsArr = Array.isArray(c.symptoms) ? (c.symptoms as string[]) : [];
        return {
          id: String(c.id || `chk-${idx}`),
          date: typeof c.checked_at === 'string' ? c.checked_at.split('T')[0] : new Date().toISOString().split('T')[0],
          checked_at: c.checked_at as string | undefined,
          workout_completed: ((c.adherence as number) ?? 100) > 0,
          workout_rating: (c.soreness as number) ?? 5,
          energy_level: (c.energy_level as number) ?? 4,
          sleep_hours: 7.5,
          sleep_quality: (c.sleep_quality as number) ?? 4,
          soreness: (c.soreness as number) ?? 3,
          unusual_symptoms: symptomsArr.join(', '),
          symptoms: symptomsArr,
          notes: (c.note as string) || '',
          note: (c.note as string) || '',
        };
      });
    }

    if (res.status === 404 || res.status === 401) return [];
    throw new ApiError(`Không thể lấy nhật ký check-in (${res.status})`, res.status);
  } catch (err: unknown) {
    if (err instanceof ApiError) throw err;
    throw new ApiError('Lỗi kết nối khi tải nhật ký thể trạng.', 503);
  }
}

export async function saveCheckIn(checkIn: Partial<CheckInLog>): Promise<CheckInLog> {
  if (isExplicitDemoMode()) {
    return {
      id: `chk-${Date.now()}`,
      date: checkIn.date || new Date().toISOString().split('T')[0],
      workout_completed: checkIn.workout_completed ?? true,
      workout_rating: checkIn.workout_rating || 5,
      energy_level: checkIn.energy_level || 4,
      sleep_hours: checkIn.sleep_hours || 7.5,
      unusual_symptoms: checkIn.unusual_symptoms,
      notes: checkIn.notes || checkIn.note,
    };
  }

  const baseUrl = getApiBaseUrl();
  const symptomsList = checkIn.unusual_symptoms
    ? checkIn.unusual_symptoms.split(',').map((s) => s.trim()).filter(Boolean)
    : checkIn.symptoms || [];

  const payload = {
    checked_at: new Date().toISOString(),
    adherence: checkIn.workout_completed ? 100 : 0,
    energy_level: checkIn.energy_level ? Math.max(1, Math.min(5, checkIn.energy_level)) : undefined,
    sleep_quality: checkIn.sleep_quality ? Math.max(1, Math.min(5, checkIn.sleep_quality)) : 4,
    soreness: checkIn.soreness ? Math.max(1, Math.min(5, checkIn.soreness)) : 3,
    symptoms: symptomsList,
    note: checkIn.notes || checkIn.note || undefined,
  };

  try {
    const res = await fetch(`${baseUrl}/me/check-ins`, {
      method: 'POST',
      headers: getRequestHeaders({ 'Content-Type': 'application/json' }),
      body: JSON.stringify(payload),
    });

    if (res.ok) {
      const saved = await res.json();
      return {
        id: String(saved.id || `chk-${Date.now()}`),
        date: new Date().toISOString().split('T')[0],
        checked_at: saved.checked_at,
        workout_completed: (saved.adherence ?? 100) > 0,
        workout_rating: saved.soreness ?? 5,
        energy_level: saved.energy_level ?? 4,
        sleep_hours: checkIn.sleep_hours || 7.5,
        notes: saved.note || '',
      };
    }

    let detail = `Không thể lưu check-in (${res.status})`;
    try {
      const errJson = await res.json();
      if (errJson.detail) detail = errJson.detail;
    } catch {
      // ignore
    }
    throw new ApiError(detail, res.status);
  } catch (err: unknown) {
    if (err instanceof ApiError) throw err;
    throw new ApiError('Lỗi kết nối khi gửi nhật ký vận động.', 503);
  }
}

// -------------------------------------------------------------
// Memory Facts (SCR-05)
// -------------------------------------------------------------
export async function fetchMemoryFacts(): Promise<MemoryProposal[]> {
  if (isExplicitDemoMode()) return INITIAL_MEMORY_FACTS;

  const baseUrl = getApiBaseUrl();
  try {
    const res = await fetch(`${baseUrl}/me/memory/facts`, {
      headers: getRequestHeaders(),
    });

    if (res.ok) {
      const data = await res.json();
      const facts: unknown[] = Array.isArray(data) ? data : data.facts || [];
      return facts.map((rawFact: unknown, idx: number): MemoryProposal => {
        const f = (rawFact || {}) as Record<string, unknown>;
        const statusStr = typeof f.status === 'string' ? f.status.toLowerCase() : '';
        const status: 'pending' | 'confirmed' | 'rejected' =
          statusStr === 'confirmed' ? 'confirmed' : statusStr === 'rejected' ? 'rejected' : 'pending';
        return {
          id: String(f.id || `fact-${idx}`),
          fact: (f.text as string) || (f.fact as string) || '',
          category: (f.kind as string) || (f.category as string) || 'personalization',
          confidence: (f.confidence as number) || 0.95,
          status,
          created_at: f.created_at as string | undefined,
        };
      });
    }

    if (res.status === 404 || res.status === 403 || res.status === 401) {
      return [];
    }
    throw new ApiError(`Không thể tải ký ức (${res.status})`, res.status);
  } catch (err: unknown) {
    if (err instanceof ApiError) throw err;
    throw new ApiError('Lỗi kết nối khi tải danh sách ký ức cá nhân hóa.', 503);
  }
}

export async function updateMemoryFactStatus(
  id: string,
  status: 'confirmed' | 'rejected'
): Promise<void> {
  if (isExplicitDemoMode()) return;

  const baseUrl = getApiBaseUrl();
  if (status === 'confirmed') {
    const res = await fetch(`${baseUrl}/me/memory/facts/${encodeURIComponent(id)}/confirm`, {
      method: 'POST',
      headers: getRequestHeaders(),
    });
    if (!res.ok) throw new ApiError(`Không thể xác nhận ký ức (${res.status})`, res.status);
  } else {
    await deleteMemoryFact(id);
  }
}

export async function deleteMemoryFact(id: string): Promise<void> {
  if (isExplicitDemoMode()) return;

  const baseUrl = getApiBaseUrl();
  const res = await fetch(`${baseUrl}/me/memory/facts/${encodeURIComponent(id)}`, {
    method: 'DELETE',
    headers: getRequestHeaders(),
  });
  if (!res.ok && res.status !== 204 && res.status !== 404) {
    throw new ApiError(`Không thể xóa ký ức (${res.status})`, res.status);
  }
}

// -------------------------------------------------------------
// Knowledge Corpus Search (SCR-06)
// -------------------------------------------------------------
export async function searchCorpusApi(query: string, category?: string): Promise<Citation[]> {
  if (isExplicitDemoMode()) {
    const q = query.toLowerCase();
    return INITIAL_CORPUS_DOCS.filter((doc) => {
      const matchCategory = !category || category === 'all' || doc.category === category;
      const matchQuery = !query || doc.title.toLowerCase().includes(q) || doc.content.toLowerCase().includes(q);
      return matchCategory && matchQuery;
    });
  }

  const baseUrl = getApiBaseUrl();
  try {
    const res = await fetch(`${baseUrl}/search`, {
      method: 'POST',
      headers: getRequestHeaders({ 'Content-Type': 'application/json' }),
      body: JSON.stringify({
        query: query.trim(),
        limit: 8,
        use_rerank: false,
      }),
    });

    if (res.ok) {
      const data = await res.json();
      const rawResults: unknown[] = Array.isArray(data.results) ? data.results : [];

      return rawResults.map((rawItem: unknown, idx: number): Citation => {
        const r = (rawItem || {}) as Record<string, unknown>;
        const payload = (r.payload || {}) as Record<string, unknown>;
        const metadata = (r.metadata || {}) as Record<string, unknown>;
        return {
          id: String(r.id || `cit-${idx}`),
          title: (payload.title as string) || (r.title as string) || (metadata.title as string) || 'Tài liệu hướng dẫn y tế',
          source: (payload.source as string) || (r.source as string) || (metadata.source as string) || 'Qdrant Knowledge Base',
          content: (payload.content as string) || (r.content as string) || (r.text as string) || '',
          score: typeof r.score === 'number' ? r.score : 0.85,
          category: (payload.category as string) || (r.category as string) || 'y_te_inbody',
        };
      });
    }

    let detail = `Lỗi tìm kiếm (${res.status})`;
    try {
      const errJson = await res.json();
      if (errJson.detail) detail = errJson.detail;
    } catch {
      // ignore
    }
    throw new ApiError(detail, res.status);
  } catch (err: unknown) {
    if (err instanceof ApiError) throw err;
    throw new ApiError('Không thể kết nối đến công cụ tra cứu tri thức Qdrant.', 503);
  }
}

// -------------------------------------------------------------
// Demo Simulated Response Generator (Explicit Demo Mode Only)
// -------------------------------------------------------------
function generateDemoAgentResponse(message: string): ChatMessage {
  const lower = message.toLowerCase();
  const now = new Date().toLocaleTimeString('vi-VN', { hour: '2-digit', minute: '2-digit' });

  const urgentKeywords = ['đau ngực', 'khó thở', 'tức ngực', 'ngất', 'choáng váng nặng', 'đột quỵ'];
  const hasUrgent = urgentKeywords.some((kw) => lower.includes(kw));

  if (hasUrgent) {
    return {
      id: `msg-${Date.now()}`,
      role: 'assistant',
      content:
        '⚠️ **CẢNH BÁO AN TOÀN Y TẾ KHẨN CẤP**\n\n' +
        'Dấu hiệu bạn vừa mô tả (**đau ngực / khó thở**) có thể là triệu chứng của biến cố tim mạch hoặc hô hấp cấp tính.\n\n' +
        '**Hành động cần làm ngay:**\n' +
        '1. Dừng ngay mọi hoạt động vận động, ngồi nghỉ ở tư thế thoải mái.\n' +
        '2. Không cố gắng tiếp tục tập luyện hoặc tự ý dùng thuốc giảm đau.\n' +
        '3. Gọi ngay đường dây cấp cứu **115** hoặc đến phòng cấp cứu gần nhất.\n\n' +
        '*Lưu ý: Trợ lý AI chỉ mang tính tham khảo, không có chức năng cấp cứu y tế.*',
      timestamp: now,
      latency_ms: 45,
      fast_path: 'urgent_safety_triage',
      status: 'ok',
      selected_agents: ['medical_safety'],
      safety_result: {
        is_urgent: true,
        risk_level: 'urgent',
        reason: 'Phát hiện triệu chứng nguy cấp liên quan đến tuần hoàn/hô hấp',
        emergency_hotline: '115',
        recommended_action: 'Đến cơ sở y tế gần nhất ngay lập tức',
      },
    };
  }

  return {
    id: `msg-${Date.now()}`,
    role: 'assistant',
    content:
      '📊 **[Chế độ Demo Mẫu] Phân tích Thể trạng & Khuyến nghị Dinh dưỡng**:\n\n' +
      'Đây là phản hồi minh họa mẫu của giao diện BodyWise trong chế độ Demo.\n' +
      '- **Cân nặng:** 72.4 kg | **BMI:** 24.5 (Tiền béo phì nhẹ theo chuẩn WPRO)\n' +
      '- **Khối cơ SMM:** 33.8 kg (Tăng trưởng tốt)\n' +
      '- **Tỷ lệ mỡ PBF:** 19.5% (Ngưỡng an toàn)\n\n' +
      '*Để kết nối và nhận tư vấn thật từ hệ thống AI Đa tác nhân, vui lòng tắt Chế độ Demo.*',
    timestamp: now,
    latency_ms: 220,
    fast_path: null,
    status: 'ok',
    selected_agents: ['inbody_analyzer'],
  };
}
