"""Builds the "Mana diena" dashboard snapshot from dumped tool data.
usage: python3 build_snapshot.py <dump_dir> <manga_repo_dir> <econ_repo_dir> <out.json>
<dump_dir> holds ArtifactData out_dir dumps:
  hub/projekti/*.json, paper/paper/main.json, planner/planner/main.json, planner/done/*.json,
  budget/config/main.json, budget/months/*.json, backlog/items/*.json,
  price/items/*.json, brief/briefs/*.json, brief/listings/*.json
Missing folders are fine (that section becomes null)."""
import json, sys, glob, os, datetime as dt
from zoneinfo import ZoneInfo

DUMP, MANGA, ECON, OUT = sys.argv[1:5]
TZ = ZoneInfo("Europe/Riga")
NOW = dt.datetime.now(TZ)
TODAY = NOW.date()

def load(path):
    try:
        d = json.load(open(path, encoding="utf-8"))
        return d.get("data", d) if isinstance(d, dict) and "data" in d and "id" in d else d
    except Exception:
        return None

def docs(pattern):
    out = []
    for f in sorted(glob.glob(os.path.join(DUMP, pattern))):
        d = load(f)
        if isinstance(d, dict):
            d.setdefault("_id", os.path.splitext(os.path.basename(f))[0])
            out.append(d)
    return out

def pdate(s):
    try: return dt.date.fromisoformat(str(s)[:10])
    except Exception: return None

snap = {"generatedAt": NOW.isoformat(timespec="seconds")}

# ---- hub (all projects, for the link grid)
hub = []
for d in docs("hub/projekti/*.json"):
    hub.append({"id": d["_id"], "name": d.get("nosaukums"), "desc": d.get("apraksts"), "url": d.get("url"),
                "tags": d.get("birkas") or [], "kind": d.get("veids"), "order": d.get("seciba", 99)})
snap["hub"] = sorted(hub, key=lambda x: (x["order"] or 99, x["name"] or "")) or None

# ---- term paper
p = load(os.path.join(DUMP, "paper/paper/main.json"))
if isinstance(p, dict):
    ms = p.get("milestones") or []
    nxt = [m for m in ms if not m.get("done")]
    nxt.sort(key=lambda m: m.get("date") or "9999")
    secs = p.get("sections") or []
    tasks = [t for s in secs for t in (s.get("tasks") or [])]
    checks = p.get("checks") or []
    log = sorted(p.get("log") or [], key=lambda l: l.get("date") or "")
    srcs = p.get("sources") or []
    snap["paper"] = {
        "title": p.get("workingTitle") or "", "deadline": p.get("deadline"), "defenceFrom": p.get("defenceFrom"), "defenceTo": p.get("defenceTo"),
        "milestones": [{"text": m.get("text"), "date": m.get("date")} for m in nxt[:4]],
        "milestonesDone": sum(1 for m in ms if m.get("done")), "milestonesTotal": len(ms),
        "tasksDone": sum(1 for t in tasks if t.get("done")), "tasksTotal": len(tasks),
        "pages": sum((s.get("pages") or 0) for s in secs), "pagesMin": p.get("pagesMin"), "pagesMax": p.get("pagesMax"),
        "sources": len(srcs), "sourcesRead": sum(1 for s in srcs if s.get("status") in ("read", "used", "done")),
        "next": (log[-1].get("next") if log else "") or "", "lastMeeting": log[-1].get("date") if log else None,
    }
else:
    snap["paper"] = None

# ---- planner
pm = load(os.path.join(DUMP, "planner/planner/main.json"))
if isinstance(pm, dict) and pm.get("tasks"):
    tasks = [t for t in pm["tasks"] if t.get("title")]
    def tinfo(t): return {"title": t.get("title"), "due": t.get("due") or "", "time": t.get("time") or "", "tag": t.get("tag") or "", "prio": bool(t.get("prio"))}
    over, today, soon, nodate = [], [], [], []
    for t in tasks:
        sf = pdate(t.get("showFrom"))
        if sf and sf > TODAY: continue
        d = pdate(t.get("due"))
        if d is None: nodate.append(t)
        elif d < TODAY: over.append(t)
        elif d == TODAY: today.append(t)
        elif (d - TODAY).days <= 7: soon.append(t)
    key = lambda t: (t.get("due") or "9999", t.get("time") or "99")
    goals = [g for g in (pm.get("goals") or []) if not g.get("done")]
    snap["planner"] = {"overdue": [tinfo(t) for t in sorted(over, key=key)][:8], "today": [tinfo(t) for t in sorted(today, key=key)][:10],
                       "week": [tinfo(t) for t in sorted(soon, key=key)][:10], "prioNoDate": [tinfo(t) for t in nodate if t.get("prio")][:5],
                       "goals": [{"title": g.get("title") or g.get("name"), "kind": g.get("kind")} for g in goals][:5]}
