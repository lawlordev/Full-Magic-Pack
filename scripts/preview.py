"""Browse the templates in this pack: a small local catalog of data/ for Loom's live preview.

Magic Set Editor itself is a Windows desktop app, so the preview shows what the pack ships instead:
every game, style, symbol font, include, export template and locale, with icons, versions,
dependencies and the frame images inside each package.

    PORT=8000 python3 -B scripts/preview.py      # serves http://127.0.0.1:8000/
"""
import html
import json
import mimetypes
import os
import sys
from collections import Counter
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, quote, unquote, urlparse

from mse_pack import DATA, ROOT, read_all

IMAGE_EXT = {".png", ".jpg", ".jpeg", ".gif", ".bmp", ".webp"}
KIND_LABEL = {
    "game": "Games", "style": "Card styles", "symbol-font": "Symbol fonts", "include": "Includes",
    "export-template": "Export templates", "locale": "Languages",
}
PACKAGES = {p["name"]: p for p in read_all()}
CHANGELOG = (ROOT / "changelog.txt").read_text(encoding="utf-8-sig", errors="replace").splitlines()
TITLE = CHANGELOG[0].strip() if CHANGELOG else "Full Magic Pack"

CSS = """
:root{--bg:#f6f3ee;--card:#fff;--ink:#1d1a16;--mute:#6d655b;--line:#e4ddd2;--acc:#8a3b12}
*{box-sizing:border-box}body{margin:0;font:15px/1.45 system-ui,sans-serif;background:var(--bg);color:var(--ink)}
header{padding:20px 28px;border-bottom:1px solid var(--line);background:var(--card)}
h1{margin:0;font-size:22px}header p{margin:4px 0 0;color:var(--mute)}a{color:var(--acc)}
.bar{display:flex;gap:8px;flex-wrap:wrap;padding:14px 28px;align-items:center}
.bar a{padding:5px 11px;border:1px solid var(--line);border-radius:99px;text-decoration:none;background:var(--card);color:var(--ink)}
.bar a.on{background:var(--ink);color:#fff;border-color:var(--ink)}
.bar input{flex:1;min-width:220px;padding:7px 12px;border:1px solid var(--line);border-radius:8px;font:inherit}
.grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(210px,1fr));gap:14px;padding:4px 28px 28px}
.pkg{background:var(--card);border:1px solid var(--line);border-radius:10px;padding:12px;text-decoration:none;color:inherit;display:flex;flex-direction:column;gap:6px}
.pkg:hover{border-color:var(--acc)}.pkg .img{height:150px;display:flex;align-items:center;justify-content:center;background:#faf8f4;border-radius:6px}
.pkg img{max-width:100%;max-height:150px}.pkg b{font-size:14px}.meta{color:var(--mute);font-size:12.5px}
main{padding:20px 28px}.files{display:grid;grid-template-columns:repeat(auto-fill,minmax(160px,1fr));gap:12px}
.files figure{margin:0;background:var(--card);border:1px solid var(--line);border-radius:8px;padding:8px;text-align:center}
.files img{max-width:100%;max-height:200px}.files figcaption{font-size:12px;color:var(--mute);word-break:break-all}
table{border-collapse:collapse}td{padding:3px 14px 3px 0;vertical-align:top}
"""


def page(title, body):
    return (f"<!doctype html><html><head><meta charset=utf-8><meta name=viewport content='width=device-width'>"
            f"<title>{html.escape(title)}</title><style>{CSS}</style></head><body>{body}</body></html>")


def esc(v):
    return html.escape(str(v or ""))


def icon_url(p):
    return f"/icon/{quote(p['name'])}" if p.get("icon_path") and p["icon_path"].is_file() else ""


