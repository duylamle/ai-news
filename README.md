---
type: artifact
scope: ai-news
created: 2026-05-06
updated: 2026-05-06
---

# AI News — Lam's Personal Feed

Tự động cào AI news từ ~60 nguồn uy tín (lab official, research papers,
practitioner blogs, newsletters, harness engineering, safety, business,
Vietnam), phân loại theo Source / Type / Language / Importance, hiển thị
qua local FE blog với filter, search, star manual, infinite scroll, và
animations mượt.

Repo này được 6 Claude Code routines (cron 07h/14h/19h SGT × 2 accounts)
ingest mỗi ngày. Lam pull về local + chạy `start.bat` để xem.

---

## Mục tiêu

1. **Đảm bảo session active** — routines ping mỗi ~5h kích hoạt session
   window cho cả 2 accounts.
2. **Cào AI news** — tận dụng routine để tổng hợp tin AI vào 1 feed.

---

## Cách dùng (xem feed local)

1. `git pull` tại folder local Drive.
2. Double-click **`start.bat`** (Windows) hoặc `./start.sh` (Mac/Linux).
3. Browser tự mở `http://localhost:8765/index.html`.
4. Filter feed qua sidebar trái: Source / Type / Language / Importance.
5. Plus: text search box, date range, sort, expand all toggle.
6. Click **★** để mark must-read manual (lưu vào `starred.json` + git).
7. Click title → mở link gốc trong tab mới.

> Lưu ý: Phải mở qua local server (`start.bat`) — không double-click thẳng
> `index.html` (CORS chặn fetch JSON từ `file://`).

---

## Cấu trúc repo

```
ai-news/
├── index.html              # FE shell, ~30KB, sidebar + masonry feed
├── start.bat / start.sh    # Local server launcher (custom Python)
├── data/
│   ├── manifest.json       # metadata: months list, total entries, sources
│   └── entries-YYYY-MM.json # 1 file/tháng, JSON array entries
├── state.json              # last fetched URLs + consecutive_empty per source
├── starred.json            # ID entries Lam đã ★ (commit lên git để sync)
├── sources.json            # 60+ nguồn config + schedule weekly + frequency tiers
├── scripts/
│   ├── fetch.py            # Parse RSS / scrape meta tag, output JSON
│   ├── classify.py         # Rule-based first-pass: source_org, type, lang, importance, tags
│   ├── append.py           # Append entries + update manifest + state
│   ├── audit_frequency.py  # Đo posts-per-week, recommend frequency tier
│   ├── generate_schedule.py # Auto-balance schedule weekly cho 2 accounts
│   ├── server.py           # Local HTTP server + /api/star endpoint
│   ├── run_local.py        # End-to-end pipeline test
│   └── requirements.txt    # feedparser, requests, beautifulsoup4
├── .gitattributes          # merge=union cho data files (concurrency safe)
├── .gitignore
├── design.md               # Design direction (Mintlify + Pinterest masonry)
└── README.md
```

---

## Source pool (~60 nguồn)

Phân theo bucket trong `sources.json`. Mỗi source có:
- `frequency`: `3` (high) / `2` (medium) / `1` (low) / `monthly` / `quarterly`
- `quality`: peer-reviewed / preprint / lab-official / corporate-blog /
  personal-blog / curated-newsletter / aggregator / community-forum / vendor-blog
- `bucket`: lab-official / academic / engineering / harness / commentary /
  business / safety / vietnam
- `preferred_days`: hint cho schedule

### Bucket overview

| Bucket | Số nguồn | Ví dụ |
|---|---|---|
| Lab Official | ~12 | Anthropic, OpenAI, DeepMind, Mistral, Cohere, Meta FAIR, MS Research, NVIDIA, Apple ML, AWS ML, Google Research, Salesforce AI |
| Academic | ~8 | arXiv (cs.AI/CL/LG), HF Daily Papers, BAIR, MIT News, alphaXiv, Papers with Code, The Gradient |
| Engineering | ~7 | Hugging Face Blog, Simon Willison, Sebastian Raschka, Eugene Yan, Hamel Husain, Latent Space, ML Mastery, LangChain |
| Harness | 4 | Addy Osmani, Mitchell Hashimoto, Karpathy, Pete Koomen |
| Commentary | ~9 | Import AI, The Batch, MIT Tech Review, TLDR AI, Ben's Bites, MarkTechPost, KDnuggets, BD TechTalks, Wired AI, The Verge AI, Last Week in AI, The Neuron, Lex Fridman |
| Business | ~5 | a16z AI, Lenny's Newsletter, Theory VC, Sequoia AI, VentureBeat AI, TechCrunch AI |
| Safety | 3 | LessWrong, Alignment Forum, FLI |
| Vietnam | 3 | FPT.AI, VinAI, Goon Nguyễn |

---

## Frequency tiers (auto-drop logic)

Mỗi source có `frequency` quyết định fetch bao nhiêu lần/tuần:

| Tier | Value | Số fetches |
|---|---|---|
| High | `3` | 3 lần/tuần (Mon/Wed/Fri) |
| Medium | `2` | 2 lần/tuần |
| Low | `1` | 1 lần/tuần |
| Monthly | `"monthly"` | 1 lần/tháng |
| Quarterly | `"quarterly"` | 1 lần/3 tháng |

**Auto-drop:** `state.json` track `consecutive_empty` per source. Khi vượt
threshold → flag `inactive: true`, skip khỏi schedule.

| Tier | Threshold (consecutive empty) | Tương đương |
|---|---|---|
| Quarterly | 4 | 1 năm silence |
| Monthly | 12 | 1 năm silence |
| Low/Medium/High | 26+ | 6 tháng silence |

