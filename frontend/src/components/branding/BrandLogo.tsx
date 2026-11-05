'use client';

import React from 'react';
import Image from 'next/image';
import Link from 'next/link';

export type BrandLogoVariant = 'horizontal' | 'tagline' | 'stacked' | 'mono-black' | 'mono-white';

export interface BrandLogoProps {
  theme?: 'light' | 'dark';
  compact?: boolean;
  withTagline?: boolean;
  variant?: BrandLogoVariant;
  href?: string;
  className?: string;
  priority?: boolean;
  height?: number;
}

export function BrandLogo({
  theme = 'dark',
  compact = false,
  withTagline = false,
  variant,
  href = '/',
  className = '',
  priority = true,
  height = 40,
}: BrandLogoProps) {
  // Khi ở dạng thu gọn (Icon Only) cho Sidebar collapsed hoặc Mobile header
  if (compact) {
    const logoMark = (
      <div className={`relative flex items-center justify-center transition-transform hover:scale-105 ${className}`}>
        <Image
          src="/brand/logo-mark.svg"
          alt="BodyWise Logo Mark"
          width={40}
          height={40}
          priority={priority}
          className="h-10 w-10 object-contain drop-shadow-[0_4px_12px_rgba(13,148,136,0.3)]"
        />
      </div>
    );
    return href ? (
      <Link href={href} aria-label="BodyWise — Trang chủ" className="inline-flex focus:outline-none focus-visible:ring-2 focus-visible:ring-teal-500 rounded-xl">
        {logoMark}
      </Link>
    ) : (
      logoMark
    );
  }

  // Xác định biến thể
  const effectiveVariant: BrandLogoVariant = variant ?? (withTagline ? 'tagline' : 'horizontal');

  let src = '/brand/logo-horizontal-dark.svg';
  let width = Math.round((height * 596) / 184); // viewBox 596x184 (~3.24)
  let alt = 'BodyWise — Trợ lý Thể trạng & Dinh dưỡng AI';

  switch (effectiveVariant) {
    case 'tagline':
      src = theme === 'light' ? '/brand/logo-tagline-light.svg' : '/brand/logo-tagline-dark.svg';
      width = Math.round((height * 596) / 184);
      alt = 'BodyWise — Hiểu cơ thể. Sống chủ động.';
      break;
    case 'stacked':
      src = '/brand/logo-stacked.svg';
      width = Math.round((height * 350) / 268);
      break;
    case 'mono-black':
      src = '/brand/logo-mono-black.svg';
      width = Math.round((height * 350) / 268);
      break;
    case 'mono-white':
      src = '/brand/logo-mono-white.svg';
      width = Math.round((height * 350) / 268);
      break;
    case 'horizontal':
    default:
      src = theme === 'light' ? '/brand/logo-horizontal-light.svg' : '/brand/logo-horizontal-dark.svg';
      width = Math.round((height * 596) / 184);
      break;
  }

  const logoImg = (
    <div className={`relative flex items-center select-none ${className}`}>
      <Image
        src={src}
        alt={alt}
        width={width}
        height={height}
        priority={priority}
        className="h-10 w-auto object-contain transition-opacity duration-200"
      />
    </div>
  );

  return href ? (
    <Link
      href={href}
      aria-label="BodyWise — Về trang chủ"
      className="inline-flex items-center focus:outline-none focus-visible:ring-2 focus-visible:ring-teal-500 rounded-xl"
    >
      {logoImg}
    </Link>
  ) : (
    logoImg
  );
}

export default BrandLogo;
