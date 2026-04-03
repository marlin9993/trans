from pathlib import Path
from typing import Dict, List

from .scanner import save_translations


def merge_and_write(
    filepath: Path,
    existing_flat: Dict[str, str],
    new_translations: Dict[str, str],
    removed_keys: List[str],
) -> int:
    """合并新旧翻译，写回 JSON 文件

    Returns:
        写入的总 key 数量
    """
    merged = {**existing_flat, **new_translations}
    for key in removed_keys:
        merged.pop(key, None)

    save_translations(filepath, merged)
    return len(merged)
