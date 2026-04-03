# trans

`trans` 是一个基于 Claude Code + Skills 的 i18n 翻译工具。

它负责扫描源语言文件、计算增量变更、生成翻译任务，并调用 Claude Code 完成多语言翻译，再把结果回写到目标语言 JSON 文件中。

## 要求

- Python 3.10+
- 已安装 `claude-agent-sdk`
- 已配置 `ANTHROPIC_API_KEY`
- 当前目录或目标项目目录中允许 Claude Code 读写翻译文件

## 安装

在仓库根目录执行：

```bash
pip install -e .
```

安装后可使用命令：

```bash
trans --help
```

如果你是手动安装依赖，也可以直接执行：

```bash
pip install claude-agent-sdk
```

## 项目准备

假设你的项目结构类似：

```text
your-project/
├── i18n/
│   └── zh.json
└── trans.yaml
```

其中 `trans.yaml` 例如：

```yaml
source_lang: zh
target_langs:
  - en
  - ja
  - de
i18n_dir: i18n
```

源语言文件 `i18n/zh.json` 可以是这样的结构：

```json
{
  "common": {
    "save": "保存",
    "cancel": "取消",
    "delete": "删除",
    "confirm": "确认"
  },
  "user": {
    "login": "登录",
    "logout": "退出登录",
    "username": "用户名",
    "password": "密码"
  },
  "order": {
    "status": {
      "pending": "待付款",
      "shipped": "已发货",
      "completed": "已完成"
    },
    "detail": "订单详情",
    "total": "共 {count} 个商品"
  },
  "error": {
    "network": "网络连接失败，请检查网络后重试",
    "not_found": "页面未找到"
  }
}
```

如果你还没有初始化，可以在目标项目目录执行：

```bash
trans init -s zh -t en,ja,de --i18n-dir i18n
```

这个命令会：

- 创建 `trans.yaml`
- 创建 `.claude/skills/`
- 创建 `.claude/commands/translate.md`
- 初始化 `i18n/<source_lang>.json`

初始化完成后，目录通常类似：

```text
your-project/
├── .claude/
│   ├── commands/
│   │   └── translate.md
│   └── skills/
│       ├── domain.md
│       ├── style.md
│       └── terminology.md
├── .trans_cache/
├── i18n/
│   ├── zh.json
│   ├── en.json
│   ├── ja.json
│   └── de.json
└── trans.yaml
```

## 常用流程

1. 准备源语言文件，例如 `i18n/zh.json`
2. 运行 `trans translate`
3. Claude Code 读取 `.trans/task.json`，生成 `.trans/result.json`
4. `trans` 将翻译结果回写到 `i18n/en.json`、`i18n/ja.json`、`i18n/de.json`

### 增量翻译

```bash
trans translate
```

默认只翻译新增或变更的 key。

### 强制全量重翻

```bash
trans translate --force
```

这个命令会忽略快照差异，按当前源语言内容重新翻译所有目标语言。

### 预览待翻译内容

```bash
trans translate --dry-run
```

只输出待翻译的 key，不调用 Claude Code。

## 其他命令

扫描当前语言文件状态：

```bash
trans scan
```

校验目标语言是否完整：

```bash
trans validate
trans validate -t en
```

查看各语言翻译进度：

```bash
trans status
```

## 输出文件

运行翻译时会生成：

- `.trans/task.json`：本次翻译任务
- `.trans/result.json`：Claude Code 写回的翻译结果
- `.trans_cache/`：快照和历史翻译缓存

这些文件用于增量翻译和结果回写，通常不建议提交到 Git。

## 工作方式

`trans` 本身不直接做翻译，而是：

- 扫描和对比 i18n 文件
- 生成标准化任务文件
- 调用 Claude Agent SDK
- 让 Claude Code 结合 `.claude/skills/` 中的术语、风格和领域知识完成翻译

因此翻译质量主要取决于：

- 源文案是否清晰
- `.claude/skills/terminology.md`
- `.claude/skills/style.md`
- `.claude/skills/domain.md`

## 示例

初始化：

```bash
trans init -s zh -t en,ja,de --i18n-dir i18n
```

执行翻译：

```bash
trans translate
```

强制重跑：

```bash
trans translate --force
```

## 说明

如果你希望正常运行翻译，请确保：

- 已安装 `claude-agent-sdk`
- 环境中已配置 `ANTHROPIC_API_KEY`
- Claude Code 相关项目配置和 `.claude/skills/` 可被当前项目读取
