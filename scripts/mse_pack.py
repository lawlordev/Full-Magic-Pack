"""Read the Magic Set Editor packages in data/ (shared by the catalog preview and the pack check)."""
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data"
PACKAGE_RE = re.compile(r"(.+)\.mse-(.+)")
HEADER_KEYS = {"short name", "full name", "icon", "installer group", "version", "game", "mse version"}


def read_package(path):
    """Return the header fields and dependencies of one package folder, or None if it is not a package."""
    match = PACKAGE_RE.fullmatch(path.name)
    if not path.is_dir() or not match:
        return None
    kind = match.group(2)
    info = {"name": path.name, "kind": kind, "path": path, "depends": [], "errors": []}
    header = path / kind
    if not header.is_file():
        info["errors"].append(f"header file '{kind}' missing")
        return info
    lines = header.read_text(encoding="utf-8-sig", errors="replace").splitlines()
    for i, line in enumerate(lines):
        if not line or line[0] in "\t #" or ":" not in line:
            continue
        key, value = line.split(":", 1)
        value = value.strip()
        if key in HEADER_KEYS and key not in info:
            info[key] = value
        elif key == "depends on":
            if value:
                parts = value.split()
                info["depends"].append((parts[0], parts[1] if len(parts) > 1 else ""))
                continue
            dep = {}
            for sub in lines[i + 1 : i + 3]:
                if sub.startswith("\t") and ":" in sub:
                    k, v = sub.strip().split(":", 1)
                    dep[k.strip()] = v.strip()
            if "package" not in dep:
                info["errors"].append(f"malformed dependency on line {i + 1}")
            else:
                info["depends"].append((dep["package"], dep.get("version", "")))
    if "icon" in info:
        # "/other.mse-xxx/file" refers to a file in another package, as MSE resolves it.
        icon = info["icon"]
        info["icon_path"] = DATA / icon[1:] if icon.startswith("/") else path / icon
    if "icon" in info and not info["icon_path"].is_file():
        info["errors"].append(f"icon file '{info['icon']}' not found")
    return info


def read_all():
    return [p for p in (read_package(d) for d in sorted(DATA.iterdir())) if p]
