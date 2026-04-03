---
name: translate
description: 执行 i18n 翻译任务
---

请执行以下翻译任务：

1. 读取 `.trans/task.json`
2. 加载翻译 skills：terminology、style、domain
3. 对每个目标语言：
   - 应用术语表，确保一致
   - 应用风格指南
   - 应用领域知识
   - 参考已有翻译（task.json 中的 existing_translations）保持风格
4. 将结果写入 `.trans/result.json`

## 输出格式

```json
{
  "results": {
    "en": {
      "translations": {
        "common.save": "Save",
        "common.cancel": "Cancel"
      },
      "notes": ["建议将 'XX' 加入术语表"],
      "missing_terms": ["XX"]
    },
    "ja": {
      "translations": {
        "common.save": "保存",
        "common.cancel": "キャンセル"
      },
      "notes": [],
      "missing_terms": []
    }
  }
}
```

## 注意

- 参考已有翻译保持风格一致
- 发现术语表缺失的高频词时报告 missing_terms
- 严格保持 JSON key 不变，只翻译 value
- 占位符 `{name}` 等原样保留