def index(query):
    kind = query.get("kind", ["style"])[0]
    q = query.get("q", [""])[0].strip().lower()
    counts = Counter(p["kind"] for p in PACKAGES.values())
    tabs = "".join(
        f"<a class='{'on' if k == kind else ''}' href='/?kind={k}'>{label} ({counts[k]})</a>"
        for k, label in KIND_LABEL.items() if counts[k])
    shown = [p for p in PACKAGES.values() if p["kind"] == kind and
             (not q or q in " ".join(str(p.get(k, "")) for k in ("name", "full name", "short name", "installer group")).lower())]
    cards = "".join(
        f"<a class=pkg href='/package/{quote(p['name'])}'><div class=img>"
        + (f"<img loading=lazy src='{icon_url(p)}' alt=''>" if icon_url(p) else "<span class=meta>no icon</span>")
        + f"</div><b>{esc(p.get('full name') or p.get('short name') or p['name'])}</b>"
          f"<span class=meta>{esc(p.get('installer group') or p['name'])}</span>"
          f"<span class=meta>version {esc(p.get('version') or '—')}</span></a>"
        for p in shown)
    body = (f"<header><h1>Full Magic Pack</h1><p>{esc(TITLE)} · {len(PACKAGES)} packages for Magic Set Editor · "
            f"<a href='/changelog'>changelog</a></p></header>"
            f"<form class=bar>{tabs}<input type=hidden name=kind value='{esc(kind)}'>"
            f"<input name=q value='{esc(q)}' placeholder='Search {esc(KIND_LABEL.get(kind, kind)).lower()}…'></form>"
            f"<div class=grid>{cards or '<p class=meta>No packages match.</p>'}</div>")
    return page("Full Magic Pack", body)


def detail(name):
    p = PACKAGES.get(name)
    if not p:
        return None
    rows = "".join(f"<tr><td class=meta>{k}</td><td>{esc(p.get(k))}</td></tr>"
                   for k in ("short name", "full name", "game", "version", "mse version", "installer group") if p.get(k))
    deps = "".join(
        f"<li><a href='/package/{quote(d)}'>{esc(d)}</a> <span class=meta>{esc(v)}</span>"
        + ("" if d in PACKAGES else " <b style='color:#b00'>missing</b>") + "</li>" for d, v in p["depends"])
    images = sorted(f for f in p["path"].rglob("*") if f.suffix.lower() in IMAGE_EXT)
    figs = "".join(
        f"<figure><img loading=lazy src='/data/{quote(str(f.relative_to(DATA)))}' alt=''>"
        f"<figcaption>{esc(f.relative_to(p['path']))}</figcaption></figure>" for f in images[:300])
    body = (f"<header><h1>{esc(p.get('full name') or name)}</h1><p><a href='/?kind={p['kind']}'>← {KIND_LABEL.get(p['kind'], p['kind'])}</a>"
            f" · {esc(name)}</p></header><main><table>{rows}</table>"
            + (f"<h3>Depends on</h3><ul>{deps}</ul>" if deps else "")
            + (f"<h3>Images ({len(images)})</h3><div class=files>{figs}</div>" if figs else "") + "</main>")
    return page(name, body)


class Handler(BaseHTTPRequestHandler):
    def send(self, status, body, ctype="text/html; charset=utf-8"):
        data = body.encode() if isinstance(body, str) else body
        self.send_response(status)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def send_file(self, path):
        try:
            path = path.resolve()
            path.relative_to(DATA)  # never serve outside data/
        except (ValueError, OSError):
            return self.send(404, "not found", "text/plain")
        if not path.is_file():
            return self.send(404, "not found", "text/plain")
        self.send(200, path.read_bytes(), mimetypes.guess_type(path.name)[0] or "application/octet-stream")

    def do_GET(self):
        url = urlparse(self.path)
        route = unquote(url.path)
        if route == "/":
            return self.send(200, index(parse_qs(url.query)))
        if route == "/health":
            return self.send(200, json.dumps({"packages": len(PACKAGES)}), "application/json")
        if route == "/changelog":
            return self.send(200, page("Changelog", f"<main><p><a href='/'>← catalog</a></p><pre style='white-space:pre-wrap'>{esc(chr(10).join(CHANGELOG))}</pre></main>"))
        if route.startswith("/package/"):
            body = detail(route[len("/package/"):])
            return self.send(200, body) if body else self.send(404, page("Not found", "<main>Unknown package.</main>"))
        if route.startswith("/icon/"):
            p = PACKAGES.get(route[len("/icon/"):])
            return self.send_file(p["icon_path"]) if p and p.get("icon_path") else self.send(404, "not found", "text/plain")
        if route.startswith("/data/"):
            return self.send_file(DATA / route[len("/data/"):])
        self.send(404, page("Not found", "<main>Not found.</main>"))

    def log_message(self, fmt, *args):
        sys.stderr.write("%s %s\n" % (self.command, fmt % args))


if __name__ == "__main__":
    port = int(os.environ.get("PORT") or 8000)
    server = ThreadingHTTPServer(("127.0.0.1", port), Handler)
    print(f"Full Magic Pack catalog: {len(PACKAGES)} packages at http://127.0.0.1:{port}/", flush=True)
    server.serve_forever()
