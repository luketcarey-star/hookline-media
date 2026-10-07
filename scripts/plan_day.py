#!/usr/bin/env python3
"""Plan one run of Jury Juice posts.

Usage: python3 scripts/plan_day.py YYYY-MM-DD am|pm [jury|oldcrow]  > plan.json
(page defaults to jury; oldcrow reads state/oldcrow/config.json and history.json)

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
PAGE = sys.argv[3] if len(sys.argv) > 3 else "jury"
SD = ROOT / "state" if PAGE == "jury" else ROOT / "state" / PAGE
cfg = json.loads((SD / "config.json").read_text())
hist = json.loads((SD / "history.json").read_text())
week1 = json.loads((SD / "week1.json").read_text()) if (SD / "week1.json").exists() else {"days": {}}
TZ = ZoneInfo(cfg["timezone"])
day = dt.date.fromisoformat(sys.argv[1])
run = sys.argv[2] if len(sys.argv) > 2 else ("am" if dt.datetime.now(TZ).hour < 12 else "pm")
rng = random.Random(f"{PAGE}-{day.isoformat()}-{run}")  # same plan if re-run
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
        cap = cfg.get("maxCarouselsPerDay")
        carousels = sum(1 for p in today_posts if p.get("format") == "carousel") + sum(1 for x in slots if x["format"] == "carousel")
        allowed = [t for t in cfg["formats"] if not (cap is not None and carousels >= cap and all(c[0] == "carousel" for c in cfg["formats"][t]))]
        caps = cfg.get("maxPerDay", {})
        allowed = [t for t in allowed if used[t] < caps.get(t, 99)] or allowed
        options = [t for t in allowed if used[t] < 1] or [t for t in allowed if used[t] < 2] or allowed
        t, why = weighted_pick(options, type_scores, cfg["minPostsBeforeLearningType"])
        used[t] += 1
        combos = [tuple([t] + c) for c in cfg["formats"][t]
                  if not (cap is not None and carousels >= cap and c[0] == "carousel")] or [tuple([t] + c) for c in cfg["formats"][t]]
        c, why2 = weighted_pick(combos, combo_scores, 3)
        slots.append({"window": window, "type": t, "format": c[1], "style": c[2], "topic": None,
                      "why": f"type {why}, format {why2}"})
    return slots


n = max(0, min(cfg["postsPerRun"], cfg["postsPerDay"] - len(today_posts)))

# Buffer's free plan holds at most 10 scheduled posts across ALL pages. Count what both bots
# have queued for the future and only plan as many posts as still fit.
BUFFER_LIMIT = 10
queued = 0
for hp in (ROOT / "state" / "history.json", ROOT / "state" / "oldcrow" / "history.json"):
    if not hp.exists():
        continue
    for p in json.loads(hp.read_text())["posts"]:
        if p.get("status") not in ("scheduled", "queued"):
            continue
        for pl in ("facebook", "instagram"):
            t = (p.get(pl) or {}).get("plannedAt")
            if t and (p.get(pl) or {}).get("postId") and dt.datetime.fromisoformat(t) > now:
                queued += 1
per_post = len(cfg.get("platforms", ["facebook", "instagram"]))
room = max(0, (BUFFER_LIMIT - queued) // per_post)
limited_by_buffer = room < n
n = min(n, room)


def enforce_carousel_caps(slots):
    """Carousels do badly on Facebook: keep them rare. Swap any carousel over the daily or weekly cap
    for a single-image version of the same type, or else for a single-image type."""
    day_cap = cfg.get("maxCarouselsPerDay", 1)
    week_cap = cfg.get("maxCarouselsPerWeek", 99)
    week_start = (day - dt.timedelta(days=6)).isoformat()
    in_day = sum(1 for p in today_posts if p.get("format") == "carousel")
    in_week = sum(1 for p in hist["posts"] if p.get("format") == "carousel" and week_start <= p.get("date", "") <= day.isoformat())
    out = []
    for sl in slots:
        if sl["format"] == "carousel" and (in_day >= day_cap or in_week >= week_cap):
            singles = [c for c in cfg["formats"].get(sl["type"], []) if c[0] == "single"]
            if singles:
                c = rng.choice(singles)
                sl = dict(sl, format="single", style=c[1], why=sl.get("why", "") + "; carousel cap -> single")
            else:
                used_types = {x["type"] for x in out} | {x["type"] for x in slots} | {p["type"] for p in today_posts}
                opts = [t for t, cs in cfg["formats"].items() if any(c[0] == "single" for c in cs)]
                t = rng.choice([t for t in opts if t not in used_types] or opts)
                c = rng.choice([c for c in cfg["formats"][t] if c[0] == "single"])
                sl = dict(sl, type=t, format="single", style=c[1], topic=None, why=sl.get("why", "") + f"; carousel cap -> {t}")
        if sl["format"] == "carousel":
            in_day += 1; in_week += 1
        out.append(sl)
    return out

taken = {pl: taken_times(pl) for pl in ("facebook", "instagram")}
out = []
# Tweet posts rotate backgrounds: black -> white (light) -> classic Twitter navy (dim) -> black...
THEMES = ["black", "light", "dim"]
last_theme = next((p["theme"] for p in reversed(hist["posts"]) if p.get("style") == "tweet" and p.get("theme") in THEMES), "dim")
for s in enforce_carousel_caps(plan_slots(n)):
    fb = pick_time(s["window"], "facebook", taken["facebook"])
    ig = pick_time(s["window"], "instagram", taken["instagram"] + ([fb] if fb else []))
    if not fb or not ig:
        continue  # window already over
    taken["facebook"].append(fb); taken["instagram"].append(ig)
    if s.get("style") == "tweet":
        last_theme = THEMES[(THEMES.index(last_theme) + 1) % 3]
        s = dict(s, theme=last_theme)
    out.append(dict(s, facebookAt=fb.isoformat(), instagramAt=ig.isoformat() if "instagram" in cfg.get("platforms", ["facebook", "instagram"]) else None))
print(json.dumps({"page": PAGE, "date": day.isoformat(), "run": run, "bufferQueued": queued,
                  "limitedByBuffer": limited_by_buffer, "mode": cfg["mode"],
                  "alreadyToday": len(today_posts), "posts": out}, indent=2))
