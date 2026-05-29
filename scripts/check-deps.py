#!/usr/bin/env python3
"""Check upstream dependency versions against what this repo uses.

Reports drift as a table. No auto-upgrades — advisory only.
Exit 0 if all dependencies are current, 1 if any have drifted.

Usage:
    scripts/check-deps.py                  # Check all dependencies
    scripts/check-deps.py --json           # Machine-readable JSON output
"""

import json
import os
import sys
import urllib.request
import urllib.error

REPO_URL = "https://github.com/chazcheadle/rtlamr-meter-reader"

DEPS = [
    {
        "name": "rtlamr",
        "type": "github-release",
        "repo": "bemasher/rtlamr",
        "pinned": "v0.9.5",
        "doc": "See SKILL.md Step 6 — curl from GitHub releases",
        "url": "https://github.com/bemasher/rtlamr/releases",
    },
    {
        "name": "paho-mqtt",
        "type": "pypi",
        "pinned": "latest (pip install paho-mqtt)",
        "doc": "Used by scripts/rtlamr-mqtt-bridge.py",
        "url": "https://pypi.org/project/paho-mqtt/",
    },
    {
        "name": "rtl-sdr (librtlsdr)",
        "type": "git-archive",
        "repo": "git.osmocom.org/rtl-sdr",
        "pinned": "latest (build from source)",
        "doc": "Built from git.osmocom.org — no release tags tracked",
        "url": "https://git.osmocom.org/rtl-sdr",
    },
]


def fetch_json(url: str, timeout: int = 10) -> dict | None:
    """Fetch JSON from a URL, return None on failure."""
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "rtlamr-dep-check/1.0"})
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return json.loads(resp.read().decode())
    except (urllib.error.URLError, urllib.error.HTTPError, json.JSONDecodeError, OSError) as e:
        return {"_error": str(e)}


def check_github_release(repo: str) -> dict | str:
    """Get the latest release tag from a GitHub repo."""
    url = f"https://api.github.com/repos/{repo}/releases/latest"
    data = fetch_json(url)
    if data is None or "_error" in (data or {}):
        return "unreachable"
    return data.get("tag_name", "unknown")


def check_pypi(package: str) -> dict | str:
    """Get the latest version from PyPI."""
    url = f"https://pypi.org/pypi/{package}/json"
    data = fetch_json(url)
    if data is None or "_error" in (data or {}):
        return "unreachable"
    return data.get("info", {}).get("version", "unknown")


CHECKERS = {
    "github-release": lambda d: check_github_release(d["repo"]),
    "pypi": lambda d: check_pypi(d["name"]),
    "git-archive": lambda d: "check git.osmocom.org manually",
}


def main():
    output_json = "--json" in sys.argv
    results = []

    for dep in DEPS:
        checker = CHECKERS.get(dep["type"])
        latest = checker(dep) if checker else "unknown"

        status = "OK"
        if isinstance(latest, str) and latest not in ("unreachable", "unknown", "check git.osmocom.org manually"):
            if dep["pinned"] != "latest (pip install paho-mqtt)" and dep["pinned"] != "latest (build from source)":
                if latest != dep["pinned"]:
                    status = "DRIFT"

        results.append({
            "name": dep["name"],
            "pinned": dep["pinned"],
            "latest": latest,
            "status": status,
            "url": dep["url"],
        })

        if not output_json:
            print(f"{status:6}  {dep['name']:20}  pinned={dep['pinned']:30}  latest={latest}")

    if output_json:
        print(json.dumps(results, indent=2))
        return

    # Count drifts
    drifts = [r for r in results if r["status"] == "DRIFT"]
    unreachables = [r for r in results if r["latest"] == "unreachable"]

    if drifts:
        print(f"\n⚠️  {len(drifts)} dependency/dependencies have drifted from pinned versions.")
        print(f"   Review each at the URL above before upgrading.")
    if unreachables:
        print(f"\n⚠️  {len(unreachables)} dependency/dependencies could not be checked (network issue).")
    if not drifts and not unreachables:
        print(f"\n✅ All dependencies are current.")

    sys.exit(1 if drifts else 0)


if __name__ == "__main__":
    main()
