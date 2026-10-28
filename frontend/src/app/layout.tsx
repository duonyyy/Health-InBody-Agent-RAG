import type { Metadata } from 'next';
import './globals.css';

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
    <html lang="vi" className="h-full antialiased dark">
      <head>
        <link rel="preconnect" href="https://fonts.googleapis.com" />
        <link rel="preconnect" href="https://fonts.gstatic.com" crossOrigin="anonymous" />
        <link
          href="https://fonts.googleapis.com/css2?family=Plus+Jakarta+Sans:wght@300;400;500;600;700;800&family=JetBrains+Mono:wght@400;500;600&display=swap"
          rel="stylesheet"
        />
      </head>
      <body className="min-h-full flex flex-col bg-[#070b14] text-slate-100 selection:bg-emerald-500/30 selection:text-emerald-200">
        {children}
      </body>
    </html>
  );
}
