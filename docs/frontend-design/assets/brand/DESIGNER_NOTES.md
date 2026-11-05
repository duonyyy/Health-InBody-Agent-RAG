# BodyWise — Logo Assets

**Concept 01 — The Vitality Orbit & Spark** · Reconstructed from the supplied BodyWise brand-board PNG.

## Contents

- `source/logo-master.svg`: master Bézier geometry and brand gradients.
- `source/construction-grid.svg`: reference coordinate grid (documentation only).
- `logo/svg/`: 8 independent, self-contained SVG logos; paths and circle, **no bitmap embedding or external fonts**.
- `logo/png/`: 8 variants × `@1x`, `@2x`, `@4x` with transparent alpha.
- `favicon/`: independent SVG, multi-resolution ICO (16/32/48) and three PNGs.
- `app-icons/`: 180 Apple, 192 PWA, 512 PWA and 512 maskable PNGs.
- `previews/`: contact sheet and source/render comparisons.
- `QA-report.json`: machine-readable validation manifest, sizes and sampled colors.

## Asset selection

| File | Recommended usage |
|---|---|
| `logo-mark.svg` | Standalone brand icon; use in compact branding |
| `logo-horizontal-light.svg` | Horizontal wordmark on a **light** surface |
| `logo-horizontal-dark.svg` | White horizontal wordmark on a **dark** surface |
| `logo-tagline-light.svg` | Horizontal logo with the exact Vietnamese slogan, light surface |
| `logo-tagline-dark.svg` | Horizontal logo and slogan, dark surface |
| `logo-stacked.svg` | Centered stacked full-color icon + wordmark |
| `logo-mono-black.svg` | Centered stacked single-color black logo |
| `logo-mono-white.svg` | Centered stacked single-color white logo |

> For dark logo variants, SVG and logo PNG backgrounds are **transparent**, not navy. Place them on a dark UI surface to see white text.

## Official design tokens

| Name | HEX |
|---|---|
| Porcelain Sand | `#F8FAFC` |
| White | `#FFFFFF` |
| Deep Slate Navy | `#0F172A` |
| Vital Teal | `#0D9488` |
| Teal Light (spark, manually corrected) | `#14B8A6` |
| Bio Sky | `#0284C7` |
| Sky Light | `#38BDF8` |

### Colors sampled from raster (not approved tokens)

The original orbit contains light green color not defined in the supplied palette. Pixel sampling (coordinates in original 1672×941 board) shows:

- `(306,248)`: `#7DCA80` (pale green at the upper-right ring),
- `(282,281)`: `#69C48C`,
- `(253,303)`: `#45BE99`.

The SVG's orbit gradient is an approximation and should be confirmed if a precise brand gradient is available.

## Accuracy evaluation

| Element | Evaluation | Note |
|---|---|---|
| General motif and layout | High resemblance | Silhouette, person, head, orbital motion and spark kept |
| Circle and four-point spark | Close | Spark changed to required `#14B8A6` |
| Bézier paths | Approximate | Original source is a raster board, not vector geometry |
| Exact contour match | **Not proven** | Source-fitted contours do not recover the original anchor/control points |
| Wordmark | Approximate | **Inter Bold** substituted for unknown original bold font, converted to paths |
| Slogan | Content exact | `Hiểu cơ thể. Sống chủ động.`; **Inter Regular** converted to paths |
| Gradient | Approximate | Sampled light-green points retained; inferred color stops |
| Monochrome | Pass | Single solid black or white, no gradients |
| File format | Pass | SVG outlines and geometry, PNG with actual alpha |
| 16px favicon | Usable with limitations | Original complex symbol compresses; test on target devices |

**Approval needed:** original font name / source `.ai` or `.svg` for pixel-precise outlines; approval for inferred orbital light green and its gradient; choice of app icon background for 192 px (reference shows light surface, while the specification explicitly names only navy/teal); whether white-on-teal app icons should be used for 512 px.

**Important:** These SVGs are editable curvature-smoothed Bézier paths, but they are a reconstruction of a PNG screenshot, **not an exact extraction of original vector data**. They are not certified as 100% pixel matched.

## Alignment correction (revision 2)

- Unified connected outer silhouette of the person and orbit to remove a sharp seam and avoid body/orbit misregistration.
- Shifted stacked master mark to the true 350px frame midpoint (was 11.5px too far left).
- Corrected optical vertical placement of mark in large app icons; all variants derive from the same master coordinates.
- Head recentered at `(115.5, 37.6)` in the master viewBox.
- Gradient and original font remain estimated from the board raster.

## Implementation

In HTML: `<img src="/assets/bodywise/logo/svg/logo-horizontal-light.svg" alt="BodyWise" />`

For PWA, link `app-icons/icon-192.png`, `app-icons/icon-512.png` and set `purpose: "maskable"` for `icon-maskable-512.png` in your manifest. In HTML `<link rel="icon" href="/assets/bodywise/favicon/favicon.svg" type="image/svg+xml">`.

## Rebuild

Sources in `source/` contain the main vector geometry. Every logo variant shares this same source-fitted cubic geometry. All 8 logos have outlined lettering; stacked mark has center-aligned source geometry and app icons have optical centering correction; there is no runtime font requirement. Output generated with `fontTools`, `CairoSVG` and `Pillow`. Only vector output assets are shipped as logo content; image reference is used for evaluation only and is not embedded.
