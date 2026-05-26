"""
内网 API 连通性测试脚本
========================
用途：部署前验证内网 LLM API 是否可达
用法：修改下方 CONFIG 配置，然后 python 内网API测试脚本.py
依赖：仅 Python 标准库（无需安装任何第三方包）
"""

import json
import ssl
import urllib.request
import urllib.error

# ============================================================
#  修改这里的配置
# ============================================================
CONFIG = {
    "url": "http://10.148.105.221:8008/open/router/v1/chat/completions",
    "api_key": "sk-your-key-here",
    "model": "deepseek-v4-flash",
    "timeout": 15,  # 秒
}
# ============================================================


def test_openai_api(config: dict) -> dict:
    """用标准库 urllib 测试 OpenAI 兼容 API（不依赖 openai/httpx 包）"""
    body = json.dumps({
        "model": config["model"],
        "messages": [{"role": "user", "content": "Hi"}],
        "max_tokens": 5,
        "temperature": 0,
    }).encode("utf-8")

    req = urllib.request.Request(
        config["url"],
        data=body,
        headers={
            "Content-Type": "application/json",
            "Authorization": f"Bearer {config['api_key']}",
        },
        method="POST",
    )

    # 不验证 SSL 证书（内网自签证书场景）
    ctx = ssl.create_default_context()
    ctx.check_hostname = False
    ctx.verify_mode = ssl.CERT_NONE

    try:
        resp = urllib.request.urlopen(
            req, timeout=config["timeout"], context=ctx,
        )
        data = json.loads(resp.read().decode("utf-8"))
        content = data.get("choices", [{}])[0].get("message", {}).get("content", "")
        model_name = data.get("model", "unknown")
        return {"success": True, "message": f"连接成功 (模型: {model_name})", "response": content}
    except urllib.error.HTTPError as e:
        body = e.read().decode("utf-8", errors="replace")
        return {"success": False, "message": f"HTTP {e.code}: {body[:300]}"}
    except urllib.error.URLError as e:
        return {"success": False, "message": f"网络错误: {e.reason}"}
    except Exception as e:
        return {"success": False, "message": f"未知错误: {str(e)[:300]}"}


def test_anthropic_api(config: dict) -> dict:
    """用标准库 urllib 测试 Anthropic Messages API"""
    body = json.dumps({
        "model": config["model"],
        "messages": [{"role": "user", "content": "Hi"}],
        "max_tokens": 5,
    }).encode("utf-8")

    req = urllib.request.Request(
        config["url"],
        data=body,
        headers={
            "Content-Type": "application/json",
            "x-api-key": config["api_key"],
            "anthropic-version": "2023-06-01",
        },
        method="POST",
    )

    ctx = ssl.create_default_context()
    ctx.check_hostname = False
    ctx.verify_mode = ssl.CERT_NONE

    try:
        resp = urllib.request.urlopen(
            req, timeout=config["timeout"], context=ctx,
        )
        data = json.loads(resp.read().decode("utf-8"))
        model_name = data.get("model", "unknown")
        parts = [b.get("text", "") for b in data.get("content", []) if b.get("type") == "text"]
        return {"success": True, "message": f"连接成功 (模型: {model_name})", "response": "".join(parts)}
    except urllib.error.HTTPError as e:
        body = e.read().decode("utf-8", errors="replace")
        return {"success": False, "message": f"HTTP {e.code}: {body[:300]}"}
    except urllib.error.URLError as e:
        return {"success": False, "message": f"网络错误: {e.reason}"}
    except Exception as e:
        return {"success": False, "message": f"未知错误: {str(e)[:300]}"}


def detect_api_type(url: str) -> str:
    """根据 URL 路径自动判断协议类型"""
    if "/messages" in url and "/v1/chat/completions" not in url:
        return "anthropic"
    return "openai"


def print_result(name: str, result: dict):
    status = "✓ 成功" if result["success"] else "✗ 失败"
    print(f"  {status} | {result['message']}")
    if not result["success"]:
        print(f"         提示: 检查 API 地址、端口、Key、防火墙规则")


def main():
    print("=" * 60)
    print("  内网 API 连通性测试")
    print("=" * 60)
    print()

    cfg = CONFIG.copy()

    # 自动判断协议类型
    api_type = detect_api_type(cfg["url"])
    print(f"  API 地址 : {cfg['url']}")
    print(f"  模型名称 : {cfg['model']}")
    print(f"  协议类型 : {api_type}")
    print(f"  超时时间 : {cfg['timeout']}s")
    print()

    # 1. TCP 连通性测试
    from urllib.parse import urlparse
    parsed = urlparse(cfg["url"])
    host = parsed.hostname
    port = parsed.port or (443 if parsed.scheme == "https" else 80)
    print(f"[1] TCP 连通性 ({host}:{port})")
    import socket
    try:
        sock = socket.create_connection((host, port), timeout=5)
        sock.close()
        print(f"  ✓ 成功 | {host}:{port} 可达")
    except Exception as e:
        print(f"  ✗ 失败 | 无法连接 {host}:{port} — {e}")
        print("         提示: 检查 IP/端口是否正确、防火墙是否放行")
        return

    # 2. API 协议测试
    print()
    print(f"[2] API 调用测试 ({api_type})")
    if api_type == "anthropic":
        result = test_anthropic_api(cfg)
    else:
        result = test_openai_api(cfg)
    print_result("API", result)

    # 3. 代理检查
    print()
    print("[3] 环境检查")
    import os
    proxy_vars = ["HTTP_PROXY", "HTTPS_PROXY", "http_proxy", "https_proxy", "NO_PROXY", "no_proxy"]
    found = False
    for v in proxy_vars:
        val = os.environ.get(v, "")
        if val:
            print(f"  ⚠ {v} = {val}")
            found = True
    if not found:
        print(f"  ✓ 未检测到代理环境变量")
    else:
        print(f"  提示: 代理可能干扰内网直连，如有问题请清除后重试")

    print()
    print("=" * 60)
    if result["success"]:
        print("  测试通过！API 可正常调用")
    else:
        print("  测试失败！请根据上述提示排查")
    print("=" * 60)


if __name__ == "__main__":
    main()
