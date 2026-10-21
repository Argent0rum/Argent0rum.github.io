"""Refreshes the project list for the hub page.

1. Asks GitHub for all of Argent0rum's repositories and saves the useful fields to dati/repos.json
   (the page reads this first, so it opens instantly even if GitHub's API is slow or rate-limited).
2. For every site that has GitHub Pages but no preview picture yet, takes a screenshot of the live
   site and saves it as atteli/<repo>.jpg (needs Playwright; skipped when --bez-atteliem is given).

Run by .github/workflows/atjaunot.yml every day and whenever projekti.json changes.
"""
import io
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

import requests

USER = "Argent0rum"
ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "dati" / "repos.json"
IMG = ROOT / "atteli"
FIELDS = ["name", "description", "homepage", "has_pages", "fork", "pushed_at", "created_at", "topics", "html_url"]


def get_repos():
    headers = {"Accept": "application/vnd.github+json"}
    if os.environ.get("GITHUB_TOKEN"):
        headers["Authorization"] = f"Bearer {os.environ['GITHUB_TOKEN']}"
    r = requests.get(f"https://api.github.com/users/{USER}/repos", params={"per_page": 100, "sort": "pushed"},
                     headers=headers, timeout=60)
    r.raise_for_status()
    return [{k: repo.get(k) for k in FIELDS} for repo in r.json()]


def site_url(repo):
    if repo.get("homepage"):
        return repo["homepage"]
    if repo["name"].lower() == f"{USER}.github.io".lower():
        return f"https://{USER.lower()}.github.io/"
    return f"https://{USER.lower()}.github.io/{repo['name']}/"


def screenshot(repos):
    from PIL import Image
    from playwright.sync_api import sync_playwright
    cfg = json.loads((ROOT / "projekti.json").read_text(encoding="utf-8"))
    hidden = {s.lower() for s in cfg.get("slept", [])}
    todo = [r for r in repos if r["has_pages"] and not r["fork"] and r["name"].lower() not in hidden
            and not (IMG / f"{r['name']}.jpg").exists()]
    if not todo:
        print("Visiem projektiem jau ir attēli.")
        return
    IMG.mkdir(exist_ok=True)
    with sync_playwright() as p:
        browser = p.chromium.launch()
        for r in todo:
            url = site_url(r)
            try:
                page = browser.new_page(viewport={"width": 1280, "height": 800})
                page.goto(url, wait_until="networkidle", timeout=60000)
                page.wait_for_timeout(2000)
                im = Image.open(io.BytesIO(page.screenshot())).convert("RGB").resize((800, 500), Image.LANCZOS)
                im.save(IMG / f"{r['name']}.jpg", quality=82, optimize=True, progressive=True)
                print(f"Attēls: {r['name']} ({url})")
                page.close()
            except Exception as e:  # site not live yet, etc. — try again tomorrow
                print(f"Neizdevās {r['name']}: {e}")
        browser.close()


def main():
    repos = get_repos()
    old = json.loads(DATA.read_text(encoding="utf-8")) if DATA.exists() else {}
    if old.get("repos") != repos:
        DATA.parent.mkdir(exist_ok=True)
        stamp = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        DATA.write_text(json.dumps({"generets": stamp, "repos": repos}, ensure_ascii=False, indent=1), encoding="utf-8")
        print(f"Saglabāti {len(repos)} repozitoriji.")
    else:
        print("Repozitoriju saraksts nav mainījies.")
    if "--bez-atteliem" not in sys.argv:
        screenshot(repos)


if __name__ == "__main__":
    main()
