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
  title: 'Health/InBody AI - Trợ lý Sức khỏe & Thể trạng Agent RAG',
  description:
    'Hệ thống AI đa tác tử phân tích chuyên sâu chỉ số InBody (BMI, PBF, SMM, mỡ nội tạng theo chuẩn WPRO), tư vấn dinh dưỡng tái tạo thể trạng, lịch tập kháng lực và cảnh báo an toàn y tế.',
  keywords: ['InBody', 'RAG', 'AI Health', 'BMI', 'PBF', 'Dinh dưỡng', 'Tập gym', 'An toàn y tế'],
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
