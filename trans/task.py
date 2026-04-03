import json
from pathlib import Path
from typing import Dict, List

from .models import (
    DiffResult,
    LangTask,
    TranslationResult,
    TranslationTask,
)


def generate_task(
    source_lang: str,
    target_langs: List[str],
    diffs: Dict[str, DiffResult],
    existing_translations: Dict[str, Dict[str, str]],
) -> TranslationTask:
    """生成包含所有语言的翻译任务"""
    tasks: Dict[str, LangTask] = {}
    for lang in target_langs:
        diff = diffs.get(lang)
        if diff is None:
            continue
        items = diff.needs_translation
        if not items:
            continue
        existing = existing_translations.get(lang, {})
        tasks[lang] = LangTask(
            items=items,
            existing_translations=existing,
        )
    return TranslationTask(source_lang=source_lang, tasks=tasks)


def write_task_file(task: TranslationTask, path: Path) -> None:
    """写入 .trans/task.json"""
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(task.model_dump(), f, ensure_ascii=False, indent=2)
        f.write("\n")


def parse_result_file(path: Path) -> TranslationResult:
    """解析 .trans/result.json"""
    if not path.exists():
        raise FileNotFoundError(f"翻译结果文件不存在: {path}")
    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)
    return TranslationResult(**data)