else:
    snap["planner"] = None

# ---- budget (this month)
cfg = load(os.path.join(DUMP, "budget/config/main.json"))
months = {d["_id"]: d.get("items") or [] for d in docs("budget/months/*.json")}
mk = TODAY.strftime("%Y-%m")
if months or (isinstance(cfg, dict) and cfg.get("subs")):
    cats = {c.get("id"): c.get("name") or c.get("lv") or c.get("id") for c in ((cfg or {}).get("cats") or [])}
    items = months.get(mk, [])
    exp = [e for e in items if e.get("kind") == "expense"]
    inc = [e for e in items if e.get("kind") == "income"]
    bycat = {}
    for e in exp: bycat[e.get("cat")] = bycat.get(e.get("cat"), 0) + float(e.get("amount") or 0)
    prev_key = (TODAY.replace(day=1) - dt.timedelta(days=1)).strftime("%Y-%m")
    prev_exp_same_day = sum(float(e.get("amount") or 0) for e in months.get(prev_key, []) if e.get("kind") == "expense" and (pdate(e.get("date")) or TODAY).day <= TODAY.day)
    subs = []
    for s in ((cfg or {}).get("subs") or []):
        n = pdate(s.get("next"))
        if s.get("active", True) and n and 0 <= (n - TODAY).days <= 14:
            subs.append({"name": s.get("name"), "amount": s.get("amount"), "next": s.get("next")})
    snap["budget"] = {"month": mk, "spent": round(sum(float(e.get("amount") or 0) for e in exp), 2), "income": round(sum(float(e.get("amount") or 0) for e in inc), 2),
                      "prevSameDay": round(prev_exp_same_day, 2), "count": len(items),
                      "topCats": [{"name": cats.get(k, k), "amount": round(v, 2)} for k, v in sorted(bycat.items(), key=lambda kv: -kv[1])[:4]],
                      "subsSoon": sorted(subs, key=lambda s: s["next"])}
else:
    snap["budget"] = None

# ---- backlog (What next?)
bl = []
for d in docs("backlog/items/*.json"):
    if d.get("statuss") in ("pabeigts", "atmests", "done", "dropped"): continue
    info = d.get("info") or {}
    bl.append({"name": d.get("nosaukums"), "type": d.get("tips"), "status": d.get("statuss"), "prio": d.get("prioritate"),
               "minutes": d.get("sesija_min"), "moods": d.get("noskanas") or [], "where": d.get("kur") or info.get("kur") or "",
               "progress": d.get("progress") or "", "why": (info.get("kapec") or "")[:160]})
snap["backlog"] = bl or None

# ---- Price Watch
pw = []
for d in docs("price/items/*.json"):
    if d.get("archived"): continue
    best = None
    if d.get("mode") == "browse":
        ps = [p.get("best") for p in (d.get("products") or []) if p.get("best") and p["best"].get("totalEUR") is not None]
        ps = [o for o in ps if (o.get("trust") or 3) >= 3] or ps
        if ps: best = min(ps, key=lambda o: o["totalEUR"])
    else:
        os_ = [o for o in (d.get("offers") or []) if o.get("totalEUR") is not None and o.get("inStock") is not False]
        safe = [o for o in os_ if (o.get("trust") or 3) >= 3]
        if safe or os_: best = min(safe or os_, key=lambda o: o["totalEUR"])
    pw.append({"name": d.get("name"), "mode": d.get("mode") or "specific", "status": d.get("status"), "checkedAt": d.get("checkedAt"), "target": d.get("target"),
               "best": round(best["totalEUR"], 2) if best else None, "store": best.get("store") if best else None, "url": best.get("url") if best else None,
               "options": len(d.get("products") or []) if d.get("mode") == "browse" else len(d.get("offers") or [])})
snap["price"] = pw or None

# ---- Daily Brief
briefs = docs("brief/briefs/*.json")
if briefs:
    latest = max(b.get("date") or "" for b in briefs)
    regions = {}
    for b in briefs:
        if b.get("date") != latest: continue
        st = b.get("stories") or []
        rank = {"top": 0, "notable": 1, "brief": 2}
        st = sorted(st, key=lambda s: rank.get(s.get("importance"), 1))
        regions[b.get("region")] = {"sixty": (b.get("sixty") or [])[:4], "top": [{"h": s.get("headline"), "url": ((s.get("sources") or [{}])[0] or {}).get("url")} for s in st[:3]],
                                    "count": len(st), "generatedAt": b.get("generatedAt"), "periodFrom": b.get("periodFrom")}
    snap["brief"] = {"date": latest, "regions": regions}
