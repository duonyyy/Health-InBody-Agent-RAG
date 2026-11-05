import type { Metadata } from 'next';
import { Plus_Jakarta_Sans, JetBrains_Mono } from 'next/font/google';
import './globals.css';

const plusJakartaSans = Plus_Jakarta_Sans({
  subsets: ['latin', 'vietnamese'],
  weight: ['300', '400', '500', '600', '700', '800'],
  variable: '--font-sans',
  display: 'swap',
});

const jetbrainsMono = JetBrains_Mono({
  subsets: ['latin'],
  weight: ['400', '500', '600'],
  variable: '--font-mono',
  display: 'swap',
});

export const metadata: Metadata = {
  title: 'BodyWise — Trợ lý Sức khỏe & Thể trạng Agent RAG',
  description:
    'Hệ thống AI đa tác tử phân tích chuyên sâu chỉ số InBody (BMI, PBF, SMM, mỡ nội tạng theo chuẩn WPRO), tư vấn dinh dưỡng tái tạo thể trạng, lịch tập kháng lực và cảnh báo an toàn y tế.',
  keywords: ['BodyWise', 'InBody', 'RAG', 'AI Health', 'BMI', 'PBF', 'Dinh dưỡng', 'Tập gym', 'An toàn y tế'],
  icons: {
    icon: [
      { url: '/favicon.ico' },
      { url: '/brand/favicon.svg', type: 'image/svg+xml' },
      { url: '/brand/favicon-32.png', sizes: '32x32', type: 'image/png' },
      { url: '/brand/favicon-16.png', sizes: '16x16', type: 'image/png' },
    ],
    apple: [
      { url: '/brand/apple-touch-icon.png', sizes: '180x180', type: 'image/png' },
    ],
  },
  manifest: '/brand/manifest.webmanifest',
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="vi" className={`h-full antialiased dark ${plusJakartaSans.variable} ${jetbrainsMono.variable}`}>
      <body className="min-h-full flex flex-col bg-[#070b14] text-slate-100 font-sans selection:bg-emerald-500/30 selection:text-emerald-200">
        {children}
      </body>
    </html>
  );
}
