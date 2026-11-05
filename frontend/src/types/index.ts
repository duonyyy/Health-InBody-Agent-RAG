export type SexType = 'male' | 'female';
export type SexAtBirthType = 'male' | 'female' | 'intersex' | 'prefer_not_to_say';
export type ActivityLevelType = 'sedentary' | 'light' | 'moderate' | 'very_active' | 'low' | 'high' | 'very_high';
export type GoalType = 'fat_loss' | 'muscle_gain' | 'maintenance' | 'fitness' | 'other';
export type SourceType =
  | 'manual'
  | 'manual_confirmed'
  | 'ocr_unconfirmed'
  | 'ocr_confirmed'
  | 'device_imported'
  | 'legacy_unconfirmed';

export interface ConsentFlags {
  health_data_processing: boolean;
  personalization: boolean;
}

export interface UserProfile {
  user_id: string;
  display_name: string;
  age?: number;
  age_range?: string;
  birth_date?: string;
  sex: SexType;
  sex_at_birth?: SexAtBirthType;
  height_cm: number;
  activity_level?: ActivityLevelType;
  goal?: GoalType;
  health_conditions?: string[];
  medical_conditions?: string[];
  dietary_restrictions?: string[];
  dietary_preferences?: string[];
  exercise_constraints?: string[];
  consent_flags?: ConsentFlags;
  acknowledged_disclaimer: boolean;
  created_at?: string;
  updated_at?: string;
}

export interface UserGoal {
  goal_type?: GoalType;
  primary_goal?: 'weight_loss' | 'muscle_gain' | 'maintenance' | 'endurance';
  target_weight_kg?: number;
  target_body_fat_pct?: number;
  target_skeletal_muscle_kg?: number;
  target_date?: string;
  training_days_per_week?: number;
  weekly_activity_level?: string;
  constraints?: string[];
  status?: 'active' | 'paused' | 'completed';
  notes?: string;
}

export interface InBodyMeasurement {
  id: string;
  user_id?: string;
  measured_at: string;
  weight_kg: number;
  height_cm: number;
  // Field names from backend P1
  smm_kg?: number;
  bfm_kg?: number;
  pbf_percent?: number;
  visceral_fat_level?: number;
  body_water_l?: number;
  source_type?: SourceType;
  confirmed_by_user?: boolean;
  confidence?: number;
  // Backward compatibility fields
  skeletal_muscle_mass_kg?: number;
  body_fat_mass_kg?: number;
  percent_body_fat?: number;
  bmi?: number;
  bmr_kcal?: number;
  notes?: string;
  source?: 'manual' | 'ocr' | 'device';
}

export interface ProgressSummary {
  latest_measurement?: InBodyMeasurement;
  previous_measurement?: InBodyMeasurement;
  weight_delta_kg?: number;
  pbf_delta?: number;
  smm_delta_kg?: number;
  total_measurements: number;
  days_tracked: number;
}

export interface SafetyResult {
  is_urgent?: boolean;
  is_caution?: boolean;
  risk_level?: 'none' | 'low' | 'moderate' | 'urgent';
  reason?: string;
  urgency_explanation?: string;
  disclaimer?: string;
  recommended_action?: string;
  emergency_hotline?: string;
}

export interface AgentTraceStep {
  node: string;
  agent?: string;
  action?: string;
  duration_ms?: number;
  status?: 'success' | 'running' | 'skipped' | 'fallback';
  details?: Record<string, unknown>;
  timestamp?: string;
}

export interface Citation {
  id?: string;
  title: string;
  source: string;
  score?: number;
  category?: string;
  content: string;
  url?: string;
}

export interface MemoryProposal {
  id: string;
  fact: string;
  category: string;
  confidence: number;
  status: 'pending' | 'confirmed' | 'rejected';
  created_at?: string;
}

export interface ChatMessage {
  id: string;
  role: 'user' | 'assistant' | 'system';
  content: string;
  timestamp: string;
  latency_ms?: number;
  fast_path?: string | null;
  status?: 'ok' | 'degraded' | 'error';
  selected_agents?: string[];
  agent_trace?: AgentTraceStep[];
  citations?: Citation[];
  safety_result?: SafetyResult;
  memory_proposals?: MemoryProposal[];
  personalization_used?: {
    latest_bmi?: number;
    latest_pbf?: number;
    profile_loaded?: boolean;
    has_medical_notes?: boolean;
  };
  errors?: string[];
  request_id?: string;
  conversation_id?: string;
  evidence_status?: string;
  limitations?: string[];
}

export interface CheckInLog {
  id: string;
  date: string;
  checked_at?: string;
  workout_completed: boolean;
  workout_rating: number; // 1-5
  energy_level: number; // 1-5
  sleep_hours: number;
  sleep_quality?: number; // 1-5
  soreness?: number; // 1-5
  unusual_symptoms?: string;
  symptoms?: string[];
  notes?: string;
  note?: string;
}

export interface BackendHealth {
  status: 'healthy' | 'degraded' | 'unhealthy' | 'offline';
  platform_state?: string;
  can_serve_traffic?: boolean;
  latency_ms?: number;
  timestamp: string;
  dependencies?: {
    postgres?: boolean;
    qdrant?: boolean;
    valkey?: boolean;
    embedding_api?: boolean;
    llm_provider?: string;
  };
}

export interface OcrField {
  value: number;
  raw_text: string;
  page_number: number;
  confidence?: number | null;
}

export interface OcrResult {
  document_type: string;
  parser_version: string;
  status: string;
  extracted_fields: Record<string, OcrField>;
  unresolved_fields: string[];
  warnings: string[];
}
