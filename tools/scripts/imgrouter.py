# -*- coding: utf-8 -*-
"""多通道图片生成后端：阿里云百炼 / Google AI Studio / 魔搭 / 硅基流动。

为什么要这一层
--------------
单家免费额度撑不住 160 张 T1，而每家的免费额度都是「每天重置、用完就拒」。
所以做成一个带账本的调度器：按顺序试，某家当天额度用尽就打上标记、当天不再碰，
自动落到下一家。第二天账本翻页，全部复活。

    python imgrouter.py --status          # 今天各家用了多少、谁被打上了额度耗尽
    python imgrouter.py --selftest        # 每家各画一张，验证 key 和链路（会消耗额度）
    python imgrouter.py --reset           # 清空今天的标记（额度提前重置时用）

通道与密钥（密钥文件里只放令牌，不要引号空格）
--------------
    dashscope    .secrets/dashscope.txt   或 $DASHSCOPE_API_KEY
    google       .secrets/google.txt      或 $GOOGLE_API_KEY / $GEMINI_API_KEY
    modelscope   .secrets/modelscope.txt  或 $MODELSCOPE_API_KEY
    siliconflow  .secrets/siliconflow.txt 或 $SILICONFLOW_API_KEY（收费，兜底）

顺序默认 dashscope → google → modelscope → siliconflow，可用 --backend 或
环境变量 IMG_BACKEND 覆盖（逗号分隔）。

各家接口差异（已核对官方文档）
----------------------------
* 百炼 qwen-image：**同步**返回，图片是 24 小时有效的 OSS URL，必须立刻下载。
  输入图支持 base64 data URI，不用图床。参数走 parameters{size,negative_prompt,...}。
* Google Gemini 图像：同步，返回 inlineData 的 base64，无水印（只有不可见 SynthID）。
  参数走 generationConfig.responseModalities=["IMAGE"]。
* 魔搭：**异步**，提交拿 task_id 再轮询 /v1/tasks/{id}。
* 硅基流动：同步，右下角有「AI生成」水印，必须 strip_watermark。
"""
import argparse
import base64
import io
import json
import os
import socket
import sys
import time
import urllib.error
import urllib.parse
import urllib.request

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from PIL import Image, ImageDraw  # noqa: E402

from ggc_assets import PROJECT  # noqa: E402

SECRETS = os.path.join(PROJECT, ".secrets")
LEDGER = os.path.join(SECRETS, "quota.json")
PROXY_FILE = os.path.join(SECRETS, "proxy.txt")

# ---------------------------------------------------------------- 代理
# 谷歌系域名在本机被 TCP 阻断（DNS 能解析，connect 超时）。用户本机跑着
# v2rayN/xray，混合入站 127.0.0.1:20808 同时支持 SOCKS5 与 HTTP CONNECT，
# 实测用 HTTP 代理走 urllib 可以 200。所以这里只对谷歌系域名套代理，
# 境内通道（魔搭/硅基/百炼）保持直连——否则白绕一圈还可能被出口拦掉。
PROXY_HOSTS = ("googleapis.com", "google.com", "gstatic.com", "googleusercontent.com")
_PROXY_CACHE = {"v": None, "done": False}


def _port_open(host, port, timeout=0.4):
    try:
        with socket.create_connection((host, port), timeout=timeout):
            return True
    except Exception:
        return False


def proxy_url():
    """返回本机可用的 HTTP 代理 URL；没有就返回 None。

    优先级：$IMG_PROXY > .secrets/proxy.txt > 自动探测常见本地混合入站端口。
    """
    if _PROXY_CACHE["done"]:
        return _PROXY_CACHE["v"]
    _PROXY_CACHE["done"] = True
    cand = (os.environ.get("IMG_PROXY") or "").strip()
    if not cand and os.path.isfile(PROXY_FILE):
        try:
            cand = open(PROXY_FILE, encoding="utf-8").read().strip()
        except Exception:
            cand = ""
    if not cand:
        for p in (20808, 10809, 7890, 7897, 1080):
            if _port_open("127.0.0.1", p):
                cand = "http://127.0.0.1:%d" % p
                break
    _PROXY_CACHE["v"] = cand or None
    return _PROXY_CACHE["v"]


