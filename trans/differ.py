from typing import Dict

from .models import DiffResult


def compute_diff(
    source_flat: Dict[str, str],
    target_flat: Dict[str, str],
    snapshot_flat: Dict[str, str],
) -> DiffResult:
    """增量 diff

    Args:
        source_flat: 当前源文件（flatten）
        target_flat: 当前目标文件（flatten）
        snapshot_flat: 上次翻译时的源文件快照（flatten）
    """
    source_keys = set(source_flat.keys())
    target_keys = set(target_flat.keys())
    snapshot_keys = set(snapshot_flat.keys())

    # 新增：source 有但 target 没有
    added_keys = source_keys - target_keys
    added = {k: source_flat[k] for k in sorted(added_keys)}

    # 变更：source 值和 snapshot 不同（说明源文案改过，需重翻）
    changed = {}
    for k in source_keys & target_keys:
        if k in snapshot_keys and snapshot_flat[k] != source_flat[k]:
            changed[k] = source_flat[k]

    # 孤儿：target 有但 source 没有
    removed = sorted(target_keys - source_keys)

    # 未变更
    unchanged = len(source_keys) - len(added) - len(changed)

    return DiffResult(
        added=added,
        changed=changed,
        removed=removed,
        unchanged=unchanged,
    )
