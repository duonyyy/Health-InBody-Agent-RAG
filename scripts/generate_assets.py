"""
Asset generator for Health/InBody Agent RAG - BodyWise Design System.
Generates master SVGs, domain icons, raster PNG icons, favicon.ico, and OG image.
"""
import os
import shutil
import json
from PIL import Image, ImageDraw, ImageFont

DOCS_BRAND_DIR = "docs/frontend-design/assets/brand"
DOCS_ICONS_DIR = "docs/frontend-design/assets/icons"
PUBLIC_BRAND_DIR = "frontend/public/brand"
PUBLIC_ICONS_DIR = "frontend/public/icons"

for d in [DOCS_BRAND_DIR, DOCS_ICONS_DIR, PUBLIC_BRAND_DIR, PUBLIC_ICONS_DIR]:
    os.makedirs(d, exist_ok=True)

# 1. Master SVG Definitions
LOGO_MARK_SVG = """<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 100 100" fill="none">
  <defs>
    <linearGradient id="bwPrimaryGrad" x1="0%" y1="0%" x2="100%" y2="100%">
      <stop offset="0%" stop-color="#14B8A6"/>
      <stop offset="50%" stop-color="#0D9488"/>
      <stop offset="100%" stop-color="#0284C7"/>
    </linearGradient>
    <linearGradient id="bwSecondaryGrad" x1="100%" y1="0%" x2="0%" y2="100%">
      <stop offset="0%" stop-color="#38BDF8"/>
      <stop offset="100%" stop-color="#0F766E"/>
    </linearGradient>
    <filter id="bwGlow" x="-20%" y="-20%" width="140%" height="140%">
      <feDropShadow dx="0" dy="4" stdDeviation="6" flood-color="#0D9488" flood-opacity="0.25"/>
    </filter>
  </defs>
  <!-- Outer Composition Arc (Body Mass & Balance) -->
  <path d="M 50 12 A 38 38 0 1 1 16 64" fill="none" stroke="url(#bwPrimaryGrad)" stroke-width="8" stroke-linecap="round" filter="url(#bwGlow)"/>
  <!-- Inner Metabolism Arc (Vitals & Hydration) -->
  <path d="M 50 26 A 24 24 0 1 0 72 60" fill="none" stroke="url(#bwSecondaryGrad)" stroke-width="6.5" stroke-linecap="round"/>
  <!-- Central Dynamic Spark / Leaf Node (Wellness & Wisdom) -->
  <path d="M 50 26 C 50 40, 68 46, 68 58 C 68 68, 59 74, 50 74 C 41 74, 34 68, 34 58 C 34 44, 50 30, 50 26 Z" fill="url(#bwPrimaryGrad)"/>
  <!-- Core Vital Center Point -->
  <circle cx="50" cy="58" r="4.5" fill="#FFFFFF"/>
</svg>"""

LOGO_HORIZONTAL_DARK_SVG = """<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 420 100" fill="none">
  <defs>
    <linearGradient id="bwTextGrad" x1="0%" y1="0%" x2="100%" y2="100%">
      <stop offset="0%" stop-color="#2DD4BF"/>
      <stop offset="100%" stop-color="#38BDF8"/>
    </linearGradient>
    <linearGradient id="bwMarkGrad" x1="0%" y1="0%" x2="100%" y2="100%">
      <stop offset="0%" stop-color="#14B8A6"/>
      <stop offset="50%" stop-color="#0D9488"/>
      <stop offset="100%" stop-color="#0284C7"/>
    </linearGradient>
    <linearGradient id="bwSecGrad" x1="100%" y1="0%" x2="0%" y2="100%">
      <stop offset="0%" stop-color="#38BDF8"/>
      <stop offset="100%" stop-color="#0F766E"/>
    </linearGradient>
  </defs>
  <!-- Mark Group -->
  <g transform="translate(10, 5) scale(0.9)">
    <path d="M 50 12 A 38 38 0 1 1 16 64" fill="none" stroke="url(#bwMarkGrad)" stroke-width="8" stroke-linecap="round"/>
    <path d="M 50 26 A 24 24 0 1 0 72 60" fill="none" stroke="url(#bwSecGrad)" stroke-width="6.5" stroke-linecap="round"/>
    <path d="M 50 26 C 50 40, 68 46, 68 58 C 68 68, 59 74, 50 74 C 41 74, 34 68, 34 58 C 34 44, 50 30, 50 26 Z" fill="url(#bwMarkGrad)"/>
    <circle cx="50" cy="58" r="4.5" fill="#FFFFFF"/>
  </g>
  <!-- Typography for Dark Backgrounds -->
  <text x="112" y="55" font-family="-apple-system, BlinkMacSystemFont, 'Segoe UI', Inter, sans-serif" font-size="38" font-weight="800" fill="#F8FAFC" letter-spacing="-0.5">Body</text>
  <text x="206" y="55" font-family="-apple-system, BlinkMacSystemFont, 'Segoe UI', Inter, sans-serif" font-size="38" font-weight="800" fill="url(#bwTextGrad)" letter-spacing="-0.5">Wise</text>
  <text x="114" y="76" font-family="-apple-system, BlinkMacSystemFont, 'Segoe UI', Inter, sans-serif" font-size="11" font-weight="600" fill="#94A3B8" letter-spacing="1.5">TRỢ LÝ THỂ TRẠNG &amp; DINH DƯỠNG AI</text>
</svg>"""

