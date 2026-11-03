# -*- coding: utf-8 -*-
"""把本地图传到 Gitee 仓库，换一个「境内可访问的公网图片 URL」。

为什么需要这一层
----------------
魔搭 API-Inference 的 Qwen-Image-Edit 是图生图，`image_url` **必须是公网可达的
URL**，data URI / base64 会被拒（实测 400 `image_url is required`）。而本机实测：

* 外国免费图床 0x0.st / catbox / tmpfiles / sm.ms / upload.cc → 被墙或 DDoS-Guard
* 免账号境内图床 paugram / chkaja / mtyqx / xinyew / imgloc / imgbb → 403/404/400
* Gitee 可达（200），raw 域名也可达（302）

所以用 Gitee 仓库当图床：传图 → 拿 `raw` 链接 → 喂魔搭。

用法
----
    python gitee_host.py --whoami                 # 验证令牌、看用户名
    python gitee_host.py --ensure-repo            # 没有仓库就建（默认 ggc-uploads）
    python gitee_host.py --upload out/a.png       # 传图并打印公网 URL
    python gitee_host.py --upload a.png --path stack/l4.png

令牌放 `.secrets/gitee.txt`（只放令牌，不要引号空格），或设 $GITEE_TOKEN。
需要的权限范围：projects（读写仓库）。仓库是 **公开** 的——raw 链接免鉴权才最稳，
所以别往这里传敏感内容。
"""
import argparse
import base64
import json
import os
import sys
import urllib.error
import urllib.parse
import urllib.request

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from ggc_assets import PROJECT  # noqa: E402

SECRETS = os.path.join(PROJECT, ".secrets")
TOKEN_FILE = os.path.join(SECRETS, "gitee.txt")
API = "https://gitee.com/api/v5"
DEFAULT_REPO = "ggc-uploads"


def token():
    t = (os.environ.get("GITEE_TOKEN") or "").strip()
    if not t and os.path.isfile(TOKEN_FILE):
        try:
            t = open(TOKEN_FILE, encoding="utf-8").read().strip()
        except Exception:
            t = ""
    return t or None


def _call(method, path, params=None, body=None, timeout=60):
    """调 Gitee v5。params 走 query，body 走 form/JSON。"""
    tok = token()
    if not tok:
        raise SystemExit("没有 Gitee 令牌：请写入 .secrets/gitee.txt 或设 $GITEE_TOKEN")
    url = API + path
    q = dict(params or {})
    q["access_token"] = tok
    url += "?" + urllib.parse.urlencode(q)
    data = None
    if body is not None:
        data = json.dumps(body).encode()
    req = urllib.request.Request(url, data=data, method=method)
    if data:
        req.add_header("Content-Type", "application/json;charset=UTF-8")
    # Gitee 是境内站，直连；显式清空代理避免被外部 HTTPS_PROXY 带偏
    op = urllib.request.build_opener(urllib.request.ProxyHandler({}))
    try:
        with op.open(req, timeout=timeout) as r:
            txt = r.read().decode("utf-8", "replace")
            return json.loads(txt) if txt.strip() else {}
    except urllib.error.HTTPError as e:
        txt = e.read().decode("utf-8", "replace")
        raise SystemExit("Gitee API %s %s 失败：HTTP %d %s"
                         % (method, path, e.code, txt[:400]))


def whoami():
    u = _call("GET", "/user")
    return u.get("login"), u.get("name")


def repo_exists(owner, repo):
    try:
        _call("GET", "/repos/%s/%s" % (owner, repo))
        return True
    except SystemExit:
        return False


def ensure_repo(owner, repo, private=False):
    if repo_exists(owner, repo):
        return False
    _call("POST", "/user/repos", body={
        "name": repo,
        "has_issues": False,
        "has_wiki": False,
        "auto_init": True,
        "private": bool(private),
        "description": "GGC art redraw staging (auto-created by gitee_host.py)",
    })
    return True


def upload(owner, repo, local_path, remote_path=None, branch="master", message=None):
    """PUT contents 接口传文件（小文件够用；<1MB 建议走这个）。"""
    remote_path = remote_path or os.path.basename(local_path)
    remote_path = remote_path.replace("\\", "/").lstrip("/")
    raw = open(local_path, "rb").read()
    b64 = base64.b64encode(raw).decode()
    path = "/repos/%s/%s/contents/%s" % (owner, repo, urllib.parse.quote(remote_path))
    # 已存在则要先取 sha，否则 422
    sha = None
    try:
        cur = _call("GET", path, params={"ref": branch})
        # 文件存在 -> dict；路径被当成目录 -> list（说明文件还没建）
        if isinstance(cur, dict):
            sha = cur.get("sha")
    except SystemExit:
        sha = None
    body = {"content": b64,
            "message": message or ("upload %s" % remote_path),
            "branch": branch}
    if sha:
        body["sha"] = sha
    _call("POST" if not sha else "PUT", path, body=body)
    return "https://gitee.com/%s/%s/raw/%s/%s" % (owner, repo, branch, remote_path)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--whoami", action="store_true")
    ap.add_argument("--ensure-repo", action="store_true")
    ap.add_argument("--repo", default=os.environ.get("GITEE_REPO") or DEFAULT_REPO)
    ap.add_argument("--private", action="store_true",
                    help="建私有仓库（注意：私有库 raw 链接需要鉴权，魔搭取不到）")
    ap.add_argument("--upload", nargs="+", help="一个或多个本地文件")
    ap.add_argument("--path", help="远端路径（单文件时用）")
    ap.add_argument("--branch", default="master")
    a = ap.parse_args()

    if not token():
        print("缺少令牌：把 Gitee 私人令牌写入 .secrets/gitee.txt")
        return 2
    owner, _ = whoami()
    print("Gitee 用户：%s" % owner)

    if a.ensure_repo:
        made = ensure_repo(owner, a.repo, private=a.private)
        print("仓库 %s/%s %s" % (owner, a.repo, "已创建" if made else "已存在"))

    if a.upload:
        for i, p in enumerate(a.upload):
            if not os.path.isfile(p):
                print("跳过（不存在）：%s" % p)
                continue
            rp = a.path if (a.path and len(a.upload) == 1) else os.path.basename(p)
            u = upload(owner, a.repo, p, rp, branch=a.branch)
            print("上传 %s -> %s" % (p, u))
    return 0


if __name__ == "__main__":
    sys.exit(main())
