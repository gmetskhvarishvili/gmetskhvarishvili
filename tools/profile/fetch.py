#!/usr/bin/env python3
"""Refresh cache.json with live numbers from NuGet and GitHub.

NuGet needs no auth. GitHub numbers use the GraphQL API and need a token in
GITHUB_TOKEN (the default Actions token works). Any source that fails keeps
its previous cached values, so the profile never renders empty.
"""
from __future__ import annotations

import datetime as dt
import json
import os
import sys
import urllib.request
from pathlib import Path

HERE = Path(__file__).resolve().parent
CACHE = HERE / "cache.json"
PROFILE = json.loads((HERE / "profile.json").read_text(encoding="utf-8"))
LOGIN = PROFILE["login"]
UA = {"User-Agent": f"{LOGIN}-profile-readme"}


def get_json(url: str, data: bytes | None = None, headers: dict | None = None) -> dict:
    req = urllib.request.Request(url, data=data, headers={**UA, **(headers or {})})
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.load(r)


def fetch_nuget() -> dict:
    packages, skip = [], 0
    while True:
        res = get_json(f"https://azuresearch-usnc.nuget.org/query?q=owner:{LOGIN}&take=200&skip={skip}&prerelease=false&semVerLevel=2.0.0")
        for p in res["data"]:
            owners = p.get("owners") or []
            if isinstance(owners, str):
                owners = [owners]
            if LOGIN.lower() in (o.lower() for o in owners):
                packages.append({
                    "id": p["id"],
                    "version": p["version"],
                    "downloads": int(p.get("totalDownloads", 0)),
                    "description": (p.get("description") or "").strip(),
                    "tags": (p.get("tags") or [])[:6],
                })
        skip += 200
        if skip >= res.get("totalHits", 0) or not res["data"]:
            break
    if not packages:
        raise RuntimeError("NuGet returned no packages")
    packages.sort(key=lambda x: -x["downloads"])
    return {"package_count": len(packages), "total_downloads": sum(p["downloads"] for p in packages), "packages": packages}


QUERY = """
query($login: String!) {
  user(login: $login) {
    followers { totalCount }
    repositories(first: 100, privacy: PUBLIC, ownerAffiliations: OWNER, orderBy: {field: NAME, direction: ASC}) {
      totalCount
      nodes { name description url stargazerCount pushedAt primaryLanguage { name } }
    }
    contributionsCollection {
      contributionCalendar {
        totalContributions
      }
    }
  }
}"""


def fetch_github() -> dict:
    token = os.environ.get("GITHUB_TOKEN")
    if not token:
        raise RuntimeError("GITHUB_TOKEN not set")
    body = json.dumps({"query": QUERY, "variables": {"login": LOGIN}}).encode()
    res = get_json("https://api.github.com/graphql", body, {"Authorization": f"bearer {token}", "Content-Type": "application/json"})
    if res.get("errors"):
        raise RuntimeError(res["errors"])
    u = res["data"]["user"]
    cal = u["contributionsCollection"]["contributionCalendar"]
    repos = [{
        "name": r["name"],
        "description": r["description"] or "",
        "url": r["url"],
        "stars": r["stargazerCount"],
        "pushed_at": r["pushedAt"],
        "language": (r["primaryLanguage"] or {}).get("name"),
    } for r in u["repositories"]["nodes"]]
    return {
        "public_repos": u["repositories"]["totalCount"],
        "followers": u["followers"]["totalCount"],
        "contributions_last_year": cal["totalContributions"],
        "repos": repos,
    }


def main() -> int:
    cache = json.loads(CACHE.read_text(encoding="utf-8")) if CACHE.exists() else {}
    ok = False
    for key, fn in (("nuget", fetch_nuget), ("github", fetch_github)):
        try:
            cache[key] = fn()
            ok = True
            print(f"{key}: ok")
        except Exception as e:  # keep the previous values
            print(f"{key}: kept cached values ({e})", file=sys.stderr)
    if ok:
        cache["fetched_at"] = dt.date.today().isoformat()
    CACHE.write_text(json.dumps(cache, indent=1), encoding="utf-8")
    return 0


if __name__ == "__main__":
    sys.exit(main())
