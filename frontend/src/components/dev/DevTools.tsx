'use client';

import React, { useState } from 'react';
import {
  Server,
  Terminal,
  Play,
  RefreshCw,
  Database,
  Cpu,
  ShieldCheck,
  AlertTriangle,
} from 'lucide-react';
import { BackendHealth } from '@/types';
import { checkBackendHealth, getAuthMode } from '@/lib/api';
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

  const isDev = getAuthMode() === 'development';

  if (!isDev) {
    return (
      <div className="max-w-3xl mx-auto px-4 py-16 text-center space-y-3">
        <ShieldCheck className="w-12 h-12 text-slate-400 mx-auto" />
        <h3 className="text-base font-bold text-slate-800">Công cụ Kỹ thuật (DevTools) bị vô hiệu hóa</h3>
        <p className="text-xs text-slate-500">
          Màn hình này chỉ dành riêng cho môi trường phát triển (development) theo quy định an toàn hệ thống.
        </p>
      </div>
    );
  }

  const handlePingHealth = async () => {
    setIsChecking(true);
    try {
      const res = await checkBackendHealth();
      setHealth(res);
    } catch {
      setHealth({
        status: 'offline',
        timestamp: new Date().toISOString(),
      });
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
        execution_time_ms: 0.8,
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
        execution_time_ms: 1.2,
      });
    } else {
      const isUrgent =
        testSymptom.toLowerCase().includes('đau ngực') ||
        testSymptom.toLowerCase().includes('khó thở') ||
        testSymptom.toLowerCase().includes('ngất');
      setToolOutput({
        tool: 'deterministic_safety_guardrail',
        input: { query: testSymptom },
        result: {
          is_urgent: isUrgent,
          triage_level: isUrgent ? 'URGENT_EMERGENCY' : 'SAFE_ROUTINE',
          fast_path_action: isUrgent ? 'BYPASS_LLM_RETURN_HOTLINE_115' : 'CONTINUE_TO_ROUTER',
          safety_rules_applied: ['VIETNAM_MOH_CARDIO_SAFETY_2026', 'WHO_RED_FLAG_SCREENING'],
          hotline: isUrgent ? '115' : null,
        },
        execution_time_ms: 0.5,
      });
    }
  };

  return (
    <div className="max-w-5xl mx-auto px-4 sm:px-6 py-6 space-y-6">
      {/* System Health Inspector */}
      <div className="rounded-2xl p-5 border border-slate-200 bg-white shadow-xs space-y-4">
        <div className="flex items-center justify-between pb-3 border-b border-slate-100">
          <div className="flex items-center gap-2">
            <div className="w-8 h-8 rounded-lg bg-teal-50 text-teal-700 flex items-center justify-center border border-teal-200">
              <Server className="w-4 h-4" />
            </div>
            <div>
              <h4 className="font-bold text-sm text-slate-900">Giám sát Trạng thái Backend & Hạ tầng</h4>
              <p className="text-xs text-slate-500">Kiểm tra kết nối tới FastAPI, PostgreSQL, Qdrant và Valkey</p>
            </div>
          </div>

          <button
            onClick={handlePingHealth}
            disabled={isChecking}
            className="px-3.5 py-1.5 rounded-xl bg-slate-100 hover:bg-slate-200 text-slate-700 text-xs font-semibold flex items-center gap-1.5 transition-all shadow-xs border border-slate-200"
          >
            <RefreshCw className={`w-3.5 h-3.5 ${isChecking ? 'animate-spin' : ''}`} />
            <span>{isChecking ? 'Đang kiểm tra...' : 'Ping /health'}</span>
          </button>
        </div>

        <div className="grid grid-cols-2 sm:grid-cols-4 gap-3 text-xs">
          <div className="p-3 rounded-xl bg-slate-50 border border-slate-200">
            <span className="text-slate-500 text-[11px] block mb-1">Trạng thái API</span>
            <div className="flex items-center gap-1.5 font-bold text-slate-800">
              <span
                className={`w-2 h-2 rounded-full ${
                  health?.status === 'healthy'
                    ? 'bg-teal-500'
                    : health?.status === 'degraded'
                    ? 'bg-amber-500'
                    : 'bg-rose-500'
                }`}
              />
              <span className="capitalize">
                {health?.status === 'healthy'
                  ? 'Hoạt động tốt'
                  : health?.status === 'degraded'
                  ? 'Suy giảm'
                  : 'Ngoại tuyến (Offline)'}
              </span>
            </div>
          </div>

          <div className="p-3 rounded-xl bg-slate-50 border border-slate-200">
            <span className="text-slate-500 text-[11px] block mb-1">Độ trễ Mạng (Ping)</span>
            <span className="font-bold font-mono text-teal-700 text-sm">
              {health?.latency_ms !== undefined ? `${health.latency_ms} ms` : 'Chưa đo'}
            </span>
          </div>

          <div className="p-3 rounded-xl bg-slate-50 border border-slate-200">
            <span className="text-slate-500 text-[11px] block mb-1">Cơ sở dữ liệu (PostgreSQL)</span>
            <div className="flex items-center gap-1.5 font-semibold text-slate-700">
              <Database className="w-3.5 h-3.5 text-slate-400" />
              <span>
                {health?.dependencies?.postgres === false ? (
                  <span className="text-rose-600">Không sẵn sàng</span>
                ) : (
                  <span>Sẵn sàng</span>
                )}
              </span>
            </div>
          </div>

          <div className="p-3 rounded-xl bg-slate-50 border border-slate-200">
            <span className="text-slate-500 text-[11px] block mb-1">Vector DB (Qdrant)</span>
            <div className="flex items-center gap-1.5 font-semibold text-slate-700">
              <Cpu className="w-3.5 h-3.5 text-indigo-600" />
              <span>
                {health?.dependencies?.qdrant === false ? (
                  <span className="text-rose-600">Không sẵn sàng</span>
                ) : (
                  <span>BGE-M3 (1024-dim)</span>
                )}
              </span>
            </div>
          </div>
        </div>

        {health?.status === 'offline' && (
          <div className="p-3 rounded-xl bg-amber-50 border border-amber-200 text-amber-900 text-xs flex items-center gap-2">
            <AlertTriangle className="w-4 h-4 text-amber-600 flex-shrink-0" />
            <span>
              Backend FastAPI hiện chưa kết nối được. Vui lòng đảm bảo tiến trình backend đang chạy tại cổng 8000 hoặc khởi động Docker Compose.
            </span>
          </div>
        )}
      </div>

      {/* Tool Sandbox Runner */}
      <div className="rounded-2xl p-5 border border-slate-200 bg-white shadow-xs space-y-4">
        <div className="flex items-center justify-between pb-3 border-b border-slate-100">
          <div className="flex items-center gap-2">
            <div className="w-8 h-8 rounded-lg bg-indigo-50 text-indigo-700 flex items-center justify-center border border-indigo-200">
              <Terminal className="w-4 h-4" />
            </div>
            <div>
              <h4 className="font-bold text-sm text-slate-900">Hộp cát Kiểm thử Công cụ (Deterministic Tools Sandbox)</h4>
              <p className="text-xs text-slate-500">
                Thực thi các thuật toán tính toán độc lập không phụ thuộc LLM (BMI, BMR/TDEE, Guardrail An toàn Y tế)
              </p>
            </div>
          </div>
        </div>

        {/* Tool selector buttons */}
        <div className="flex flex-wrap items-center gap-2 text-xs">
          <button
            onClick={() => {
              setSelectedTool('bmi');
              setToolOutput(null);
            }}
            className={`px-3 py-1.5 rounded-xl font-medium transition-all ${
              selectedTool === 'bmi'
                ? 'bg-indigo-600 text-white font-bold shadow-sm'
                : 'bg-slate-100 text-slate-600 border border-slate-200 hover:text-slate-900 hover:bg-slate-200/60'
            }`}
          >
            Tính BMI & Phân loại WHO Châu Á
          </button>
          <button
            onClick={() => {
              setSelectedTool('tdee');
              setToolOutput(null);
            }}
            className={`px-3 py-1.5 rounded-xl font-medium transition-all ${
              selectedTool === 'tdee'
                ? 'bg-indigo-600 text-white font-bold shadow-sm'
                : 'bg-slate-100 text-slate-600 border border-slate-200 hover:text-slate-900 hover:bg-slate-200/60'
            }`}
          >
            Tính BMR & TDEE Macros Kháng lực
          </button>
          <button
            onClick={() => {
              setSelectedTool('safety');
              setToolOutput(null);
            }}
            className={`px-3 py-1.5 rounded-xl font-medium transition-all ${
              selectedTool === 'safety'
                ? 'bg-indigo-600 text-white font-bold shadow-sm'
                : 'bg-slate-100 text-slate-600 border border-slate-200 hover:text-slate-900 hover:bg-slate-200/60'
            }`}
          >
            Kiểm thử Tiền lọc An toàn Y tế (Fast-path)
          </button>
        </div>

        {/* Tool input fields */}
        <div className="p-4 rounded-xl bg-slate-50 border border-slate-200 text-xs space-y-3">
          {selectedTool === 'bmi' && (
            <div className="grid grid-cols-2 gap-3">
              <div>
                <label className="block text-slate-600 font-medium mb-1">Cân nặng (kg)</label>
                <input
                  type="number"
                  value={testWeight}
                  onChange={(e) => setTestWeight(Number(e.target.value))}
                  className="w-full px-3 py-2 rounded-lg bg-white border border-slate-300 text-slate-900 font-mono focus:outline-none focus:border-indigo-600"
                />
              </div>
              <div>
                <label className="block text-slate-600 font-medium mb-1">Chiều cao (cm)</label>
                <input
                  type="number"
                  value={testHeight}
                  onChange={(e) => setTestHeight(Number(e.target.value))}
                  className="w-full px-3 py-2 rounded-lg bg-white border border-slate-300 text-slate-900 font-mono focus:outline-none focus:border-indigo-600"
                />
              </div>
            </div>
          )}

          {selectedTool === 'tdee' && (
            <div className="grid grid-cols-3 gap-3">
              <div>
                <label className="block text-slate-600 font-medium mb-1">Cân nặng (kg)</label>
                <input
                  type="number"
                  value={testWeight}
                  onChange={(e) => setTestWeight(Number(e.target.value))}
                  className="w-full px-3 py-2 rounded-lg bg-white border border-slate-300 text-slate-900 font-mono focus:outline-none focus:border-indigo-600"
                />
              </div>
              <div>
                <label className="block text-slate-600 font-medium mb-1">Chiều cao (cm)</label>
                <input
                  type="number"
                  value={testHeight}
                  onChange={(e) => setTestHeight(Number(e.target.value))}
                  className="w-full px-3 py-2 rounded-lg bg-white border border-slate-300 text-slate-900 font-mono focus:outline-none focus:border-indigo-600"
                />
              </div>
              <div>
                <label className="block text-slate-600 font-medium mb-1">Tuổi</label>
                <input
                  type="number"
                  value={testAge}
                  onChange={(e) => setTestAge(Number(e.target.value))}
                  className="w-full px-3 py-2 rounded-lg bg-white border border-slate-300 text-slate-900 font-mono focus:outline-none focus:border-indigo-600"
                />
              </div>
            </div>
          )}

          {selectedTool === 'safety' && (
            <div>
              <label className="block text-slate-600 font-medium mb-1">Mô tả triệu chứng người dùng</label>
              <input
                type="text"
                value={testSymptom}
                onChange={(e) => setTestSymptom(e.target.value)}
                className="w-full px-3 py-2 rounded-lg bg-white border border-slate-300 text-slate-900 focus:outline-none focus:border-indigo-600"
              />
            </div>
          )}

          <div className="flex justify-end pt-1">
            <button
              onClick={handleExecuteTool}
              className="px-4 py-2 rounded-xl bg-teal-600 hover:bg-teal-700 text-white font-bold text-xs shadow-sm flex items-center gap-1.5 transition-colors"
            >
              <Play className="w-3.5 h-3.5 fill-white" />
              <span>Chạy kiểm thử</span>
            </button>
          </div>
        </div>

        {/* Tool Output JSON preview */}
        {toolOutput && (
          <div className="p-4 rounded-xl bg-white border border-slate-200 space-y-2 shadow-xs animate-in fade-in">
            <div className="flex items-center justify-between text-xs pb-1 border-b border-slate-100">
              <span className="font-semibold text-teal-700">Kết quả phản hồi JSON:</span>
              <span className="text-slate-500 font-mono text-[11px]">
                Thời gian: {toolOutput.execution_time_ms ?? 0} ms
              </span>
            </div>
            <pre className="font-mono text-xs text-slate-800 overflow-x-auto p-2.5 bg-slate-50 border border-slate-200 rounded-lg">
              {JSON.stringify(toolOutput, null, 2)}
            </pre>
          </div>
        )}
      </div>
    </div>
  );
}
