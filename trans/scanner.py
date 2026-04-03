import json
from pathlib import Path
from typing import Dict, Optional

from .models import ProjectConfig, ScanResult


def flatten(data: dict, prefix: str = "") -> Dict[str, str]:
    """嵌套 JSON → 扁平 dot-path
    {"common": {"hello": "你好"}} → {"common.hello": "你好"}
    """
    result: Dict[str, str] = {}
    for key, value in data.items():
        full_key = f"{prefix}.{key}" if prefix else key
        if isinstance(value, dict):
            result.update(flatten(value, full_key))
        else:
            result[full_key] = str(value)
    return result


def unflatten(flat: Dict[str, str]) -> dict:
    """扁平 dot-path → 嵌套 JSON
    {"common.hello": "你好"} → {"common": {"hello": "你好"}}
    """
    result: dict = {}
    for key, value in flat.items():
        parts = key.split(".")
        current = result
        for part in parts[:-1]:
            if part not in current:
                current[part] = {}
            current = current[part]
        current[parts[-1]] = value
    return result


def scan_i18n_files(project_dir: Path, config: ProjectConfig) -> Dict[str, Path]:
    """扫描 i18n 目录，返回 {lang: filepath}"""
    i18n_dir = project_dir / config.i18n_dir
    if not i18n_dir.exists():
        return {}

    result: Dict[str, Path] = {}
    for fp in sorted(i18n_dir.glob("*.json")):
        lang = fp.stem
        result[lang] = fp
    return result


def load_translations(filepath: Path) -> Dict[str, str]:
    """读取 JSON 文件 → flatten dict"""
    if not filepath.exists():
        return {}
    with open(filepath, "r", encoding="utf-8") as f:
        data = json.load(f)
    return flatten(data)


def save_translations(filepath: Path, flat: Dict[str, str]) -> None:
    """unflatten → 写入 JSON（sort_keys, indent=2, ensure_ascii=False）"""
    filepath.parent.mkdir(parents=True, exist_ok=True)
    nested = unflatten(flat)
    with open(filepath, "w", encoding="utf-8") as f:
        json.dump(nested, f, ensure_ascii=False, indent=2, sort_keys=True)
        f.write("\n")


def scan_project(project_dir: Path, config: ProjectConfig) -> Dict[str, ScanResult]:
    """扫描所有语言文件，返回 {lang: ScanResult}"""
    files = scan_i18n_files(project_dir, config)
    results: Dict[str, ScanResult] = {}
    for lang, filepath in files.items():
        keys = load_translations(filepath)
        results[lang] = ScanResult(
            lang=lang,
            file_path=filepath,
            total_keys=len(keys),
            keys=keys,
        )
    return results
