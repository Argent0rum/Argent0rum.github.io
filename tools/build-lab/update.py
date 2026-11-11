#!/usr/bin/env python3
"""Build Lab data updater.

Adds characters, weapons / light cones and gear sets that are NEW in the public game-data sources to
data/hsr.json and data/genshin.json. Existing entries are never changed or removed (they hold curated
build advice), so the files only ever grow.

Sources (plain data, no API keys):
  Star Rail  - https://github.com/Mar-7th/StarRailRes  (index_min/en/*.json)
  Genshin    - the data file inside the genshin-db npm package (src/min/data.min.json)

New entries get their real stats and skill numbers. Their build advice (stat weights, main stats, sets)
is estimated from the kit text and marked as such until someone curates it.

Usage:
  python update.py              add new entries, write the files, print a report
  python update.py --check      also rebuild existing entries from the sources and report differences
  python update.py --genshin-data PATH   use a local data.min.json instead of downloading the package
"""
import io, json, re, sys, tarfile, urllib.request
from pathlib import Path

HERE = Path(__file__).resolve().parent
DATA = HERE / "data"
SRR = "https://raw.githubusercontent.com/Mar-7th/StarRailRes/master/index_min/en/"
UA = {"User-Agent": "build-lab-updater"}


def get(url, binary=False):
    with urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=120) as r:
        b = r.read()
    return b if binary else json.loads(b.decode("utf-8"))


def clean(s):
    """Game text → plain text (drop colour tags and similar markup)."""
    s = re.sub(r"</?(color|i|b|u|unbreak|size|align)[^>]*>", "", s or "")
    return s.replace("\\n", "\n").strip()


def r4(x, n=6):
    return round(x, n)


# ----------------------------------------------------------------------------------------------- Star Rail
HSR_PROP = {"HPAddedRatio": "HP%", "AttackAddedRatio": "ATK%", "DefenceAddedRatio": "DEF%", "SpeedDelta": "SPD",
            "CriticalChanceBase": "CRIT Rate", "CriticalDamageBase": "CRIT DMG", "StatusProbabilityBase": "Effect Hit Rate",
            "StatusResistanceBase": "Effect RES", "BreakDamageAddedRatioBase": "Break Effect"}
DMG_PATHS = {"Destruction", "Hunt", "Erudition", "Nihility", "Remembrance", "Elation"}


def hsr_scaling(kit):
    """Which stat does the kit mostly scale on? Counted from the skill texts."""
    text = " ".join(k["d"] for k in kit)
    n = {"ATK": len(re.findall(r"% of [^.]{0,40}?ATK", text)), "HP": len(re.findall(r"% of [^.]{0,40}?(?:Max )?HP", text)),
         "DEF": len(re.findall(r"% of [^.]{0,40}?DEF", text))}
    return max(n, key=lambda k: (n[k], k == "ATK"))


def hsr_advice(c):
    """Estimated stat weights and main stats for a character with no curated data yet."""
    sc, text, dmg = hsr_scaling(c["kit"]), " ".join(k["d"] for k in c["kit"]), c["path"] in DMG_PATHS
    w = dict.fromkeys(["ATK", "ATK%", "DEF", "DEF%", "HP", "HP%", "SPD", "CRIT Rate", "CRIT DMG", "Effect Hit Rate", "Effect RES", "Break Effect"], 0.0)
    w[sc], w[sc + "%"], w["SPD"] = 0.75, 1.0 if not dmg else 0.75, 1.0
    if dmg:
        w["CRIT Rate"] = w["CRIT DMG"] = 1.0
    else:
        w["Effect RES"] = 0.5
    if "base chance" in text:
        w["Effect Hit Rate"] = 1.0 if c["path"] == "Nihility" else 0.5
    if "Break Effect" in text or "Super Break" in text:
        w["Break Effect"] = 1.0
    el = c["el"] + " DMG Boost"
    mains = {"Body": ["CRIT Rate", "CRIT DMG"] if dmg else [sc + "%"], "Feet": ["SPD", sc + "%"],
             "Planar Sphere": [sc + "%", el] if dmg else [sc + "%"], "Link Rope": [sc + "%"] if dmg else ["Energy Regeneration Rate", sc + "%"]}
    subs = [k for k, v in sorted(w.items(), key=lambda kv: -kv[1]) if v >= 0.75 and not k in ("ATK", "HP", "DEF")][:4]
    return {"weights": w, "mains": mains, "subs": subs, "relics": [], "ornaments": [], "team": [], "breakpoints": [],
            "recSrc": "estimated automatically from the skill text (no guide data for this character yet)"}


