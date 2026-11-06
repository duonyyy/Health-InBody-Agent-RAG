'use client';

import { FormEvent, useState } from 'react';
import { authenticateAccount } from '@/lib/api';
import { BrandLogo } from '@/components/branding/BrandLogo';

export default function AuthPanel({ onAuthenticated }: { onAuthenticated: () => void }) {
  const [register, setRegister] = useState(false);
  const [username, setUsername] = useState('');
  const [password, setPassword] = useState('');
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setBusy(true);
    setError('');
    try {
      await authenticateAccount(username.trim(), password, register);
      setPassword('');
      onAuthenticated();
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : 'Không thể đăng nhập. Vui lòng thử lại.');
    } finally {
      setBusy(false);
    }
  }

  return (
    <main className="min-h-screen flex items-center justify-center bg-slate-50 p-4">
      <div className="w-full max-w-sm rounded-2xl border border-slate-200 bg-white p-7 shadow-sm">
        <BrandLogo theme="light" href="/" height={40} />
        <h1 className="mt-7 text-xl font-bold text-slate-900">{register ? 'Tạo tài khoản' : 'Đăng nhập'}</h1>
        <p className="mt-1 text-sm text-slate-600">Truy cập hồ sơ và trò chuyện của riêng bạn.</p>
        <form className="mt-6 space-y-4" onSubmit={submit}>
          <label className="block text-sm font-medium text-slate-700">Tên đăng nhập
            <input autoComplete="username" required minLength={3} maxLength={40} value={username}
              onChange={(event) => setUsername(event.target.value)}
              className="mt-1 w-full rounded-lg border border-slate-300 p-2.5 text-slate-900" />
          </label>
          <label className="block text-sm font-medium text-slate-700">Mật khẩu
            <input type="password" autoComplete={register ? 'new-password' : 'current-password'} required
              minLength={12} maxLength={128} value={password} onChange={(event) => setPassword(event.target.value)}
              className="mt-1 w-full rounded-lg border border-slate-300 p-2.5 text-slate-900" />
          </label>
          {error && <p role="alert" className="text-sm text-rose-700">{error}</p>}
          <button type="submit" disabled={busy} className="w-full rounded-lg bg-teal-700 p-2.5 font-semibold text-white disabled:opacity-60">
            {busy ? 'Đang xử lý...' : register ? 'Tạo tài khoản' : 'Đăng nhập'}
          </button>
        </form>
        <button type="button" className="mt-4 text-sm text-teal-800 underline" onClick={() => { setRegister(!register); setError(''); }}>
          {register ? 'Đã có tài khoản? Đăng nhập' : 'Chưa có tài khoản? Đăng ký'}
        </button>
      </div>
    </main>
  );
}
