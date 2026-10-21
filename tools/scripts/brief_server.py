"""本地填写服务：把清单页上的"国画重彩替代描述"即时写进工程目录。

为什么需要它：浏览器里的 blob 下载在预览面板里会被静默拦截，localStorage 又
随预览会话销毁。角色清单页打开后每敲一个字就 POST 一次，落到
`validation/roster_briefs.json`——不依赖下载、不依赖浏览器缓存。

用法：
    python tools/scripts/brief_server.py [--port 8770]
浏览器打开 http://127.0.0.1:8770/
"""

import argparse
import csv
import io
import json
import os
import sys
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

DOCS = os.path.join(ROOT, "docs")
VAL = os.path.join(ROOT, "validation")
PAGE = os.path.join(DOCS, "CHARACTER_ROSTER.html")
STATE = os.path.join(VAL, "roster_briefs.json")
DRAFT = os.path.join(VAL, "roster_briefs_draft.json")

CORS = {
    "Access-Control-Allow-Origin": "*",
    "Access-Control-Allow-Methods": "GET, POST, OPTIONS",
    "Access-Control-Allow-Headers": "Content-Type",
    "Cache-Control": "no-store",
}


def load_state():
    if not os.path.isfile(STATE):
        return {}
    try:
        with io.open(STATE, encoding="utf-8") as fh:
            return json.load(fh)
    except Exception:
        return {}


def effective_state():
    """草稿打底、真实填写覆盖。这样页面一打开 42 个框都有字，用户改而不是从零写。"""
    base = {}
    if os.path.isfile(DRAFT):
        try:
            with io.open(DRAFT, encoding="utf-8") as fh:
                base = json.load(fh)
        except Exception:
            base = {}
    base.update(load_state())
    return base


def save_state(data):
    os.makedirs(VAL, exist_ok=True)
    tmp = STATE + ".tmp"
    with io.open(tmp, "w", encoding="utf-8") as fh:
        json.dump(data, fh, ensure_ascii=False, indent=1, sort_keys=True)
    os.replace(tmp, STATE)


def build_csv(data):
    rows = [["预制体", "中文名", "英文名", "阵营", "类型", "国画重彩替代描述"]]
    try:
        from characters_meta import ROSTER
    except Exception:
        ROSTER = []
    for e in ROSTER:
        p = e["prefab"]
        rows.append([p, e.get("cn", ""), e.get("en", ""), e.get("faction", ""),
                     e.get("role", ""), data.get(p, "")])
    buf = io.StringIO()
    w = csv.writer(buf, lineterminator="\r\n")
    w.writerows(rows)
    return "\ufeff" + buf.getvalue()


class Handler(BaseHTTPRequestHandler):
    server_version = "GGCBrief/1.0"

    def log_message(self, fmt, *args):
        pass  # keep the console for real events

    def _send(self, code, body, ctype="application/json; charset=utf-8", extra=None):
        raw = body.encode("utf-8") if isinstance(body, str) else body
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(raw)))
        for k, v in CORS.items():
            self.send_header(k, v)
        for k, v in (extra or {}).items():
            self.send_header(k, v)
        self.end_headers()
        self.wfile.write(raw)

    def do_OPTIONS(self):
        self.send_response(204)
        for k, v in CORS.items():
            self.send_header(k, v)
        self.end_headers()

    def do_GET(self):
        path = self.path.split("?")[0]
        if path in ("/", "/index.html"):
            if not os.path.isfile(PAGE):
                self._send(500, "roster page missing; run build_roster_v2.py first",
                           "text/plain; charset=utf-8")
                return
            with open(PAGE, "rb") as fh:
                self._send(200, fh.read(), "text/html; charset=utf-8")
            return
        if path == "/state":
            self._send(200, json.dumps(effective_state(), ensure_ascii=False))
            return
        if path == "/csv":
            body = build_csv(effective_state()).encode("utf-8")
            self._send(200, body, "text/csv; charset=utf-8", {
                "Content-Disposition":
                    "attachment; filename*=UTF-8''%E8%A7%92%E8%89%B2%E6%9B%BF%E4%BB%A3%E6%8F%8F%E8%BF%B0.csv"})
            return
        self._send(404, json.dumps({"error": "not found"}))

    def do_POST(self):
        path = self.path.split("?")[0]
        if path != "/save":
            self._send(404, json.dumps({"error": "not found"}))
            return
        try:
            n = int(self.headers.get("Content-Length") or 0)
            data = json.loads(self.rfile.read(n).decode("utf-8") or "{}")
            if not isinstance(data, dict):
                raise ValueError("payload must be an object")
        except Exception as exc:
            self._send(400, json.dumps({"error": str(exc)}))
            return
        clean = {str(k): str(v) for k, v in data.items() if str(v).strip()}
        save_state(clean)
        ts = time.strftime("%H:%M:%S")
        print("[%s] saved %d briefs -> %s" % (ts, len(clean), os.path.relpath(STATE, ROOT)),
              flush=True)
        self._send(200, json.dumps({"ok": True, "count": len(clean), "time": ts},
                                   ensure_ascii=False))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--port", type=int, default=8770)
    a = ap.parse_args()
    srv = ThreadingHTTPServer(("127.0.0.1", a.port), Handler)
    print("brief server: http://127.0.0.1:%d/  (state -> %s)" %
          (a.port, os.path.relpath(STATE, ROOT)), flush=True)
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()