def hsr_build(S):
    paths = {k: v["name"].replace("The ", "") for k, v in S["paths"].items()}
    chars, lcs, sets = {}, {}, {}
    for cid, c in S["characters"].items():
        if cid.startswith("8") and int(cid) % 2 == 0:
            continue                                   # the second Trailblazer of each pair is identical
        v = S["character_promotions"][cid]["values"][-1]
        lv = lambda k: r4(v[k]["base"] + v[k]["step"] * 79)
        traces = {}
        for t in c["skill_trees"]:
            for lev in S["character_skill_trees"].get(t, {}).get("levels", []):
                for p in lev["properties"]:
                    name = HSR_PROP.get(p["type"]) or S["properties"].get(p["type"], {}).get("name", p["type"])
                    traces[name] = r4(traces.get(name, 0) + p["value"])
        kit, seen = [], set()
        for sid in c["skills"]:
            s = S["character_skills"].get(sid)
            if not s or not s["type_text"] or (s["type_text"], s["name"]) in seen:
                continue
            seen.add((s["type_text"], s["name"]))
            kit.append({"t": s["type_text"], "n": s["name"], "d": clean(s["desc"]), "p": s["params"], "m": s["max_level"], "tag": s["effect_text"]})
        path = paths.get(c["path"], c["path"])
        name = f"Trailblazer ({path})" if cid.startswith("8") else c["name"]
        chars[cid] = {"name": name, "r": c["rarity"], "path": path, "el": {"Thunder": "Lightning"}.get(c["element"], c["element"]),
                      "base": {"HP": lv("hp"), "ATK": lv("atk"), "DEF": lv("def"), "SPD": lv("spd"), "CRIT Rate": lv("crit_rate"), "CRIT DMG": lv("crit_dmg")},
                      "traces": traces, "eid": [{"n": S["character_ranks"][r]["name"], "d": clean(S["character_ranks"][r]["desc"])} for r in c["ranks"] if r in S["character_ranks"]],
                      "kit": kit}
    for lid, l in S["light_cones"].items():
        v, rk = S["light_cone_promotions"][lid]["values"][-1], S["light_cone_ranks"].get(lid, {})
        lcs[lid] = {"name": l["name"], "r": l["rarity"], "path": paths.get(l["path"], l["path"]),
                    "stats": {k.upper() if k != "def" else "DEF": r4(v[k]["base"] + v[k]["step"] * 79) for k in ("hp", "atk", "def")},
                    "sk": rk.get("skill", ""), "d": clean(rk.get("desc", "")), "p": rk.get("params", [])}
    for sid, s in S["relic_sets"].items():
        sets[s["name"]] = {"id": sid, "planar": int(sid) >= 300, "d": [clean(x) for x in s["desc"]]}
    return chars, lcs, sets