else:
    snap["brief"] = None
lst = {d["_id"]: d for d in docs("brief/listings/*.json")}
ev = []
for e in (lst.get("events", {}).get("items") or []):
    s, en = pdate(e.get("start")), pdate(e.get("end")) or pdate(e.get("start"))
    if not s or en < TODAY or (s - TODAY).days > 10: continue
    ev.append({"name": e.get("name"), "start": e.get("start"), "end": e.get("end"), "time": e.get("time"), "city": e.get("city"), "venue": e.get("venue"),
               "price": e.get("price"), "url": e.get("url"), "like": bool(e.get("mightLike")), "cat": e.get("category"), "scope": e.get("scope")})
ev.sort(key=lambda e: (not e["like"], e["start"]))
snap["events"] = ev[:10] or None
cp = []
for c in (lst.get("competitions", {}).get("items") or []):
    d = pdate(c.get("deadline"))
    if not d or d < TODAY or (d - TODAY).days > 21: continue
    cp.append({"name": c.get("name"), "deadline": c.get("deadline"), "prize": c.get("prize"), "url": c.get("url"), "like": bool(c.get("mightLike")), "type": c.get("type")})
snap["comps"] = sorted(cp, key=lambda c: c["deadline"])[:8] or None

# ---- Next Chapter (recent releases from the tracker's repo)
try:
    lib = {s["id"]: s for s in json.load(open(os.path.join(MANGA, "docs/data/library.json"), encoding="utf-8"))["series"]}
    rel = json.load(open(os.path.join(MANGA, "docs/data/releases.json"), encoding="utf-8"))
    recent = []
    for sid, r in (rel.get("series") or {}).items():
        if not r.get("date") or sid not in lib: continue
        try: when = dt.datetime.fromisoformat(r["date"].replace("Z", "+00:00"))
        except Exception: continue
        if (NOW - when).total_seconds() > 72 * 3600: continue
        s = lib[sid]
        start = s.get("start") or 0
        recent.append({"title": s.get("title"), "chapter": r.get("chapter") or r.get("latest"), "date": r["date"], "url": r.get("url") if r.get("exact") else None,
                       "keepingUp": (r.get("latest") or 0) - start <= 15, "notStarted": start <= 0})
    recent.sort(key=lambda x: (not x["keepingUp"], x["date"]), reverse=False)
    recent.sort(key=lambda x: x["date"], reverse=True)
    snap["manga"] = {"checked": rel.get("checked"), "recent": [x for x in recent if x["keepingUp"]][:12], "recentAll": len(recent)}
except Exception as e:
    snap["manga"] = None

# ---- Economy in numbers (headline indicators)
try:
    E = json.load(open(os.path.join(ECON, "docs/data/dati.json"), encoding="utf-8"))
    out = []
    for r in E["raditaji"]:
        if str(r.get("galvenais")) not in ("True", "true", "1"): continue
        data = r.get("dati")
        if isinstance(data, str):
            import ast; data = ast.literal_eval(data)
        def last(code):
            ser = [x for x in (data or {}).get(code, []) if x[1] is not None]
            return ser[-1] if ser else None
        lv, eu = last("LV"), last("EU27_2020")
        ser_lv = [x for x in (data or {}).get("LV", []) if x[1] is not None]
        out.append({"id": r["id"], "name": r.get("lv"), "unit": r.get("vieniba_lv"), "dec": int(r.get("decimales") or 1), "good": int(r.get("labi") or 0),
                    "lv": {"period": lv[0], "value": lv[1]} if lv else None, "lvPrev": {"period": ser_lv[-2][0], "value": ser_lv[-2][1]} if len(ser_lv) > 1 else None,
                    "eu": {"period": eu[0], "value": eu[1]} if eu else None})
    snap["econ"] = {"generated": E.get("generets"), "items": out}
except Exception:
    snap["econ"] = None

s = json.dumps(snap, ensure_ascii=False, separators=(",", ":"))
open(OUT, "w", encoding="utf-8").write(s)
print("snapshot bytes:", len(s.encode()), {k: (len(v) if isinstance(v, list) else ("ok" if v else None)) for k, v in snap.items()})
