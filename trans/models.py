from pathlib import Path
from typing import Dict, List, Optional

from pydantic import BaseModel


class ProjectConfig(BaseModel):
    """trans.yaml 配置"""
    source_lang: str
    target_langs: List[str]
    i18n_dir: str = "i18n"


class LangTask(BaseModel):
    """单个目标语言的翻译任务"""
    items: Dict[str, str]                      # dot-path → 源文本（待翻译）
    existing_translations: Dict[str, str]       # 已有翻译（风格参考）


class TranslationTask(BaseModel):
    """Python 生成 → CC 消费，所有语言打包"""
    source_lang: str
    tasks: Dict[str, LangTask]                 # target_lang → LangTask


class LangResult(BaseModel):
    """单个目标语言的翻译结果"""
    translations: Dict[str, str]               # dot-path → 译文
    notes: Optional[List[str]] = None
    missing_terms: Optional[List[str]] = None


class TranslationResult(BaseModel):
    """CC 生成 → Python 消费"""
    results: Dict[str, LangResult]             # target_lang → LangResult


class DiffResult(BaseModel):
    """增量 diff 结果"""
    added: Dict[str, str]                      # 新增 key → 源文本
    changed: Dict[str, str]                    # 变更 key → 新源文本
    removed: List[str]                         # 孤儿 key
    unchanged: int                             # 未变更数量

    @property
    def needs_translation(self) -> Dict[str, str]:
        """需要翻译的 key（added + changed）"""
        result = {**self.added, **self.changed}
        return result

    @property
    def total_changes(self) -> int:
        return len(self.added) + len(self.changed)


class ScanResult(BaseModel):
    """扫描结果"""
    lang: str
    file_path: Path
    total_keys: int
    keys: Dict[str, str]                       # flatten 后的所有 key-value
