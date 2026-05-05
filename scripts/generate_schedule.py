"""Generate balanced schedule for 2 accounts × 3 slots × 7 days based on
frequency tiers in sources.json. Outputs schedule object + readable table.

Frequency tiers:
  3 = high  → 3 fetches/week (Mon/Wed/Fri)
  2 = medium → 2 fetches/week
  1 = low   → 1 fetch/week
  "monthly" → 1 fetch every 4 weeks (handled at runtime, slot rotates)
  "quarterly" → 1 fetch every 12 weeks
  inactive: True → skipped

Distribution rules:
  - Account A: weekday focus (Mon-Fri)  — Lam reads during work
  - Account B: weekday focus + curated weekend reads
  - Same source NEVER scheduled in both accounts on same day
  - Slot 1/2/3 cap: max 3 sources per slot to avoid token blow
"""

import io
import json
import sys
from collections import defaultdict
from pathlib import Path

if sys.stdout.encoding and sys.stdout.encoding.lower() != "utf-8":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")

WEEKDAYS = ["mon", "tue", "wed", "thu", "fri", "sat", "sun"]
WORKDAYS = ["mon", "tue", "wed", "thu", "fri"]
WEEKEND = ["sat", "sun"]
SLOTS = ["slot1", "slot2", "slot3"]
ACCOUNTS = ["A", "B"]

# Slot capacity: max sources per slot per run
SLOT_CAP = 3


def freq_to_days(freq, preferred_days, account_idx, source_idx):
    """Pick which days of week this source should fetch.

    preferred_days hints, else use deterministic spread.
    Account A and B must NOT use same day if same source (enforced by alternating).
    """
    if freq == 3:
        # Mon/Wed/Fri pattern
        return ["mon", "wed", "fri"]
    if freq == 2:
        # Tue/Thu or Mon/Thu — alternate per source to spread load
        return ["mon", "thu"] if source_idx % 2 == 0 else ["tue", "fri"]
    if freq == 1:
        # 1 day/week — use preferred_days[0] if set, else rotate
        if preferred_days:
            return [preferred_days[0]]
        return [WEEKDAYS[source_idx % 7]]
    if freq == "monthly":
        # 1x/month → assign 1 weekend day, fetch only on week 1 of each month (handled in agent)
        return [preferred_days[0] if preferred_days else "sat"]
    if freq == "quarterly":
        # 1x/3-months → assign Sun, fetch only on first Sun of quarter
        return ["sun"]
    return []


def main():
    p = Path("sources.json")
    data = json.loads(p.read_text(encoding="utf-8"))
    sources = data["sources"]

    # Filter inactive
    active = {sid: meta for sid, meta in sources.items() if not meta.get("inactive")}

    # Group by bucket for balance
    by_bucket = defaultdict(list)
    for sid, meta in active.items():
        by_bucket[meta.get("bucket", "other")].append((sid, meta))

    # Init empty schedule
    schedule = {acc: {d: {s: [] for s in SLOTS} for d in WEEKDAYS} for acc in ACCOUNTS}

    # Round-robin assign sources, alternating accounts
    all_assignments = []  # list of (sid, meta, freq, days_to_assign)

    # Manually steer: high-volume = A morning, business = A evening, research = B
    # But auto distribute with backpressure
    sources_sorted = sorted(active.items(), key=lambda x: (-1 if x[1].get("frequency") == 3 else 0, x[0]))

    source_idx = 0
    for sid, meta in sources_sorted:
        freq = meta.get("frequency", 1)
        if freq == 0 or meta.get("inactive"):
            continue
        preferred = meta.get("preferred_days", [])
        days = freq_to_days(freq, preferred, source_idx, source_idx)

        # Pick account based on bucket (creator vs observer)
        bucket = meta.get("bucket", "other")
        if bucket in ("lab-official", "engineering", "business", "harness", "vietnam"):
            account_pref = "A"
        else:
            account_pref = "B"

        for day in days:
            # Find slot with least load in preferred account first
            best_slot = None
            best_acc = None
            best_load = 99
            for acc_try in [account_pref, "B" if account_pref == "A" else "A"]:
                for slot in SLOTS:
                    # Skip if same source already on this day (other account)
                    if any(sid in schedule[a][day][s] for a in ACCOUNTS for s in SLOTS):
                        continue
                    load = len(schedule[acc_try][day][slot])
                    if load < SLOT_CAP and load < best_load:
                        best_load = load
                        best_slot = slot
                        best_acc = acc_try
                if best_slot:
                    break
            if best_slot:
                schedule[best_acc][day][best_slot].append(sid)

        source_idx += 1

    data["schedule"] = schedule
    p.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")

    # Print readable table
    print()
    print("=" * 100)
    print("SCHEDULE — Account A (weekday focus)")
    print("=" * 100)
    print(f"{'DAY':<5} {'SLOT1 (07h SGT)':<33} {'SLOT2 (14h SGT)':<33} {'SLOT3 (19h SGT)':<33}")
    print("-" * 100)
    for day in WEEKDAYS:
        s1 = ", ".join(schedule["A"][day]["slot1"])[:32]
        s2 = ", ".join(schedule["A"][day]["slot2"])[:32]
        s3 = ", ".join(schedule["A"][day]["slot3"])[:32]
        print(f"{day:<5} {s1:<33} {s2:<33} {s3:<33}")

    print()
    print("=" * 100)
    print("SCHEDULE — Account B (weekend deep-read)")
    print("=" * 100)
    print(f"{'DAY':<5} {'SLOT1 (07h SGT)':<33} {'SLOT2 (14h SGT)':<33} {'SLOT3 (19h SGT)':<33}")
    print("-" * 100)
    for day in WEEKDAYS:
        s1 = ", ".join(schedule["B"][day]["slot1"])[:32]
        s2 = ", ".join(schedule["B"][day]["slot2"])[:32]
        s3 = ", ".join(schedule["B"][day]["slot3"])[:32]
        print(f"{day:<5} {s1:<33} {s2:<33} {s3:<33}")

    # Stats summary
    print()
    total_jobs = sum(len(schedule[a][d][s]) for a in ACCOUNTS for d in WEEKDAYS for s in SLOTS)
    print(f"Total fetch jobs/week: {total_jobs}")
    print(f"Active sources: {len(active)}/{len(sources)}")
    inactive = [sid for sid, m in sources.items() if m.get("inactive")]
    if inactive:
        print(f"Inactive: {inactive}")


if __name__ == "__main__":
    main()
