'use client';

import React, { useState, useRef } from 'react';
import {
  UploadCloud,
  Sparkles,
  Check,
  AlertCircle,
  RefreshCw,
  Save,
  ArrowRight,
} from 'lucide-react';
import { InBodyMeasurement } from '@/types';
import { uploadInBodyOcrFile } from '@/lib/api';

interface OcrScannerProps {
  onSaveOcrResult: (result: Partial<InBodyMeasurement>) => Promise<void>;
  onSwitchToManual?: () => void;
}

export default function OcrScanner({ onSaveOcrResult, onSwitchToManual }: OcrScannerProps) {
  const [file, setFile] = useState<File | null>(null);
  const [previewUrl, setPreviewUrl] = useState<string | null>(null);
  const [isScanning, setIsScanning] = useState(false);
  const [extractedData, setExtractedData] = useState<Partial<InBodyMeasurement> | null>(null);
  const [errorMsg, setErrorMsg] = useState('');
  const [isSaved, setIsSaved] = useState(false);
  const fileInputRef = useRef<HTMLInputElement>(null);

  const handleFileChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    setErrorMsg('');
    setExtractedData(null);
    setIsSaved(false);
    if (e.target.files && e.target.files[0]) {
      const selected = e.target.files[0];
      setFile(selected);
      setPreviewUrl(URL.createObjectURL(selected));
    }
  };

  const handleScan = async () => {
    if (!file) return;
    setIsScanning(true);
    setErrorMsg('');

    try {
      const draft = await uploadInBodyOcrFile(file);
      setExtractedData(draft);
    } catch (err: unknown) {
      const message =
        err instanceof Error ? err.message : 'Có lỗi xảy ra khi bóc tách ảnh phiếu InBody.';
      setErrorMsg(message);
    } finally {
      setIsScanning(false);
    }
  };

  const handleSaveToProfile = async () => {
    if (!extractedData) return;
    try {
      await onSaveOcrResult({
        ...extractedData,
        source_type: 'ocr_confirmed',
        confirmed_by_user: true,
      });
      setIsSaved(true);
      setTimeout(() => {
        setIsSaved(false);
        setExtractedData(null);
        setFile(null);
        setPreviewUrl(null);
      }, 2500);
    } catch (err: unknown) {
      const message = err instanceof Error ? err.message : 'Không thể lưu vào hồ sơ.';
      setErrorMsg(message);
    }
  };

  return (
    <div className="rounded-2xl p-6 border border-slate-200 bg-white shadow-xs">
      <div className="flex items-center justify-between mb-4 pb-3 border-b border-slate-200">
        <div>
          <div className="flex items-center gap-2">
            <h4 className="font-bold text-sm text-slate-900 flex items-center gap-2">
              <Sparkles className="w-4 h-4 text-teal-600" />
              <span>Quét Phiếu Đo InBody bằng Trí Tuệ Nhân Tạo (AI OCR)</span>
            </h4>
            <span className="text-[10px] uppercase font-bold tracking-wider px-2 py-0.5 rounded-full bg-teal-50 text-teal-800 border border-teal-200">
              Quy trình 3 bước
            </span>
          </div>
          <p className="text-xs text-slate-500 mt-0.5">
            Tải ảnh chụp phiếu đo InBody $\rightarrow$ Nhận bản nháp $\rightarrow$ Đối chiếu & Lưu vào hồ sơ cá nhân.
          </p>
        </div>
      </div>

      {errorMsg && (
        <div className="mb-4 p-4 rounded-xl bg-rose-50 border border-rose-200 text-rose-900 text-xs flex flex-col sm:flex-row items-start sm:items-center justify-between gap-3 animate-in fade-in shadow-xs">
          <div className="flex items-start gap-2.5">
            <AlertCircle className="w-4 h-4 text-rose-600 flex-shrink-0 mt-0.5" />
            <div className="space-y-1">
              <span className="font-bold block">Thông báo bóc tách:</span>
              <p className="text-rose-800 leading-relaxed font-medium">{errorMsg}</p>
            </div>
          </div>
          {onSwitchToManual && (
            <button
              onClick={onSwitchToManual}
              className="px-3.5 py-1.5 rounded-lg bg-rose-600 hover:bg-rose-700 text-white font-bold text-xs flex items-center gap-1 self-end sm:self-auto flex-shrink-0 shadow-xs"
            >
              <span>Nhập thủ công</span>
              <ArrowRight className="w-3.5 h-3.5" />
            </button>
          )}
        </div>
      )}

      {isSaved && (
        <div className="mb-4 p-3 rounded-xl bg-emerald-50 border border-emerald-200 text-emerald-900 text-xs flex items-center gap-2 font-bold animate-in fade-in">
          <Check className="w-4 h-4 text-emerald-600 flex-shrink-0" />
          <span>Đã lưu thành công kết quả đo vào hồ sơ của bạn!</span>
        </div>
      )}

      {/* Upload Dropzone */}
      {!extractedData && (
        <div
          onClick={() => fileInputRef.current?.click()}
          className="border-2 border-dashed border-slate-300 hover:border-teal-500 rounded-2xl p-8 text-center cursor-pointer bg-slate-50 hover:bg-slate-100/70 transition-all group"
        >
          <input
            type="file"
            ref={fileInputRef}
            onChange={handleFileChange}
            accept="image/*"
            className="hidden"
          />

          {previewUrl ? (
            <div className="flex flex-col items-center">
              {/* eslint-disable-next-line @next/next/no-img-element */}
              <img
                src={previewUrl}
                alt="Phiếu InBody preview"
                className="max-h-56 rounded-xl border border-slate-300 shadow-md mb-3 object-contain"
              />
              <span className="text-xs text-slate-800 font-bold">{file?.name}</span>
              <span className="text-[11px] text-slate-500 mt-0.5">Nhấp để chọn ảnh khác</span>
            </div>
          ) : (
            <div className="flex flex-col items-center">
              <div className="w-12 h-12 rounded-2xl bg-white group-hover:bg-teal-50 text-slate-500 group-hover:text-teal-700 flex items-center justify-center mb-3 transition-colors border border-slate-200 shadow-xs">
                <UploadCloud className="w-6 h-6" />
              </div>
              <h5 className="text-sm font-bold text-slate-800 group-hover:text-teal-800 transition-colors">
                Kéo thả ảnh phiếu InBody vào đây hoặc nhấp để chọn tệp
              </h5>
              <p className="text-xs text-slate-500 mt-1 max-w-md">
                Hỗ trợ ảnh định dạng JPG, PNG, WEBP (khuyến nghị chụp thẳng, đủ ánh sáng, rõ hàng số đo Cân nặng, SMM, PBF).
              </p>
            </div>
          )}
        </div>
      )}

      {/* Action Scan Button */}
      {file && !extractedData && (
        <div className="flex justify-end mt-4">
          <button
            onClick={handleScan}
            disabled={isScanning}
            className="px-5 py-2.5 rounded-xl bg-gradient-to-r from-teal-600 to-emerald-600 hover:brightness-105 text-white font-bold text-xs shadow-sm flex items-center gap-2 transition-all disabled:opacity-60"
          >
            {isScanning ? (
              <>
                <RefreshCw className="w-4 h-4 animate-spin" />
                <span>Đang gửi ảnh tới cổng OCR máy chủ...</span>
              </>
            ) : (
              <>
                <Sparkles className="w-4 h-4" />
                <span>Bắt đầu Bóc tách Số liệu bằng AI OCR</span>
              </>
            )}
          </button>
        </div>
      )}

      {/* Extracted Review Form (Draft step) */}
      {extractedData && (
        <div className="mt-4 p-4 rounded-xl bg-slate-50 border border-slate-200 space-y-4 animate-in fade-in">
          <div className="flex items-center justify-between pb-2 border-b border-slate-200">
            <span className="text-xs font-bold text-teal-800 flex items-center gap-1.5">
              <Check className="w-4 h-4 text-teal-600" />
              <span>Bóc tách thành công! Vui lòng đối chiếu số liệu trước khi xác nhận:</span>
            </span>
            <span className="text-[11px] text-slate-500 font-mono">
              Bản nháp cần người dùng xác nhận
            </span>
          </div>

          <div className="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-6 gap-2.5">
            <div>
              <label className="block text-[11px] font-semibold text-slate-600 mb-1">Cân nặng (kg)</label>
              <input
                type="number"
                step="0.1"
                value={extractedData.weight_kg ?? ''}
                onChange={(e) =>
                  setExtractedData({
                    ...extractedData,
                    weight_kg: e.target.value ? Number(e.target.value) : undefined,
                  })
                }
                className="w-full px-2.5 py-1.5 rounded-lg bg-white border border-slate-300 text-slate-900 text-xs font-mono font-bold focus:border-teal-600"
              />
            </div>

            <div>
              <label className="block text-[11px] font-semibold text-slate-600 mb-1">Cơ xương (SMM kg)</label>
              <input
                type="number"
                step="0.1"
                value={extractedData.smm_kg ?? extractedData.skeletal_muscle_mass_kg ?? ''}
                onChange={(e) =>
                  setExtractedData({
                    ...extractedData,
                    smm_kg: e.target.value ? Number(e.target.value) : undefined,
                    skeletal_muscle_mass_kg: e.target.value ? Number(e.target.value) : undefined,
                  })
                }
                className="w-full px-2.5 py-1.5 rounded-lg bg-white border border-slate-300 text-teal-700 text-xs font-mono font-bold focus:border-teal-600"
              />
            </div>

            <div>
              <label className="block text-[11px] font-semibold text-slate-600 mb-1">Khối mỡ (BFM kg)</label>
              <input
                type="number"
                step="0.1"
                value={extractedData.bfm_kg ?? extractedData.body_fat_mass_kg ?? ''}
                onChange={(e) =>
                  setExtractedData({
                    ...extractedData,
                    bfm_kg: e.target.value ? Number(e.target.value) : undefined,
                    body_fat_mass_kg: e.target.value ? Number(e.target.value) : undefined,
                  })
                }
                className="w-full px-2.5 py-1.5 rounded-lg bg-white border border-slate-300 text-slate-900 text-xs font-mono focus:border-teal-600"
              />
            </div>

            <div>
              <label className="block text-[11px] font-semibold text-slate-600 mb-1">Tỷ lệ Mỡ (PBF %)</label>
              <input
                type="number"
                step="0.1"
                value={extractedData.pbf_percent ?? extractedData.percent_body_fat ?? ''}
                onChange={(e) =>
                  setExtractedData({
                    ...extractedData,
                    pbf_percent: e.target.value ? Number(e.target.value) : undefined,
                    percent_body_fat: e.target.value ? Number(e.target.value) : undefined,
                  })
                }
                className="w-full px-2.5 py-1.5 rounded-lg bg-white border border-slate-300 text-amber-700 text-xs font-mono font-bold focus:border-teal-600"
              />
            </div>

            <div>
              <label className="block text-[11px] font-semibold text-slate-600 mb-1">Mỡ nội tạng (VFL)</label>
              <input
                type="number"
                step="1"
                value={extractedData.visceral_fat_level ?? ''}
                onChange={(e) =>
                  setExtractedData({
                    ...extractedData,
                    visceral_fat_level: e.target.value ? Number(e.target.value) : undefined,
                  })
                }
                className="w-full px-2.5 py-1.5 rounded-lg bg-white border border-slate-300 text-purple-700 text-xs font-mono font-bold focus:border-teal-600"
              />
            </div>

            <div>
              <label className="block text-[11px] font-semibold text-slate-600 mb-1">Chiều cao (cm)</label>
              <input
                type="number"
                step="0.5"
                value={extractedData.height_cm ?? ''}
                onChange={(e) =>
                  setExtractedData({
                    ...extractedData,
                    height_cm: e.target.value ? Number(e.target.value) : undefined,
                  })
                }
                className="w-full px-2.5 py-1.5 rounded-lg bg-white border border-slate-300 text-slate-900 text-xs font-mono focus:border-teal-600"
              />
            </div>
          </div>

          <div className="flex items-center justify-between pt-2">
            <button
              onClick={() => setExtractedData(null)}
              className="text-xs text-slate-500 hover:text-slate-800 font-medium"
            >
              ← Chọn lại ảnh khác
            </button>

            <button
              onClick={handleSaveToProfile}
              className="px-4 py-2 rounded-xl bg-teal-600 hover:bg-teal-700 text-white font-bold text-xs shadow-sm flex items-center gap-1.5 transition-transform active:scale-95"
            >
              <Save className="w-3.5 h-3.5" />
              <span>Xác nhận & Lưu vào Hồ sơ</span>
            </button>
          </div>
        </div>
      )}
    </div>
  );
}