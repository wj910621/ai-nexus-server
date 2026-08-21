"""SSE (Server-Sent Events) 辅助工具"""
import json
from typing import Any, AsyncGenerator


def sse_format(data: dict[str, Any], event: str = "message") -> str:
    """格式化 SSE 消息

    SSE 协议规定：每条消息由若干字段行组成，以一个空行 (\\n\\n) 结束。
    `event:` 行指定事件类型，`data:` 行携带 JSON 序列化后的负载。
    """
    return f"event: {event}\ndata: {json.dumps(data, ensure_ascii=False)}\n\n"


def sse_done() -> str:
    """SSE 结束信号

    沿用 OpenAI 的 `data: [DONE]` 约定，前端据此关闭 EventSource。
    """
    return "data: [DONE]\n\n"


def sse_error(message: str, code: str = "error") -> str:
    """SSE 错误消息"""
    return f"event: error\ndata: {json.dumps({'error': message, 'code': code}, ensure_ascii=False)}\n\n"


def calculate_refund(used_tokens: int, total_tokens: int, cost: int) -> int:
    """计算部分退款 - 按未使用比例退款

    Args:
        used_tokens: 实际使用的 token 数
        total_tokens: 预估总 token 数
        cost: 总成本（积分）

    Returns:
        应退还的积分数（向下取整）
    """
    if total_tokens <= 0:
        return 0
    unused_ratio = max(0, 1 - used_tokens / total_tokens)
    return int(cost * unused_ratio)


async def sse_stream(
    generator: AsyncGenerator[str, None],
    on_abort: Any | None = None,
) -> AsyncGenerator[str, None]:
    """包装异步生成器为 SSE 流

    Args:
        generator: yield str chunks (e.g. LLM token deltas)
        on_abort: async callable() invoked in `finally` (covers client
            disconnect / generator early exit). Use this to refund unused
            credits.

    Yields:
        SSE-formatted strings: `event: token\\ndata: {...}\\n\\n` for each
        chunk, `data: [DONE]\\n\\n` at the end, or `event: error\\n...` on
        exception.
    """
    try:
        async for chunk in generator:
            yield sse_format({"text": chunk}, event="token")
        yield sse_done()
    except Exception as exc:
        yield sse_error(str(exc))
    finally:
        if on_abort is not None:
            await on_abort()
