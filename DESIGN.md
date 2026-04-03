# Trans —— 基于 Claude Code + Skills 的 i18n 翻译引擎

## 一、核心架构

```
                        ┌─────────────────────────────┐
                        │        自动化触发             │
                        │  cron / CI/CD / git hook     │
                        └──────────────┬──────────────┘
                                       │
                                       ▼
┌──────────────────────────────────────────────────────────┐
│                  Python 工程层（脚手架）                    │
│                                                          │
│   scan → diff → 生成 task.json → 触发 CC → 解析 result   │
│                                                          │
│   只做文件操作，不做翻译，不拼 prompt                       │
└──────────────────────────┬───────────────────────────────┘
                           │ claude --print -p "..."
                           │ （单次调用，所有语言打包）
                           ▼
┌──────────────────────────────────────────────────────────┐
│              Claude Code Agent（翻译引擎）                  │
│                                                          │
│   ┌────────────────────────────────────────────────────┐ │
│   │  单次调用内的渐进式上下文构建：                       │ │
│   │                                                    │ │
│   │  1. 读 task.json → 理解翻译范围                     │ │
│   │  2. 读 terminology.md → 加载术语表                  │ │
│   │  3. 读 style.md → 加载风格规则                      │ │
│   │  4. 读 domain.md → 理解业务上下文                   │ │
│   │  5. 读已有翻译文件 → 建立风格参照                    │ │
│   │  6. 读 .trans_cache/ 历史翻译 → 保持一致性           │ │
│   │  7. 逐步推理每个 key 的最佳翻译                      │ │
│   │  8. 写 result.json + notes + missing_terms          │ │
│   └────────────────────────────────────────────────────┘ │
│                                                          │
│   Skills（翻译智能，渐进积累）：                           │
│   ┌──────────┐ ┌──────────┐ ┌──────────┐                │
│   │terminology│ │  style   │ │  domain  │                │
│   │  术语表   │ │ 翻译风格 │ │ 领域知识 │                │
│   └──────────┘ └──────────┘ └──────────┘                │
└──────────────────────────────────────────────────────────┘
```

### 职责分离

| 层 | 职责 | 不做什么 |
|----|------|---------|
| **Python** | 文件扫描、JSON flatten/unflatten、增量 diff、快照管理、CLI、触发 CC | 不做翻译、不拼 prompt、不调 API |
| **CC Agent** | 理解上下文、应用术语/风格/领域知识、渐进式推理、执行翻译、输出建议 | 不关心文件路径、不直接操作 JSON |

### 为什么不用 Python 拼 prompt 调 API

1. **翻译质量**：CC 的 agent 推理（多文件交叉引用、上下文关联）远超单次 API 调用
2. **不重复造轮子**：CC 已有的 skills 加载、渐进式上下文、工具调用全部复用
3. **渐进提升**：skills 文件越积累翻译质量越高，CC 自动利用历史翻译保持一致性
4. **自动化**：`claude --print` 是无交互模式，可直接用于 cron/CI/CD

---

## 二、两种使用模式

### 2.1 自动化模式（`claude --print`）

```bash
# 可在 cron / CI/CD / git hook 中运行，无需人工
trans translate
```

内部执行：
```bash
claude --print -p "读取 .trans/task.json，使用你的翻译 skills 完成所有语言的翻译"
```

- 所有目标语言打包在一个 task.json 中，CC 一次处理，**一次冷启动**
- CC 在单次调用内完整使用 agent 能力：读文件、grep、交叉引用 skills
- 全自动，无人值守

### 2.2 交互模式（CC 会话内 `/translate`）

```bash
# 开发者在 CC 会话中直接使用
> /translate
```

- 零冷启动，复用当前 CC 会话
- 可交互式调整：补充术语、修改风格、重翻特定 key
- 产出的 skills 积累供自动化模式使用

### 两种模式共享同一套 Skills 文件

```
交互模式积累知识 ──→ skills/*.md ──→ 自动化模式消费知识
```

---

