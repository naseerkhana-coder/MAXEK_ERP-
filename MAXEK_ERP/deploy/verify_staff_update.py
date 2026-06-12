#!/usr/bin/env python3
"""Quick check that Employee Master update is live."""
from __future__ import annotations

import re
import sys
import urllib.parse
import urllib.request
from http.cookiejar import CookieJar

BASE = sys.argv[1] if len(sys.argv) > 1 else "http://127.0.0.1:5000"


def main() -> int:
    cj = CookieJar()
    opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(cj))
    data = urllib.parse.urlencode({"username": "admin", "password": "admin"}).encode()
    req = urllib.request.Request(f"{BASE}/login", data=data, method="POST")
    opener.open(req, timeout=10)
    html = opener.open(f"{BASE}/staff", timeout=10).read().decode("utf-8", "replace")
    labels = [
        "Employee Code (Auto)",
        "Bank Account Number",
        "IFSC Code",
        "Aadhaar Document",
        "PAN Document",
    ]
    ok = True
    for label in labels:
        found = label in html
        print(f"{label}: {'OK' if found else 'MISSING'}")
        ok = ok and found
    match = re.search(r'value="(EMP\d+)" readonly', html)
    print(f"Auto code preview: {match.group(1) if match else 'not found'}")
    return 0 if ok and match else 1


if __name__ == "__main__":
    raise SystemExit(main())
