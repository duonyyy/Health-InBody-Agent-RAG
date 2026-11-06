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
} from 'lucide-react';
import { UserProfile, UserGoal, CheckInLog, MemoryProposal, SexAtBirthType, ActivityLevelType } from '@/types';
import {
  fetchUserProfile,
  fetchCurrentGoal,
  saveCurrentGoal,
  saveUserProfile,
  fetchCheckIns,
  saveCheckIn,
  fetchMemoryFacts,
  updateMemoryFactStatus,
  deleteMemoryFact,
} from '@/lib/api';

interface ProfileAndGoalsProps {
  onProfileSaved?: () => void;
}

export default function ProfileAndGoals({ onProfileSaved }: ProfileAndGoalsProps) {
  const [profile, setProfile] = useState<UserProfile | null>(null);
  const [goal, setGoal] = useState<UserGoal>({});
  const [isSavingGoal, setIsSavingGoal] = useState(false);
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
      const [p, chk, mem, currentGoal] = await Promise.allSettled([
        fetchUserProfile(),
        fetchCheckIns(),
        fetchMemoryFacts(),
        fetchCurrentGoal(),
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
      if (currentGoal.status === 'fulfilled') setGoal(currentGoal.value || {});
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
        const [prof, chk, mem, currentGoal] = await Promise.allSettled([
          fetchUserProfile(),
          fetchCheckIns(),
          fetchMemoryFacts(),
          fetchCurrentGoal(),
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
        if (currentGoal.status === 'fulfilled') setGoal(currentGoal.value || {});
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

  const handleSaveGoal = async (e: React.FormEvent) => {
    e.preventDefault();
    setIsSavingGoal(true);
    setErrorMessage(null);
    try {
      setGoal(await saveCurrentGoal(goal));
      if (onProfileSaved) onProfileSaved();
    } catch (err) {
      setErrorMessage(err instanceof Error ? err.message : 'Không thể lưu mục tiêu.');
    } finally {
      setIsSavingGoal(false);
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
      {/* Global Error Notice */}
      {errorMessage && (
        <div className="p-4 rounded-2xl bg-rose-50 border border-rose-200 text-rose-900 text-xs flex items-center justify-between gap-3 shadow-xs">
          <div className="flex items-center gap-2.5">
            <AlertCircle className="w-4 h-4 text-rose-600 flex-shrink-0" />
            <span className="font-medium">{errorMessage}</span>
          </div>
          <button
            onClick={loadAllData}
            className="px-3 py-1.5 rounded-xl bg-rose-600 hover:bg-rose-700 text-white font-semibold flex items-center gap-1.5 transition-colors"
          >
            <RotateCw className="w-3.5 h-3.5" />
            <span>Thử lại</span>
          </button>
        </div>
      )}

      {/* Loading Skeleton */}
      {isLoading && (
        <div className="flex items-center gap-2 px-3.5 py-2 rounded-xl bg-white border border-slate-200 text-xs text-slate-700 w-fit shadow-xs">
          <Loader2 className="w-4 h-4 animate-spin text-teal-600" />
          <span>Đang đồng bộ hồ sơ và ký ức cá nhân hóa từ máy chủ...</span>
        </div>
      )}

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* Profile Card */}
        <div className="rounded-2xl p-5 border border-slate-200 bg-white shadow-xs space-y-4">
          <div className="flex items-center justify-between pb-3 border-b border-slate-100">
            <div className="flex items-center gap-2">
              <div className="w-8 h-8 rounded-lg bg-teal-50 text-teal-700 flex items-center justify-center border border-teal-200">
                <User className="w-4 h-4" />
              </div>
              <div>
                <h4 className="font-bold text-sm text-slate-900">Thông tin Cá nhân & Thể chất</h4>
                <p className="text-xs text-slate-500">Được bảo vệ theo quyền riêng tư và dùng cho Agent</p>
              </div>
            </div>

            {saveSuccess && (
              <span className="text-xs text-teal-700 flex items-center gap-1 font-semibold animate-in fade-in">
                <Check className="w-3.5 h-3.5" />
                <span>Đã lưu thành công!</span>
              </span>
            )}
          </div>

          {profile ? (
            <form onSubmit={handleSaveProfile} className="space-y-3.5 text-xs">
              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label className="block text-slate-700 font-medium mb-1">Họ tên / Biệt danh</label>
                  <input
                    type="text"
                    value={profile.display_name}
                    onChange={(e) => setProfile({ ...profile, display_name: e.target.value })}
                    className="w-full px-3 py-2 rounded-xl bg-slate-50 border border-slate-300 text-slate-900 focus:bg-white focus:outline-none focus:border-teal-600 font-medium"
                    required
                  />
                </div>

                <div>
                  <label className="block text-slate-700 font-medium mb-1">Nhóm tuổi</label>
                  <select value={profile.age_range || ''}
                    onChange={(e) => setProfile({ ...profile, age_range: e.target.value || undefined, birth_date: undefined })}
                    className="w-full px-3 py-2 rounded-xl bg-slate-50 border border-slate-300 text-slate-900">
                    <option value="">Chưa chọn</option>
                    <option value="under_18">Dưới 18</option>
                    <option value="18_24">18–24</option>
                    <option value="25_34">25–34</option>
                    <option value="35_44">35–44</option>
                    <option value="45_54">45–54</option>
                    <option value="55_64">55–64</option>
                    <option value="65_plus">65 trở lên</option>
                  </select>
                </div>

                <div>
                  <label className="block text-slate-700 font-medium mb-1">Giới tính sinh học</label>
                  <select
                    value={profile.sex_at_birth || profile.sex || ''}
                    onChange={(e) =>
                      setProfile({
                        ...profile,
                        sex: e.target.value === 'male' || e.target.value === 'female' ? e.target.value : undefined,
                        sex_at_birth: e.target.value as SexAtBirthType,
                      })
                    }
                    className="w-full px-3 py-2 rounded-xl bg-slate-50 border border-slate-300 text-slate-900 focus:bg-white focus:outline-none focus:border-teal-600 font-medium"
                  >
                    <option value="" disabled>Chọn giới tính sinh học</option>
                    <option value="male">Nam (Chuẩn WPRO Châu Á)</option>
                    <option value="female">Nữ (Chuẩn WPRO Châu Á)</option>
                    <option value="intersex">Liên giới tính</option>
                    <option value="prefer_not_to_say">Không muốn trả lời</option>
                  </select>
                </div>

                <div>
                  <label className="block text-slate-700 font-medium mb-1">Chiều cao (cm)</label>
                  <input
                    type="number"
                    step="0.5"
                    min="100"
                    max="230"
                    value={profile.height_cm ?? ''}
                    onChange={(e) => setProfile({ ...profile, height_cm: Number(e.target.value) })}
                    className="w-full px-3 py-2 rounded-xl bg-slate-50 border border-slate-300 text-slate-900 focus:bg-white focus:outline-none focus:border-teal-600 font-mono"
                    required
                  />
                </div>
              </div>

              <div>
                <label className="block text-slate-700 font-medium mb-1">Mức độ hoạt động thể chất</label>
                <select
                  value={profile.activity_level || ''}
                  onChange={(e) => setProfile({ ...profile, activity_level: e.target.value as ActivityLevelType })}
                  className="w-full px-3 py-2 rounded-xl bg-slate-50 border border-slate-300 text-slate-900 focus:bg-white focus:outline-none focus:border-teal-600 font-medium"
                >
                  <option value="" disabled>Chọn mức độ hoạt động</option>
                  <option value="low">Ít vận động</option>
                  <option value="moderate">Vừa phải (Tập gym/chạy bộ 3-5 buổi/tuần)</option>
                  <option value="high">Nhiều</option>
                  <option value="very_high">Rất nhiều</option>
                </select>
              </div>

              <div>
                <label className="block text-slate-700 font-medium mb-1">Tiền sử bệnh nền / Khớp</label>
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
                  className="w-full px-3 py-2 rounded-xl bg-slate-50 border border-slate-300 text-slate-900 focus:bg-white focus:outline-none focus:border-teal-600"
                />
              </div>

              <div>
                <label className="block text-slate-700 font-medium mb-1">Dị ứng & Kiêng cữ thức ăn</label>
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
                  className="w-full px-3 py-2 rounded-xl bg-slate-50 border border-slate-300 text-slate-900 focus:bg-white focus:outline-none focus:border-teal-600"
                />
              </div>

              <div className="flex items-center justify-end pt-2">
                <div className="mr-auto space-y-2 text-xs text-slate-700">
                  <label className="flex items-center gap-2">
                    <input type="checkbox" checked={Boolean(profile.consent_flags?.health_data_processing)}
                      onChange={(e) => setProfile({ ...profile, consent_flags: {
                        health_data_processing: e.target.checked,
                        personalization: e.target.checked && Boolean(profile.consent_flags?.personalization),
                      } })} />
                    Đồng ý xử lý dữ liệu sức khỏe
                  </label>
                  <label className="flex items-center gap-2">
                    <input type="checkbox" checked={Boolean(profile.consent_flags?.personalization)}
                      disabled={!profile.consent_flags?.health_data_processing}
                      onChange={(e) => setProfile({ ...profile, consent_flags: {
                        health_data_processing: true, personalization: e.target.checked,
                      } })} />
                    Đồng ý cá nhân hóa câu trả lời
                  </label>
                </div>
                <button
                  type="submit"
                  disabled={isSaving}
                  className="px-4 py-2 rounded-xl bg-teal-600 hover:bg-teal-700 text-white font-bold text-xs shadow-sm flex items-center gap-1.5 transition-all disabled:opacity-60"
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
        <div className="rounded-2xl p-5 border border-slate-200 bg-white shadow-xs space-y-4">
          <div className="flex items-center justify-between pb-3 border-b border-slate-100">
            <div className="flex items-center gap-2">
              <div className="w-8 h-8 rounded-lg bg-sky-50 text-sky-700 flex items-center justify-center border border-sky-200">
                <Target className="w-4 h-4" />
              </div>
              <div>
                <h4 className="font-bold text-sm text-slate-900">Mục tiêu Thể trạng & Hình thể</h4>
                <p className="text-xs text-slate-500">Định hướng kế hoạch tập luyện và calo thâm hụt</p>
              </div>
            </div>
          </div>

          <form onSubmit={handleSaveGoal} className="space-y-3.5 text-xs">
            <label className="block text-slate-700 font-medium">Loại mục tiêu
              <select required value={goal.goal_type || ''}
                onChange={(e) => setGoal({ ...goal, goal_type: e.target.value as UserGoal['goal_type'] })}
                className="mt-1 w-full rounded-xl border border-slate-300 bg-slate-50 px-3 py-2">
                <option value="" disabled>Chọn mục tiêu</option>
                <option value="fat_loss">Giảm mỡ</option>
                <option value="muscle_gain">Tăng cơ</option>
                <option value="maintenance">Duy trì</option>
                <option value="fitness">Cải thiện thể lực</option>
                <option value="other">Khác</option>
              </select>
            </label>
            <div className="grid grid-cols-2 gap-3">
              <div>
                <label className="block text-slate-700 font-medium mb-1">Cân nặng mục tiêu (kg)</label>
                <input
                  type="number"
                  step="0.5"
                  value={goal.target_weight_kg || ''}
                  onChange={(e) => setGoal({ ...goal, target_weight_kg: Number(e.target.value) })}
                  placeholder="70.0"
                  className="w-full px-3 py-2 rounded-xl bg-slate-50 border border-slate-300 text-teal-700 font-bold font-mono text-sm focus:bg-white focus:outline-none focus:border-teal-600"
                />
              </div>

              <div>
                <label className="block text-slate-700 font-medium mb-1">Thời hạn dự kiến</label>
                <input
                  type="date"
                  value={goal.target_date || ''}
                  onChange={(e) => setGoal({ ...goal, target_date: e.target.value })}
                  className="w-full px-3 py-2 rounded-xl bg-slate-50 border border-slate-300 text-slate-900 font-mono text-xs focus:bg-white focus:outline-none focus:border-teal-600"
                />
              </div>
            </div>

            <div className="p-3 rounded-xl bg-teal-50 border border-teal-200 text-xs text-teal-900 flex items-start gap-2">
              <ShieldCheck className="w-4 h-4 text-teal-600 flex-shrink-0 mt-0.5" />
              <span className="leading-relaxed">
                Mục tiêu được lưu riêng trong hồ sơ của bạn sau khi bạn đồng ý xử lý dữ liệu sức khỏe.
              </span>
            </div>
            <button type="submit" disabled={isSavingGoal} className="rounded-xl bg-teal-700 px-4 py-2 font-semibold text-white disabled:opacity-60">
              {isSavingGoal ? 'Đang lưu...' : 'Lưu mục tiêu'}
            </button>
          </form>
        </div>
      </div>

      {/* Check-in & Memory Section */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* Weekly Check-in Log */}
        <div className="rounded-2xl p-5 border border-slate-200 bg-white shadow-xs space-y-4">
          <div className="flex items-center justify-between pb-3 border-b border-slate-100">
            <div className="flex items-center gap-2">
              <div className="w-8 h-8 rounded-lg bg-teal-50 text-teal-700 flex items-center justify-center border border-teal-200">
                <ClipboardCheck className="w-4 h-4" />
              </div>
              <div>
                <h4 className="font-bold text-sm text-slate-900">Check-in Thể trạng Định kỳ</h4>
                <p className="text-xs text-slate-500">Ghi nhận mức năng lượng và cảnh báo triệu chứng</p>
              </div>
            </div>

            {checkInSuccess && (
              <span className="text-xs text-teal-700 flex items-center gap-1 font-semibold animate-in fade-in">
                <Check className="w-3.5 h-3.5" />
                <span>Đã ghi nhận!</span>
              </span>
            )}
          </div>

          <form onSubmit={handleAddCheckIn} className="space-y-3 text-xs">
            <div className="grid grid-cols-3 gap-2.5">
              <div>
                <label className="block text-slate-600 font-medium mb-1">Mức hoàn thành tập</label>
                <div className="flex items-center gap-1 bg-slate-50 p-2 rounded-xl border border-slate-300 justify-center">
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
                            ? 'text-amber-500 fill-amber-500'
                            : 'text-slate-300'
                        }`}
                      />
                    </button>
                  ))}
                </div>
              </div>

              <div>
                <label className="block text-slate-600 font-medium mb-1">Năng lượng (1-5)</label>
                <input
                  type="number"
                  min="1"
                  max="5"
                  value={energy}
                  onChange={(e) => setEnergy(Number(e.target.value))}
                  className="w-full px-3 py-2 rounded-xl bg-slate-50 border border-slate-300 text-center font-bold text-teal-700 font-mono focus:bg-white focus:outline-none focus:border-teal-600"
                />
              </div>

              <div>
                <label className="block text-slate-600 font-medium mb-1">Ngủ (tiếng/ngày)</label>
                <input
                  type="number"
                  step="0.5"
                  min="3"
                  max="14"
                  value={sleep}
                  onChange={(e) => setSleep(Number(e.target.value))}
                  className="w-full px-3 py-2 rounded-xl bg-slate-50 border border-slate-300 text-center font-bold text-sky-700 font-mono focus:bg-white focus:outline-none focus:border-teal-600"
                />
              </div>
            </div>

            <div>
              <label className="block text-slate-600 font-medium mb-1">Triệu chứng bất thường (nếu có)</label>
              <input
                type="text"
                value={symptoms}
                onChange={(e) => setSymptoms(e.target.value)}
                placeholder="Ví dụ: Đau mỏi khớp vai, căng gân kheo..."
                className="w-full px-3 py-2 rounded-xl bg-slate-50 border border-slate-300 text-slate-900 focus:bg-white focus:outline-none focus:border-teal-600"
              />
            </div>

            <div className="flex justify-end">
              <button
                type="submit"
                disabled={isSubmittingCheckIn}
                className="px-4 py-2 rounded-xl bg-teal-600 hover:bg-teal-700 text-white font-bold text-xs shadow-sm flex items-center gap-1.5 transition-transform active:scale-95 disabled:opacity-60"
              >
                {isSubmittingCheckIn ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : <Plus className="w-3.5 h-3.5" />}
                <span>{isSubmittingCheckIn ? 'Đang gửi...' : 'Gửi Check-in Tuần Này'}</span>
              </button>
            </div>
          </form>

          {/* Recent check-ins */}
          <div className="pt-3 border-t border-slate-100 space-y-2">
            <span className="text-[11px] font-semibold text-slate-500 uppercase tracking-wider">
              Lịch sử check-in gần nhất ({checkIns.length}):
            </span>
            {checkIns.length > 0 ? (
              checkIns.slice(0, 5).map((chk) => (
                <div
                  key={chk.id}
                  className="p-2.5 rounded-xl bg-slate-50 border border-slate-200 text-xs flex items-center justify-between"
                >
                  <div>
                    <div className="font-semibold text-slate-800 flex items-center gap-2">
                      <span>{chk.date}</span>
                      <span className="text-amber-600 font-medium">★ {chk.workout_rating}/5</span>
                      <span className="text-sky-700 font-mono">{chk.sleep_hours}h ngủ</span>
                    </div>
                    {chk.unusual_symptoms && (
                      <div className="text-[11px] text-rose-600 font-medium mt-0.5">
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
        <div className="rounded-2xl p-5 border border-slate-200 bg-white shadow-xs space-y-4">
          <div className="flex items-center justify-between pb-3 border-b border-slate-100">
            <div className="flex items-center gap-2">
              <div className="w-8 h-8 rounded-lg bg-sky-50 text-sky-700 flex items-center justify-center border border-sky-200">
                <Brain className="w-4 h-4" />
              </div>
              <div>
                <h4 className="font-bold text-sm text-slate-900">Ký ức Cá nhân hóa (Memory Facts)</h4>
                <p className="text-xs text-slate-500">Sự thật thể trạng AI ghi nhận, bạn toàn quyền kiểm soát</p>
              </div>
            </div>
          </div>

          <div className="space-y-2 text-xs">
            {memoryFacts.length > 0 ? (
              memoryFacts.map((fact) => (
                <div
                  key={fact.id}
                  className="p-3 rounded-xl bg-slate-50 border border-slate-200 flex items-start justify-between gap-3 group"
                >
                  <div className="space-y-1">
                    <div className="flex items-center gap-2">
                      <span className="text-[10px] px-1.5 py-0.5 rounded bg-sky-50 text-sky-700 border border-sky-200 uppercase font-semibold">
                        {fact.category}
                      </span>
                      {fact.status === 'confirmed' ? (
                        <span className="text-[10px] text-teal-700 font-semibold flex items-center gap-0.5">
                          <Check className="w-3 h-3" />
                          <span>Đã xác nhận</span>
                        </span>
                      ) : (
                        <span className="text-[10px] text-amber-700 font-semibold">
                          Chờ xác nhận
                        </span>
                      )}
                    </div>
                    <p className="text-slate-800 font-medium leading-relaxed">{fact.fact}</p>
                  </div>

                  <div className="flex items-center gap-1.5 flex-shrink-0">
                    {fact.status !== 'confirmed' && (
                      <button
                        onClick={() => handleConfirmMemory(fact.id)}
                        className="p-1.5 rounded-lg bg-teal-50 hover:bg-teal-100 text-teal-700 border border-teal-300 transition-colors"
                        title="Xác nhận sự thật này"
                      >
                        <Check className="w-3.5 h-3.5" />
                      </button>
                    )}
                    <button
                      onClick={() => handleDeleteMemory(fact.id)}
                      className="p-1.5 rounded-lg bg-slate-100 hover:bg-rose-50 text-slate-500 hover:text-rose-600 border border-slate-200 hover:border-rose-300 transition-colors"
                      title="Xóa vĩnh viễn sự thật này"
                    >
                      <Trash2 className="w-3.5 h-3.5" />
                    </button>
                  </div>
                </div>
              ))
            ) : (
              <div className="p-6 text-center text-xs text-slate-500 rounded-xl bg-slate-50 border border-slate-200">
                Chưa có sự thật nào được trích xuất. Khi bạn trò chuyện cùng Trợ lý AI (ví dụ: chia sẻ dị ứng thức ăn hoặc tiền sử vận động), các sự thật thể trạng sẽ tự động xuất hiện tại đây để bạn kiểm soát.
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}
