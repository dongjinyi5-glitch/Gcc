#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""阿里云 AK/SK 探针。

目的：判断 .secrets/dashscope.txt 里放的是「百炼 API-KEY（sk-...）」还是
「阿里云 AccessKey ID/Secret（LTAI...）」，如果是后者，则用 AK/SK 走
OpenAPI（ACS3-HMAC-SHA256 签名）尝试：

  1. BSS QueryAccountBalance  -> 回答「账户有没有余额」
  2. 百炼 CreateApiKey        -> 直接铸造一个能用的 sk- API-KEY
  3. 百炼 ListApiKeys         -> 看看是否已有可复用的 KEY

全程不打印任何密钥原文，只打印掩码与判定结果。

用法:
  python tools/scripts/aliyun_ak_probe.py
  python tools/scripts/aliyun_ak_probe.py --save   # 铸到 key 就写回 .secrets/dashscope.txt
"""
import argparse
import base64
import hashlib
import hmac
import json
import os
import re
import sys
import urllib.error
import urllib.parse
import urllib.request
import uuid
from datetime import datetime, timezone

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
SECRETS = os.path.join(ROOT, ".secrets")
DASH_FILE = os.path.join(SECRETS, "dashscope.txt")

UA = "aliyun-ak-probe/1.0"


# ------------------------------------------------------------------ 读凭据
AK_FILE = os.path.join(SECRETS, "aliyun_ak.txt")


def load_credential():
    """返回 ('apikey', key) 或 ('aksk', (ak_id, ak_secret)) 或 (None, None)。

    优先读 .secrets/aliyun_ak.txt（AccessKey 专用），其次 dashscope.txt。
    """
    raw = ""
    for p in (AK_FILE, DASH_FILE):
        if os.path.isfile(p):
            t = open(p, encoding="utf-8").read()
            t = "\n".join(l for l in t.splitlines() if not l.strip().startswith("#"))
            if "LTAI" in t:
                raw = t
                break
            if not raw:
                raw = t
    raw = raw.strip()
    if not raw:
        return None, None

    # sk-xxx 单独一行
    m = re.search(r"\bsk-[A-Za-z0-9_\-]{16,}", raw)
    if m and "LTAI" not in raw:
        return "apikey", m.group(0)

    # LTAI... + 32 位 secret，可能带 label
    ids = re.findall(r"LTAI[A-Za-z0-9]{8,30}", raw)
    secrets = re.findall(r"\b[A-Za-z0-9]{30}\b", raw)
    secrets = [s for s in secrets if not s.startswith("LTAI")]
    if ids:
        ak_id = ids[0]
        # secret 取「不是 ak_id、长度 30」的第一个
        ak_secret = secrets[0] if secrets else ""
        if not ak_secret:
            lines = [l.strip() for l in raw.splitlines() if l.strip()]
            for l in lines:
                if l == ak_id:
                    continue
                l = re.split(r"[:=：\s]+", l)[-1].strip()
                if len(l) >= 24 and l != ak_id:
                    ak_secret = l
                    break
        return ("aksk", (ak_id, ak_secret)) if ak_secret else (None, None)

    return "unknown", raw


def mask(s, keep=4):
    if not s:
        return "<empty>"
    if len(s) <= keep * 2:
        return s[:keep] + "*" * (len(s) - keep)
    return s[:keep] + "*" * (len(s) - keep * 2) + s[-keep:]


# ------------------------------------------------------------------ 签名
def _pct(s):
    return urllib.parse.quote(str(s), safe="~")


def acs3_call(ak_id, ak_secret, host, action, version, params=None,
              body=None, method="POST", timeout=20):
    """ACS3-HMAC-SHA256 签名调用 POP OpenAPI（RPC 风格，参数进 query）。"""
    params = dict(params or {})
    params.setdefault("Action", action)
    params.setdefault("Version", version)
    params.setdefault("Format", "JSON")

    qs = "&".join("%s=%s" % (_pct(k), _pct(params[k]))
                  for k in sorted(params))
    body_bytes = b"" if body is None else body.encode("utf-8")
    body_hash = hashlib.sha256(body_bytes).hexdigest()

    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    nonce = str(uuid.uuid4())

    headers = {
        "host": host,
        "x-acs-action": action,
        "x-acs-version": version,
        "x-acs-date": now,
        "x-acs-signature-nonce": nonce,
        "x-acs-content-sha256": body_hash,
    }
    if body is not None:
        headers["content-type"] = "application/json"

    signed_headers = ";".join(sorted(headers))
    canon_headers = "".join("%s:%s\n" % (k, headers[k]) for k in sorted(headers))

    canonical = "\n".join([method, "/", qs, canon_headers, signed_headers, body_hash])
    sts = "ACS3-HMAC-SHA256\n" + hashlib.sha256(canonical.encode("utf-8")).hexdigest()
    sig = hmac.new(ak_secret.encode("utf-8"), sts.encode("utf-8"),
                   hashlib.sha256).hexdigest()

    headers["Authorization"] = (
        "ACS3-HMAC-SHA256 Credential=%s,SignedHeaders=%s,Signature=%s"
        % (ak_id, signed_headers, sig))
    headers["User-Agent"] = UA

    url = "https://%s/?%s" % (host, qs)
    req = urllib.request.Request(url, data=body_bytes if body is not None else None,
                                 headers=headers, method=method)
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
    try:
        with opener.open(req, timeout=timeout) as r:
            txt = r.read().decode("utf-8", "replace")
            return r.status, txt
    except urllib.error.HTTPError as e:
        return e.code, e.read().decode("utf-8", "replace")
    except Exception as e:
        return -1, "%s: %s" % (type(e).__name__, e)


def show(tag, code, txt):
    print("[%s] HTTP %s" % (tag, code))
    try:
        d = json.loads(txt)
        print(json.dumps(d, ensure_ascii=False, indent=1)[:1500])
        return d
    except Exception:
        print(txt[:800])
        return None


# ------------------------------------------------------------------ 主流程
def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--save", action="store_true", help="铸到 API-KEY 就写回 dashscope.txt")
    ap.add_argument("--balance", action="store_true", help="只查账户余额后退出")
    ap.add_argument("--bill", nargs="?", const="", default=None,
                    help="查当月账单明细（可指定账期，如 --bill 2026-10）")
    ap.add_argument("--region", default="cn-beijing")
    args = ap.parse_args()

    kind, cred = load_credential()
    if args.bill is not None:
        if kind != "aksk":
            print("没有 AccessKey，无法查账单")
            return 2
        cycle = args.bill or datetime.now().strftime("%Y-%m")
        code, txt = acs3_call(cred[0], cred[1], "business.aliyuncs.com",
                              "QueryBill", "2017-12-14",
                              params={"BillingCycle": cycle}, timeout=25)
        d = json.loads(txt) if txt.startswith("{") else {}
        items = (((d.get("Data") or {}).get("Items") or {}).get("Item") or [])
        print("账期 %s  共 %d 条" % (cycle, len(items)))
        tot = 0.0
        for it in items:
            amt = float(it.get("PretaxGrossAmount") or 0)
            tot += amt
            print("  %s ~ %s  %-22s %8.2f %s  %s"
                  % (it.get("UsageStartTime"), it.get("UsageEndTime"),
                     it.get("ProductDetail") or it.get("ProductName"),
                     amt, it.get("Currency"), it.get("Status")))
        print("  合计 %.2f 元" % tot)
        return 0

    kind, cred = load_credential()
    if args.balance:
        if kind != "aksk":
            print("没有 AccessKey，无法查余额")
            return 2
        code, txt = acs3_call(cred[0], cred[1], "business.aliyuncs.com",
                              "QueryAccountBalance", "2017-12-14")
        d = json.loads(txt) if txt.startswith("{") else {}
        dat = d.get("Data") or {}
        print("可用余额 %s %s（现金 %s / 信用 %s）" % (
            dat.get("AvailableAmount"), dat.get("Currency", ""),
            dat.get("AvailableCashAmount"), dat.get("CreditAmount")))
        return 0

    kind, cred = load_credential()
    print("凭据判定：%s" % kind)
    if kind == "apikey":
        print("  已是 API-KEY：%s" % mask(cred))
        print("  直接用 imgrouter --selftest 即可，本脚本无需运行。")
        return 0
    if kind != "aksk":
        print("  无法识别内容，请检查文件格式（应为 sk-... 或 LTAI... + Secret）")
        return 2

    ak_id, ak_secret = cred
    print("  AccessKey ID : %s (len=%d)" % (mask(ak_id), len(ak_id)))
    print("  Secret       : %s (len=%d)" % (mask(ak_secret), len(ak_secret)))
    print("  注意：AK/SK 不是百炼 API-KEY，模型调用必须用 sk- 开头的 KEY。")
    print()

    # --- 1. 余额
    print("=" * 64)
    print("1) BSS QueryAccountBalance（账户余额）")
    code, txt = acs3_call(ak_id, ak_secret, "business.aliyuncs.com",
                          "QueryAccountBalance", "2017-12-14")
    d = show("balance", code, txt)
    if d and d.get("Data"):
        dat = d["Data"]
        print("  -> 可用余额 %s %s / 现金 %s / 信用 %s" % (
            dat.get("AvailableAmount"), dat.get("Currency", ""),
            dat.get("AvailableCashAmount"), dat.get("CreditAmount")))

    # --- 2. 已有 API-KEY
    print()
    print("=" * 64)
    print("2) 百炼 ListApiKeys（看是否已有可用 KEY）")
    for act, ver, body in (("ListApiKeys", "2023-12-29", None),
                           ("ListApiKeys", "2024-08-30", None)):
        code, txt = acs3_call(ak_id, ak_secret, "bailian.%s.aliyuncs.com" % args.region,
                              act, ver, params={"PageNumber": 1, "PageSize": 20})
        d = show("list %s" % ver, code, txt)
        if d and d.get("Success"):
            break

    # --- 3. 铸造新 KEY
    print()
    print("=" * 64)
    print("3) 百炼 CreateApiKey（尝试直接铸一个 sk- KEY）")
    newkey = None
    for ver in ("2023-12-29", "2024-08-30"):
        for body in ('{}', '{"description":"ggc-t1-redraw"}',
                     '{"description":"ggc-t1-redraw","workspace_id":""}'):
            code, txt = acs3_call(ak_id, ak_secret,
                                  "bailian.%s.aliyuncs.com" % args.region,
                                  "CreateApiKey", ver, body=body)
            d = show("create %s %s" % (ver, body[:24]), code, txt)
            if code == 200 and d:
                cand = (d.get("Data") or {}).get("api_key") or d.get("api_key")
                if cand:
                    newkey = cand
                    break
        if newkey:
            break

    if newkey:
        print()
        print("  *** 铸造成功：%s ***" % mask(newkey, 6))
        if args.save:
            open(DASH_FILE, "w", encoding="utf-8").write(newkey + "\n")
            print("  已写回 .secrets/dashscope.txt")
        else:
            print("  未写回（加 --save 可自动写入）")
        return 0

    print()
    print("结论：AK/SK 可用，但没能通过 OpenAPI 铸出 API-KEY（多半是 RAM 用户缺权限）。")
    print("      请到百炼控制台 → API-KEY 管理 → 创建，把 sk-... 贴进 .secrets/dashscope.txt。")
    return 1


if __name__ == "__main__":
    sys.exit(main())
