---
type: artifact
scope: ai-news
created: 2026-05-07
updated: 2026-05-07
---

# Setup 3 Routines cho Account B

> Khi Lam switch sang account B, paste cho Claude session mới: "Setup 3 routines AI news Account B" — Claude sẽ dùng RemoteTrigger tạo. Hoặc Lam tự tạo qua web UI claude.ai/code/routines.

## Common config (3 routines)

- **Repo**: `https://github.com/duylamle/ai-news`
- **Model**: `claude-haiku-4-5-20251001`
- **Allowed tools**: `Bash, Read, Write, Edit, Glob, Grep`

## Routine 1: `ai-news-B-slot1`

- **Cron**: `0 0 * * *` (07h SGT / 00h UTC)

## Routine 2: `ai-news-B-slot2`

- **Cron**: `0 7 * * *` (14h SGT / 07h UTC)

## Routine 3: `ai-news-B-slot3`

- **Cron**: `0 12 * * *` (19h SGT / 12h UTC)

## Prompt template

Paste vào "Instructions" của mỗi routine, **thay `SLOT_NAME`** thành `slot1` / `slot2` / `slot3` (xuất hiện 3 chỗ: line 5, line 8 commit message, line 10 empty commit message):

```
You are AI news ingestion routine for account B, SLOT_NAME.

Repo: duylamle/ai-news. PAT: [PASTE_YOUR_PAT_HERE]

## Steps

1. sleep $((30 + RANDOM % 60))  # avoid push collision with account A
2. git remote set-url origin https://x-access-token:${PAT}@github.com/duylamle/ai-news
   git config user.email "routine@anthropic.local"; git config user.name "AI News Routine B"
   git pull --rebase origin main
3. pip install -q feedparser requests beautifulsoup4 2>/dev/null || true
4. WEEKDAY=$(date -u +%a | tr 'A-Z' 'a-z')
5. SOURCE_IDS=$(jq -r ".schedule.B.${WEEKDAY}.SLOT_NAME[]" sources.json)
6. python scripts/run_local.py --sources-list $SOURCE_IDS
7. python -c "
import json
from pathlib import Path
vn = 'àáảãạăằắẳẵặâầấẩẫậèéẻẽẹêềếểễệìíỉĩịòóỏõọôồốổỗộơờớởỡợùúủũụưừứửữựỳýỷỹỵđ'
for f in sorted(Path('data').glob('entries-*.jsonl')):
    entries = []
    with f.open(encoding='utf-8') as fh:
        for line in fh:
            line = line.strip()
            if line: entries.append(json.loads(line))
    changed = False
    for e in entries:
        if 'language' not in e:
            text = e.get('title','') + ' ' + e.get('excerpt','')
            cnt = sum(1 for c in text if c in vn or c in vn.upper())
            e['language'] = 'vi' if cnt / max(len(text), 1) > 0.02 else 'en'
            changed = True
        if not e.get('excerpt_vn'):
            e['excerpt_vn'] = e.get('excerpt', '')
            changed = True
    if changed:
        with f.open('w', encoding='utf-8') as fh:
            for e in entries: fh.write(json.dumps(e, ensure_ascii=False) + '\n')
"
8. git add data/ state.json
   if [ -n "$(git diff --cached --name-only)" ]; then
     git commit -m "feed: B-SLOT_NAME $(date -u +%Y-%m-%d)"
   else
     git commit --allow-empty -m "feed: B-SLOT_NAME $(date -u +%Y-%m-%d) 0 entries"
   fi
   git pull --rebase origin main; git push origin main

Constraints: không invent articles. Source fail → skip không crash. Push reject → retry 1 lần. Mục tiêu chính kick session, news bonus.
```

## Pre-requisites (Lam check trước khi tạo)

1. Account B đã **authorize GitHub OAuth với Anthropic Claude Code** (similar account A)
   - Vào https://claude.ai/settings → Integrations → GitHub → connect/authorize
   - Grant access cho `duylamle/ai-news`

2. Repo `duylamle/ai-news` đã **public** (đã làm rồi cho account A)

## Verify sau khi tạo

```bash
# Check routines list
gh api /v1/code/triggers  # Hoặc xem tại https://claude.ai/code/routines
```

3 routines B mới phải có status **Enabled**, không phải `auto_disabled_repo_access`.

## Run thử

Sau tạo xong → click **"Run now"** trên routine B-slot1 để verify. Hoặc đợi cron 07h SGT mai.

Sau ~3 phút check git log:
```bash
cd "G:\My Drive\My 2nd Brain\knowledge\personal-branding\projects\ai-news"
git pull
git log origin/main --oneline -5
```

→ Sẽ thấy commit `feed: B-slot1 ...`.
