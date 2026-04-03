from pathlib import Path
from typing import Optional

import yaml

from .models import ProjectConfig

CONFIG_FILENAME = "trans.yaml"


def find_project_dir(start: Optional[Path] = None) -> Path:
    """从给定目录向上查找包含 trans.yaml 的项目根目录"""
    current = (start or Path.cwd()).resolve()
    while True:
        if (current / CONFIG_FILENAME).exists():
            return current
        parent = current.parent
        if parent == current:
            raise FileNotFoundError(
                f"未找到 {CONFIG_FILENAME}，请先运行 trans init"
            )
        current = parent


def load_config(project_dir: Path) -> ProjectConfig:
    """读取 trans.yaml"""
    config_path = project_dir / CONFIG_FILENAME
    if not config_path.exists():
        raise FileNotFoundError(
            f"未找到 {config_path}，请先运行 trans init"
        )
    with open(config_path, "r", encoding="utf-8") as f:
        data = yaml.safe_load(f)
    return ProjectConfig(**data)


def save_config(project_dir: Path, config: ProjectConfig) -> Path:
    """写入 trans.yaml"""
    config_path = project_dir / CONFIG_FILENAME
    with open(config_path, "w", encoding="utf-8") as f:
        yaml.dump(
            config.model_dump(),
            f,
            default_flow_style=False,
            allow_unicode=True,
            sort_keys=False,
        )
    return config_path