## 三、Python 工程层

### 3.1 项目结构

```
    /path/to/trans/
├── trans/
│   ├── __init__.py
│   ├── cli.py          # Click CLI 入口
│   ├── scanner.py      # i18n 文件发现、JSON 读写、flatten/unflatten
│   ├── differ.py       # 增量 diff：对比快照检测变更
│   ├── task.py         # 生成 task.json、解析 result.json
│   ├── writer.py       # 将翻译结果 merge 回 JSON 并写入
│   ├── snapshot.py     # 快照管理（.trans_cache/）
│   ├── config.py       # 读取 trans.yaml 配置
│   └── models.py       # 数据结构定义
├── pyproject.toml
└── skills/             # Skills 模板（init 时复制到目标项目）
    ├── terminology.md
    ├── style.md
    ├── domain.md
    └── translate.md    # /translate 命令
```

### 3.2 目标项目结构（init 后）

```
目标项目/
├── .claude/
│   ├── skills/
│   │   ├── terminology.md    # 术语表（团队共建，git 管理）
│   │   ├── style.md          # 翻译风格指南
│   │   └── domain.md         # 项目领域知识
│   └── commands/
│       └── translate.md      # /translate 命令（交互模式用）
├── trans.yaml                # 翻译配置
├── i18n/
│   ├── zh.json               # 源语言
│   ├── en.json               # 目标语言
│   └── ja.json               # 目标语言
└── .trans_cache/
    ├── zh.snapshot.json      # 源文件快照（增量 diff 用）
    ├── en.translated.json    # 上次翻译结果（CC 参照用）
    └── ja.translated.json
```

### 3.3 配置文件 trans.yaml

```yaml
source_lang: zh
target_langs:
  - en
  - ja
i18n_dir: i18n
```

### 3.4 数据模型 models.py

```python
from pydantic import BaseModel
from typing import Dict, List, Optional

class TranslationTask(BaseModel):
    """Python 生成 → CC 消费，所有语言打包"""
    source_lang: str
    tasks: Dict[str, LangTask]         # target_lang → LangTask

class LangTask(BaseModel):
    """单个目标语言的翻译任务"""
    items: Dict[str, str]              # dot-path → 源文本（待翻译）
    existing_translations: Dict[str, str]  # 已有翻译（风格参考）

class TranslationResult(BaseModel):
    """CC 生成 → Python 消费"""
    results: Dict[str, LangResult]     # target_lang → LangResult

class LangResult(BaseModel):
    """单个目标语言的翻译结果"""
    translations: Dict[str, str]       # dot-path → 译文
    notes: Optional[List[str]] = None
    missing_terms: Optional[List[str]] = None

class DiffResult(BaseModel):
    """增量 diff 结果"""
    added: Dict[str, str]
    changed: Dict[str, str]
    removed: List[str]
    unchanged: int
```

### 3.5 scanner.py —— 文件发现与 JSON 操作

```python
def flatten(data: dict, prefix: str = "") -> Dict[str, str]:
    """
    {"common": {"hello": "你好"}} → {"common.hello": "你好"}
    """

def unflatten(flat: Dict[str, str]) -> dict:
    """
    {"common.hello": "你好"} → {"common": {"hello": "你好"}}
    """

def scan_i18n_files(project_dir: Path, config) -> Dict[str, Path]:
    """扫描 i18n_dir，返回 {lang: filepath}"""

def load_translations(filepath: Path) -> Dict[str, str]:
    """读取 JSON → flatten"""

def save_translations(filepath: Path, flat: Dict[str, str]):
    """unflatten → 写 JSON（sort_keys, indent=2, ensure_ascii=False）"""
```

### 3.6 differ.py —— 增量 Diff

```python
def compute_diff(
    source_flat: Dict[str, str],       # 当前源文件
    target_flat: Dict[str, str],        # 当前目标文件
    snapshot_flat: Dict[str, str],      # 上次源文件快照
) -> DiffResult:
    """
    added:   source 有但 target 没有 → 新 key
    changed: source 值和 snapshot 不同 → 源文案变更，需重翻
    removed: target 有但 source 没有 → 孤儿 key（报告不删除）
    """
```

