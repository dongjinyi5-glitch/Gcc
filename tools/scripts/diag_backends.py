r"""诊断四家通道：分离「密钥问题」与「网络问题」。

每家各打一个最轻量的探针请求：
  - dashscope   : 国内站 + 国际站各打一次（key 有区域归属）
  - google      : 直连 + 走系统代理各打一次（502 是代理隧道，不是 key）
  - modelscope  : 打 /v1/models 与一次生成，看 401 的具体原因
  - siliconflow : 只查余额，不打图

用法：
  python tools/scripts/diag_backends.py
"""
import io
import json
import os
import sys
import urllib.error
import urllib.request

PROJECT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.join(PROJECT, "tools", "scripts"))


def tok(name):
    p = os.path.join(PROJECT, ".secrets", name + ".txt")
    if not os.path.exists(p):
        return None
    t = open(p, encoding="utf-8").read().strip()
    return t or None


def call(url, method="GET", body=None, headers=None, proxy=None, timeout=40):
    """proxy=None -> 直连；proxy='env' -> 走系统代理。返回 (状态, 前 300 字)。"""
    if proxy == "env":
        op = urllib.request.build_opener()
    else:
        op = urllib.request.build_opener(urllib.request.ProxyHandler({}))
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(url, data=data, method=method)
    for k, v in (headers or {}).items():
        req.add_header(k, v)
    if data:
        req.add_header("Content-Type", "application/json")
    try:
        with op.open(req, timeout=timeout) as r:
            return r.status, r.read()[:300].decode("utf-8", "replace")
    except urllib.error.HTTPError as e:
        return e.code, e.read()[:300].decode("utf-8", "replace")
    except Exception as e:
        return None, repr(e)[:200]


def line(tag, res):
    st, msg = res
    print("  %-34s %-5s %s" % (tag, st if st else "ERR", msg.replace("\n", " ")[:180]))


def main():
    print("=" * 78)
    print("1) 阿里云百炼 dashscope")
    k = tok("dashscope")
    if not k:
        print("   没有密钥")
    else:
        h = {"Authorization": "Bearer " + k}
        for tag, base in (("国内站 dashscope.aliyuncs.com", "https://dashscope.aliyuncs.com"),
                          ("国际站 dashscope-intl", "https://dashscope-intl.aliyuncs.com")):
            line(tag + " /compatible-mode/models",
                 call(base + "/compatible-mode/v1/models", headers=h))
        # 生成接口的最小探针（不传图，纯文本模型，成本≈0）
        body = {"model": "qwen-image-edit", "input": {"messages": [{"role": "user",
                "content": [{"text": "测试"}]}]}, "parameters": {"n": 1, "size": "1024*1024"}}
        line("国内站 生成探针", call(
            "https://dashscope.aliyuncs.com/api/v1/services/aigc/multimodal-generation/generation",
            "POST", body, h))

    print("\n2) Google AI Studio")
    k = tok("google")
    if not k:
        print("   没有密钥")
    else:
        h = {"x-goog-api-key": k}
        u = "https://generativelanguage.googleapis.com/v1beta/models"
        line("直连 /models", call(u, headers=h, proxy=None))
        line("走代理 /models", call(u, headers=h, proxy="env"))
        line("直连 生成探针(gemini-2.5-flash-image)", call(
            "https://generativelanguage.googleapis.com/v1beta/models/"
            "gemini-2.5-flash-image:generateContent", "POST",
            {"contents": [{"parts": [{"text": "draw a red square"}]}]}, h, proxy=None))

    print("\n3) 魔搭 ModelScope")
    k = tok("modelscope")
    if not k:
        print("   没有密钥")
    else:
        h = {"Authorization": "Bearer " + k}
        line("直连 /v1/models", call("https://api-inference.modelscope.cn/v1/models",
                                     headers=h, proxy=None))
        line("直连 生成探针", call("https://api-inference.modelscope.cn/v1/images/generations",
                                   "POST", {"model": "Qwen/Qwen-Image-Edit-2509",
                                            "prompt": "test"}, h, proxy=None))

    print("\n4) 硅基流动")
    k = tok("siliconflow")
    if not k:
        print("   没有密钥")
    else:
        line("直连 /v1/user/info", call("https://api.siliconflow.cn/v1/user/info",
                                        headers={"Authorization": "Bearer " + k}, proxy=None))
    print("=" * 78)


if __name__ == "__main__":
    main()