LOGO_HORIZONTAL_LIGHT_SVG = """<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 420 100" fill="none">
  <defs>
    <linearGradient id="bwLightTextGrad" x1="0%" y1="0%" x2="100%" y2="100%">
      <stop offset="0%" stop-color="#0D9488"/>
      <stop offset="100%" stop-color="#0284C7"/>
    </linearGradient>
    <linearGradient id="bwMarkGradL" x1="0%" y1="0%" x2="100%" y2="100%">
      <stop offset="0%" stop-color="#14B8A6"/>
      <stop offset="50%" stop-color="#0D9488"/>
      <stop offset="100%" stop-color="#0284C7"/>
    </linearGradient>
    <linearGradient id="bwSecGradL" x1="100%" y1="0%" x2="0%" y2="100%">
      <stop offset="0%" stop-color="#38BDF8"/>
      <stop offset="100%" stop-color="#0F766E"/>
    </linearGradient>
  </defs>
  <!-- Mark Group -->
  <g transform="translate(10, 5) scale(0.9)">
    <path d="M 50 12 A 38 38 0 1 1 16 64" fill="none" stroke="url(#bwMarkGradL)" stroke-width="8" stroke-linecap="round"/>
    <path d="M 50 26 A 24 24 0 1 0 72 60" fill="none" stroke="url(#bwSecGradL)" stroke-width="6.5" stroke-linecap="round"/>
    <path d="M 50 26 C 50 40, 68 46, 68 58 C 68 68, 59 74, 50 74 C 41 74, 34 68, 34 58 C 34 44, 50 30, 50 26 Z" fill="url(#bwMarkGradL)"/>
    <circle cx="50" cy="58" r="4.5" fill="#FFFFFF"/>
  </g>
  <!-- Typography for Light Backgrounds -->
  <text x="112" y="55" font-family="-apple-system, BlinkMacSystemFont, 'Segoe UI', Inter, sans-serif" font-size="38" font-weight="800" fill="#0F172A" letter-spacing="-0.5">Body</text>
  <text x="206" y="55" font-family="-apple-system, BlinkMacSystemFont, 'Segoe UI', Inter, sans-serif" font-size="38" font-weight="800" fill="url(#bwLightTextGrad)" letter-spacing="-0.5">Wise</text>
  <text x="114" y="76" font-family="-apple-system, BlinkMacSystemFont, 'Segoe UI', Inter, sans-serif" font-size="11" font-weight="600" fill="#475569" letter-spacing="1.5">TRỢ LÝ THỂ TRẠNG &amp; DINH DƯỠNG AI</text>
</svg>"""

LOGO_MONO_SVG = """<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 420 100" fill="none">
  <!-- Mark Group Monochromatic -->
  <g transform="translate(10, 5) scale(0.9)">
    <path d="M 50 12 A 38 38 0 1 1 16 64" fill="none" stroke="currentColor" stroke-width="8" stroke-linecap="round"/>
    <path d="M 50 26 A 24 24 0 1 0 72 60" fill="none" stroke="currentColor" stroke-width="6.5" stroke-linecap="round"/>
    <path d="M 50 26 C 50 40, 68 46, 68 58 C 68 68, 59 74, 50 74 C 41 74, 34 68, 34 58 C 34 44, 50 30, 50 26 Z" fill="currentColor"/>
    <circle cx="50" cy="58" r="4.5" fill="#FFFFFF"/>
  </g>
  <text x="112" y="55" font-family="-apple-system, BlinkMacSystemFont, 'Segoe UI', Inter, sans-serif" font-size="38" font-weight="800" fill="currentColor" letter-spacing="-0.5">BodyWise</text>
  <text x="114" y="76" font-family="-apple-system, BlinkMacSystemFont, 'Segoe UI', Inter, sans-serif" font-size="11" font-weight="600" fill="currentColor" opacity="0.8" letter-spacing="1.5">TRỢ LÝ THỂ TRẠNG &amp; DINH DƯỠNG AI</text>
</svg>"""