### 3.7 snapshot.py —— 快照管理

```python
def load_snapshot(cache_dir: Path, lang: str) -> Dict[str, str]:
    """读取 .trans_cache/{lang}.snapshot.json"""

def save_snapshot(cache_dir: Path, lang: str, flat: Dict[str, str]):
    """保存源文件快照"""

def load_prev_translation(cache_dir: Path, lang: str) -> Dict[str, str]:
    """读取 .trans_cache/{lang}.translated.json（上次翻译结果）"""

def save_prev_translation(cache_dir: Path, lang: str, flat: Dict[str, str]):
    """保存翻译结果（供下次 CC 参照风格）"""
```

### 3.8 task.py —— 翻译任务生成与结果解析

```python
def generate_task(
    source_lang: str,
    source_flat: Dict[str, str],
    target_langs: List[str],
    diffs: Dict[str, DiffResult],           # lang → diff
    existing_translations: Dict[str, Dict],  # lang → flat
) -> TranslationTask:
    """生成包含所有语言的翻译任务"""

def write_task_file(task: TranslationTask, path: Path):
    """写入 .trans/task.json"""

def parse_result_file(path: Path) -> TranslationResult:
    """解析 .trans/result.json"""
```

### 3.9 writer.py —— 结果回写

```python
def merge_and_write(
    filepath: Path,
    existing_flat: Dict[str, str],
    new_translations: Dict[str, str],
    removed_keys: List[str],
):
    """合并新旧翻译 → unflatten → 写入 JSON"""
```

### 3.10 CLI 调用 CC

```python
import subprocess

def call_claude(project_dir: Path):
    """单次 CC 调用，处理所有语言"""
    prompt = (
        "请读取 .trans/task.json，使用你的翻译 skills "
        "(terminology、style、domain) 完成所有语言的翻译，"
        "将结果写入 .trans/result.json。"
    )
    subprocess.run(
        ["claude", "--print", "-p", prompt],
        cwd=str(project_dir),
        check=True,
    )
```

### 3.11 CLI 命令

```bash
trans init -s zh -t en,ja --i18n-dir i18n   # 初始化
trans scan                                   # 扫描文件状态
trans translate                              # 增量翻译（调用 CC）
trans translate --force                      # 全量重翻
trans translate --dry-run                    # 预览待翻译内容
trans validate                               # 校验翻译完整性
trans status                                 # 各语言翻译进度
```

---

## 四、CC Agent 渐进式上下文

### 4.1 单次调用内的上下文构建

CC 在一次 `--print` 调用中通过工具调用逐步构建上下文：

```
CC 启动
  │
  ├─ 读 task.json → "zh → en, ja，共 15 个 key 待翻译"
  │
  ├─ 读 terminology.md → 加载术语表（120 个术语）
  │
  ├─ 读 style.md → 翻译风格规则
  │
  ├─ 读 domain.md → "电商后台 B 端 SaaS"
  │
  ├─ 读 en.json → 已有 200 条翻译，建立风格基准
  │   ├─ 发现 "Save" 已被使用 → 新 key "common.save" 复用
  │   └─ 发现错误提示格式 "Error. Please..." → 新错误提示保持一致
  │
  ├─ 读 .trans_cache/en.translated.json → 对比上次翻译
  │
  ├─ 逐条翻译，应用术语表 + 风格 + 领域知识
  │   ├─ "退款" → 查术语表 → "Refund"（不是 Return）
  │   ├─ "供应商管理" → 查领域知识 → "Vendor Management"
  │   └─ "共 {count} 个商品" → 占位符保留 → "{count} items"
  │
  └─ 写 result.json + notes + missing_terms
```

### 4.2 跨会话的渐进提升