def _open(req, timeout, force_proxy=None):
    """按域名决定是否走代理的 urlopen。

    force_proxy: True 强制走、False 强制直连、None 按 PROXY_HOSTS 判断。
    """
    host = (urllib.parse.urlsplit(req.full_url).hostname or "").lower()
    if force_proxy is None:
        need = any(host == h or host.endswith("." + h) for h in PROXY_HOSTS)
    else:
        need = bool(force_proxy)
    p = proxy_url() if need else None
    if p:
        op = urllib.request.build_opener(
            urllib.request.ProxyHandler({"http": p, "https": p}))
    else:
        # 显式清空代理：避免继承外部 HTTPS_PROXY（本机默认指向沙箱 5006，会把谷歌掐成 502）
        op = urllib.request.build_opener(urllib.request.ProxyHandler({}))
    return op.open(req, timeout=timeout)

# 顺序原则：能直接吃本地图的排前面，需要额外条件的往后。
# 2026-10-26 变更：百炼已从默认顺序移除。原因两条：
#   1) `qwen-image-edit` 这个模型 ID 已经下线（2026 年图生图并入 qwen-image-2.0/3.0 系列），
#      "新用户 100 张免费额度"是过时信息，实测 qwen-image-2.0-pro 直接扣 0.50 元/张，
#      且 DeductedByCoupons=0（没有任何免费额度抵扣）。
#   2) 用户明确要求：免费额度用完/没有免费额度时，不再使用阿里云。
# 要临时启用百炼，用 --backend dashscope 显式指定，并加 --paid-ok。
ORDER_DEFAULT = ["modelscope", "google", "siliconflow"]

MODEL_CANDIDATES = {
    # 当前有效的百炼图像模型（qwen-image-edit 已下线）。全部为付费模型。
    "dashscope": ["qwen-image-3.0"],
    "google": ["gemini-2.5-flash-image", "gemini-3-pro-image",
               "gemini-2.5-flash-image-preview"],
    # 2026-10-27 实测：2511 能**守住构图**换画风（2509 不行——要么糊成色块，
    # 要么直接另画一张）。所以 2511 排第一，2509 只作兜底。
    "modelscope": ["Qwen/Qwen-Image-Edit-2511", "Qwen/Qwen-Image-Edit-2509",
                   "Qwen/Qwen-Image-Edit"],
    "siliconflow": ["Qwen/Qwen-Image-Edit-2509"],
}

# 会真金白银扣费的模型。默认拒绝调用，除非 IMG_ALLOW_PAID=1 或 --paid-ok。
PAID_MODELS = {"qwen-image-2.0", "qwen-image-2.0-pro", "qwen-image-3.0",
               "qwen-image-3.0-pro", "qwen-image", "wan2.7-image",
               "wan2.7-image-pro", "wanx2.1-t2i-turbo", "wanx2.1-t2i-plus"}

# 命中这些字样就判定为「额度/余额问题」，打标记换下一家；其余错误只记不改状态
QUOTA_HINTS = ("quota", "insufficient", "balance", "arrear", "arrearage",
               "exhaust", "free tier", "freetier", "throttl", "rate limit",
               "resource_exhausted", "limit exceeded", "not enough", "欠费",
               "额度", "余额")

# 密钥本身有问题时的可读原因（token() 里填，generate() 里报）
KEY_HINTS = {}


# ---------------------------------------------------------------- 密钥与账本
def token(name):
    envs = {"dashscope": ["DASHSCOPE_API_KEY"],
            "google": ["GOOGLE_API_KEY", "GEMINI_API_KEY"],
            "modelscope": ["MODELSCOPE_API_KEY"],
            "siliconflow": ["SILICONFLOW_API_KEY"]}[name]
    for e in envs:
        v = (os.environ.get(e) or "").strip()
        if v:
            return _check_key(name, v)
    p = os.path.join(SECRETS, name + ".txt")
    if os.path.isfile(p):
        for line in open(p, encoding="utf-8"):
            line = line.strip().strip('"').strip("'")
            if line and not line.startswith("#"):
                return _check_key(name, line)
    return None


