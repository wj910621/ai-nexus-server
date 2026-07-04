"""
测试本地 Ollama LLM 对话
"""

import json
import urllib.request
import urllib.error

MODEL = "qwen2.5:7b-instruct-q4_K_M"
BASE_URL = "http://localhost:11434"


def chat_once(prompt: str):
    data = json.dumps({
        "model": MODEL,
        "messages": [{"role": "user", "content": prompt}],
        "stream": False,
    }).encode("utf-8")
    req = urllib.request.Request(
        f"{BASE_URL}/api/chat",
        data=data,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=120) as resp:
            result = json.loads(resp.read())
        return result["message"]["content"]
    except urllib.error.HTTPError as e:
        body = e.read().decode("utf-8")
        return f"HTTP Error {e.code}: {body}"


if __name__ == "__main__":
    try:
        reply = chat_once("你好，请用一句话介绍自己")
        print(f"本地 LLM 回复:\n{reply}")
    except Exception as e:
        print(f"本地 LLM 测试失败: {e}")
