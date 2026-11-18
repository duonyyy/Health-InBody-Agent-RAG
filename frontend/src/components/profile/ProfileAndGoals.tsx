'use client';

import React, { useState, useEffect, useCallback, useRef } from 'react';
import {
  User,
  Target,
  ClipboardCheck,
  Brain,
  Save,
  Check,
  Trash2,
  ShieldCheck,
  Plus,
  Loader2,
  AlertCircle,
  RotateCw,
} from 'lucide-react';
import {
  UserProfile,
  UserGoal,
  CheckInLog,
  MemoryProposal,
  SexAtBirthType,
  ActivityLevelType,
  SafetyResult,
} from '@/types';
import SafetyBanner from '@/components/chat/SafetyBanner';
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
  const [checkInError, setCheckInError] = useState<string | null>(null);
  const [memoryError, setMemoryError] = useState<string | null>(null);

  // New Check-in form state conforming to backend contract
  const [adherence, setAdherence] = useState(100);
  const [energy, setEnergy] = useState(4);
  const [sleepQuality, setSleepQuality] = useState(4);
  const [soreness, setSoreness] = useState(1);
  const [symptoms, setSymptoms] = useState('');
  const [checkInNotes, setCheckInNotes] = useState('');
  const [checkInSuccess, setCheckInSuccess] = useState(false);
  const [isSubmittingCheckIn, setIsSubmittingCheckIn] = useState(false);
  const [latestCheckInSafety, setLatestCheckInSafety] = useState<SafetyResult | null>(null);
  const checkInRequestSeqRef = useRef(0);

  const loadAllData = useCallback(async () => {
    setIsLoading(true);
    setErrorMessage(null);
    setCheckInError(null);
    setMemoryError(null);
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
      } else {
        setCheckInError(chk.reason instanceof Error ? chk.reason.message : 'Không thể tải lịch sử check-in.');
      }

      if (mem.status === 'fulfilled') {
        setMemoryFacts(mem.value);
      } else {
        setMemoryError(mem.reason instanceof Error ? mem.reason.message : 'Không thể tải ký ức cá nhân hóa.');
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
      setCheckInError(null);
      setMemoryError(null);
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
        } else {
          setCheckInError(chk.reason instanceof Error ? chk.reason.message : 'Không thể tải lịch sử check-in.');
        }

        if (mem.status === 'fulfilled') {
          setMemoryFacts(mem.value);
        } else {
          setMemoryError(mem.reason instanceof Error ? mem.reason.message : 'Không thể tải ký ức cá nhân hóa.');
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
    const requestSeq = ++checkInRequestSeqRef.current;
    setIsSubmittingCheckIn(true);
    setCheckInError(null);
    setCheckInSuccess(false);
    try {
      const parsedSymptoms = symptoms
        .split(',')
        .map((s) => s.trim())
        .filter(Boolean);
      const newLog = await saveCheckIn({
        adherence,
        energy_level: energy,
        sleep_quality: sleepQuality,
        soreness,
        symptoms: parsedSymptoms.length > 0 ? parsedSymptoms : undefined,
        note: checkInNotes.trim() || undefined,
      });
      setCheckIns((prev) => [newLog, ...prev]);
      if (requestSeq === checkInRequestSeqRef.current) {
        setLatestCheckInSafety(newLog.safety_result || null);
        setSymptoms('');
        setCheckInNotes('');
        const isUrgent =
          newLog.safety_result?.risk_level === 'urgent' || newLog.safety_result?.is_urgent;
        if (!isUrgent) {
          setCheckInSuccess(true);
          setTimeout(() => setCheckInSuccess(false), 3000);
        }
      }
    } catch (err: unknown) {
      if (requestSeq === checkInRequestSeqRef.current) {
        const msg = err instanceof Error ? err.message : 'Không thể lưu check-in.';
        setCheckInError(msg);
      }
    } finally {
      if (requestSeq === checkInRequestSeqRef.current) {
        setIsSubmittingCheckIn(false);
      }
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

          {/* Safety Warning from Latest Check-in */}
          {latestCheckInSafety && (
            <div className="pt-1">
              <SafetyBanner safety={latestCheckInSafety} />
            </div>
          )}

          {/* Check-in Error Alert */}
          {checkInError && (
            <div className="p-3 rounded-xl bg-amber-50 border border-amber-200 text-amber-900 text-xs flex items-center gap-2">
              <AlertCircle className="w-4 h-4 text-amber-600 flex-shrink-0" />
              <span className="font-medium">{checkInError}</span>
            </div>
          )}

          <form onSubmit={handleAddCheckIn} className="space-y-3 text-xs">
            <div className="grid grid-cols-2 sm:grid-cols-4 gap-2.5">
              <div>
                <label className="block text-slate-600 font-medium mb-1">Tuân thủ (%)</label>
                <input
                  type="number"
                  min="0"
                  max="100"
                  step="5"
                  value={adherence}
                  onChange={(e) => setAdherence(Number(e.target.value))}
                  className="w-full px-2.5 py-1.5 rounded-xl bg-slate-50 border border-slate-300 text-center font-bold text-teal-700 font-mono focus:bg-white focus:outline-none focus:border-teal-600"
                  required
                />
              </div>

              <div>
                <label className="block text-slate-600 font-medium mb-1">Năng lượng (1-5)</label>
                <select
                  value={energy}
                  onChange={(e) => setEnergy(Number(e.target.value))}
                  className="w-full px-2 py-1.5 rounded-xl bg-slate-50 border border-slate-300 text-slate-900 focus:bg-white focus:outline-none focus:border-teal-600"
                >
                  <option value={1}>1 - Rất thấp</option>
                  <option value={2}>2 - Hơi mệt</option>
                  <option value={3}>3 - Bình thường</option>
                  <option value={4}>4 - Tốt</option>
                  <option value={5}>5 - Rất sung mãn</option>
                </select>
              </div>

              <div>
                <label className="block text-slate-600 font-medium mb-1">Giấc ngủ (1-5)</label>
                <select
                  value={sleepQuality}
                  onChange={(e) => setSleepQuality(Number(e.target.value))}
                  className="w-full px-2 py-1.5 rounded-xl bg-slate-50 border border-slate-300 text-slate-900 focus:bg-white focus:outline-none focus:border-teal-600"
                >
                  <option value={1}>1 - Rất kém</option>
                  <option value={2}>2 - Kém/Chập chờn</option>
                  <option value={3}>3 - Tạm ổn</option>
                  <option value={4}>4 - Ngủ ngon</option>
                  <option value={5}>5 - Rất sâu giấc</option>
                </select>
              </div>

              <div>
                <label className="block text-slate-600 font-medium mb-1">Đau mỏi (1-5)</label>
                <select
                  value={soreness}
                  onChange={(e) => setSoreness(Number(e.target.value))}
                  className="w-full px-2 py-1.5 rounded-xl bg-slate-50 border border-slate-300 text-slate-900 focus:bg-white focus:outline-none focus:border-teal-600"
                >
                  <option value={1}>1 - Không mỏi</option>
                  <option value={2}>2 - Mỏi nhẹ</option>
                  <option value={3}>3 - Mỏi vừa</option>
                  <option value={4}>4 - Đau nhiều</option>
                  <option value={5}>5 - Đau dữ dội</option>
                </select>
              </div>
            </div>

            <div>
              <label className="block text-slate-600 font-medium mb-1">Triệu chứng bất thường (nếu có)</label>
              <input
                type="text"
                value={symptoms}
                onChange={(e) => setSymptoms(e.target.value)}
                placeholder="Ví dụ: Đau thắt ngực, khó thở, chóng mặt, sưng khớp gối..."
                className="w-full px-3 py-2 rounded-xl bg-slate-50 border border-slate-300 text-slate-900 focus:bg-white focus:outline-none focus:border-teal-600"
              />
            </div>

            <div>
              <label className="block text-slate-600 font-medium mb-1">Ghi chú thêm</label>
              <input
                type="text"
                value={checkInNotes}
                onChange={(e) => setCheckInNotes(e.target.value)}
                placeholder="Ví dụ: Cảm thấy cơ bắp phục hồi tốt, uống đủ 2L nước..."
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
              checkIns.slice(0, 5).map((chk) => {
                const isUrgent = chk.safety_result?.risk_level === 'urgent' || chk.safety_result?.is_urgent;
                const isCaution = chk.safety_result?.risk_level === 'medical_caution' || chk.safety_result?.is_caution;
                const symptomList = Array.isArray(chk.symptoms)
                  ? chk.symptoms
                  : chk.unusual_symptoms
                  ? [chk.unusual_symptoms]
                  : [];

                return (
                  <div
                    key={chk.id}
                    className={`p-3 rounded-xl border text-xs space-y-1.5 ${
                      isUrgent
                        ? 'bg-rose-50/60 border-rose-300'
                        : isCaution
                        ? 'bg-amber-50/60 border-amber-300'
                        : 'bg-slate-50 border-slate-200'
                    }`}
                  >
                    <div className="font-semibold text-slate-800 flex flex-wrap items-center gap-2">
                      <span className="text-slate-600 font-mono">{chk.date || chk.checked_at?.slice(0, 10)}</span>
                      {chk.adherence != null && (
                        <span className="text-teal-700 font-medium bg-teal-50 px-1.5 py-0.5 rounded border border-teal-200">
                          Tuân thủ {chk.adherence}%
                        </span>
                      )}
                      {chk.energy_level != null && (
                        <span className="text-slate-700">⚡ Năng lượng: {chk.energy_level}/5</span>
                      )}
                      {chk.sleep_quality != null && (
                        <span className="text-sky-700 font-medium">💤 Ngủ: {chk.sleep_quality}/5</span>
                      )}
                      {chk.soreness != null && (
                        <span className="text-amber-800">💪 Đau mỏi: {chk.soreness}/5</span>
                      )}
                    </div>

                    {symptomList.length > 0 && (
                      <div className="text-[11px] text-rose-700 font-medium flex items-center gap-1">
                        <span>⚠️ Triệu chứng: {symptomList.join(', ')}</span>
                      </div>
                    )}

                    {(chk.note || chk.notes) && (
                      <div className="text-[11px] text-slate-600 italic">
                        &ldquo;{chk.note || chk.notes}&rdquo;
                      </div>
                    )}

                    {isUrgent && (
                      <div
                        role="alert"
                        className="text-[11px] p-2 rounded-lg bg-rose-100 border border-rose-400 text-rose-950 font-semibold"
                      >
                        🚨 Cảnh báo khẩn cấp: {chk.safety_result?.recommended_action || 'Cần can thiệp y tế ngay lập tức.'}
                      </div>
                    )}

                    {!isUrgent && isCaution && (
                      <div
                        role="status"
                        className="text-[11px] p-2 rounded-lg bg-amber-100 border border-amber-400 text-amber-950 font-medium"
                      >
                        ⚠️ Lưu ý an toàn: {chk.safety_result?.recommended_action || 'Theo dõi sát diễn biến thể trạng.'}
                      </div>
                    )}
                  </div>
                );
              })
            ) : checkInError ? (
              <div className="text-xs text-amber-700 py-2">
                Không thể hiển thị danh sách do lỗi tải dữ liệu.
              </div>
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

          {/* Memory Error Alert */}
          {memoryError && (
            <div className="p-3 rounded-xl bg-amber-50 border border-amber-200 text-amber-900 text-xs flex items-center gap-2">
              <AlertCircle className="w-4 h-4 text-amber-600 flex-shrink-0" />
              <span className="font-medium">{memoryError}</span>
            </div>
          )}

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
            ) : memoryError ? (
              <div className="text-xs text-amber-700 py-2">
                Không thể hiển thị ký ức do lỗi tải dữ liệu.
              </div>
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
