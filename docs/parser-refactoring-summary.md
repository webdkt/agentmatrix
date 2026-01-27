# Parser 重组总结

## 概述

成功完成了 Deep Researcher 中 parser 函数的重组和去重工作，遵循了清晰的职责分离原则。

## 重组前的问题

1. **重复代码**：`_multi_section_parser` 在两个地方存在：
   - `parser_utils.py` (完整版，217行)
   - `deep_researcher.py` (简化版，100行)
   - `deep_researcher_helper.py` (完整版，200行)

2. **职责不清**：
   - 通用parser与业务parser混在一起
   - `DeepResearcherPrompts` 类中包含了parser方法（不应该）

3. **维护困难**：
   - 重复的代码需要同步修改
   - 不清楚应该在哪里修改parser

## 重组方案

### 1. parser_utils.py - 通用解析工具

**位置**：`src/agentmatrix/skills/parser_utils.py`

**职责**：提供通用的、可复用的parser函数

**内容**：
- `multi_section_parser()` - 多section解析（完整版，支持正则、ALL/ANY模式）
- `simple_section_parser()` - 单section解析（新增）

**特点**：
- ✅ 完全通用，可用于任何skill
- ✅ 不依赖业务逻辑
- ✅ 代码优化（倒序遍历、提前终止）

### 2. deep_researcher_helper.py - Deep Research 特有parser

**位置**：`src/agentmatrix/skills/deep_researcher_helper.py`

**职责**：提供 Deep Research 特有的parser函数和prompts

**新增内容**：
```python
def persona_parser(raw_reply: str) -> dict:
    """解析人设生成输出，验证"你是"开头"""

def research_plan_parser(raw_reply: str) -> dict:
    """解析研究计划，验证章节大纲格式"""
```

**特点**：
- ✅ 复用 `parser_utils.py` 的通用parser
- ✅ 添加 Deep Research 特有的验证逻辑
- ✅ 作为独立函数，易于测试和维护

**原有内容**（保留）：
- `DeepResearcherPrompts` 类 - 只包含prompt模板
- `Notebook`, `Note`, `Page` - 番茄笔记数据结构
- `ResearchContext` - 研究上下文

### 3. deep_researcher.py - 主业务逻辑

**位置**：`src/agentmatrix/skills/deep_researcher.py`

**修改**：
- ❌ 删除了 `_simple_section_parser()` (重复)
- ❌ 删除了 `_multi_section_parser()` (重复)
- ❌ 删除了 `_research_plan_parser()` 方法 (移到helper)
- ❌ 删除了内嵌的 `persona_parser()` (移到helper)
- ✅ 新增导入：从helper导入 `persona_parser` 和 `research_plan_parser`

**结果**：
- 代码从 462行 减少到 429行
- 更清晰的职责分离
- 更易于维护

## 文件结构对比

### 重组前

```
parser_utils.py (217行)
└── multi_section_parser() ← 通用

deep_researcher_helper.py (637行)
├── DeepResearcherPrompts
│   ├── _simple_section_parser() ← 重复！
│   └── _multi_section_parser() ← 重复！
└── Notebook, Note, Page

deep_researcher.py (462行)
├── _simple_section_parser() ← 重复！
├── _multi_section_parser() ← 重复！
├── _research_plan_parser() ← 业务逻辑
└── DeepResearcherMixin
    └── persona_parser() ← 内嵌函数，业务逻辑
```

### 重组后

```
parser_utils.py (217行)
├── multi_section_parser() ← 唯一的通用parser
└── simple_section_parser() ← 新增

deep_researcher_helper.py (564行) ← 减少了73行！
├── persona_parser() ← 新增，独立函数
├── research_plan_parser() ← 新增，独立函数
├── DeepResearcherPrompts ← 只包含prompts
└── Notebook, Note, Page

deep_researcher.py (429行) ← 减少了33行！
└── DeepResearcherMixin
    └── 导入并使用helper中的parser
```

## 代码示例

### Deep Research 特有parser (helper中)

```python
def persona_parser(raw_reply: str) -> dict:
    """解析人设生成输出"""
    from .parser_utils import simple_section_parser

    result = simple_section_parser(raw_reply, "[正式文稿]")
    if result['status'] == 'success':
        if not result['data'].startswith("你是"):
            return {"status": "error", "feedback": "正式文稿必须以'你是'开头"}
    return result


def research_plan_parser(raw_reply: str) -> dict:
    """解析研究计划输出"""
    from .parser_utils import multi_section_parser

    plan = multi_section_parser(
        raw_reply,
        section_headers=["[研究计划]", "[章节大纲]", "[关键问题清单]"]
    )

    if plan['status'] == 'error':
        return plan

    # Deep Research 特有的验证逻辑
    chapter_outline = plan['sections'].get("[章节大纲]", "").strip()
    for line in chapter_outline.split('\n'):
        line = line.strip()
        if line and not line.startswith('# '):
            return {
                "status": "error",
                "feedback": "章节大纲格式错误，每行必须以 '# ' 开头表示一级标题"
            }

    return plan
```

### 使用parser (deep_researcher.py中)

```python
from .deep_researcher_helper import (
    ResearchContext,
    Notebook,
    format_prompt,
    DeepResearcherPrompts,
    persona_parser,          # ← 导入特有parser
    research_plan_parser     # ← 导入特有parser
)

# 使用
director_persona = await self.brain.think_with_retry(
    director_prompt,
    persona_parser  # 直接使用
)

final_plan = await self.brain.think_with_retry(
    final_plan_prompt,
    research_plan_parser  # 直接使用
)
```

## 关键设计原则

### 1. 通用性原则

- **通用parser** → `parser_utils.py`
  - 不依赖业务逻辑
  - 可用于任何skill
  - 参数化配置

### 2. 业务隔离原则

- **业务parser** → 各skill的helper文件
  - 复用通用parser
  - 添加业务验证逻辑
  - 作为独立函数，易于测试

### 3. 单一职责原则

- **Prompts类** → 只包含prompt模板
- **Parser函数** → 独立函数，不放在类中
- **业务逻辑** → 主skill文件

## 优势

### 1. 代码复用
- ✅ 消除了重复的 `_multi_section_parser` (3处 → 1处)
- ✅ 通用parser可被所有skill使用

### 2. 易于维护
- ✅ 通用parser修改一处即可
- ✅ 业务parser独立，修改不影响其他skill
- ✅ 职责清晰，知道在哪里修改什么

### 3. 易于测试
- ✅ 独立的parser函数易于单元测试
- ✅ 不依赖类实例，可以直接测试

### 4. 代码精简
- ✅ `deep_researcher_helper.py`：637行 → 564行 (-73行, -11.5%)
- ✅ `deep_researcher.py`：462行 → 429行 (-33行, -7.1%)
- ✅ 总计减少了106行重复代码

## 后续建议

1. **统一使用parser_utils**
   - 其他skill也应该使用 `parser_utils.py` 中的通用parser
   - 避免在各skill中重复实现

2. **文档化parser模式**
   - 为常见的parser模式创建文档
   - 提供更多示例代码

3. **扩展通用parser**
   - 根据需要添加更多通用parser
   - 如：JSON parser, XML parser等

## 总结

这次重组成功实现了：
- ✅ 消除了代码重复
- ✅ 明确了职责分离
- ✅ 提高了可维护性
- ✅ 遵循了项目架构规范

代码现在更加清晰、模块化，符合单一职责原则和DRY（Don't Repeat Yourself）原则。