```
会话间通过文件传递"记忆"：

.trans_cache/zh.snapshot.json    → 让 Python 知道哪些 key 变了
.trans_cache/en.translated.json  → 让 CC 参照上次翻译风格
.claude/skills/terminology.md    → 术语表（越积累越全）
.claude/skills/style.md          → 风格规则（持续迭代）
.claude/skills/domain.md         → 领域知识（逐步完善）

翻译质量随 skills 积累而渐进提升
```

每次翻译后 CC 输出 `missing_terms` → 补充进 terminology.md → 下次 CC 自动获得更强的上下文。

---

## 五、完整工作流

### 5.1 初始化

```bash
cd /my/project
trans init -s zh -t en,ja --i18n-dir src/locales
```

Python 层执行：
1. 创建 `trans.yaml`
2. 创建 `src/locales/` 目录
3. 创建 `src/locales/zh.json`（空 `{}`，如不存在）
4. 复制 skills 模板到 `.claude/skills/`
5. 创建 `.claude/commands/translate.md`
6. 创建 `.trans_cache/` 目录

### 5.2 翻译（自动化）

```bash
trans translate
```

```
Python 层                                    CC Agent
─────────                                   ─────────

1. 读 trans.yaml
2. scan: 发现 zh.json, en.json, ja.json
3. flatten 所有文件
4. diff (所有目标语言):
   - 对比快照 → 检测新增/变更 key
5. 生成 task.json (所有语言打包):
   {
     "source_lang": "zh",
     "tasks": {
       "en": { "items": {...}, "existing_translations": {...} },
       "ja": { "items": {...}, "existing_translations": {...} }
     }
   }
                       ──→  6. claude --print (单次调用)
                            7. CC 读取 task.json
                            8. CC 加载 skills
                            9. CC 读取已有翻译、缓存
                            10. CC 渐进式推理翻译
                       ←──  11. CC 写入 result.json

12. 解析 result.json
13. merge 翻译回各语言 JSON
14. 更新快照 + 缓存
15. 输出报告
```

### 5.3 翻译报告

```
Scanning i18n files...
  zh: 142 keys (source)
  en: 138 keys (4 missing)
  ja: 130 keys (12 missing)

Computing diff...
  en: 4 new, 0 changed
  ja: 12 new, 0 changed

Calling Claude Code...
  ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━ done

Merging results...
  en: +4 keys → 142 total
  ja: +12 keys → 142 total

Done! Translated 16 keys across 2 languages (1 CC call).

Notes:
  [en] 建议将 "售后" 加入术语表 (order.after_sale)
  [ja] 建议将 "供应商" 加入术语表 (vendor.name)

Run `trans validate` to check quality.
```

### 5.4 增量翻译

```
第一次: 100 key → 翻译 100 key × 2 语言 = 1 次 CC 调用
第二次: +5 key → 只翻译 5 key × 2 语言 = 1 次 CC 调用
第三次: 改 2 key 中文 → 只重翻 2 key × 2 语言 = 1 次 CC 调用
```

### 5.5 自动化触发

```bash
# git pre-commit hook
trans translate && git add i18n/

# CI/CD
- run: pip install trans && trans translate

# cron（每天凌晨）
0 2 * * * cd /my/project && trans translate
```

---

## 六、Skills 设计

### 6.1 terminology.md —— 术语表

```markdown
---
name: terminology
description: 翻译术语表，确保多语言术语一致性
---

# 翻译术语表

## 通用术语

| 中文 | English | 日本語 | 备注 |
|------|---------|--------|------|
| 保存 | Save | 保存 | 按钮/操作 |
| 删除 | Delete | 削除 | 按钮/操作 |
| 取消 | Cancel | キャンセル | 按钮/操作 |
| 确认 | Confirm | 確認 | 按钮/操作 |
| 提交 | Submit | 送信 | 表单操作 |
| 搜索 | Search | 検索 | 搜索框 |
| 购物车 | Shopping Cart | カート | 电商场景 |

## 规则

1. 术语表中存在的词**必须**使用指定翻译，不得自由发挥
2. 发现高频词未在术语表中时，在 notes 中提示建议补充
3. 同一概念在不同模块的翻译必须一致
```

