'use client';

import React, { useState, useEffect } from 'react';
import {
  User,
  Target,
  ClipboardCheck,
  Brain,
  Save,
  Check,
  Trash2,
  AlertCircle,
  ShieldCheck,
  Star,
  Plus,
} from 'lucide-react';
import { UserProfile, UserGoal, CheckInLog, MemoryProposal } from '@/types';
import {
  fetchUserProfile,
  saveUserProfile,
  fetchCheckIns,
  saveCheckIn,
  fetchMemoryFacts,
  updateMemoryFactStatus,
  deleteMemoryFact,
} from '@/lib/api';
import { INITIAL_GOAL } from '@/lib/mockData';

export default function ProfileAndGoals() {
  const [profile, setProfile] = useState<UserProfile | null>(null);
  const [goal, setGoal] = useState<UserGoal>(INITIAL_GOAL);
  const [checkIns, setCheckIns] = useState<CheckInLog[]>([]);
  const [memoryFacts, setMemoryFacts] = useState<MemoryProposal[]>([]);
  const [isSaving, setIsSaving] = useState(false);
  const [saveSuccess, setSaveSuccess] = useState(false);

  // New Check-in form state
  const [rating, setRating] = useState(5);
  const [energy, setEnergy] = useState(4);
  const [sleep, setSleep] = useState(7.5);
  const [symptoms, setSymptoms] = useState('');
  const [checkInNotes, setCheckInNotes] = useState('');
  const [checkInSuccess, setCheckInSuccess] = useState(false);

  useEffect(() => {
    const load = async () => {
      const p = await fetchUserProfile();
      setProfile(p);
      const chk = await fetchCheckIns();
      setCheckIns(chk);
      const mem = await fetchMemoryFacts();
      setMemoryFacts(mem);
    };
    load();
  }, []);

  const handleSaveProfile = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!profile) return;
    setIsSaving(true);
    try {
      await saveUserProfile(profile);
      setSaveSuccess(true);
      setTimeout(() => setSaveSuccess(false), 3000);
    } catch (err) {
      console.error(err);
    } finally {
      setIsSaving(false);
    }
  };

  const handleAddCheckIn = async (e: React.FormEvent) => {
    e.preventDefault();
    const newLog = await saveCheckIn({
      workout_completed: true,
      workout_rating: rating,
      energy_level: energy,
      sleep_hours: sleep,
      unusual_symptoms: symptoms.trim() || undefined,
      notes: checkInNotes.trim() || undefined,
    });
    setCheckIns([newLog, ...checkIns]);
    setSymptoms('');
    setCheckInNotes('');
    setCheckInSuccess(true);
    setTimeout(() => setCheckInSuccess(false), 3000);
  };

  const handleConfirmMemory = async (id: string) => {
    await updateMemoryFactStatus(id, 'confirmed');
    setMemoryFacts(memoryFacts.map((f) => (f.id === id ? { ...f, status: 'confirmed' } : f)));
  };

  const handleDeleteMemory = async (id: string) => {
    await deleteMemoryFact(id);
    setMemoryFacts(memoryFacts.filter((f) => f.id !== id));
  };

  if (!profile) {
    return (
      <div className="p-8 text-center text-xs text-slate-400">Đang tải hồ sơ người dùng...</div>
    );
  }

  return (
    <div className="max-w-6xl mx-auto px-4 sm:px-6 py-6 space-y-6">
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* Profile Card */}
        <div className="glass-card rounded-2xl p-5 border border-slate-800/80 bg-slate-900/60 shadow-lg space-y-4">
          <div className="flex items-center justify-between pb-3 border-b border-slate-800">
            <div className="flex items-center gap-2">
              <div className="w-8 h-8 rounded-lg bg-indigo-500/20 text-indigo-400 flex items-center justify-center border border-indigo-500/30">
                <User className="w-4 h-4" />
              </div>
              <div>
                <h4 className="font-bold text-sm text-slate-100">Thông tin Cá nhân & Thể chất</h4>
                <p className="text-xs text-slate-400">Được mã hóa và chỉ dùng cho ngữ cảnh Agent</p>
              </div>
            </div>

            {saveSuccess && (
              <span className="text-xs text-emerald-400 flex items-center gap-1 font-semibold animate-in fade-in">
                <Check className="w-3.5 h-3.5" />
                <span>Đã lưu!</span>
              </span>
            )}
          </div>

          <form onSubmit={handleSaveProfile} className="space-y-3.5 text-xs">
            <div className="grid grid-cols-2 gap-3">
              <div>
                <label className="block text-slate-300 font-medium mb-1">Họ tên / Biệt danh</label>
                <input
                  type="text"
                  value={profile.display_name}
                  onChange={(e) => setProfile({ ...profile, display_name: e.target.value })}
                  className="w-full px-3 py-2 rounded-xl bg-slate-950 border border-slate-700 text-slate-100 focus:outline-none focus:border-indigo-500 font-medium"
                />
              </div>

              <div>
                <label className="block text-slate-300 font-medium mb-1">Tuổi</label>
                <input
                  type="number"
                  value={profile.age || 27}
                  onChange={(e) => setProfile({ ...profile, age: Number(e.target.value) })}
                  className="w-full px-3 py-2 rounded-xl bg-slate-950 border border-slate-700 text-slate-100 focus:outline-none focus:border-indigo-500 font-mono"
                />
              </div>

              <div>
                <label className="block text-slate-300 font-medium mb-1">Giới tính sinh học</label>
                <select
                  value={profile.sex}
                  onChange={(e) => setProfile({ ...profile, sex: e.target.value as any })}
                  className="w-full px-3 py-2 rounded-xl bg-slate-950 border border-slate-700 text-slate-100 focus:outline-none focus:border-indigo-500"
                >
                  <option value="male">Nam (WPRO Male standard)</option>
                  <option value="female">Nữ (WPRO Female standard)</option>
                </select>
              </div>

              <div>
                <label className="block text-slate-300 font-medium mb-1">Chiều cao (cm)</label>
                <input
                  type="number"
                  step="0.5"
                  value={profile.height_cm}
                  onChange={(e) => setProfile({ ...profile, height_cm: Number(e.target.value) })}
                  className="w-full px-3 py-2 rounded-xl bg-slate-950 border border-slate-700 text-slate-100 focus:outline-none focus:border-indigo-500 font-mono"
                />
              </div>
            </div>

            <div>
              <label className="block text-slate-300 font-medium mb-1">Mức độ hoạt động thể chất</label>
              <select
                value={profile.activity_level || 'moderate'}
                onChange={(e) => setProfile({ ...profile, activity_level: e.target.value as any })}
                className="w-full px-3 py-2 rounded-xl bg-slate-950 border border-slate-700 text-slate-100 focus:outline-none focus:border-indigo-500"
              >
                <option value="sedentary">Ít vận động (Dân văn phòng, ngồi nhiều)</option>
                <option value="light">Nhẹ (Tập thể dục 1-2 buổi/tuần)</option>
                <option value="moderate">Vừa phải (Tập gym/chạy bộ 3-5 buổi/tuần)</option>
                <option value="very_active">Nặng (Vận động viên hoặc lao động nặng)</option>
              </select>
            </div>

            <div>
              <label className="block text-slate-300 font-medium mb-1">Tiền sử bệnh nền / Cơ xương khớp</label>
              <input
                type="text"
                value={(profile.health_conditions || []).join(', ')}
                onChange={(e) =>
                  setProfile({
                    ...profile,
                    health_conditions: e.target.value.split(',').map((s) => s.trim()),
                  })
                }
                placeholder="Ví dụ: Căng mỏi thắt lưng, đau khớp gối..."
                className="w-full px-3 py-2 rounded-xl bg-slate-950 border border-slate-700 text-slate-100 focus:outline-none focus:border-indigo-500"
              />
            </div>

            <div>
              <label className="block text-slate-300 font-medium mb-1">Dị ứng & Kiêng cữ thức ăn</label>
              <input
                type="text"
                value={(profile.dietary_restrictions || []).join(', ')}
                onChange={(e) =>
                  setProfile({
                    ...profile,
                    dietary_restrictions: e.target.value.split(',').map((s) => s.trim()),
                  })
                }
                placeholder="Ví dụ: Không dung nạp lactose, kiêng đường..."
                className="w-full px-3 py-2 rounded-xl bg-slate-950 border border-slate-700 text-slate-100 focus:outline-none focus:border-indigo-500"
              />
            </div>

            <div className="flex items-center justify-end pt-2">
              <button
                type="submit"
                disabled={isSaving}
                className="px-4 py-2 rounded-xl bg-indigo-600 hover:bg-indigo-500 text-white font-bold text-xs shadow-md shadow-indigo-600/30 flex items-center gap-1.5 transition-all"
              >
                <Save className="w-3.5 h-3.5" />
                <span>{isSaving ? 'Đang lưu...' : 'Lưu Hồ sơ Cá nhân'}</span>
              </button>
            </div>
          </form>
        </div>

        {/* Goals & Targets */}
        <div className="glass-card rounded-2xl p-5 border border-slate-800/80 bg-slate-900/60 shadow-lg space-y-4">
          <div className="flex items-center justify-between pb-3 border-b border-slate-800">
            <div className="flex items-center gap-2">
              <div className="w-8 h-8 rounded-lg bg-emerald-500/20 text-emerald-400 flex items-center justify-center border border-emerald-500/30">
                <Target className="w-4 h-4" />
              </div>
              <div>
                <h4 className="font-bold text-sm text-slate-100">Mục tiêu Thể trạng & Hình thể</h4>
                <p className="text-xs text-slate-400">Định hướng kế hoạch tập luyện và calo thâm hụt</p>
              </div>
            </div>
          </div>

          <div className="space-y-3.5 text-xs">
            <div className="grid grid-cols-2 gap-3">
              <div>
                <label className="block text-slate-300 font-medium mb-1">Cân nặng mục tiêu (kg)</label>
                <input
                  type="number"
                  step="0.5"
                  value={goal.target_weight_kg || 70.0}
                  onChange={(e) => setGoal({ ...goal, target_weight_kg: Number(e.target.value) })}
                  className="w-full px-3 py-2 rounded-xl bg-slate-950 border border-slate-700 text-emerald-400 font-bold font-mono text-sm focus:outline-none focus:border-emerald-500"
                />
              </div>

              <div>
                <label className="block text-slate-300 font-medium mb-1">Tỷ lệ Mỡ mục tiêu (%)</label>
                <input
                  type="number"
                  step="0.5"
                  value={goal.target_body_fat_pct || 16.5}
                  onChange={(e) => setGoal({ ...goal, target_body_fat_pct: Number(e.target.value) })}
                  className="w-full px-3 py-2 rounded-xl bg-slate-950 border border-slate-700 text-amber-400 font-bold font-mono text-sm focus:outline-none focus:border-emerald-500"
                />
              </div>

              <div>
                <label className="block text-slate-300 font-medium mb-1">Khối Cơ xương SMM mục tiêu (kg)</label>
                <input
                  type="number"
                  step="0.5"
                  value={goal.target_skeletal_muscle_kg || 34.5}
                  onChange={(e) =>
                    setGoal({ ...goal, target_skeletal_muscle_kg: Number(e.target.value) })
                  }
                  className="w-full px-3 py-2 rounded-xl bg-slate-950 border border-slate-700 text-sky-400 font-bold font-mono text-sm focus:outline-none focus:border-emerald-500"
                />
              </div>

              <div>
                <label className="block text-slate-300 font-medium mb-1">Thời hạn dự kiến</label>
                <input
                  type="date"
                  value={goal.target_date || '2026-12-31'}
                  onChange={(e) => setGoal({ ...goal, target_date: e.target.value })}
                  className="w-full px-3 py-2 rounded-xl bg-slate-950 border border-slate-700 text-slate-100 font-mono text-xs focus:outline-none focus:border-emerald-500"
                />
              </div>
            </div>

            <div>
              <label className="block text-slate-300 font-medium mb-1">Ghi chú & Định hướng</label>
              <textarea
                value={goal.notes || ''}
                onChange={(e) => setGoal({ ...goal, notes: e.target.value })}
                rows={3}
                className="w-full px-3 py-2 rounded-xl bg-slate-950 border border-slate-700 text-slate-100 focus:outline-none focus:border-emerald-500"
                placeholder="Ghi chú chi tiết mục tiêu của bạn..."
              />
            </div>

            <div className="p-3 rounded-xl bg-emerald-950/40 border border-emerald-800/60 text-xs text-emerald-200 flex items-start gap-2">
              <ShieldCheck className="w-4 h-4 text-emerald-400 flex-shrink-0 mt-0.5" />
              <span>
                Mục tiêu này sẽ tự động được Agent tham chiếu khi tư vấn thực đơn calo thâm hụt và bài tập kháng lực trong mục Chat.
              </span>
            </div>
          </div>
        </div>
      </div>

      {/* Check-in & Memory Section */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* Weekly Check-in Log */}
        <div className="glass-card rounded-2xl p-5 border border-slate-800/80 bg-slate-900/60 shadow-lg space-y-4">
          <div className="flex items-center justify-between pb-3 border-b border-slate-800">
            <div className="flex items-center gap-2">
              <div className="w-8 h-8 rounded-lg bg-teal-500/20 text-teal-400 flex items-center justify-center border border-teal-500/30">
                <ClipboardCheck className="w-4 h-4" />
              </div>
              <div>
                <h4 className="font-bold text-sm text-slate-100">Check-in Thể trạng Định kỳ</h4>
                <p className="text-xs text-slate-400">Theo dõi hồi phục cơ bắp và cảnh báo triệu chứng</p>
              </div>
            </div>

            {checkInSuccess && (
              <span className="text-xs text-emerald-400 flex items-center gap-1 font-semibold animate-in fade-in">
                <Check className="w-3.5 h-3.5" />
                <span>Đã ghi nhận!</span>
              </span>
            )}
          </div>

          <form onSubmit={handleAddCheckIn} className="space-y-3 text-xs">
            <div className="grid grid-cols-3 gap-2.5">
              <div>
                <label className="block text-slate-400 mb-1">Mức hoàn thành tập</label>
                <div className="flex items-center gap-1 bg-slate-950 p-2 rounded-xl border border-slate-700 justify-center">
                  {[1, 2, 3, 4, 5].map((star) => (
                    <button
                      key={star}
                      type="button"
                      onClick={() => setRating(star)}
                      className="p-0.5"
                    >
                      <Star
                        className={`w-3.5 h-3.5 ${
                          star <= rating
                            ? 'text-amber-400 fill-amber-400'
                            : 'text-slate-600'
                        }`}
                      />
                    </button>
                  ))}
                </div>
              </div>

              <div>
                <label className="block text-slate-400 mb-1">Năng lượng (1-5)</label>
                <input
                  type="number"
                  min="1"
                  max="5"
                  value={energy}
                  onChange={(e) => setEnergy(Number(e.target.value))}
                  className="w-full px-3 py-2 rounded-xl bg-slate-950 border border-slate-700 text-center font-bold text-emerald-400 font-mono"
                />
              </div>

              <div>
                <label className="block text-slate-400 mb-1">Ngủ (tiếng/ngày)</label>
                <input
                  type="number"
                  step="0.5"
                  value={sleep}
                  onChange={(e) => setSleep(Number(e.target.value))}
                  className="w-full px-3 py-2 rounded-xl bg-slate-950 border border-slate-700 text-center font-bold text-sky-400 font-mono"
                />
              </div>
            </div>

            <div>
              <label className="block text-slate-400 mb-1">Triệu chứng bất thường (nếu có)</label>
              <input
                type="text"
                value={symptoms}
                onChange={(e) => setSymptoms(e.target.value)}
                placeholder="Ví dụ: Đau nhức vai trái, căng mỏi gân kheo..."
                className="w-full px-3 py-2 rounded-xl bg-slate-950 border border-slate-700 text-slate-100 focus:outline-none focus:border-teal-500"
              />
            </div>

            <div className="flex justify-end">
              <button
                type="submit"
                className="px-4 py-2 rounded-xl bg-teal-600 hover:bg-teal-500 text-white font-bold text-xs shadow-md shadow-teal-600/30 flex items-center gap-1.5"
              >
                <Plus className="w-3.5 h-3.5" />
                <span>Gửi Check-in Tuần Này</span>
              </button>
            </div>
          </form>

          {/* Recent check-ins */}
          <div className="pt-3 border-t border-slate-800 space-y-2">
            <span className="text-[11px] font-semibold text-slate-400 uppercase tracking-wider">
              Lịch sử check-in gần nhất:
            </span>
            {checkIns.map((chk) => (
              <div
                key={chk.id}
                className="p-2.5 rounded-xl bg-slate-950/70 border border-slate-800 text-xs flex items-center justify-between"
              >
                <div>
                  <div className="font-semibold text-slate-200 flex items-center gap-2">
                    <span>{chk.date}</span>
                    <span className="text-amber-400">★ {chk.workout_rating}/5</span>
                    <span className="text-sky-400 font-mono">{chk.sleep_hours}h ngủ</span>
                  </div>
                  {chk.unusual_symptoms && (
                    <div className="text-[11px] text-rose-300 mt-0.5">
                      ⚠️ {chk.unusual_symptoms}
                    </div>
                  )}
                </div>
              </div>
            ))}
          </div>
        </div>

        {/* Memory Facts Management */}
        <div className="glass-card rounded-2xl p-5 border border-slate-800/80 bg-slate-900/60 shadow-lg space-y-4">
          <div className="flex items-center justify-between pb-3 border-b border-slate-800">
            <div className="flex items-center gap-2">
              <div className="w-8 h-8 rounded-lg bg-purple-500/20 text-purple-400 flex items-center justify-center border border-purple-500/30">
                <Brain className="w-4 h-4" />
              </div>
              <div>
                <h4 className="font-bold text-sm text-slate-100">Ký ức Cá nhân hóa (Memory Facts)</h4>
                <p className="text-xs text-slate-400">Thông tin AI đã học được, bạn hoàn toàn kiểm soát</p>
              </div>
            </div>
          </div>

          <div className="space-y-2 text-xs">
            {memoryFacts.map((fact) => (
              <div
                key={fact.id}
                className="p-3 rounded-xl bg-slate-950/80 border border-slate-800 flex items-start justify-between gap-3 group"
              >
                <div className="space-y-1">
                  <div className="flex items-center gap-2">
                    <span className="text-[10px] px-1.5 py-0.2 rounded bg-purple-950 text-purple-300 border border-purple-800">
                      {fact.category}
                    </span>
                    <span className="text-[10px] text-slate-500 font-mono">
                      Tin cậy: {Math.round(fact.confidence * 100)}%
                    </span>
                    {fact.status === 'confirmed' && (
                      <span className="text-[10px] text-emerald-400 font-semibold flex items-center gap-0.5">
                        <Check className="w-3 h-3" />
                        <span>Đã xác nhận</span>
                      </span>
                    )}
                  </div>
                  <p className="text-slate-200 font-medium leading-relaxed">{fact.fact}</p>
                </div>

                <div className="flex items-center gap-1.5 flex-shrink-0">
                  {fact.status !== 'confirmed' && (
                    <button
                      onClick={() => handleConfirmMemory(fact.id)}
                      className="p-1.5 rounded-lg bg-emerald-600/20 hover:bg-emerald-600/40 text-emerald-300 border border-emerald-500/40"
                      title="Xác nhận sự thật này"
                    >
                      <Check className="w-3.5 h-3.5" />
                    </button>
                  )}
                  <button
                    onClick={() => handleDeleteMemory(fact.id)}
                    className="p-1.5 rounded-lg bg-slate-800 hover:bg-rose-900/40 text-slate-400 hover:text-rose-300 border border-slate-700"
                    title="Xóa vĩnh viễn sự thật này"
                  >
                    <Trash2 className="w-3.5 h-3.5" />
                  </button>
                </div>
              </div>
            ))}
          </div>
        </div>
      </div>
    </div>
  );
}