APP_ICON_SQUIRCLE_SVG = """<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 512 512" fill="none">
  <defs>
    <linearGradient id="appBgGrad" x1="0%" y1="0%" x2="100%" y2="100%">
      <stop offset="0%" stop-color="#0F172A"/>
      <stop offset="50%" stop-color="#090E17"/>
      <stop offset="100%" stop-color="#042F2E"/>
    </linearGradient>
    <linearGradient id="appMarkGrad" x1="0%" y1="0%" x2="100%" y2="100%">
      <stop offset="0%" stop-color="#2DD4BF"/>
      <stop offset="50%" stop-color="#0D9488"/>
      <stop offset="100%" stop-color="#38BDF8"/>
    </linearGradient>
    <linearGradient id="appSecGrad" x1="100%" y1="0%" x2="0%" y2="100%">
      <stop offset="0%" stop-color="#38BDF8"/>
      <stop offset="100%" stop-color="#14B8A6"/>
    </linearGradient>
    <filter id="appGlow" x="-20%" y="-20%" width="140%" height="140%">
      <feDropShadow dx="0" dy="12" stdDeviation="24" flood-color="#0D9488" flood-opacity="0.35"/>
    </filter>
  </defs>
  <!-- Squircle container -->
  <rect width="512" height="512" rx="128" fill="url(#appBgGrad)"/>
  <rect x="2" y="2" width="508" height="508" rx="126" stroke="#1E293B" stroke-width="4" fill="none"/>
  <!-- Mark Group Scaled -->
  <g transform="translate(106, 106) scale(3)" filter="url(#appGlow)">
    <path d="M 50 12 A 38 38 0 1 1 16 64" fill="none" stroke="url(#appMarkGrad)" stroke-width="7.5" stroke-linecap="round"/>
    <path d="M 50 26 A 24 24 0 1 0 72 60" fill="none" stroke="url(#appSecGrad)" stroke-width="6" stroke-linecap="round"/>
    <path d="M 50 26 C 50 40, 68 46, 68 58 C 68 68, 59 74, 50 74 C 41 74, 34 68, 34 58 C 34 44, 50 30, 50 26 Z" fill="url(#appMarkGrad)"/>
    <circle cx="50" cy="58" r="4.5" fill="#FFFFFF"/>
  </g>
</svg>"""

