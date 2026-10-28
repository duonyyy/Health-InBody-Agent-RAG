export type SexType = 'male' | 'female';

export interface UserProfile {
  user_id: string;
  display_name: string;
  age?: number;
  sex: SexType;
  height_cm: number;
  activity_level?: 'sedentary' | 'light' | 'moderate' | 'very_active';
  health_conditions?: string[];
  dietary_restrictions?: string[];
  acknowledged_disclaimer: boolean;
  created_at?: string;
  updated_at?: string;
}

export interface UserGoal {
  target_weight_kg?: number;
  target_body_fat_pct?: number;
  target_skeletal_muscle_kg?: number;
  target_date?: string;
  primary_goal?: 'weight_loss' | 'muscle_gain' | 'maintenance' | 'endurance';
  notes?: string;
}

export interface InBodyMeasurement {
  id: string;
  user_id: string;
  measured_at: string;
  weight_kg: number;
  height_cm: number;
  skeletal_muscle_mass_kg?: number;
  body_fat_mass_kg?: number;
  percent_body_fat?: number;
  visceral_fat_level?: number;
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
  details?: Record<string, any>;
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
}

export interface CheckInLog {
  id: string;
  date: string;
  workout_completed: boolean;
  workout_rating: number; // 1-5
  energy_level: number; // 1-5
  sleep_hours: number;
  unusual_symptoms?: string;
  notes?: string;
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
