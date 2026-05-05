---
type: artifact
scope: ai-news
created: 2026-05-06
updated: 2026-05-06
---

# AI News — Project Context for Claude

> Folder này là **project AI News Aggregator** của Lam — auto cào AI news từ
> ~60 nguồn về local feed, render qua FE blog có filter + animations.
>
> Khi Claude quay lại session sau, đọc file này để có context nhanh, không
> cần re-explore.

---

## Vai trò folder

- **Local working copy** của repo GitHub `duylamle/ai-news` (private)
- Lam pull về đây → mở `start.bat` → xem feed local qua browser
- Routines cloud (Claude Code) push lên GitHub → Lam pull về update local

---

## Quick reference

| Task | File / Command |
|---|---|
| Xem feed local | Double-click `start.bat` → `localhost:8765` |
| Add source mới | Edit `sources.json`, chạy `python scripts/generate_schedule.py` |
| Audit frequency | `python scripts/audit_frequency.py` |
| Test pipeline | `python scripts/run_local.py --sources-list <id> [<id>...]` |
| Reset state | `echo "{}" > state.json && rm data/entries-*.jsonl` |

---

## Architecture (TL;DR)

```
Cloud routine (Claude Haiku 4.5)
  → git clone duylamle/ai-news
  → đọc sources.json schedule cho (account, weekday, slot)
  → fetch sources qua scripts/fetch.py
  → classify qua scripts/classify.py (rule-based)
  → append qua scripts/append.py vào data/entries-YYYY-MM.jsonl
  → git commit + push

Local (Lam)
  → git pull
  → start.bat → python scripts/server.py (port 8765)
  → browser load index.html → fetch manifest.json + entries-*.jsonl
  → render masonry feed với 4 filters + search + sort + star
```

---

## Design decisions đã chốt

1. **Storage = JSONL không phải JSON** (mỗi entry 1 line)
   - Append rẻ (không re-parse cả file)
   - Git diff sạch (1 entry mới = 1 line diff)
   - `merge=union` work hoàn hảo cho concurrency 2-account push
   - Tolerant: 1 line corrupt không bể cả file

2. **Translation = Google Translate widget FE** (không Haiku translate)
   - Routine cào EN raw, không dịch trong agent → tiết kiệm token
   - Lam click dropdown trên header → toàn page dịch VN
   - Search VN không work với data EN — Lam search EN keywords

3. **Star = manual only** (Lam click ★)
   - Agent KHÔNG bao giờ gán `must-read`
   - 2 lớp lưu: `localStorage` (instant) + `starred.json` (git sync)
   - Server `/api/star` POST endpoint để ghi file

4. **Frequency tiers expand**
   - `3` (high), `2` (medium), `1` (low), `monthly`, `quarterly`
   - Auto-drop sau N consecutive empty fetches (1 năm silence)

5. **Filter: 4 trục only** (đã bỏ Topic, Audience, Relevance vì noise)
   - Source / Type / Language / Importance
   - Plus: Search box, Date range, Sort, Expand-all toggle

6. **Layout: sidebar trái** (280px) + content masonry 3-cột phải
   - Click "Show more" → card scale 1.015 + indigo border (cam reserved cho ★)

---

## Sources pool (`sources.json`)

~60 nguồn chia 8 buckets. Schedule weekly trong `sources.json.schedule.{A|B}.{weekday}.{slot}`.

**Đã DROP** (DEAD/Medium/inaccessible):
- Chip Huyen, Lilian Weng, Stanford SAIL (DEAD >180d)
- Towards Data Science, Towards AI, Cassie Kozyrkov (Medium paywall)
- TOPBOTS, Distill, AI Trends (DEAD)

**Buckets:** lab-official, academic, engineering, harness, commentary,
business, safety, vietnam.

---

## Scripts (`scripts/`)

| File | Mục đích |
|---|---|
| `fetch.py` | Parse RSS / scrape meta tag, output JSON entries; track consecutive_empty |
| `classify.py` | Rule-based: source_org, types (multi-label), language, importance, tags |
| `append.py` | Read JSONL → dedup by id+url → write back sorted newest-first → update manifest |
| `audit_frequency.py` | Đo posts-per-week 60d → recommend frequency tier |
| `generate_schedule.py` | Auto-balance schedule cho 2 accounts × 7 days × 3 slots |
| `server.py` | Local HTTP server với `/api/star` endpoint |
| `run_local.py` | E2E pipeline test (fetch → classify → append) |

---

## Data files

| File | Format | Purpose |
|---|---|---|
| `data/manifest.json` | JSON | total entries, months list, sources index |
| `data/entries-YYYY-MM.jsonl` | JSONL | 1 entry/line, 1 file/month |
| `state.json` | JSON | per-source: seen_urls, last_fetched, consecutive_empty, inactive flag |
| `starred.json` | JSON | `{starred: {entry_id: timestamp}}` — Lam ★ |
| `sources.json` | JSON | sources pool + schedule + frequency tiers |

---

## Goals reminder

1. **Mục tiêu chính:** Đảm bảo session active mỗi ~5h cho 2 Claude accounts
   (kick-start session window). Routine ping = required.

2. **Mục tiêu phụ:** Tận dụng routine cào AI news. Nếu phần này fail không
   được crash routine — kick session vẫn phải thành công.

---

## Khi Claude làm việc trên folder này

**Đọc tài liệu trước:**
- `README.md` — user-facing docs
- `design.md` — design direction (Mintlify + Pinterest masonry, VNG orange)
- File này — context kỹ thuật

**Convention:**
- Không edit files mà không hỏi Lam (trừ khi đã agreed scope)
- Sau mỗi thay đổi script → suggest test trước khi push
- Sau mỗi thay đổi UI → suggest Lam refresh `Ctrl+Shift+R` để bypass cache
- Bug fix → ưu tiên defensive coding (dedupe at insertion, guard race conditions)

**Trên cloud routine context:**
- Agent là Claude Haiku 4.5
- Token cost target: ~3.2K equivalent quota / run (trên Max 5x: ~1.5% session window)
- Pipeline tier 1 default cho 90% bài, tier 2 escalate cho 1-2 lab-official articles
- Catch-up missed runs qua `git log` (không cần debt.json — agent hết quota thì không ghi được)

**File system layout warning:**
- Folder này nằm trên Google Drive (`G:\My Drive\My 2nd Brain\...`)
- Có khả năng file 0-bytes hoặc lock khi Drive sync chậm
- Scripts cần handle empty/corrupt file (`load_jsonl` đã tolerant)