Lam có thể chạy `python scripts/audit_frequency.py` định kỳ để re-evaluate
sources + adjust frequency.

---

## Classification taxonomy (4 trục filter)

### Trục 1: Source

ID nguồn cụ thể (anthropic-news, arxiv-cs-ai, simon-willison, goon-nguyen...).

### Trục 2: Type (gộp Quality + Content Type)

| Value | Khi nào |
|---|---|
| `research-published` | Source quality = peer-reviewed (NeurIPS, ICML, conference) |
| `research-draft` | Source quality = preprint (arXiv) |
| `newsletter` | Source quality = curated-newsletter / aggregator |
| `company-blog` | Source quality = corporate / lab / vendor blog |
| `personal-blog` | Source quality = personal / community-forum |
| `release` | Title chứa "introducing/announcing/launching/new model..." |
| `tutorial` | Title chứa "how to / guide / walkthrough..." |
| `essay` | Title chứa "thoughts on / reflections / perspective..." |
| `news` | Default fallback nếu không match content keyword |

Multi-label: 1 entry có cả type theo source + content keyword (vd `company-blog + release`).

### Trục 3: Language

- `en` — English (default)
- `vi` — Vietnamese (auto-detect by diacritic density)

### Trục 4: Importance

| Value | Ai gán | Khi nào |
|---|---|---|
| `must-read` | **Lam manual ★** | Lam click star button |
| `worth-reading` | Agent auto | Match keywords AI x product (claude code, agents, RAG, model release, API, eval, safety, prompt, open-source LLM) |
| `skim` | Agent auto (default) | Còn lại — academic theory thuần, infrastructure deep |

Filter Importance = `must-read` chỉ hiện entries Lam đã ★. Sort by importance đặt starred lên đầu.

---

## Lưu trữ Star (cross-device sync)

Click ★ trên card → 2 lớp lưu:
1. **localStorage** — instant render lần sau (không cần internet)
2. **`starred.json`** trong repo — server local POST `/api/star` → ghi file

Lam manual `git push` để sync sang máy khác / cloud routine. `starred.json`
là source of truth ổn định, localStorage chỉ là cache.

---

## Animations (subtle UX)

- Sidebar slide-in từ trái khi load
- Cards stagger fade-in (mỗi card delay 30ms)
- Card hover: lift 2px + indigo shadow tint
- Title hover: underline animation chạy trái → phải
- ★ click: pop bounce + pulse ring vàng
- Filter chip add: pop bounce in
- Show more click: card scale 1.015 + brand border + summary smooth reveal
- Loading state: shimmer indigo wave
- A11Y: tự disable với `prefers-reduced-motion: reduce`

---

## Setup routines (sau khi push GitHub)

1. **Tạo PAT GitHub** — Settings → Developer settings → Personal access tokens
   → Fine-grained → New token với scope:
   - Repository: `duylamle/ai-news` (single repo)
   - Permissions: Contents (read/write), Metadata (read)
2. **Push initial skeleton** lên GitHub (Lam làm 1 lần).
3. **Tạo 6 routines** qua Claude Code (3 routines/account × 2 accounts):
   - Cron: `0 0 * * *`, `0 7 * * *`, `0 12 * * *` (UTC = 07h/14h/19h SGT)
   - Model: Claude Haiku 4.5
   - Repo: `https://{PAT}@github.com/duylamle/ai-news`
   - Prompt: từ template trong plan, fill `{ACCOUNT}` + `{SLOT}`

---

## Maintenance

- **Thêm source mới:** edit `sources.json`, thêm vào `sources.{id}` + thêm
  `id` vào `schedule.{A|B}.{weekday}.{slot}` phù hợp. Hoặc chạy
  `python scripts/generate_schedule.py` auto-rebalance.
- **Pause source:** xóa `id` khỏi `schedule`, hoặc set `inactive: true` trong
  source meta. Source meta giữ lại để Lam có thể re-enable sau.
- **Đổi frequency:** chạy `python scripts/audit_frequency.py` xem PPW
  recommendations. Edit `frequency` trong `sources.json` rồi regen schedule.
- **Re-check inactive sources:** Lam định kỳ (~3 tháng) chạy audit, nếu
  source flagged `inactive` lại có bài mới → manually unflag + add lại schedule.
- **File phình to:** sau ~6 tháng, archive entries cũ hơn 90 ngày sang
  `archive/YYYY-QN.json`. Header sẽ link tới archive (v2).

---

## Troubleshooting

**Browser báo "manifest.json failed":**
→ Đang mở `file://`, cần dùng `start.bat` để chạy local server.

**Routine không chạy:**
→ Check claude.ai/code/routines panel. Thường lý do:
- PAT hết hạn → tạo PAT mới
- Quota cạn → run kế tiếp tự catch up qua git log
- GitHub repo deleted/renamed → fix URL trong routine config

**Entries trùng:**
→ Dedupe theo URL trong `state.json` + check `id` trong `entries-YYYY-MM.json`.
Race condition ở FE (loadMonth gọi song song) đã có defensive dedupe in-memory.
Nếu vẫn trùng → reset `state.json` về `{}` (sẽ dedupe lại từ data files).

**Search VN không work:**
→ Data agent cào về là English (hoặc VN với Goon Nguyễn). Khi routine cloud
chạy thật với Haiku, sẽ có `excerpt_vn` tiếng Việt → search VN sẽ work.
Hiện tại Lam dùng Google Translate widget trên header để dịch UI sang VN.

**Bài quá dài:**
→ Excerpt cap 1000 chars khi fetch. Click "Show more" để expand inline với
scrollbar (max-height 600px), card scale 1.015 với brand border.
