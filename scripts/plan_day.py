#!/usr/bin/env python3
"""Plan one day of Jury Juice posts.

Usage: python3 scripts/plan_day.py YYYY-MM-DD  > plan.json

Picks each post's type, format (carousel/single), style (tweet/photo) and a random
posting time for Facebook and Instagram. Week 1 follows state/week1.json. After that,
types and posting hours are chosen with a 70/30 explore-exploit mix based on the
engagement rates saved in state/history.json.
"""
import json, random, sys, datetime as dt
from collections import defaultdict
from pathlib import Path
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parent.parent
cfg = json.loads((ROOT / "state/config.json").read_text())
hist = json.loads((ROOT / "state/history.json").read_text())
week1 = json.loads((ROOT / "state/week1.json").read_text())
TZ = ZoneInfo(cfg["timezone"])
day = dt.date.fromisoformat(sys.argv[1])
rng = random.Random(f"jj-{day.isoformat()}")  # same plan if re-run the same day
EXPLORE = cfg["exploreShare"]
WINDOWS = cfg["windows"]
ORDER = ["morning", "afternoon", "evening"]


def rate(post, platform=None):
    """Engagement rate saved on a post, for one platform or averaged over both."""
    m = post.get("metrics") or {}
    vals = [m[p]["engagementRate"] for p in ([platform] if platform else ["facebook", "instagram"])
            if isinstance(m.get(p), dict) and isinstance(m[p].get("engagementRate"), (int, float))]
    return sum(vals) / len(vals) if vals else None


def weighted_pick(options, scores, min_n):
    """70% exploit (weighted by average score, needs min_n samples), 30% explore (uniform)."""
    measured = {o: s for o, s in scores.items() if o in options and len(s) >= min_n}
    if measured and rng.random() > EXPLORE:
        avg = {o: max(sum(s) / len(s), 1e-6) for o, s in measured.items()}
        total = sum(avg.values())
        r, acc = rng.random() * total, 0.0
        for o, a in avg.items():
            acc += a
            if r <= acc:
                return o, "exploit"
    return rng.choice(list(options)), "explore"


def pick_time(window, platform, avoid=None):
    lo, hi = WINDOWS[window]
    hours = list(range(lo, hi))
    hour_scores = defaultdict(list)
    for p in hist["posts"]:
        t = (p.get(platform) or {}).get("sentAt") or (p.get(platform) or {}).get("plannedAt")
        r = rate(p, platform)
        if t and r is not None:
            hour_scores[dt.datetime.fromisoformat(t).astimezone(TZ).hour].append(r)
    enough = sum(len(v) for v in hour_scores.values()) >= cfg["minPostsBeforeLearningTime"]
    for _ in range(50):
        if enough:
            h, _why = weighted_pick(hours, hour_scores, 2)
        else:
            h = rng.choice(hours)
        t = dt.datetime.combine(day, dt.time(h, rng.randrange(60)), TZ)
        if avoid is None or abs((t - avoid).total_seconds()) >= 10 * 60:
            return t
    return t


def plan_slots():
    key = day.isoformat()
    if key in week1["days"]:
        return [dict(s, why="week 1 plan") for s in week1["days"][key]]
    # Learned plan: score each type and each type+format+style combo by engagement.
    type_scores, combo_scores = defaultdict(list), defaultdict(list)
    for p in hist["posts"]:
        r = rate(p)
        if r is None:
            continue
        type_scores[p["type"]].append(r)
        combo_scores[(p["type"], p["format"], p["style"])].append(r)
    slots, used = [], defaultdict(int)
    for window in ORDER[: cfg["postsPerDay"]]:
        options = [t for t in cfg["formats"] if used[t] < 1]
        t, why = weighted_pick(options, type_scores, cfg["minPostsBeforeLearningType"])
        used[t] += 1
        combos = [tuple([t] + c) for c in cfg["formats"][t]]
        c, why2 = weighted_pick(combos, combo_scores, 3)
        slots.append({"window": window, "type": t, "format": c[1], "style": c[2], "topic": None,
                      "why": f"type {why}, format {why2}"})
    return slots


out = []
for s in plan_slots():
    fb = pick_time(s["window"], "facebook")
    ig = pick_time(s["window"], "instagram", avoid=fb)
    out.append(dict(s, facebookAt=fb.isoformat(), instagramAt=ig.isoformat()))
print(json.dumps({"date": day.isoformat(), "mode": cfg["mode"], "posts": out}, indent=2))