### 6.2 style.md —— 翻译风格

```markdown
---
name: style
description: 翻译风格指南，控制语气、格式、表达方式
---

# 翻译风格指南

## 语气

- 中文→英文：专业简洁，面向 B 端用户
- 中文→日文：使用「です/ます」体

## 按钮文本

- 英文：动词开头，首字母大写，≤ 3 词
- 日文：体言止め或简洁动词

## 错误提示

- 格式：[问题] + [建议操作]

## 占位符

- `{name}`, `{count}`, `%s` 等占位符原样保留

## 禁止

- 不添加原文没有的标点或语气词
- 品牌名/产品名不翻译
```

### 6.3 domain.md —— 领域知识

```markdown
---
name: domain
description: 项目领域上下文，帮助理解翻译场景
---

# 项目领域知识

## 项目类型

电商管理后台（B 端 SaaS）

## 用户画像

- 商家运营人员，技术水平一般

## 关键业务概念

- SKU：保留 "SKU"
- GMV：Gross Merchandise Volume
- 佣金：Commission（不是 fee）
- 供应商：Vendor（不是 supplier）

## 常见场景

1. 商品管理：上架、下架、库存、价格
2. 订单管理：发货、退款、售后
3. 数据报表：GMV、转化率、UV
4. 权限管理：角色、权限组
```

### 6.4 translate.md —— CC 命令（交互模式）

```markdown
---
name: translate
description: 执行 i18n 翻译任务
---

请执行以下翻译任务：

1. 读取 .trans/task.json
2. 加载翻译 skills：terminology、style、domain
3. 对每个目标语言：
   - 应用术语表，确保一致
   - 应用风格指南
   - 应用领域知识
   - 参考已有翻译保持风格
4. 将结果写入 .trans/result.json：
```json
{
  "results": {
    "en": {
      "translations": {"common.save": "Save"},
      "notes": [],
      "missing_terms": []
    }
  }
}
```

## 注意

- 参考已有翻译（task.json 中的 existing_translations）保持风格一致
- 发现术语表缺失的高频词时报告 missing_terms
- 严格保持 JSON key 不变，只翻译 value
```

---

## 七、渐进式知识积累

```
时间线：

第1次翻译
  CC 翻译 100 key，报告 missing_terms: ["售后", "供应商", "佣金"]
  开发者补充 terminology.md

第2次翻译
  CC 用上补充的术语，翻译更准
  CC 报告 missing_terms: ["规格", "sku"]

第3次翻译
  开发者补充了 domain.md 中的业务概念
  CC 翻译质量进一步提升

第N次翻译
  terminology.md: 200+ 术语
  style.md: 覆盖各种场景的规则
  domain.md: 完整的业务知识
  → 翻译质量趋近人工专家水平
```

Skills 文件是团队知识资产，放入 git 版本管理，团队共同维护。

---

## 八、依赖与安装

### Python 依赖

已有：click, pydantic, pyyaml, rich

无额外依赖。不使用 anthropic SDK。

### 系统依赖

- Claude Code CLI 已安装且已登录

### 安装

```bash
source ~/py/py3/bin/activate
cd /path/to/trans
pip install -e .
```

---

## 九、实现优先级

| 顺序 | 模块 | 说明 |
|------|------|------|
| 1 | models.py | 数据结构 |
| 2 | scanner.py | JSON 读写、flatten/unflatten |
| 3 | config.py | 读取 trans.yaml |
| 4 | differ.py + snapshot.py | 增量 diff + 快照 |
| 5 | task.py + writer.py | 任务生成 + 结果回写 |
| 6 | cli.py (init, scan) | 基础命令 |
| 7 | skills 模板 | 术语表/风格/领域/命令 |
| 8 | cli.py (translate) | 翻译命令（调用 CC） |
| 9 | cli.py (validate, status) | 校验和状态 |
| 10 | 端到端测试 | 完整流程验证 |
