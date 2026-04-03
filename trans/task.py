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

    # 兼容两种结果格式：
    # 1. 旧格式：{"results": {"en": {"translations": {...}}}}
    # 2. 当前 SDK 常见格式：{"en": {"a.b": "..."}, "ja": {...}}
    if "results" in data and isinstance(data["results"], dict):
        return TranslationResult(**data)

    normalized_results = {}
    for lang, lang_data in data.items():
        if not isinstance(lang_data, dict):
            continue

        if "translations" in lang_data:
            normalized_results[lang] = lang_data
            continue

        # 顶层语言对象直接是 dot-path -> 译文
        if all(isinstance(k, str) and isinstance(v, str) for k, v in lang_data.items()):
            normalized_results[lang] = {
                "translations": lang_data,
                "notes": None,
                "missing_terms": None,
            }

    return TranslationResult(results=normalized_results)