# 2. Domain Icons SVGs (24x24 standard grid)
DOMAIN_ICONS = {
    "bmi.svg": """<svg xmlns="http://www.w3.org/2000/svg" width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
  <path d="m12 14 4-4"/>
  <path d="M3.34 19a10 10 0 1 1 17.32 0"/>
  <path d="M8 19h8"/>
  <circle cx="12" cy="14" r="2"/>
</svg>""",
    "pbf.svg": """<svg xmlns="http://www.w3.org/2000/svg" width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
  <path d="M12 2.69l5.66 5.66a8 8 0 1 1-11.31 0z"/>
  <path d="M10 15a2 2 0 1 0 4 0"/>
</svg>""",
    "smm.svg": """<svg xmlns="http://www.w3.org/2000/svg" width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
  <path d="m6.5 6.5 11 11"/>
  <path d="m21 21-1-1a2 2 0 0 0-2.83 0l-.88.88a2 2 0 0 1-2.83 0l-7.07-7.07a2 2 0 0 1 0-2.83l.88-.88a2 2 0 0 0 0-2.83L6.27 6.27a2 2 0 0 0-2.83 0l-.88.88a2 2 0 0 1-2.83 0L3 3"/>
  <path d="m14.5 9.5 3-3"/>
</svg>""",
    "vfl.svg": """<svg xmlns="http://www.w3.org/2000/svg" width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
  <path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z"/>
  <circle cx="12" cy="11" r="3"/>
</svg>""",
    "bfm.svg": """<svg xmlns="http://www.w3.org/2000/svg" width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
  <circle cx="12" cy="12" r="10"/>
  <path d="M8 12a4 4 0 0 0 8 0"/>
  <path d="M9 9h.01"/>
  <path d="M15 9h.01"/>
</svg>""",
    "nutrition.svg": """<svg xmlns="http://www.w3.org/2000/svg" width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
  <path d="M18 8h1a4 4 0 0 1 0 8h-1"/>
  <path d="M2 8h16v9a4 4 0 0 1-4 4H6a4 4 0 0 1-4-4V8z"/>
  <line x1="6" y1="1" x2="6" y2="4"/>
  <line x1="10" y1="1" x2="10" y2="4"/>
  <line x1="14" y1="1" x2="14" y2="4"/>
</svg>""",
    "workout.svg": """<svg xmlns="http://www.w3.org/2000/svg" width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
  <path d="M14.4 14.4 9.6 9.6"/>
  <path d="M18.65 8.65a2 2 0 0 0 0-2.83l-4.47-4.47a2 2 0 0 0-2.83 0l-1.41 1.41a2 2 0 0 0 0 2.83l4.47 4.47a2 2 0 0 0 2.83 0z"/>
  <path d="M9.82 17.48a2 2 0 0 0-2.83 0L2.52 21.95a2 2 0 0 0 0 2.83l1.41 1.41a2 2 0 0 0 2.83 0l4.47-4.47a2 2 0 0 0 0-2.83z"/>
  <path d="m21.5 15.5-4-4"/>
  <path d="m6.5 12.5-4-4"/>
</svg>""",
    "ocr-scan.svg": """<svg xmlns="http://www.w3.org/2000/svg" width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
  <path d="M3 7V5a2 2 0 0 1 2-2h2"/>
  <path d="M17 3h2a2 2 0 0 1 2 2v2"/>
  <path d="M21 17v2a2 2 0 0 1-2 2h-2"/>
  <path d="M7 21H5a2 2 0 0 1-2-2v-2"/>
  <rect width="10" height="8" x="7" y="8" rx="1"/>
  <line x1="10" y1="12" x2="14" y2="12"/>
</svg>""",
    "safety-shield.svg": """<svg xmlns="http://www.w3.org/2000/svg" width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
  <path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z"/>
  <path d="m9 12 2 2 4-4"/>
</svg>""",
    "memory-facts.svg": """<svg xmlns="http://www.w3.org/2000/svg" width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
  <path d="M12 2a5 5 0 0 1 5 5c0 1.9-1 3.5-2.5 4.3V14a2 2 0 0 1-2 2h-1a2 2 0 0 1-2-2v-2.7C8 10.5 7 8.9 7 7a5 5 0 0 1 5-5z"/>
  <path d="M9 18h6"/>
  <path d="M10 22h4"/>
</svg>""",
    "evidence-doc.svg": """<svg xmlns="http://www.w3.org/2000/svg" width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
  <path d="M4 19.5v-15A2.5 2.5 0 0 1 6.5 2H20v20H6.5a2.5 2.5 0 0 1-2.5-2.5Z"/>
  <path d="M6 6h10"/>
  <path d="M6 10h10"/>
  <path d="M6 14h6"/>
</svg>"""
}

# Write SVGs to docs and public
brand_svgs = {
    "logo-mark.svg": LOGO_MARK_SVG,
    "logo-horizontal-dark.svg": LOGO_HORIZONTAL_DARK_SVG,
    "logo-horizontal-light.svg": LOGO_HORIZONTAL_LIGHT_SVG,
    "logo-mono.svg": LOGO_MONO_SVG,
    "app-icon.svg": APP_ICON_SQUIRCLE_SVG,
}

for name, content in brand_svgs.items():
    with open(os.path.join(DOCS_BRAND_DIR, name), "w", encoding="utf-8") as f:
        f.write(content)
    with open(os.path.join(PUBLIC_BRAND_DIR, name), "w", encoding="utf-8") as f:
        f.write(content)

for name, content in DOMAIN_ICONS.items():
    with open(os.path.join(DOCS_ICONS_DIR, name), "w", encoding="utf-8") as f:
        f.write(content)
    with open(os.path.join(PUBLIC_ICONS_DIR, name), "w", encoding="utf-8") as f:
        f.write(content)

# Write metadata json for domain icons
icons_manifest = {
    "system": "BodyWise Domain Iconography v1.0",
    "grid": "24x24 px vector",
    "style": "Clean geometric stroke (2.0px), stroke-linecap round",
    "icons": list(DOMAIN_ICONS.keys())
}
with open(os.path.join(DOCS_ICONS_DIR, "icons.json"), "w", encoding="utf-8") as f:
    json.dump(icons_manifest, f, indent=2, ensure_ascii=False)
