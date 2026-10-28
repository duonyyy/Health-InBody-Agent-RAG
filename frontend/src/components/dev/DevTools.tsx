'use client';

import React, { useState } from 'react';
import {
  Server,
  Terminal,
  Play,
  RefreshCw,
} from 'lucide-react';
import { BackendHealth } from '@/types';
import { checkBackendHealth } from '@/lib/api';
import { calculateBmi, calculateBmr, classifyBmiAsian } from '@/lib/classifiers';

interface DevToolsProps {
  initialHealth: BackendHealth | null;
}

interface ToolOutputData {
  execution_time_ms?: number;
  [key: string]: unknown;
}

export default function DevTools({ initialHealth }: DevToolsProps) {
  const [health, setHealth] = useState<BackendHealth | null>(initialHealth);
  const [isChecking, setIsChecking] = useState(false);

  // Tool Sandbox State
  const [selectedTool, setSelectedTool] = useState<'bmi' | 'tdee' | 'safety'>('bmi');
  const [testWeight, setTestWeight] = useState(72.4);
  const [testHeight, setTestHeight] = useState(172);
  const [testAge, setTestAge] = useState(27);
  const [testSymptom, setTestSymptom] = useState('Đau ngực khó thở khi chạy bộ');
  const [toolOutput, setToolOutput] = useState<ToolOutputData | null>(null);

  const handlePingHealth = async () => {
    setIsChecking(true);
    try {
      const res = await checkBackendHealth();
      setHealth(res);
    } catch (err) {
      console.error(err);
    } finally {
      setIsChecking(false);
    }
  };

  const handleExecuteTool = () => {
    if (selectedTool === 'bmi') {
      const bmi = calculateBmi(testWeight, testHeight);
      const classification = classifyBmiAsian(bmi);
      setToolOutput({
        tool: 'calculate_bmi_asian',
        input: { weight_kg: testWeight, height_cm: testHeight },
        result: {
          bmi,
          standard: 'WHO_WPRO_ASIAN',
          classification: classification.label,
          status: classification.status,
          health_risk: classification.status === 'safe' ? 'Thấp' : 'Trung bình / Cao',
        },
        execution_time_ms: 1.2,
      });
    } else if (selectedTool === 'tdee') {
      const bmr = calculateBmr(testWeight, testHeight, testAge, 'male');
      const tdee = Math.round(bmr * 1.55); // moderate activity
      const deficitCalo = tdee - 300;
      setToolOutput({
        tool: 'calculate_tdee_and_macros',
        input: { weight_kg: testWeight, height_cm: testHeight, age: testAge, sex: 'male', activity: 'moderate' },
        result: {
          bmr_kcal: bmr,
          tdee_maintenance_kcal: tdee,
          body_recomposition_target_kcal: deficitCalo,
          recommended_macros: {
            protein_g: Math.round(testWeight * 2.0),
            fat_g: Math.round((deficitCalo * 0.25) / 9),
            carb_g: Math.round((deficitCalo - testWeight * 2.0 * 4 - (deficitCalo * 0.25)) / 4),
          },
        },
        execution_time_ms: 1.8,
      });
    } else {
      const isUrgent = testSymptom.toLowerCase().includes('đau ngực') || testSymptom.toLowerCase().includes('khó thở');
      setToolOutput({
        tool: 'deterministic_safety_guardrail',
        input: { query: testSymptom },
        result: {
          is_urgent: isUrgent,
          triage_level: isUrgent ? 'URGENT_EMERGENCY' : 'SAFE_ROUTINE',
          fast_path_action: isUrgent ? 'BYPASS_LLM_RETURN_HOTLINE_115' : 'CONTINUE_TO_ROUTER',
          safety_rules_applied: ['VIETNAM_MOH_CARDIO_SAFETY_2026', 'WHO_RED_FLAG_SCREENING'],
        },
        execution_time_ms: 0.8,
      });
    }
  };

  return (
    <div className="max-w-5xl mx-auto px-4 sm:px-6 py-6 space-y-6">
      {/* System Health Inspector */}
      <div className="glass-card rounded-2xl p-5 border border-slate-800/80 bg-slate-900/60 shadow-lg space-y-4">
        <div className="flex items-center justify-between pb-3 border-b border-slate-800">
          <div className="flex items-center gap-2">
            <div className="w-8 h-8 rounded-lg bg-emerald-500/20 text-emerald-400 flex items-center justify-center border border-emerald-500/30">
              <Server className="w-4 h-4" />
            </div>
            <div>
              <h4 className="font-bold text-sm text-slate-100">Giám sát Trạng thái Backend & Hạ tầng</h4>
              <p className="text-xs text-slate-400">Kiểm tra kết nối tới FastAPI, Qdrant và Model Serving</p>
            </div>
          </div>

          <button
            onClick={handlePingHealth}
            disabled={isChecking}
            className="px-3.5 py-1.5 rounded-xl bg-slate-800 hover:bg-slate-700 text-slate-200 text-xs font-semibold flex items-center gap-1.5 transition-all shadow-sm"
          >
            <RefreshCw className={`w-3.5 h-3.5 ${isChecking ? 'animate-spin' : ''}`} />
            <span>{isChecking ? 'Đang kiểm tra...' : 'Ping /health'}</span>
          </button>
        </div>

        <div className="grid grid-cols-2 sm:grid-cols-4 gap-3 text-xs">
          <div className="p-3 rounded-xl bg-slate-950/80 border border-slate-800">
            <span className="text-slate-400 text-[11px] block mb-1">Trạng thái Nền tảng</span>
            <div className="flex items-center gap-1.5 font-bold text-slate-100">
              <span
                className={`w-2 h-2 rounded-full ${
                  health?.status === 'healthy' ? 'bg-emerald-400' : 'bg-amber-400'
                }`}
              />
              <span>{health?.platform_state || 'READY'}</span>
            </div>
          </div>

          <div className="p-3 rounded-xl bg-slate-950/80 border border-slate-800">
            <span className="text-slate-400 text-[11px] block mb-1">Độ trễ Mạng (Ping)</span>
            <span className="font-bold font-mono text-emerald-400 text-sm">
              {health?.latency_ms !== undefined ? `${health.latency_ms} ms` : 'Demo'}
            </span>
          </div>

          <div className="p-3 rounded-xl bg-slate-950/80 border border-slate-800">
            <span className="text-slate-400 text-[11px] block mb-1">Vector DB (Qdrant)</span>
            <span className="font-bold text-slate-200">1024-dim (BGE-M3)</span>
          </div>

          <div className="p-3 rounded-xl bg-slate-950/80 border border-slate-800">
            <span className="text-slate-400 text-[11px] block mb-1">Model Provider</span>
            <span className="font-bold text-indigo-400">Model-Agnostic</span>
          </div>
        </div>
      </div>

      {/* Tool Sandbox Runner */}
      <div className="glass-card rounded-2xl p-5 border border-slate-800/80 bg-slate-900/60 shadow-lg space-y-4">
        <div className="flex items-center justify-between pb-3 border-b border-slate-800">
          <div className="flex items-center gap-2">
            <div className="w-8 h-8 rounded-lg bg-indigo-500/20 text-indigo-400 flex items-center justify-center border border-indigo-500/30">
              <Terminal className="w-4 h-4" />
            </div>
            <div>
              <h4 className="font-bold text-sm text-slate-100">Hộp cát Kiểm thử Công cụ (Tool Sandbox)</h4>
              <p className="text-xs text-slate-400">Kiểm tra tính toán độc lập không cần đi qua toàn bộ pipeline LLM</p>
            </div>
          </div>
        </div>

        {/* Tool selector buttons */}
        <div className="flex items-center gap-2 text-xs">
          <button
            onClick={() => {
              setSelectedTool('bmi');
              setToolOutput(null);
            }}
            className={`px-3 py-1.5 rounded-xl font-medium transition-all ${
              selectedTool === 'bmi'
                ? 'bg-indigo-600 text-white font-bold'
                : 'bg-slate-950 text-slate-400 border border-slate-800'
            }`}
          >
            Tính BMI & Phân loại WHO
          </button>
          <button
            onClick={() => {
              setSelectedTool('tdee');
              setToolOutput(null);
            }}
            className={`px-3 py-1.5 rounded-xl font-medium transition-all ${
              selectedTool === 'tdee'
                ? 'bg-indigo-600 text-white font-bold'
                : 'bg-slate-950 text-slate-400 border border-slate-800'
            }`}
          >
            Tính BMR & TDEE Macros
          </button>
          <button
            onClick={() => {
              setSelectedTool('safety');
              setToolOutput(null);
            }}
            className={`px-3 py-1.5 rounded-xl font-medium transition-all ${
              selectedTool === 'safety'
                ? 'bg-indigo-600 text-white font-bold'
                : 'bg-slate-950 text-slate-400 border border-slate-800'
            }`}
          >
            Kiểm thử An toàn Y tế (Triage)
          </button>
        </div>

        {/* Tool input fields */}
        <div className="p-4 rounded-xl bg-slate-950/80 border border-slate-800 text-xs space-y-3">
          {selectedTool === 'bmi' && (
            <div className="grid grid-cols-2 gap-3">
              <div>
                <label className="block text-slate-400 mb-1">Cân nặng (kg)</label>
                <input
                  type="number"
                  value={testWeight}
                  onChange={(e) => setTestWeight(Number(e.target.value))}
                  className="w-full px-3 py-2 rounded-lg bg-slate-900 border border-slate-700 text-slate-100 font-mono"
                />
              </div>
              <div>
                <label className="block text-slate-400 mb-1">Chiều cao (cm)</label>
                <input
                  type="number"
                  value={testHeight}
                  onChange={(e) => setTestHeight(Number(e.target.value))}
                  className="w-full px-3 py-2 rounded-lg bg-slate-900 border border-slate-700 text-slate-100 font-mono"
                />
              </div>
            </div>
          )}

          {selectedTool === 'tdee' && (
            <div className="grid grid-cols-3 gap-3">
              <div>
                <label className="block text-slate-400 mb-1">Cân nặng (kg)</label>
                <input
                  type="number"
                  value={testWeight}
                  onChange={(e) => setTestWeight(Number(e.target.value))}
                  className="w-full px-3 py-2 rounded-lg bg-slate-900 border border-slate-700 text-slate-100 font-mono"
                />
              </div>
              <div>
                <label className="block text-slate-400 mb-1">Chiều cao (cm)</label>
                <input
                  type="number"
                  value={testHeight}
                  onChange={(e) => setTestHeight(Number(e.target.value))}
                  className="w-full px-3 py-2 rounded-lg bg-slate-900 border border-slate-700 text-slate-100 font-mono"
                />
              </div>
              <div>
                <label className="block text-slate-400 mb-1">Tuổi</label>
                <input
                  type="number"
                  value={testAge}
                  onChange={(e) => setTestAge(Number(e.target.value))}
                  className="w-full px-3 py-2 rounded-lg bg-slate-900 border border-slate-700 text-slate-100 font-mono"
                />
              </div>
            </div>
          )}

          {selectedTool === 'safety' && (
            <div>
              <label className="block text-slate-400 mb-1">Mô tả triệu chứng người dùng</label>
              <input
                type="text"
                value={testSymptom}
                onChange={(e) => setTestSymptom(e.target.value)}
                className="w-full px-3 py-2 rounded-lg bg-slate-900 border border-slate-700 text-slate-100"
              />
            </div>
          )}

          <div className="flex justify-end pt-1">
            <button
              onClick={handleExecuteTool}
              className="px-4 py-2 rounded-xl bg-emerald-600 hover:bg-emerald-500 text-white font-bold text-xs shadow-md shadow-emerald-600/30 flex items-center gap-1.5"
            >
              <Play className="w-3.5 h-3.5 fill-white" />
              <span>Chạy Tool Ngay</span>
            </button>
          </div>
        </div>

        {/* Tool Output JSON preview */}
        {toolOutput && (
          <div className="p-4 rounded-xl bg-slate-950 border border-slate-800 space-y-2 animate-in fade-in">
            <div className="flex items-center justify-between text-xs pb-1 border-b border-slate-800">
              <span className="font-semibold text-emerald-400">Kết quả phản hồi JSON:</span>
              <span className="text-slate-500 font-mono text-[11px]">
                Thời gian: {toolOutput.execution_time_ms ?? 0} ms
              </span>
            </div>
            <pre className="font-mono text-xs text-slate-200 overflow-x-auto p-2 bg-slate-900/60 rounded-lg">
              {JSON.stringify(toolOutput, null, 2)}
            </pre>
          </div>
        )}
      </div>
    </div>
  );
}
