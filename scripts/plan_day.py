#!/usr/bin/env python3
"""Plan one run of Jury Juice posts.

Usage: python3 scripts/plan_day.py YYYY-MM-DD am|pm  > plan.json

The bot runs twice a day. Each run makes up to `postsPerRun` posts in its own time
windows (am run: 8:00 to 14:30, pm run: 15:30 to 22:30), never more than
`postsPerDay` for the whole day (posts already in history for that date count).

For each post it picks the type, format (carousel/single), style (tweet/photo) and a
random posting time for Facebook and Instagram. The am run follows state/week1.json while
that plan has entries for the date. Otherwise types and posting hours are chosen with a
70/30 exploit-explore mix based on the engagement rates saved in state/history.json.
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
run = sys.argv[2] if len(sys.argv) > 2 else ("am" if dt.datetime.now(TZ).hour < 12 else "pm")
rng = random.Random(f"jj-{day.isoformat()}-{run}")  # same plan if re-run
EXPLORE = cfg["exploreShare"]
WINDOWS = cfg["runs"][run]["windows"]          # {name: ["HH:MM", "HH:MM"]}
now = dt.datetime.now(TZ)
today_posts = [p for p in hist["posts"] if p.get("date") == day.isoformat()]


def at(hhmm):
    h, m = map(int, hhmm.split(":"))
    return dt.datetime.combine(day, dt.time(h, m), TZ)


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


def taken_times(platform):
    out = []
    for p in today_posts:
        t = (p.get(platform) or {}).get("sentAt") or (p.get(platform) or {}).get("plannedAt")
        if t:
            out.append(dt.datetime.fromisoformat(t).astimezone(TZ))
    return out


hour_scores = {pl: defaultdict(list) for pl in ("facebook", "instagram")}
for p in hist["posts"]:
    for pl in hour_scores:
        t = (p.get(pl) or {}).get("sentAt") or (p.get(pl) or {}).get("plannedAt")
        r = rate(p, pl)
        if t and r is not None:
            hour_scores[pl][dt.datetime.fromisoformat(t).astimezone(TZ).hour].append(r)


def pick_time(window, platform, taken):
    lo, hi = at(WINDOWS[window][0]), at(WINDOWS[window][1])
    lo = max(lo, now + dt.timedelta(minutes=20))
    if lo >= hi:
        return None
    hours = sorted({(lo + dt.timedelta(minutes=k)).hour for k in range(0, int((hi - lo).total_seconds() // 60))})
    enough = sum(len(v) for v in hour_scores[platform].values()) >= cfg["minPostsBeforeLearningTime"]
    t = None
    for _ in range(80):
        if enough:
            h, _ = weighted_pick(hours, hour_scores[platform], 2)
            start = max(lo, dt.datetime.combine(day, dt.time(h, 0), TZ))
            end = min(hi, start.replace(minute=0) + dt.timedelta(hours=1))
        else:
            start, end = lo, hi
        span = int((end - start).total_seconds() // 60)
        if span <= 0:
            continue
        t = start + dt.timedelta(minutes=rng.randrange(span))
        if all(abs((t - x).total_seconds()) >= 30 * 60 for x in taken):
            return t
    return t


def plan_slots(n):
    names = list(WINDOWS)[:n]
    key = day.isoformat()
    if run == "am" and key in week1["days"] and not today_posts:
        return [dict(s, window=names[i], why="week 1 plan") for i, s in enumerate(week1["days"][key][:n])]
    # Learned plan: score each type and each type+format+style combo by engagement.
    type_scores, combo_scores = defaultdict(list), defaultdict(list)
    for p in hist["posts"]:
        r = rate(p)
        if r is None:
            continue
        type_scores[p["type"]].append(r)
        combo_scores[(p["type"], p["format"], p["style"])].append(r)
    used = defaultdict(int)
    for p in today_posts:
        used[p["type"]] += 1
    slots = []
    for window in names:
        options = [t for t in cfg["formats"] if used[t] < 1] or [t for t in cfg["formats"] if used[t] < 2]
        t, why = weighted_pick(options, type_scores, cfg["minPostsBeforeLearningType"])
        used[t] += 1
        combos = [tuple([t] + c) for c in cfg["formats"][t]]
        c, why2 = weighted_pick(combos, combo_scores, 3)
        slots.append({"window": window, "type": t, "format": c[1], "style": c[2], "topic": None,
                      "why": f"type {why}, format {why2}"})
    return slots


n = max(0, min(cfg["postsPerRun"], cfg["postsPerDay"] - len(today_posts)))
taken = {pl: taken_times(pl) for pl in ("facebook", "instagram")}
out = []
for s in plan_slots(n):
    fb = pick_time(s["window"], "facebook", taken["facebook"])
    ig = pick_time(s["window"], "instagram", taken["instagram"] + ([fb] if fb else []))
    if not fb or not ig:
        continue  # window already over
    taken["facebook"].append(fb); taken["instagram"].append(ig)
    out.append(dict(s, facebookAt=fb.isoformat(), instagramAt=ig.isoformat()))
print(json.dumps({"date": day.isoformat(), "run": run, "mode": cfg["mode"],
                  "alreadyToday": len(today_posts), "posts": out}, indent=2))
