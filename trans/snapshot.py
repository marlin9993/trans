import json
from pathlib import Path
from typing import Dict


CACHE_DIR = ".trans_cache"


def _cache_path(project_dir: Path) -> Path:
    return project_dir / CACHE_DIR


def load_snapshot(project_dir: Path, lang: str) -> Dict[str, str]:
    """读取源文件快照"""
    path = _cache_path(project_dir) / f"{lang}.snapshot.json"
    if not path.exists():
        return {}
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def save_snapshot(project_dir: Path, lang: str, flat: Dict[str, str]) -> None:
    """保存源文件快照"""
    cache_dir = _cache_path(project_dir)
    cache_dir.mkdir(exist_ok=True)
    path = cache_dir / f"{lang}.snapshot.json"
    with open(path, "w", encoding="utf-8") as f:
        json.dump(flat, f, ensure_ascii=False, indent=2, sort_keys=True)
        f.write("\n")


def load_prev_translation(project_dir: Path, lang: str) -> Dict[str, str]:
    """读取上次翻译结果（供 CC 参照风格）"""
    path = _cache_path(project_dir) / f"{lang}.translated.json"
    if not path.exists():
        return {}
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def save_prev_translation(project_dir: Path, lang: str, flat: Dict[str, str]) -> None:
    """保存翻译结果"""
    cache_dir = _cache_path(project_dir)
    cache_dir.mkdir(exist_ok=True)
    path = cache_dir / f"{lang}.translated.json"
    with open(path, "w", encoding="utf-8") as f:
        json.dump(flat, f, ensure_ascii=False, indent=2, sort_keys=True)
        f.write("\n")
