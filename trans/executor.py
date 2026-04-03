import asyncio
from pathlib import Path

from rich.console import Console


def run_claude_translation(project_dir: Path, prompt: str, console: Console) -> None:
    """Run translation via Claude Agent SDK."""
    try:
        from claude_agent_sdk import ClaudeAgentOptions, ResultMessage, query
        from claude_agent_sdk.types import StreamEvent
    except ImportError as exc:
        raise RuntimeError(
            "未安装 claude-agent-sdk。请执行 `pip install claude-agent-sdk`，"
            "并确保已配置 ANTHROPIC_API_KEY。"
        ) from exc

    async def _run() -> None:
        options = ClaudeAgentOptions(
            cwd=str(project_dir),
            permission_mode="bypassPermissions",
            include_partial_messages=True,
            setting_sources=["user", "project", "local"],
        )

        saw_text = False
        in_text_block = False

        async for message in query(prompt=prompt, options=options):
            if isinstance(message, StreamEvent):
                event = message.event
                event_type = event.get("type")

                if event_type == "content_block_start":
                    block = event.get("content_block", {})
                    if block.get("type") == "tool_use":
                        if in_text_block:
                            console.file.write("\n")
                            console.file.flush()
                            in_text_block = False
                        tool_name = block.get("name", "unknown")
                        console.print(f"[dim][tool][/dim] {tool_name}")

                elif event_type == "content_block_delta":
                    delta = event.get("delta", {})
                    if delta.get("type") == "text_delta":
                        text = delta.get("text", "")
                        if text:
                            console.file.write(text)
                            console.file.flush()
                            saw_text = True
                            in_text_block = True

                elif event_type == "message_stop" and in_text_block:
                    console.file.write("\n")
                    console.file.flush()
                    in_text_block = False

                continue

            if isinstance(message, ResultMessage):
                if in_text_block:
                    console.file.write("\n")
                    console.file.flush()
                    in_text_block = False

                if message.result and not saw_text:
                    console.print(message.result)

                if message.is_error:
                    raise RuntimeError(message.result or "Claude Agent SDK 执行失败")

    asyncio.run(_run())