def hsr_update(check):
    cur = json.loads((DATA / "hsr.json").read_text(encoding="utf-8"))
    S = {n: get(SRR + n + ".json") for n in ["characters", "character_promotions", "character_skills", "character_skill_trees", "character_ranks",
                                              "light_cones", "light_cone_promotions", "light_cone_ranks", "relic_sets", "paths", "properties"]}
    chars, lcs, sets = hsr_build(S)
    added = {"characters": [], "light cones": [], "relic sets": []}
    names = {c["name"] for c in cur["chars"].values()}
    for cid, c in chars.items():
        if cid in cur["chars"] or cid + "b1" in cur["chars"] or "{" in c["name"]:
            continue
        if c["name"] in names:
            c["name"] += f" ({c['path']})"
        c.update(hsr_advice(c))
        same = sorted((l for l in lcs.items() if l[1]["path"] == c["path"]), key=lambda kv: (-kv[1]["r"], -int(kv[0])))
        c["recLC"] = [k for k, _ in same[:4]]
        c["sigLC"] = c["recLC"][0] if c["recLC"] else None
        cur["chars"][cid] = c
        added["characters"].append(c["name"])
    for lid, l in lcs.items():
        if lid not in cur["lcs"]:
            cur["lcs"][lid] = l; added["light cones"].append(l["name"])
    have_ids = {s["id"] for s in cur["sets"].values()}
    for n, s in sets.items():
        if n not in cur["sets"] and s["id"] not in have_ids:
            cur["sets"][n] = s; added["relic sets"].append(n)
    if check:
        bad = []
        for cid, c in chars.items():
            o = cur["chars"].get(cid)
            if not o or cid in [x for x in added["characters"]]:
                continue
            for f in ("r", "path", "el", "base", "traces"):
                if json.dumps(o.get(f), sort_keys=True) != json.dumps(c[f], sort_keys=True):
                    bad.append(f"{cid} {o['name']}: {f}")
            if [k["n"] for k in o["kit"]] != [k["n"] for k in c["kit"]] or [k["p"] for k in o["kit"]] != [k["p"] for k in c["kit"]]:
                bad.append(f"{cid} {o['name']}: kit")
        lb = [lid for lid, l in lcs.items() if lid in cur["lcs"] and json.dumps({k: cur["lcs"][lid].get(k) for k in l}, sort_keys=True) != json.dumps(l, sort_keys=True)]
        print(f"[check] Star Rail: {len(chars)} characters rebuilt, {len(bad)} field differences; {len(lcs)} light cones, {len(lb)} differ")
        for b in bad[:12]:
            print("   ", b)
    return cur, added


# ------------------------------------------------------------------------------------------------- Genshin
GI_ASC = {"FIGHT_PROP_CRITICAL": "CRIT Rate", "FIGHT_PROP_CRITICAL_HURT": "CRIT DMG", "FIGHT_PROP_ATTACK_PERCENT": "ATK%", "FIGHT_PROP_HP_PERCENT": "HP%",
          "FIGHT_PROP_DEFENSE_PERCENT": "DEF%", "FIGHT_PROP_ELEMENT_MASTERY": "Elemental Mastery", "FIGHT_PROP_CHARGE_EFFICIENCY": "Energy Recharge",
          "FIGHT_PROP_HEAL_ADD": "Healing Bonus", "FIGHT_PROP_PHYSICAL_ADD_HURT": "Physical DMG Bonus"}
TAL = [("combat1", "Normal Attack"), ("combat2", "Elemental Skill"), ("combat3", "Elemental Burst"), ("combatsp", "Alternate Sprint")]


def gi_data(path):
    if path:
        return json.loads(Path(path).read_text(encoding="utf-8"))
    meta = get("https://registry.npmjs.org/genshin-db/latest")
    tgz = get(meta["dist"]["tarball"], binary=True)
    with tarfile.open(fileobj=io.BytesIO(tgz), mode="r:gz") as t:
        return json.loads(t.extractfile("package/src/min/data.min.json").read().decode("utf-8"))


def gi_scale(tal):
    lab = " ".join(l for t in tal for l in t.get("lab", []))
    n = {"ATK": len(re.findall(r"P\}(?: ATK|$|\|| ?\+| ?/|×)", lab)) + lab.count("% ATK"), "HP": lab.count("Max HP"), "DEF": lab.count("DEF")}
    return max(n, key=lambda k: (n[k], k == "ATK"))


