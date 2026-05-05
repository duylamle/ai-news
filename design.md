---
type: artifact
scope: ai-news
created: 2026-05-06
updated: 2026-05-06
---

# AI News — Design Direction

## Mood & Tone

**Tươi sáng + công nghệ + reading-friendly** — feed dạng Pinterest masonry để
Lam scan nhanh, nhưng giữ tone "AI engineering thoughtful" thay vì lifestyle
fluff.

**Inspired by:** Mintlify (white airy + brand green + ultra-round corners) +
Pinterest (masonry asymmetric grid) + Linear (compact precision typography).

**Not:** Pinterest's warm/craft palette (quá lifestyle), Claude's parchment
serif (quá editorial slow), Vercel's mono-restraint (quá enterprise lạnh).

## Layout

**Masonry 3 cột bất đối xứng:**
- Desktop: 3 cột, gap 16px
- Tablet: 2 cột
- Mobile: 1 cột stack
- Card height variable theo content (excerpt 3 dòng truncate, expand inline khi click)
- Random seed + content length quyết height → tránh đều răng cưa

**Card structure:**
```
┌─────────────────────────┐
│ [Source badge] [Quality]│  ← top metadata row
│                         │
│ Title (2-3 lines max)   │  ← bold, link
│                         │
│ Excerpt 3 dòng…         │  ← body, truncate
│ ▸ Show more             │  ← expand inline
│                         │
│ Type · Topic · Audience │  ← footer classify (subtle)
│ #tag #tag               │
│ 2026-05-05    [↗ link]  │  ← bottom row
└─────────────────────────┘
```

## Color Palette

### Light mode (default — tươi sáng)

```
--bg:           #fafbfc      (canvas, hơi xanh đá)
--surface:      #ffffff      (card)
--surface-2:    #f4f6f8      (filter dropdown bg)
--border:       rgba(15,23,42,0.08)   (whisper border)
--border-hover: rgba(99,102,241,0.4)  (card hover)

--text:         #0f172a      (primary)
--text-soft:    #334155      (body)
--text-dim:     #64748b      (meta)
--text-faint:   #94a3b8      (footer classify)

--brand:        #6366f1      (indigo — accent CTA, focus)
--brand-soft:   #eef2ff      (badge bg, hover surface)
--brand-deep:   #4f46e5      (hover state)

--accent-1:     #06b6d4      (cyan — research/academic)
--accent-2:     #10b981      (emerald — engineering/tutorial)
--accent-3:     #f59e0b      (amber — must-read)
--accent-4:     #f43f5e      (rose — model-release)
--accent-5:     #8b5cf6      (violet — harness/personal-blog)
```

### Dark mode (toggle, optional v2)

Để v2 — focus light mode trước.

## Typography

```
--font-sans:    'Inter', -apple-system, BlinkMacSystemFont, sans-serif
--font-mono:    'JetBrains Mono', 'Geist Mono', ui-monospace, monospace
```

Inter cho mọi text. Mono cho `tags`, `source-id`, `arxiv:xxx` references.

### Hierarchy

- **Title card:** 17px, weight 600, line-height 1.35, letter-spacing -0.01em
- **Body excerpt:** 14px, weight 400, line-height 1.55
- **Meta:** 12px, weight 500, letter-spacing 0.02em
- **Footer classify:** 11px, weight 400, color `--text-faint`
- **Badge:** 11px, weight 500, uppercase letter-spacing 0.04em

## Visual Language

### Border radius
- Card: **16px** (Mintlify ultra-round)
- Badge: **6px** (compact pill cho meta tags)
- Button: **8px** (filter dropdowns)
- Input: **8px**

### Shadow (Mintlify-style barely-there)
```css
--shadow-card: 0 1px 2px rgba(15,23,42,0.04), 
               0 0 0 1px rgba(15,23,42,0.06);
--shadow-card-hover: 0 4px 12px rgba(99,102,241,0.08),
                     0 0 0 1px rgba(99,102,241,0.18);
```

→ Card lift on hover với indigo tint shadow → feel "interactive AI feed".

### Gradient accents (Mintlify atmospheric touch)
- Header background: subtle gradient `linear-gradient(180deg, #fafbfc 0%, #ffffff 100%)`
- Header bottom border: 1px solid với subtle indigo tint

## Filter UI (sticky header)

- Sticky top với `backdrop-filter: blur(8px)`, bg `rgba(255,255,255,0.85)`
- Filters trong 1 row gọn (dropdowns nhỏ hơn current — `--text-soft`)
- Search box wider, prominent
- "Reset" button transparent, hover indigo

## Card hover/interaction

- **Idle:** subtle border, no shadow
- **Hover:** card lift 1px, shadow indigo tint, border indigo soft
- **Active (clicked):** brief 100ms scale 0.99 feedback
- **Focus visible (keyboard):** 2px indigo outline ring

## Color coding semantics

Card top-left badge color = **source quality** (deterministic, không cần Lam đoán):

| Quality | Badge color | Meaning |
|---|---|---|
| `lab-official` | indigo | Research from major labs |
| `peer-reviewed` | cyan | Conference paper accepted |
| `preprint` | sky blue (lighter cyan) | arXiv unreviewed |
| `corporate-blog` | indigo soft | News from company blog |
| `personal-blog` | violet | Solo author, opinionated |
| `curated-newsletter` | emerald | Editorial digest |
| `aggregator` | gray | Auto-curated feed |
| `community-forum` | amber | LessWrong, Alignment Forum |
| `vendor-blog` | rose | Product blog (vendor bias warning) |

Importance highlight (top-right corner):
- `must-read`: amber dot/badge (subtle pulse animation)
- `worth-reading`: no badge (default)
- `skim`: dim, slightly grayed out card

## Microinteractions

- Card hover: 150ms ease shadow + border transition
- Show more toggle: 200ms ease slide expand
- Filter dropdown change: instant filter, fade re-render 100ms
- Stats counter: animated count-up khi filter thay đổi (~300ms)
- Loading state: shimmer skeleton 3 cards (no spinner)

## Accessibility

- Contrast ratio ≥ 4.5 cho text trên `--bg`
- Focus ring 2px indigo cho keyboard nav
- Aria-labels trên dropdowns + buttons
- `prefers-reduced-motion`: disable lift transitions
- Title link `target="_blank"` có `rel="noopener noreferrer"`

## Empty/error states

- 0 entries: friendly indigo tinted illustration + "Đợi routine cào lần đầu…"
- Filter no match: "Không có entry khớp filter • Reset để xem tất cả"
- Fetch fail: warning amber "Đảm bảo bạn đã chạy start.bat"

## What's NOT in this design

- No dark mode v1 (focus light)
- No animation heavy (chỉ subtle transitions)
- No card images (text-first, AI news không cần thumbnails)
- No infinite scroll (paginate 100 entries / page, "Load more" button)
- No emoji decorations (clean engineering tone)
