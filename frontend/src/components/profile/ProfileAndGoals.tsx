'use client';

import React, { useState, useEffect, useCallback } from 'react';
import {
  User,
  Target,
  ClipboardCheck,
  Brain,
  Save,
  Check,
  Trash2,
  ShieldCheck,
  Star,
  Plus,
  Loader2,
  AlertCircle,
  RotateCw,
  Info,
} from 'lucide-react';
import { UserProfile, UserGoal, CheckInLog, MemoryProposal, SexAtBirthType, ActivityLevelType } from '@/types';
import {
  fetchUserProfile,
  saveUserProfile,
  fetchCheckIns,
  saveCheckIn,
  fetchMemoryFacts,
  updateMemoryFactStatus,
  deleteMemoryFact,
  getAuthMode,
} from '@/lib/api';
import { INITIAL_GOAL } from '@/lib/mockData';

interface ProfileAndGoalsProps {
  onProfileSaved?: () => void;
}

export default function ProfileAndGoals({ onProfileSaved }: ProfileAndGoalsProps) {
  const [profile, setProfile] = useState<UserProfile | null>(null);
  const [goal, setGoal] = useState<UserGoal>(INITIAL_GOAL);
  const [checkIns, setCheckIns] = useState<CheckInLog[]>([]);
  const [memoryFacts, setMemoryFacts] = useState<MemoryProposal[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [isSaving, setIsSaving] = useState(false);
  const [saveSuccess, setSaveSuccess] = useState(false);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);

  // New Check-in form state
  const [rating, setRating] = useState(5);
  const [energy, setEnergy] = useState(4);
  const [sleep, setSleep] = useState(7.5);
  const [symptoms, setSymptoms] = useState('');
  const [checkInNotes, setCheckInNotes] = useState('');
  const [checkInSuccess, setCheckInSuccess] = useState(false);
  const [isSubmittingCheckIn, setIsSubmittingCheckIn] = useState(false);

  const loadAllData = useCallback(async () => {
    setIsLoading(true);
    setErrorMessage(null);
    try {
      const [p, chk, mem] = await Promise.allSettled([
        fetchUserProfile(),
        fetchCheckIns(),
        fetchMemoryFacts(),
      ]);

      if (p.status === 'fulfilled') {
        setProfile(p.value);
      } else {
        setErrorMessage(p.reason instanceof Error ? p.reason.message : 'Không thể tải hồ sơ cá nhân.');
      }

      if (chk.status === 'fulfilled') {
        setCheckIns(chk.value);
      }

      if (mem.status === 'fulfilled') {
        setMemoryFacts(mem.value);
      }
    } finally {
      setIsLoading(false);
    }
  }, []);

  useEffect(() => {
    let ignore = false;
    async function init() {
      setIsLoading(true);
      setErrorMessage(null);
      try {
        const [prof, chk, mem] = await Promise.allSettled([
          fetchUserProfile(),
          fetchCheckIns(),
          fetchMemoryFacts(),
        ]);

        if (ignore) return;

        if (prof.status === 'fulfilled') {
          setProfile(prof.value);
        } else {
          setErrorMessage(
            prof.reason instanceof Error
              ? prof.reason.message
              : 'Không thể kết nối đến máy chủ để tải hồ sơ cá nhân.'
          );
        }

        if (chk.status === 'fulfilled') {
          setCheckIns(chk.value);
        }

        if (mem.status === 'fulfilled') {
          setMemoryFacts(mem.value);
        }
      } finally {
        if (!ignore) {
          setIsLoading(false);
        }
      }
    }
    init();
    return () => {
      ignore = true;
    };
  }, []);

  const handleSaveProfile = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!profile) return;
    setIsSaving(true);
    setErrorMessage(null);
    try {
      const updated = await saveUserProfile(profile);
      setProfile(updated);
      setSaveSuccess(true);
      if (onProfileSaved) onProfileSaved();
      setTimeout(() => setSaveSuccess(false), 3000);
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : 'Không thể lưu hồ sơ cá nhân.';
      setErrorMessage(msg);
    } finally {
      setIsSaving(false);
    }
  };

  const handleAddCheckIn = async (e: React.FormEvent) => {
    e.preventDefault();
    setIsSubmittingCheckIn(true);
    try {
      const newLog = await saveCheckIn({
        workout_completed: true,
        workout_rating: rating,
        energy_level: energy,
        sleep_hours: sleep,
        unusual_symptoms: symptoms.trim() || undefined,
        notes: checkInNotes.trim() || undefined,
      });
      setCheckIns((prev) => [newLog, ...prev]);
      setSymptoms('');
      setCheckInNotes('');
      setCheckInSuccess(true);
      setTimeout(() => setCheckInSuccess(false), 3000);
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : 'Không thể lưu check-in.';
      alert(msg);
    } finally {
      setIsSubmittingCheckIn(false);
    }
  };

  const handleConfirmMemory = async (id: string) => {
    try {
      await updateMemoryFactStatus(id, 'confirmed');
      setMemoryFacts((prev) =>
        prev.map((f) => (f.id === id ? { ...f, status: 'confirmed' } : f))
      );
    } catch (err: unknown) {
      alert(err instanceof Error ? err.message : 'Lỗi khi xác nhận ký ức.');
    }
  };

  const handleDeleteMemory = async (id: string) => {
    try {
      await deleteMemoryFact(id);
      setMemoryFacts((prev) => prev.filter((f) => f.id !== id));
    } catch (err: unknown) {
      alert(err instanceof Error ? err.message : 'Lỗi khi xóa ký ức.');
    }
  };

  return (
    <div className="max-w-6xl mx-auto px-4 sm:px-6 py-6 space-y-6">
      {/* Production Auth Notice */}
      {getAuthMode() === 'production' && (
        <div className="p-4 rounded-2xl bg-amber-950/40 border border-amber-600/50 text-amber-200 text-xs flex items-start gap-3 shadow-md">
          <Info className="w-4 h-4 text-amber-400 flex-shrink-0 mt-0.5" />
          <div className="space-y-1">
            <span className="font-bold text-amber-300">Cơ chế Bảo vệ Danh tính Y tế (Production Auth Gate)</span>
            <p className="text-amber-200/90 leading-relaxed">
              Dữ liệu sức khỏe được bảo vệ nghiêm ngặt. Khi chưa đăng nhập qua Auth Gateway có chữ ký máy chủ, các thay đổi cá nhân chỉ áp dụng trong phạm vi phiên hoặc hiển thị có giới hạn.
            </p>
          </div>
        </div>
      )}

      {/* Global Error Notice */}
      {errorMessage && (
        <div className="p-4 rounded-2xl bg-rose-950/60 border border-rose-800 text-rose-200 text-xs flex items-center justify-between gap-3 shadow-md">
          <div className="flex items-center gap-2.5">
            <AlertCircle className="w-4 h-4 text-rose-400 flex-shrink-0" />
            <span>{errorMessage}</span>
          </div>
          <button
            onClick={loadAllData}
            className="px-3 py-1.5 rounded-xl bg-rose-900/80 hover:bg-rose-800 text-white font-semibold flex items-center gap-1.5 transition-colors"
          >
            <RotateCw className="w-3.5 h-3.5" />
            <span>Thử lại</span>
          </button>
        </div>
      )}

      {/* Loading Skeleton */}
      {isLoading && (
        <div className="flex items-center gap-2 px-3.5 py-2 rounded-xl bg-slate-900/90 border border-slate-800 text-xs text-slate-300 w-fit shadow-sm">
          <Loader2 className="w-4 h-4 animate-spin text-teal-400" />
          <span>Đang đồng bộ hồ sơ và ký ức cá nhân hóa từ máy chủ...</span>
        </div>
      )}

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* Profile Card */}
        <div className="glass-card rounded-2xl p-5 border border-slate-800/80 bg-slate-900/60 shadow-lg space-y-4">
          <div className="flex items-center justify-between pb-3 border-b border-slate-800">
            <div className="flex items-center gap-2">
              <div className="w-8 h-8 rounded-lg bg-teal-500/20 text-teal-400 flex items-center justify-center border border-teal-500/30">
                <User className="w-4 h-4" />
              </div>
              <div>
                <h4 className="font-bold text-sm text-slate-100">Thông tin Cá nhân & Thể chất</h4>
                <p className="text-xs text-slate-400">Được bảo vệ theo quyền riêng tư và dùng cho Agent</p>
              </div>
            </div>

            {saveSuccess && (
              <span className="text-xs text-teal-400 flex items-center gap-1 font-semibold animate-in fade-in">
                <Check className="w-3.5 h-3.5" />
                <span>Đã lưu thành công!</span>
              </span>
            )}
          </div>

          {profile ? (
            <form onSubmit={handleSaveProfile} className="space-y-3.5 text-xs">
              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label className="block text-slate-300 font-medium mb-1">Họ tên / Biệt danh</label>
                  <input
                    type="text"
                    value={profile.display_name}
                    onChange={(e) => setProfile({ ...profile, display_name: e.target.value })}
                    className="w-full px-3 py-2 rounded-xl bg-slate-950 border border-slate-700 text-slate-100 focus:outline-none focus:border-teal-500 font-medium"
                    required
                  />
                </div>

                <div>
                  <label className="block text-slate-300 font-medium mb-1">Tuổi</label>
                  <input
                    type="number"
                    min="10"
                    max="100"
                    value={profile.age || ''}
                    onChange={(e) =>
                      setProfile({ ...profile, age: e.target.value ? Number(e.target.value) : undefined })
                    }
                    placeholder="27"
                    className="w-full px-3 py-2 rounded-xl bg-slate-950 border border-slate-700 text-slate-100 focus:outline-none focus:border-teal-500 font-mono"
                  />
                </div>

                <div>
                  <label className="block text-slate-300 font-medium mb-1">Giới tính sinh học</label>
                  <select
                    value={profile.sex_at_birth || profile.sex}
                    onChange={(e) =>
                      setProfile({
                        ...profile,
                        sex: e.target.value as 'male' | 'female',
                        sex_at_birth: e.target.value as SexAtBirthType,
                      })
                    }
                    className="w-full px-3 py-2 rounded-xl bg-slate-950 border border-slate-700 text-slate-100 focus:outline-none focus:border-teal-500"
                  >
                    <option value="male">Nam (Chuẩn WPRO Châu Á)</option>
                    <option value="female">Nữ (Chuẩn WPRO Châu Á)</option>
                  </select>
                </div>

                <div>
                  <label className="block text-slate-300 font-medium mb-1">Chiều cao (cm)</label>
                  <input
                    type="number"
                    step="0.5"
                    min="100"
                    max="230"
                    value={profile.height_cm}
                    onChange={(e) => setProfile({ ...profile, height_cm: Number(e.target.value) })}
                    className="w-full px-3 py-2 rounded-xl bg-slate-950 border border-slate-700 text-slate-100 focus:outline-none focus:border-teal-500 font-mono"
                    required
                  />
                </div>
              </div>

              <div>
                <label className="block text-slate-300 font-medium mb-1">Mức độ hoạt động thể chất</label>
                <select
                  value={profile.activity_level || 'moderate'}
                  onChange={(e) => setProfile({ ...profile, activity_level: e.target.value as ActivityLevelType })}
                  className="w-full px-3 py-2 rounded-xl bg-slate-950 border border-slate-700 text-slate-100 focus:outline-none focus:border-teal-500"
                >
                  <option value="sedentary">Ít vận động (Dân văn phòng, ngồi nhiều)</option>
                  <option value="light">Nhẹ (Tập thể dục 1-2 buổi/tuần)</option>
                  <option value="moderate">Vừa phải (Tập gym/chạy bộ 3-5 buổi/tuần)</option>
                  <option value="very_active">Nặng (Vận động viên hoặc lao động nặng)</option>
                </select>
              </div>

              <div>
                <label className="block text-slate-300 font-medium mb-1">Tiền sử bệnh nền / Khớp</label>
                <input
                  type="text"
                  value={(profile.health_conditions || profile.medical_conditions || []).join(', ')}
                  onChange={(e) =>
                    setProfile({
                      ...profile,
                      health_conditions: e.target.value.split(',').map((s) => s.trim()).filter(Boolean),
                      medical_conditions: e.target.value.split(',').map((s) => s.trim()).filter(Boolean),
                    })
                  }
                  placeholder="Ví dụ: Đau mỏi thắt lưng, thoái hóa khớp gối..."
                  className="w-full px-3 py-2 rounded-xl bg-slate-950 border border-slate-700 text-slate-100 focus:outline-none focus:border-teal-500"
                />
              </div>

              <div>
                <label className="block text-slate-300 font-medium mb-1">Dị ứng & Kiêng cữ thức ăn</label>
                <input
                  type="text"
                  value={(profile.dietary_restrictions || profile.dietary_preferences || []).join(', ')}
                  onChange={(e) =>
                    setProfile({
                      ...profile,
                      dietary_restrictions: e.target.value.split(',').map((s) => s.trim()).filter(Boolean),
                      dietary_preferences: e.target.value.split(',').map((s) => s.trim()).filter(Boolean),
                    })
                  }
                  placeholder="Ví dụ: Không dung nạp lactose, kiêng đường..."
                  className="w-full px-3 py-2 rounded-xl bg-slate-950 border border-slate-700 text-slate-100 focus:outline-none focus:border-teal-500"
                />
              </div>

              <div className="flex items-center justify-end pt-2">
                <button
                  type="submit"
                  disabled={isSaving}
                  className="px-4 py-2 rounded-xl bg-gradient-to-r from-teal-500 to-sky-500 hover:brightness-110 text-slate-950 font-bold text-xs shadow-md shadow-teal-500/25 flex items-center gap-1.5 transition-all disabled:opacity-60"
                >
                  {isSaving ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : <Save className="w-3.5 h-3.5" />}
                  <span>{isSaving ? 'Đang lưu...' : 'Lưu Hồ sơ Cá nhân'}</span>
                </button>
              </div>
            </form>
          ) : (
            <div className="py-8 text-center text-xs text-slate-500">
              Chưa thể tải dữ liệu hồ sơ. Vui lòng kiểm tra kết nối mạng.
            </div>
          )}
        </div>

        {/* Goals & Targets */}
        <div className="glass-card rounded-2xl p-5 border border-slate-800/80 bg-slate-900/60 shadow-lg space-y-4">
          <div className="flex items-center justify-between pb-3 border-b border-slate-800">
            <div className="flex items-center gap-2">
              <div className="w-8 h-8 rounded-lg bg-sky-500/20 text-sky-400 flex items-center justify-center border border-sky-500/30">
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
                  value={goal.target_weight_kg || ''}
                  onChange={(e) => setGoal({ ...goal, target_weight_kg: Number(e.target.value) })}
                  placeholder="70.0"
                  className="w-full px-3 py-2 rounded-xl bg-slate-950 border border-slate-700 text-teal-400 font-bold font-mono text-sm focus:outline-none focus:border-teal-500"
                />
              </div>

              <div>
                <label className="block text-slate-300 font-medium mb-1">Tỷ lệ Mỡ mục tiêu (%)</label>
                <input
                  type="number"
                  step="0.5"
                  value={goal.target_body_fat_pct || ''}
                  onChange={(e) => setGoal({ ...goal, target_body_fat_pct: Number(e.target.value) })}
                  placeholder="16.5"
                  className="w-full px-3 py-2 rounded-xl bg-slate-950 border border-slate-700 text-amber-400 font-bold font-mono text-sm focus:outline-none focus:border-teal-500"
                />
              </div>

              <div>
                <label className="block text-slate-300 font-medium mb-1">Khối Cơ xương SMM (kg)</label>
                <input
                  type="number"
                  step="0.5"
                  value={goal.target_skeletal_muscle_kg || ''}
                  onChange={(e) =>
                    setGoal({ ...goal, target_skeletal_muscle_kg: Number(e.target.value) })
                  }
                  placeholder="34.5"
                  className="w-full px-3 py-2 rounded-xl bg-slate-950 border border-slate-700 text-sky-400 font-bold font-mono text-sm focus:outline-none focus:border-teal-500"
                />
              </div>

              <div>
                <label className="block text-slate-300 font-medium mb-1">Thời hạn dự kiến</label>
                <input
                  type="date"
                  value={goal.target_date || ''}
                  onChange={(e) => setGoal({ ...goal, target_date: e.target.value })}
                  className="w-full px-3 py-2 rounded-xl bg-slate-950 border border-slate-700 text-slate-100 font-mono text-xs focus:outline-none focus:border-teal-500"
                />
              </div>
            </div>

            <div>
              <label className="block text-slate-300 font-medium mb-1">Ghi chú & Định hướng</label>
              <textarea
                value={goal.notes || ''}
                onChange={(e) => setGoal({ ...goal, notes: e.target.value })}
                rows={3}
                className="w-full px-3 py-2 rounded-xl bg-slate-950 border border-slate-700 text-slate-100 focus:outline-none focus:border-teal-500"
                placeholder="Ghi chú chi tiết mục tiêu của bạn..."
              />
            </div>

            <div className="p-3 rounded-xl bg-teal-950/40 border border-teal-800/60 text-xs text-teal-200 flex items-start gap-2">
              <ShieldCheck className="w-4 h-4 text-teal-400 flex-shrink-0 mt-0.5" />
              <span>
                Mục tiêu này sẽ tự động được Trợ lý AI BodyWise tham chiếu khi gợi ý thực đơn đa lượng (macros) và lịch tập kháng lực.
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
                <p className="text-xs text-slate-400">Ghi nhận mức năng lượng và cảnh báo triệu chứng</p>
              </div>
            </div>

            {checkInSuccess && (
              <span className="text-xs text-teal-400 flex items-center gap-1 font-semibold animate-in fade-in">
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
                  className="w-full px-3 py-2 rounded-xl bg-slate-950 border border-slate-700 text-center font-bold text-teal-400 font-mono"
                />
              </div>

              <div>
                <label className="block text-slate-400 mb-1">Ngủ (tiếng/ngày)</label>
                <input
                  type="number"
                  step="0.5"
                  min="3"
                  max="14"
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
                placeholder="Ví dụ: Đau mỏi khớp vai, căng gân kheo..."
                className="w-full px-3 py-2 rounded-xl bg-slate-950 border border-slate-700 text-slate-100 focus:outline-none focus:border-teal-500"
              />
            </div>

            <div className="flex justify-end">
              <button
                type="submit"
                disabled={isSubmittingCheckIn}
                className="px-4 py-2 rounded-xl bg-teal-600 hover:bg-teal-500 text-slate-950 font-bold text-xs shadow-md shadow-teal-600/30 flex items-center gap-1.5 transition-transform active:scale-95 disabled:opacity-60"
              >
                {isSubmittingCheckIn ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : <Plus className="w-3.5 h-3.5" />}
                <span>{isSubmittingCheckIn ? 'Đang gửi...' : 'Gửi Check-in Tuần Này'}</span>
              </button>
            </div>
          </form>

          {/* Recent check-ins */}
          <div className="pt-3 border-t border-slate-800 space-y-2">
            <span className="text-[11px] font-semibold text-slate-400 uppercase tracking-wider">
              Lịch sử check-in gần nhất ({checkIns.length}):
            </span>
            {checkIns.length > 0 ? (
              checkIns.slice(0, 5).map((chk) => (
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
              ))
            ) : (
              <div className="text-xs text-slate-500 py-3 text-center">
                Chưa có bản ghi check-in nào. Hãy gửi bản check-in đầu tiên ở trên!
              </div>
            )}
          </div>
        </div>

        {/* Memory Facts Management */}
        <div className="glass-card rounded-2xl p-5 border border-slate-800/80 bg-slate-900/60 shadow-lg space-y-4">
          <div className="flex items-center justify-between pb-3 border-b border-slate-800">
            <div className="flex items-center gap-2">
              <div className="w-8 h-8 rounded-lg bg-sky-500/20 text-sky-400 flex items-center justify-center border border-sky-500/30">
                <Brain className="w-4 h-4" />
              </div>
              <div>
                <h4 className="font-bold text-sm text-slate-100">Ký ức Cá nhân hóa (Memory Facts)</h4>
                <p className="text-xs text-slate-400">Sự thật thể trạng AI ghi nhận, bạn toàn quyền kiểm soát</p>
              </div>
            </div>
          </div>

          <div className="space-y-2 text-xs">
            {memoryFacts.length > 0 ? (
              memoryFacts.map((fact) => (
                <div
                  key={fact.id}
                  className="p-3 rounded-xl bg-slate-950/80 border border-slate-800 flex items-start justify-between gap-3 group"
                >
                  <div className="space-y-1">
                    <div className="flex items-center gap-2">
                      <span className="text-[10px] px-1.5 py-0.5 rounded bg-sky-950 text-sky-300 border border-sky-800 uppercase font-semibold">
                        {fact.category}
                      </span>
                      {fact.status === 'confirmed' ? (
                        <span className="text-[10px] text-teal-400 font-semibold flex items-center gap-0.5">
                          <Check className="w-3 h-3" />
                          <span>Đã xác nhận</span>
                        </span>
                      ) : (
                        <span className="text-[10px] text-amber-400 font-semibold">
                          Chờ xác nhận
                        </span>
                      )}
                    </div>
                    <p className="text-slate-200 font-medium leading-relaxed">{fact.fact}</p>
                  </div>

                  <div className="flex items-center gap-1.5 flex-shrink-0">
                    {fact.status !== 'confirmed' && (
                      <button
                        onClick={() => handleConfirmMemory(fact.id)}
                        className="p-1.5 rounded-lg bg-teal-600/20 hover:bg-teal-600/40 text-teal-300 border border-teal-500/40 transition-colors"
                        title="Xác nhận sự thật này"
                      >
                        <Check className="w-3.5 h-3.5" />
                      </button>
                    )}
                    <button
                      onClick={() => handleDeleteMemory(fact.id)}
                      className="p-1.5 rounded-lg bg-slate-800 hover:bg-rose-900/40 text-slate-400 hover:text-rose-300 border border-slate-700 transition-colors"
                      title="Xóa vĩnh viễn sự thật này"
                    >
                      <Trash2 className="w-3.5 h-3.5" />
                    </button>
                  </div>
                </div>
              ))
            ) : (
              <div className="p-6 text-center text-xs text-slate-500 rounded-xl bg-slate-950/40 border border-slate-800">
                Chưa có sự thật nào được trích xuất. Khi bạn trò chuyện cùng Trợ lý AI (ví dụ: chia sẻ dị ứng thức ăn hoặc tiền sử vận động), các sự thật thể trạng sẽ tự động xuất hiện tại đây để bạn kiểm soát.
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}