def gi_build_all(G):
    en, st, cv, ver = G["data"]["English"], G["stats"], G["curve"], G["version"]
    chars, weapons, sets = {}, {}, {}
    for key, c in en["characters"].items():
        s, t, k = st["characters"].get(key), en["talents"].get(key), en["constellations"].get(key)
        if not s or not t or "traveler" in key or key in ("aether", "lumine"):
            continue
        pr, cu = s["promotion"][-1], cv["characters"]["90"]
        asc = GI_ASC.get(s["specialized"]) or (c.get("substatText") or "")
        tal = []
        for ck, label in TAL:
            x = t.get(ck)
            if not x:
                continue
            params = (st["talents"].get(key, {}).get(ck) or {})
            tal.append({"t": label, "n": x["name"], "d": clean(x.get("description") or x.get("descriptionRaw")), "lab": (x.get("attributes") or {}).get("labels", []),
                        "p": {pk: [r4(v, 5) for v in pv] for pk, pv in params.items()}})
        chars[key] = {"name": c["name"], "r": c["rarity"], "el": c.get("elementText"), "wt": c.get("weaponText"), "region": c.get("region") or "", "title": c.get("title") or "",
                      "asc": asc, "ascv": r4(pr.get("specialized", 0), 4),
                      "base": {x: round(s["base"][x] * cu[s["curve"][x]] + pr[x], 1) for x in ("hp", "attack", "defense")},
                      "cr": s["base"].get("critrate", 0.05), "cd": s["base"].get("critdmg", 0.5),
                      "pas": [{"n": t[p]["name"], "d": clean(t[p].get("description") or t[p].get("descriptionRaw"))} for p in ("passive1", "passive2", "passive3", "passive4") if t.get(p)],
                      "cons": [{"n": k[x]["name"], "d": clean(k[x].get("description") or k[x].get("descriptionRaw"))} for x in ("c1", "c2", "c3", "c4", "c5", "c6")] if k else [],
                      "tal": tal, "ver": str(ver.get("characters", {}).get(key, ""))}
    for key, w in en["weapons"].items():
        s = st["weapons"].get(key)
        if not s or w.get("rarity", 0) < 3:
            continue
        top = max(p["maxlevel"] for p in s["promotion"]); cu = cv["weapons"][str(top)]
        sub = GI_ASC.get(s.get("specialized"), w.get("mainStatText") or "")
        weapons[key] = {"name": w["name"], "type": w.get("weaponText"), "r": w["rarity"], "atk": round(s["base"]["attack"] * cu[s["curve"]["attack"]] + s["promotion"][-1]["attack"], 1),
                        "sub": sub or None, "subv": r4(s["base"].get("specialized", 0) * cu.get(s["curve"].get("specialized"), 0), 4) if sub else 0,
                        "pn": w.get("effectName") or "", "R": [clean(w[r]["description"] if isinstance(w.get(r), dict) else "") for r in ("r1", "r2", "r3", "r4", "r5") if w.get(r)],
                        "ver": str(ver.get("weapons", {}).get(key, ""))}
    for key, a in en["artifacts"].items():
        if max(a.get("rarityList") or [0]) < 4:
            continue
        sets[key] = {"name": a["name"], "rar": a["rarityList"], "e1": a.get("effect1Pc"), "e2": a.get("effect2Pc"), "e4": a.get("effect4Pc")}
    return chars, weapons, sets


def gi_advice(c, weapons):
    sc = gi_scale(c["tal"])
    text = " ".join(t["d"] for t in c["tal"]) + " ".join(p["d"] for p in c["pas"])
    em = len(re.findall(r"Elemental Mastery", text))
    heal = "heal" in text.lower() or "restores HP" in text
    dmg = c["asc"] in ("CRIT Rate", "CRIT DMG") or not heal
    pct = sc + "%"
    best = sorted((kv for kv in weapons.items() if kv[1]["type"] == c["wt"]), key=lambda kv: (-kv[1]["r"], -kv[1]["atk"]))
    c["scaleGuess"], c["emHint"] = sc, em
    c["build"] = {"role": "Estimated from the kit", "sets": [], "sands": [pct] + (["Elemental Mastery"] if em >= 3 else []) + ["Energy Recharge"],
                  "goblet": [c["el"] + " DMG Bonus", pct] if dmg else [pct], "circlet": ["CRIT Rate", "CRIT DMG"] if dmg else [pct, "Healing Bonus"],
                  "subs": (["CRIT Rate", "CRIT DMG"] if dmg else []) + [pct, "Energy Recharge"] + (["Elemental Mastery"] if em >= 3 else []),
                  "er": "", "weapons": [k for k, _ in best[:5]], "src": "estimated automatically from the kit (no guide data for this character yet)", "note": ""}