with open(os.path.join(PUBLIC_ICONS_DIR, "icons.json"), "w", encoding="utf-8") as f:
    json.dump(icons_manifest, f, indent=2, ensure_ascii=False)

# 3. High-Quality Raster Assets via Pillow
def draw_app_icon(size=512, radius=None):
    if radius is None:
        radius = int(size * 0.25)
    img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)

    # Draw rounded squircle background
    draw.rounded_rectangle([0, 0, size, size], radius=radius, fill=(15, 23, 42, 255), outline=(30, 41, 59, 255), width=max(1, int(size * 0.015)))

    # Draw outer composition arc
    cx, cy = size // 2, size // 2
    r_outer = int(size * 0.38)
    stroke_w_outer = max(3, int(size * 0.075))
    draw.arc([cx - r_outer, cy - r_outer, cx + r_outer, cy + r_outer], start=210, end=45, fill=(13, 148, 136, 255), width=stroke_w_outer)

    # Draw inner metabolism arc
    r_inner = int(size * 0.24)
    stroke_w_inner = max(2, int(size * 0.06))
    draw.arc([cx - r_inner, cy - r_inner, cx + r_inner, cy + r_inner], start=30, end=230, fill=(56, 189, 248, 255), width=stroke_w_inner)

    # Central Spark node
    r_center = max(4, int(size * 0.12))
    draw.ellipse([cx - r_center, cy - r_center + int(size * 0.04), cx + r_center, cy + r_center + int(size * 0.04)], fill=(20, 184, 166, 255))
    
    # White pupil / core spark
    r_pupil = max(2, int(size * 0.04))
    draw.ellipse([cx - r_pupil, cy - r_pupil + int(size * 0.04), cx + r_pupil, cy + r_pupil + int(size * 0.04)], fill=(255, 255, 255, 255))

    return img

# Generate Favicons & App Icons
sizes = {
    "favicon-16.png": 16,
    "favicon-32.png": 32,
    "favicon-48.png": 48,
    "favicon-192.png": 192,
    "favicon-512.png": 512,
    "apple-touch-icon.png": 180,
    "app-icon.png": 512
}

ico_frames = []
for fname, s in sizes.items():
    icon_img = draw_app_icon(s)
    path_docs = os.path.join(DOCS_BRAND_DIR, fname)
    path_pub = os.path.join(PUBLIC_BRAND_DIR, fname)
    icon_img.save(path_docs, "PNG")
    icon_img.save(path_pub, "PNG")
    if s in (16, 32, 48):
        ico_frames.append(icon_img)

# Save multi-size favicon.ico
ico_path_docs = os.path.join(DOCS_BRAND_DIR, "favicon.ico")
ico_path_pub = os.path.join(PUBLIC_BRAND_DIR, "favicon.ico")
ico_path_root = "frontend/src/app/favicon.ico"
ico_frames[0].save(ico_path_docs, format="ICO", sizes=[(16, 16), (32, 32), (48, 48)])
shutil.copy2(ico_path_docs, ico_path_pub)
shutil.copy2(ico_path_docs, ico_path_root)

