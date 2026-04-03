import asyncio
from dataclasses import asdict, is_dataclass
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

from rich.console import Console


def _serialize_message(message: Any) -> dict:
    if is_dataclass(message):
        data = asdict(message)
        if isinstance(data, dict):
            data.setdefault("_message_type", type(message).__name__)
            return data

    if hasattr(message, "model_dump"):
        data = message.model_dump()
        if isinstance(data, dict):
            data.setdefault("_message_type", type(message).__name__)
            return data

    if hasattr(message, "event"):
        return {
            "_message_type": type(message).__name__,
            "event": getattr(message, "event"),
        }

    result = {"_message_type": type(message).__name__}
    for attr in ("result", "is_error", "session_id", "subtype", "type"):
        if hasattr(message, attr):
            result[attr] = getattr(message, attr)
    return result


def run_claude_translation(
    project_dir: Path,
    prompt: str,
    console: Console,
    raw_events: bool = False,
    log_path: Optional[Path] = None,
) -> None:
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
        log_file = None

        if log_path is not None:
            log_path.parent.mkdir(parents=True, exist_ok=True)
            log_file = log_path.open("w", encoding="utf-8")
            metadata = {
                "_record_type": "run_metadata",
                "recorded_at": datetime.now(timezone.utc).isoformat(),
                "cwd": str(project_dir),
                "prompt": prompt,
                "options": {
                    "permission_mode": "bypassPermissions",
                    "include_partial_messages": True,
                    "setting_sources": ["user", "project", "local"],
                },
                "raw_events_to_terminal": raw_events,
            }
            log_file.write(json.dumps(metadata, ensure_ascii=False) + "\n")
            log_file.flush()

        try:
            async for message in query(prompt=prompt, options=options):
                serialized = _serialize_message(message)
                if log_file is not None:
                    log_file.write(
                        json.dumps(
                            {
                                "_record_type": "sdk_message",
                                "recorded_at": datetime.now(timezone.utc).isoformat(),
                                "payload": serialized,
                            },
                            ensure_ascii=False,
                        )
                        + "\n"
                    )
                    log_file.flush()

                if raw_events:
                    if in_text_block:
                        console.file.write("\n")
                        console.file.flush()
                        in_text_block = False
                    console.print_json(data=serialized)

                if isinstance(message, StreamEvent):
                    event = message.event
                    event_type = event.get("type")

                    if not raw_events and event_type == "content_block_start":
                        block = event.get("content_block", {})
                        if block.get("type") == "tool_use":
                            if in_text_block:
                                console.file.write("\n")
                                console.file.flush()
                                in_text_block = False
                            tool_name = block.get("name", "unknown")
                            console.print(f"[dim][tool][/dim] {tool_name}")

                    elif not raw_events and event_type == "content_block_delta":
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

                    if message.result and not saw_text and not raw_events:
                        console.print(message.result)

                    if message.is_error:
                        raise RuntimeError(message.result or "Claude Agent SDK 执行失败")
        finally:
            if log_file is not None:
                log_file.close()

    asyncio.run(_run())