def _check_key(name, v):
    """挡掉「把阿里云 AccessKey 当 API-KEY 用」这类错误，避免发畸形 header。"""
    if v.startswith("LTAI"):
        KEY_HINTS[name] = ("凭据是阿里云 AccessKey ID，不是模型 API-KEY；"
                           "需在百炼控制台创建 sk- 开头的 API-KEY")
        return None
    if name == "dashscope" and not v.startswith("sk-"):
        KEY_HINTS[name] = "百炼 API-KEY 应以 sk- 开头，当前值不像有效 KEY"
        return None
    return v


def today():
    return time.strftime("%Y-%m-%d")


def load_ledger():
    if os.path.isfile(LEDGER):
        try:
            return json.load(open(LEDGER, encoding="utf-8"))
        except Exception:
            pass
    return {}


def save_ledger(d):
    os.makedirs(SECRETS, exist_ok=True)
    json.dump(d, open(LEDGER, "w", encoding="utf-8"), ensure_ascii=False, indent=1)


def day_state(d, name):
    """今天这一家的状态，缺省建一条。"""
    t = d.setdefault(today(), {})
    return t.setdefault(name, {"ok": 0, "fail": 0, "net": 0, "exhausted": False,
                               "last_error": None, "model": None})


def mark_ok(name, model):
    d = load_ledger()
    s = day_state(d, name)
    s["ok"] += 1
    s["model"] = model
    s["net"] = 0          # 通了就重置网络故障计数
    save_ledger(d)


def mark_fail(name, err, quota, net=False):
    d = load_ledger()
    s = day_state(d, name)
    s["fail"] += 1
    if net:
        s["net"] = s.get("net", 0) + 1
    s["last_error"] = str(err)[:300]
    if quota:
        s["exhausted"] = True
    save_ledger(d)


def is_network_err(err):
    """区分「连不上」与「密钥/参数错」——前者不该反复重试烧时间。"""
    low = str(err).lower()
    return any(h in low for h in ("urlerror", "tunnel connection failed",
                                  "timed out", "timeout", "10060", "10061",
                                  "getaddrinfo", "name or service not known",
                                  "connection refused", "connection reset",
                                  "ssl", "unreachable", "no route"))


def is_exhausted(name):
    d = load_ledger()
    return bool(day_state(d, name).get("exhausted"))


def is_blocked(name):
    """当天不再尝试这一家的两种情形：额度耗尽 / 连续网络不可达。"""
    s = day_state(load_ledger(), name)
    if s.get("exhausted"):
        return "额度耗尽"
    if s.get("net", 0) >= 3 and s.get("ok", 0) == 0:
        return "网络不可达（连续 %d 次）" % s["net"]
    return None


# ---------------------------------------------------------------- HTTP 小工具
class QuotaError(RuntimeError):
    pass


class ApiError(RuntimeError):
    pass


def looks_like_quota(text):
    low = str(text).lower()
    return any(h in low for h in QUOTA_HINTS)


def post_json(url, body, headers, timeout=240, tries=2):
    data = json.dumps(body).encode()
    last = None
    for i in range(tries):
        req = urllib.request.Request(url, data=data, method="POST")
        for k, v in headers.items():
            req.add_header(k, v)
        req.add_header("Content-Type", "application/json")
        try:
            with _open(req, timeout) as r:
                return json.loads(r.read().decode())
        except urllib.error.HTTPError as e:
            txt = e.read().decode("utf-8", "replace")
            last = "HTTP %d %s" % (e.code, txt[:400])
            if e.code in (429, 402) or looks_like_quota(txt):
                raise QuotaError(last)
            if e.code in (500, 502, 503, 504):
                time.sleep(2 ** i)
                continue
            raise ApiError(last)
        except QuotaError:
            raise
        except Exception as e:
            last = repr(e)
            time.sleep(2 ** i)
    raise ApiError("重试 %d 次仍失败: %s" % (tries, last))


def get_json(url, headers, timeout=120):
    req = urllib.request.Request(url, method="GET")
    for k, v in headers.items():
        req.add_header(k, v)
    try:
        with _open(req, timeout) as r:
            return json.loads(r.read().decode())
    except urllib.error.HTTPError as e:
        txt = e.read().decode("utf-8", "replace")
        msg = "HTTP %d %s" % (e.code, txt[:400])
        if e.code in (429, 402) or looks_like_quota(txt):
            raise QuotaError(msg)
        raise ApiError(msg)