# 4. Generate OG Image (1200x630)
def generate_og_image():
    w, h = 1200, 630
    og = Image.new("RGBA", (w, h), (8, 13, 26, 255))
    draw = ImageDraw.Draw(og)

    # Ambient Teal glow in corner
    for r in range(350, 0, -25):
        alpha = int((350 - r) / 350 * 28)
        draw.ellipse([w - 300 - r, -100 - r, w - 300 + r, -100 + r], fill=(13, 148, 136, alpha))

    # Grid line accents
    for x in range(0, w, 60):
        draw.line([(x, 0), (x, h)], fill=(255, 255, 255, 5), width=1)
    for y in range(0, h, 60):
        draw.line([(0, y), (w, y)], fill=(255, 255, 255, 5), width=1)

    # Card container mockup
    card_x0, card_y0, card_x1, card_y1 = 640, 110, 1120, 520
    draw.rounded_rectangle([card_x0, card_y0, card_x1, card_y1], radius=24, fill=(15, 23, 42, 230), outline=(51, 65, 85, 255), width=2)

    # Header of mockup card
    draw.text((card_x0 + 36, card_y0 + 36), "KẾT QUẢ THỂ TRẠNG INBODY", fill=(148, 163, 184, 255))
    draw.text((card_x0 + 36, card_y0 + 70), "Hồ sơ: 72.4 kg  •  BMI: 22.8", fill=(248, 250, 252, 255))

    # Sub-metrics inside card
    draw.rounded_rectangle([card_x0 + 36, card_y0 + 130, card_x0 + 210, card_y0 + 220], radius=16, fill=(30, 41, 59, 200), outline=(13, 148, 136, 120), width=1)
    draw.text((card_x0 + 50, card_y0 + 145), "TỶ LỆ MỠ (PBF)", fill=(148, 163, 184, 255))
    draw.text((card_x0 + 50, card_y0 + 175), "19.5 %", fill=(45, 212, 191, 255))

    draw.rounded_rectangle([card_x0 + 230, card_y0 + 130, card_x0 + 440, card_y0 + 220], radius=16, fill=(30, 41, 59, 200), outline=(56, 189, 248, 120), width=1)
    draw.text((card_x0 + 245, card_y0 + 145), "CƠ XƯƠNG (SMM)", fill=(148, 163, 184, 255))
    draw.text((card_x0 + 245, card_y0 + 175), "33.8 kg", fill=(56, 189, 248, 255))

    # Safety banner mockup
    draw.rounded_rectangle([card_x0 + 36, card_y0 + 245, card_x1 - 36, card_y0 + 360], radius=16, fill=(4, 47, 46, 160), outline=(13, 148, 136, 180), width=1)
    draw.text((card_x0 + 56, card_y0 + 265), "AN TOÀN Y TẾ & TRÍCH DẪN RAG", fill=(20, 184, 166, 255))
    draw.text((card_x0 + 56, card_y0 + 300), "Dữ liệu đối soát chuẩn WPRO • Nguồn tài liệu y tế minh bạch", fill=(203, 213, 225, 255))

    # Main Left Branding
    # Stamp Icon
    app_icon_120 = draw_app_icon(120, radius=30)
    og.paste(app_icon_120, (90, 150), app_icon_120)

    # Brand Title
    draw.text((90, 300), "BodyWise", fill=(248, 250, 252, 255))
    draw.text((90, 370), "Trợ lý Thể trạng & Dinh dưỡng AI", fill=(45, 212, 191, 255))
    draw.text((90, 430), "Phân tích chỉ số InBody (BMI, PBF, SMM, mỡ nội tạng theo WHO)\nTư vấn dinh dưỡng tái tạo thể trạng & Cảnh báo an toàn y tế", fill=(148, 163, 184, 255))

    draw.rounded_rectangle([90, 520, 320, 565], radius=22, fill=(13, 148, 136, 255))
    draw.text((120, 532), "KHÁM PHÁ NGAY →", fill=(255, 255, 255, 255))

    og.save(os.path.join(DOCS_BRAND_DIR, "og-image.png"), "PNG")
    og.save(os.path.join(PUBLIC_BRAND_DIR, "og-image.png"), "PNG")

generate_og_image()

# 5. Generate PWA Web Manifest
webmanifest = {
    "name": "BodyWise — Trợ lý Thể trạng & Dinh dưỡng AI",
    "short_name": "BodyWise",
    "description": "Trợ lý AI phân tích InBody, dinh dưỡng thể trạng và cảnh báo an toàn y tế.",
    "start_url": "/",
    "display": "standalone",
    "background_color": "#080D1A",
    "theme_color": "#0D9488",
    "icons": [
        {
            "src": "/brand/favicon-192.png",
            "sizes": "192x192",
            "type": "image/png"
        },
        {
            "src": "/brand/favicon-512.png",
            "sizes": "512x512",
            "type": "image/png"
        },
        {
            "src": "/brand/app-icon.png",
            "sizes": "512x512",
            "type": "image/png",
            "purpose": "maskable any"
        }
    ]
}

with open(os.path.join(DOCS_BRAND_DIR, "manifest.webmanifest"), "w", encoding="utf-8") as f:
    json.dump(webmanifest, f, indent=2, ensure_ascii=False)
with open(os.path.join(PUBLIC_BRAND_DIR, "manifest.webmanifest"), "w", encoding="utf-8") as f:
    json.dump(webmanifest, f, indent=2, ensure_ascii=False)
with open(os.path.join(PUBLIC_BRAND_DIR, "manifest.json"), "w", encoding="utf-8") as f:
    json.dump(webmanifest, f, indent=2, ensure_ascii=False)

print("Generated all BodyWise brand and iconography assets successfully!")

