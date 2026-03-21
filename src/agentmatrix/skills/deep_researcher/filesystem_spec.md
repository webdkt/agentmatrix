# Deep Research File System Spec

所有路径相对于 `/work_files/`。

## 目录结构

```
/work_files/
├── research_state/              # 研究状态（核心共享目录）
│   ├── phase.md                 # 当前阶段
│   ├── research_title.md        # 研究标题（一行）
│   ├── research_purpose.md      # 研究目的
│   ├── personas.md              # Director 和 Researcher 人设
│   ├── blueprint_overview.md    # 研究蓝图概览
│   ├── research_plan.md         # 研究任务列表
│   ├── chapter_outline.md       # 章节大纲
│   └── research_overall_summary.md  # 研究整体总结
├── notebook/                    # 研究笔记（按章节组织）
│   └── {chapter_name}.md        # 章节笔记文件
├── drafts/                      # 报告草稿（按章节组织）
│   └── {chapter_name}.md        # 章节草稿文件
└── final_report.md              # 最终报告
```

## File Formats

### phase.md
单行，值域：`planning` | `research` | `writing` | `done`

### research_plan.md
每行一个任务，格式：
```
- [pending] 任务描述
- [in_progress] 任务描述
- [completed] 任务描述 | 总结: 已完成的简要说明
```
状态值域：`pending` | `in_progress` | `completed`
至少一个任务应为 `in_progress`（当前正在做的），其余为 `pending`。

### chapter_outline.md
每行一个一级章节标题：
```
# 章节标题1
# 章节标题2
```
章节标题是 notebook/ 和 drafts/ 下文件的命名依据。

### notebook/{chapter_name}.md
研究笔记，按时间戳组织：
```
## 笔记 - 2026-03-19 14:30
笔记内容...

## 笔记 - 2026-03-19 15:00
更多内容...
```

### research_state/personas.md
Director 和 Researcher 人设，结构：
```
## Director Persona
人设内容...

## Researcher Persona
人设内容...
```
