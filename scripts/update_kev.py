#!/usr/bin/env python3
"""Refresh the CISA KEV table in README.md between the KEV markers."""
import json
import re
import urllib.request
from pathlib import Path

FEED = "https://www.cisa.gov/sites/default/files/feeds/known_exploited_vulnerabilities.json"
README = Path(__file__).resolve().parent.parent / "README.md"
START, END = "<!-- KEV-START -->", "<!-- KEV-END -->"
LIMIT = 5


def main():
    req = urllib.request.Request(FEED, headers={"User-Agent": "v3nomtech-readme-bot"})
    with urllib.request.urlopen(req, timeout=30) as r:
        vulns = json.load(r)["vulnerabilities"]

    latest = sorted(vulns, key=lambda v: (v["dateAdded"], v["cveID"]), reverse=True)[:LIMIT]

    rows = [
        "| CVE | Vendor / Product | Vulnerability | Added | Ransomware |",
        "|---|---|---|---|:---:|",
    ]
    for v in latest:
        cve = v["cveID"]
        name = v["vulnerabilityName"].strip().replace("|", "/")
        ransom = "⚠️" if v.get("knownRansomwareCampaignUse") == "Known" else "—"
        rows.append(
            f"| [{cve}](https://nvd.nist.gov/vuln/detail/{cve}) "
            f"| {v['vendorProject'].strip()} {v['product'].strip()} | {name} | {v['dateAdded']} | {ransom} |"
        )

    table = "\n".join(rows)
    text = README.read_text(encoding="utf-8")
    new = re.sub(
        rf"{re.escape(START)}.*?{re.escape(END)}",
        f"{START}\n{table}\n{END}",
        text,
        flags=re.S,
    )
    README.write_text(new, encoding="utf-8")


if __name__ == "__main__":
    main()