def gi_update(check, path):
    cur = json.loads((DATA / "genshin.json").read_text(encoding="utf-8"))
    chars, weapons, sets = gi_build_all(gi_data(path))
    added = {"characters": [], "weapons": [], "artifact sets": []}
    for key, w in weapons.items():
        if key not in cur["weapons"]:
            cur["weapons"][key] = w; added["weapons"].append(w["name"])
    for key, s in sets.items():
        if key not in cur["sets"]:
            cur["sets"][key] = s; added["artifact sets"].append(s["name"])
    for key, c in chars.items():
        if key in cur["chars"]:
            continue
        gi_advice(c, cur["weapons"])
        cur["chars"][key] = c; added["characters"].append(c["name"])
    if check:
        bad = []
        for key, c in chars.items():
            o = cur["chars"].get(key)
            if not o or c["name"] in added["characters"]:
                continue
            for f in ("r", "el", "wt", "asc", "ascv", "base", "cr", "cd"):
                if json.dumps(o.get(f), sort_keys=True) != json.dumps(c[f], sort_keys=True):
                    bad.append(f"{key}: {f} ours={o.get(f)} new={c[f]}")
            if [t["n"] for t in o["tal"]] != [t["n"] for t in c["tal"]] or [t.get("lab") for t in o["tal"]] != [t["lab"] for t in c["tal"]] or [t.get("p") for t in o["tal"]] != [t["p"] for t in c["tal"]]:
                bad.append(f"{key}: talents")
        wb = [k for k, w in weapons.items() if k in cur["weapons"] and any(cur["weapons"][k].get(f) != w[f] for f in ("atk", "sub", "subv", "r", "type"))]
        print(f"[check] Genshin: {len(chars)} characters rebuilt, {len(bad)} field differences; {len(weapons)} weapons, {len(wb)} differ; {len(sets)} sets")
        for b in bad[:12]:
            print("   ", b)
        for k in wb[:6]:
            print("    weapon", k, {f: (cur["weapons"][k].get(f), weapons[k][f]) for f in ("atk", "sub", "subv")})
    return cur, added


def main():
    check = "--check" in sys.argv
    gpath = sys.argv[sys.argv.index("--genshin-data") + 1] if "--genshin-data" in sys.argv else None
    report, changed = [], False
    for name, fn, file in (("Star Rail", lambda: hsr_update(check), "hsr.json"), ("Genshin", lambda: gi_update(check, gpath), "genshin.json")):
        try:
            data, added = fn()
        except Exception as e:                           # one source being down must not block the other
            report.append(f"{name}: FAILED ({type(e).__name__}: {e})"); continue
        n = sum(len(v) for v in added.values())
        if n and "--dry" not in sys.argv:
            (DATA / file).write_text(json.dumps(data, ensure_ascii=False, separators=(",", ":")), encoding="utf-8"); changed = True
        report.append(f"{name}: " + ("; ".join(f"{len(v)} new {k}: {', '.join(v[:12])}{' …' if len(v) > 12 else ''}" for k, v in added.items() if v) or "nothing new"))
    print("\n".join(report))
    (HERE / "last_update.txt").write_text("\n".join(report) + "\n", encoding="utf-8") if changed else None
    if any("FAILED" in r for r in report):
        sys.exit(1)


if __name__ == "__main__":
    main()
