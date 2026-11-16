"""Check the pack the way the sync job and MSE's installer builder rely on it.

Fails on: missing executables, packages without a header file, icons that do not exist,
malformed dependencies, and dependencies on packages that are not in data/.
"""
import sys

from mse_pack import ROOT, read_all

errors = []
for exe in ("mse.exe", "magicseteditor.exe"):
    if not (ROOT / exe).is_file():
        errors.append(f"{exe} missing from the repo root")
packages = read_all()
names = {p["name"] for p in packages}
for p in packages:
    errors += [f"{p['name']}: {e}" for e in p["errors"]]
    errors += [f"{p['name']}: depends on missing package {d}" for d, _ in p["depends"] if d not in names]
    if p["kind"] != "locale" and "version" not in p and not p["errors"]:
        print(f"warning: {p['name']} has no version header")

for e in errors:
    print(f"error: {e}")
print(f"{len(packages)} packages checked, {len(errors)} errors")
sys.exit(1 if errors else 0)