def fetch_bytes(url, timeout=180):
    req = urllib.request.Request(url, method="GET")
    with _open(req, timeout) as r:
        return r.read()


# ---------------------------------------------------------------- 输入图准备
def data_uri(path, size="1024x1024"):
    """把本地图变成 data:image/png;base64。

    沿用 sfimg.b64img 的两条经验：透明区不能压成白（否则模型把白当成内容），
    长宽比要保住（否则模型自己补一条边）。所以先按不透明像素的中位色压平，
    再等比缩放居中补边。
    """
    im = Image.open(path).convert("RGBA")
    px = list(im.getdata())
    opaque = [p[:3] for p in px if p[3] > 200]
    bg = tuple(sorted(c[i] for c in opaque)[len(opaque) // 2] for i in range(3)) \
        if opaque else (110, 105, 100)

    flat = Image.new("RGB", im.size, bg)
    flat.paste(im, (0, 0), im)

    tw, th = (int(v) for v in size.lower().replace("*", "x").split("x"))
    scale = min(tw / flat.width, th / flat.height)
    nw, nh = max(1, round(flat.width * scale)), max(1, round(flat.height * scale))
    flat = flat.resize((nw, nh), Image.LANCZOS)
    canvas = Image.new("RGB", (tw, th), bg)
    canvas.paste(flat, ((tw - nw) // 2, (th - nh) // 2))

    buf = io.BytesIO()
    canvas.save(buf, "PNG")
    return "data:image/png;base64," + base64.b64encode(buf.getvalue()).decode()


# ---------------------------------------------------------------- 各通道
def gen_dashscope(job, model=None):
    """阿里云百炼 qwen-image 系列：同步，返回 24h 有效的 URL。"""
    key = token("dashscope")
    if not key:
        raise ApiError("没有 dashscope 密钥")
    model = model or os.environ.get("DASHSCOPE_IMAGE_MODEL") or MODEL_CANDIDATES["dashscope"][0]
    if model in PAID_MODELS and os.environ.get("IMG_ALLOW_PAID") != "1":
        raise ApiError(
            "%s 是付费模型（约 0.5 元/张，无免费额度）。默认拒绝调用；"
            "确实要用请加 --paid-ok 或设 IMG_ALLOW_PAID=1" % model)
    size = (job.get("size") or "1024x1024").replace("x", "*")
    content = []
    if job.get("image"):
        content.append({"image": data_uri(job["image"], size.replace("*", "x"))})
    content.append({"text": job["prompt"]})
    params = {"n": 1, "watermark": False, "size": size,
              "prompt_extend": False}
    if job.get("negative_prompt"):
        params["negative_prompt"] = job["negative_prompt"][:500]
    if job.get("seed") is not None:
        params["seed"] = int(job["seed"]) % 2147483647

    body = {"model": model,
            "input": {"messages": [{"role": "user", "content": content}]},
            "parameters": params}
    url = ("https://dashscope.aliyuncs.com/api/v1/services/aigc/"
           "multimodal-generation/generation")
    d = post_json(url, body, {"Authorization": "Bearer " + key})

    ch = ((d.get("output") or {}).get("choices") or [])
    img_url = None
    for c in ch:
        for part in ((c.get("message") or {}).get("content") or []):
            if part.get("image"):
                img_url = part["image"]
                break
        if img_url:
            break
    if not img_url:
        msg = json.dumps(d, ensure_ascii=False)[:400]
        if looks_like_quota(msg):
            raise QuotaError(msg)
        raise ApiError("返回里没有图片: " + msg)
    raw = fetch_bytes(img_url)
    return Image.open(io.BytesIO(raw)).convert("RGB"), model, None


_ASPECTS = ["1:1", "2:3", "3:2", "3:4", "4:3", "4:5", "5:4", "9:16", "16:9", "21:9"]


def best_aspect(w, h):
    """从 Gemini 允许的比例里挑最接近的一个（超出范围会 400）。"""
    if not w or not h:
        return "1:1"
    target = float(w) / float(h)
    best, bd = "1:1", 1e9
    for a in _ASPECTS:
        aw, ah = (float(v) for v in a.split(":"))
        d = abs(target - aw / ah)
        if d < bd:
            best, bd = a, d
    return best


def gen_google(job, model=None):
    """Google AI Studio Gemini 图像：同步，返回 inlineData 的 base64。"""
    key = token("google")
    if not key:
        raise ApiError("没有 google 密钥")
    model = model or os.environ.get("GOOGLE_IMAGE_MODEL") or MODEL_CANDIDATES["google"][0]
    parts = []
    if job.get("image"):
        uri = data_uri(job["image"], job.get("size") or "1024x1024")
        parts.append({"inline_data": {"mime_type": "image/png",
                                      "data": uri.split(",", 1)[1]}})
    prompt = job["prompt"]
    if job.get("negative_prompt"):
        prompt += "\n避免出现：" + job["negative_prompt"][:400]
    parts.append({"text": prompt})

    # 比例：优先 job["aspect"]，其次按 size / 输入图算最接近的合法比例。
    # Gemini 只接受固定的几档，超出会 400，所以必须"就近取"而不是照搬。
    asp = job.get("aspect")
    if not asp:
        if job.get("size"):
            try:
                w, h = (int(v) for v in str(job["size"]).lower().replace("*", "x").split("x"))
                asp = best_aspect(w, h)
            except Exception:
                asp = None
        elif job.get("image"):
            try:
                with Image.open(job["image"]) as _im:
                    asp = best_aspect(_im.width, _im.height)
            except Exception:
                asp = None

    body = {"contents": [{"parts": parts}],
            "generationConfig": {"responseModalities": ["IMAGE"]}}
    if asp:
        body["generationConfig"]["imageConfig"] = {"aspectRatio": asp}
    url = ("https://generativelanguage.googleapis.com/v1beta/models/"
           "%s:generateContent" % model)

    def _call(b):
        return post_json(url, b, {"x-goog-api-key": key}, timeout=180)

    try:
        d = _call(body)
    except ApiError as e:
        msg = str(e)
        if "responseModalit" in msg:
            # 有些模型不接受只返回 IMAGE，退回 TEXT+IMAGE
            body["generationConfig"]["responseModalities"] = ["TEXT", "IMAGE"]
            d = _call(body)
        elif "imageConfig" in msg or "aspectRatio" in msg or "image_size" in msg:
            # 老模型不认 imageConfig，去掉重试
            body["generationConfig"].pop("imageConfig", None)
            d = _call(body)
        else:
            raise

    cands = d.get("candidates") or []
    for c in cands:
        for p in ((c.get("content") or {}).get("parts") or []):
            inl = p.get("inlineData") or p.get("inline_data")
            if inl and inl.get("data"):
                raw = base64.b64decode(inl["data"])
                return Image.open(io.BytesIO(raw)).convert("RGB"), model, None
    msg = json.dumps(d, ensure_ascii=False)[:400]
    if looks_like_quota(msg):
        raise QuotaError(msg)
    raise ApiError("返回里没有图片: " + msg)


def public_url_for(path):
    """把本地图映射成公网 URL。

    魔搭**只认公网可达的 image_url**（实测 2026-10-26）：
      - base64 data URI（字符串或数组）会被**静默忽略**，模型退化成纯文生图；
      - 境外免费图床（uguu / catbox / 0x0 / tmpfiles）阿里后端抓不到，同样被忽略；
      - 只有阿里自家 OSS 之类的境内可达 URL 才真正生效。
    所以要接魔搭，必须先把图放到境内可访问的位置，用 IMG_PUBLIC_BASE 指过去：
      IMG_PUBLIC_BASE=https://my-bucket.oss-cn-hangzhou.aliyuncs.com/lineart
    映射规则：IMG_PUBLIC_BASE + "/" + 文件名。
    """
    base = (os.environ.get("IMG_PUBLIC_BASE") or "").strip().rstrip("/")
    if not base:
        return None
    return base + "/" + os.path.basename(path)


def gen_modelscope(job, model=None):
    """魔搭 API-Inference：异步，提交拿 task_id 再轮询。

    实测（2026-10-26）四个必须的点：
      1) 提交时必须带 `X-ModelScope-Async-Mode: true`，否则拿到的不是真任务；
      2) 轮询时必须带 `X-ModelScope-Task-Type: image_generation`；
      3) 结果图在 `output_images`（URL 列表），**不是** `output.images`；
      4) `image_url` 必须是**公网 URL 或 data URI，且要包成 list**。字符串形式的
         data URI 会被直接丢弃（报 `image_url is required`），裸 base64 报
         `not a valid image URL or base64 data`。包成 list 的 data URI 实测可用，
         所以**不需要图床**（2026-10-27 纠正了早先"不认 base64"的结论）。
    提交响应里的 task_status 是占位值（会直接写 SUCCEED），不可信，以轮询为准。
    实测一次约 65–75 秒。
    """
    key = token("modelscope")
    if not key:
        raise ApiError("没有 modelscope 密钥")
    model = model or os.environ.get("MODELSCOPE_IMAGE_MODEL") or MODEL_CANDIDATES["modelscope"][0]
    hdr = {"Authorization": "Bearer " + key,
           "X-ModelScope-Async-Mode": "true"}
    poll_hdr = dict(hdr)
    poll_hdr["X-ModelScope-Task-Type"] = "image_generation"
    body = {"model": model, "prompt": job["prompt"], "n": 1}
    if job.get("image") or job.get("image_url_public"):
        # 实测（2026-10-27）：`image_url` **必须是列表**。
        #   ["data:image/png;base64,..."]  -> 接受，正常出图（构图跟着输入走）
        #   "data:image/png;base64,..."    -> 400 image_url is required（字符串被丢弃）
        #   "<裸 base64>"                  -> 400 not a valid image URL or base64 data
        # 所以这里统一包成 list；有公网 URL 就优先用 URL（更快，不用传大 body）。
        url = job.get("image_url_public")
        if url:
            body["image_url"] = url if isinstance(url, list) else [url]
        else:
            body["image_url"] = [data_uri(job["image"],
                                          job.get("size") or "1024x1024")]
    if job.get("negative_prompt"):
        body["negative_prompt"] = job["negative_prompt"]
    # 实测（2026-10-27）：不传 size 时固定输出 760x1280 竖幅，**完全无视输入图比例**，
    # 对"按层切回"是致命的。size 必须是 "WxH"（用 * 会 400 size format should be WxH）。
    if job.get("size"):
        body["size"] = str(job["size"]).replace("*", "x")

    d = post_json("https://api-inference.modelscope.cn/v1/images/generations",
                  body, hdr)
    task = d.get("task_id") or (d.get("data") or {}).get("task_id")
    if not task:
        msg = json.dumps(d, ensure_ascii=False)[:400]
        if looks_like_quota(msg):
            raise QuotaError(msg)
        raise ApiError("没拿到 task_id: " + msg)

    deadline = time.time() + 420
    while time.time() < deadline:
        time.sleep(4)
        r = get_json("https://api-inference.modelscope.cn/v1/tasks/%s" % task,
                     poll_hdr)
        st = (r.get("task_status") or r.get("status") or "").upper()
        if st in ("SUCCEED", "SUCCESS", "SUCCEEDED"):
            # 实测字段名是 output_images；保留其它可能的位置作兜底
            imgs = (r.get("output_images")
                    or (r.get("output") or {}).get("images")
                    or r.get("images") or [])
            if not imgs:
                raise ApiError("任务成功但没有图片: " + json.dumps(r, ensure_ascii=False)[:300])
            u = imgs[0].get("url") if isinstance(imgs[0], dict) else imgs[0]
            return Image.open(io.BytesIO(fetch_bytes(u))).convert("RGB"), model, None
        if st in ("FAILED", "FAIL", "CANCELED", "ERROR"):
            msg = json.dumps(r, ensure_ascii=False)[:400]
            if looks_like_quota(msg):
                raise QuotaError(msg)
            raise ApiError("任务失败: " + msg)
    raise ApiError("轮询超时（>420s）")


def gen_siliconflow(job, model=None):
    """硅基流动：沿用 sfimg 的实现（含水印擦除与 alpha 重蒙版）。"""
    import sfimg
    j = dict(job)
    if model:
        j["model"] = model
    j.setdefault("model", MODEL_CANDIDATES["siliconflow"][0])
    rec = sfimg.generate(j, j.pop("_outdir"))
    return Image.open(rec["file"]).convert("RGB"), rec["model"], rec["file"]


BACKENDS = {"dashscope": gen_dashscope, "google": gen_google,
            "modelscope": gen_modelscope, "siliconflow": gen_siliconflow}


# ---------------------------------------------------------------- 调度
def order(override=None):
    o = override or os.environ.get("IMG_BACKEND") or ",".join(ORDER_DEFAULT)
    return [x.strip() for x in o.split(",") if x.strip()]


def generate(job, outdir):
    """按顺序试各家；额度耗尽的当天跳过。返回 rec（含 backend 字段）。"""
    os.makedirs(outdir, exist_ok=True)
    tried = []
    for name in order(job.get("backend")):
        fn = BACKENDS.get(name)
        if fn is None:
            continue
        if not token(name):
            tried.append("%s: %s" % (name, KEY_HINTS.get(name, "无密钥")))
            continue
        blocked = is_blocked(name)
        if blocked:
            tried.append("%s: 今天%s" % (name, blocked))
            continue
        t0 = time.time()
        try:
            j = dict(job)
            j["_outdir"] = outdir
            im, model, reuse = fn(j)
        except QuotaError as e:
            mark_fail(name, e, quota=True)
            tried.append("%s: 额度耗尽 -> %s" % (name, str(e)[:120]))
            print("    [%s] 额度耗尽，切下一家：%s" % (name, str(e)[:140]))
            continue
        except ApiError as e:
            mark_fail(name, e, quota=False, net=is_network_err(e))
            tried.append("%s: %s" % (name, str(e)[:120]))
            print("    [%s] 失败，切下一家：%s" % (name, str(e)[:140]))
            continue
        except SystemExit as e:      # sfimg 用 SystemExit 报错
            msg = str(e)
            q = looks_like_quota(msg)
            mark_fail(name, msg, quota=q, net=is_network_err(msg))
            tried.append("%s: %s" % (name, msg[:120]))
            print("    [%s] %s，切下一家：%s"
                  % (name, "额度耗尽" if q else "失败", msg[:140]))
            continue

        mark_ok(name, model)
        stem = "%s_%s" % (job["name"], job.get("seed", 0))
        out = os.path.join(outdir, stem + ".png")
        if reuse and os.path.abspath(reuse) != os.path.abspath(out):
            im.save(out)
        elif not reuse:
            im.save(out)
        return {"name": job["name"], "file": out, "model": model,
                "backend": name, "seed": job.get("seed"),
                "size": im.size, "seconds": round(time.time() - t0, 1),
                "prompt": job["prompt"]}

    raise SystemExit("所有通道都不可用：\n  " + "\n  ".join(tried))


# ---------------------------------------------------------------- 命令行
def probe_png(path):
    """自检用的合成白描：一个方框 + 一道斜线，够模型判断「有没有跟线」。"""
    im = Image.new("RGB", (1024, 1024), (250, 246, 238))
    d = ImageDraw.Draw(im)
    d.rectangle([220, 260, 800, 760], outline=(26, 22, 19), width=10)
    d.line([300, 700, 720, 320], fill=(26, 22, 19), width=10)
    im.save(path)
    return path


def follow_check(src, gen):
    """判断这一家「是否跟住了线稿」，而不只是「有没有返回图」。

    这是关键分水岭：
      - 纯文生图模型（如 Kolors）会忽略输入图，自己另画一张 → edge 很低
      - 真正的图像编辑模型会照线稿上色 → edge 高
    """
    try:
        import fidelity as FID
        la = Image.open(src).convert("RGB")
        sc = FID.score(la, gen, la.convert("RGBA"))
        e, p = sc["edge"], sc["pigment"]
        if e >= 0.40 and p >= 0.30:
            return "结构 edge=%.3f pig=%.3f  → 跟住线稿且上了色，可用" % (e, p)
        if e >= 0.40:
            return "结构 edge=%.3f pig=%.3f  → 跟住了但颜色太淡" % (e, p)
        return ("结构 edge=%.3f  → **没跟住线稿**（很可能忽略了输入图，只按文字另画）"
                % e)
    except Exception as e:
        return "结构打分失败：%r" % e


def cmd_status(_a):
    d = load_ledger()
    t = d.get(today(), {})
    print("账本：%s" % LEDGER)
    print("日期：%s\n" % today())
    print("%-12s %-6s %-6s %-16s %s" % ("通道", "成功", "失败", "今日状态", "最后错误"))
    for name in ORDER_DEFAULT:
        s = t.get(name) or {}
        blocked = is_blocked(name)
        state = ("停用:" + blocked) if blocked else ("正常" if s.get("ok") else "未成功")
        print("%-12s %-6s %-6s %-16s %s"
              % (name, s.get("ok", 0), s.get("fail", 0), state,
                 (s.get("last_error") or "")[:60]))
        if not token(name):
            print("%-12s   （%s，会被跳过）"
                  % ("", KEY_HINTS.get(name, "没有密钥")))


def cmd_reset(_a):
    d = load_ledger()
    d.pop(today(), None)
    save_ledger(d)
    print("已清空 %s 的额度标记" % today())


def cmd_selftest(args):
    tmp = os.path.join(PROJECT, "art", "gen", "_selftest")
    os.makedirs(tmp, exist_ok=True)
    src = probe_png(os.path.join(tmp, "probe.png"))
    job = {"name": "selftest", "image": src, "seed": 7,
           "prompt": "把这张白描线稿上色：中国重彩国画，石青石绿朱砂，笔触中等粗细，"
                     "严格保持线稿的轮廓与位置不变",
           "negative_prompt": "文字，水印，签名"}
    print("自检：每家各画一张（会消耗额度）\n")
    for name in order(args.backend):
        if not token(name):
            print("  %-12s 跳过：没有密钥" % name)
            continue
        blocked = is_blocked(name)
        if blocked:
            print("  %-12s 跳过：今天%s" % (name, blocked))
            continue
        t0 = time.time()
        try:
            j = dict(job)
            j["_outdir"] = tmp
            im, model, _ = BACKENDS[name](j)
            out = os.path.join(tmp, "%s.png" % name)
            im.save(out)
            mark_ok(name, model)
            print("  %-12s OK   %-30s %4.0fs  %s"
                  % (name, model, time.time() - t0, os.path.basename(out)))
            # 光「出图」不算通过：必须证明它跟住了线稿。
            # 否则就是 Kolors 那种「忽略输入图、自己另画一张」—— 那会让整条流水线失效。
            print("  %-12s      %s" % ("", follow_check(src, im)))
        except (QuotaError, ApiError) as e:
            q = isinstance(e, QuotaError) or looks_like_quota(str(e))
            mark_fail(name, e, quota=q, net=is_network_err(e))
            print("  %-12s %s  %s" % (name, "额度耗尽" if q else "失败",
                                      str(e)[:150]))
        except SystemExit as e:          # sfimg 用 SystemExit 报错
            q = looks_like_quota(str(e))
            mark_fail(name, e, quota=q, net=is_network_err(e))
            print("  %-12s %s  %s" % (name, "额度耗尽" if q else "失败",
                                      str(e)[:150]))
    print("\n自检图在 %s" % tmp)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--status", action="store_true")
    ap.add_argument("--reset", action="store_true")
    ap.add_argument("--selftest", action="store_true")
    ap.add_argument("--backend", help="覆盖顺序，逗号分隔，如 dashscope,google")
    ap.add_argument("--paid-ok", action="store_true",
                    help="允许调用付费模型（默认拒绝，防止误扣费）")
    args = ap.parse_args()
    if args.paid_ok:
        os.environ["IMG_ALLOW_PAID"] = "1"
    if args.status:
        return cmd_status(args)
    if args.reset:
        return cmd_reset(args)
    if args.selftest:
        return cmd_selftest(args)
    ap.print_help()


if __name__ == "__main__":
    main()
