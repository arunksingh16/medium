"""Step 4: the API footprint of your test suite.

Merges out/footprint-*.json (written by tests/conftest.py) and prints every
AWS operation your green build depended on. Operations that returned 501 are
flagged. Check this list against the emulator's fidelity scores before you
trust a green build. Usage: python 04_footprint.py [emulator|moto]
"""
import json
import sys
from collections import defaultdict
from pathlib import Path

backend = sys.argv[1] if len(sys.argv) > 1 else "emulator"
files = sorted(Path("out").glob(f"footprint-{backend}-*.json"))
if not files:
    sys.exit(f"No out/footprint-{backend}-*.json yet. Run the tests first.")

agg = defaultdict(lambda: defaultdict(int))
for f in files:
    for r in json.loads(f.read_text()):
        agg[(r["service"], r["operation"])][r["status"]] += r["calls"]

print(f"AWS API footprint of the test suite ({backend}, {len(files)} file(s))\n")
print(f"{'service':12} {'operation':22} {'calls':>5}  statuses")
print("-" * 60)
flagged = []
for (svc, op), st in sorted(agg.items()):
    total = sum(st.values())
    statuses = ", ".join(f"{k}x{v}" for k, v in sorted(st.items()))
    mark = ""
    if 501 in st:
        mark = "  <-- NOT IMPLEMENTED"
        flagged.append(f"{svc}:{op}")
    print(f"{svc:12} {op:22} {total:5}  {statuses}{mark}")
print("-" * 60)
print(f"{len(agg)} distinct operations across {len({s for s, _ in agg})} services")
if flagged:
    print("Not implemented in this emulator version:", ", ".join(flagged))
    sys.exit(1)
