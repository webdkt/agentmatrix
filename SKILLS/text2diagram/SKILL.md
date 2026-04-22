---
name: text2diagram
description: 使用 D2 语言创建各种类型的图表（流程图、架构图、组织结构图等）并生成 SVG
trigger: 当用户需要创建、编辑或生成图表、流程图、架构图、组织结构图时使用此技能
---

# Text2Diagram Skill

使用 D2 语言创建各种类型的图表：流程图、架构图、组织结构图、网络图等。

## 快速开始

1. **确保系统已安装 D2**
   ```bash
   d2 --version
   ```

   如果未安装，请参考 [D2 官方文档](https://d2lang.com) 或使用：
   ```bash
   curl -fsSL https://d2lang.com/install.sh | sh -s --
   ```

2. **学习 D2 语法**
   - 参考 [SYNTAX.md](./SYNTAX.md) 了解完整的 D2 语法
   - 参考 [quick-start.md](./quick-start.md) 快速入门

3. **参考示例**
   - 参考 [EXAMPLES.md](./EXAMPLES.md) 了解示例集合
   - 查看 `examples/` 目录中的示例文件

4. **编写 D2 文件**
   - 创建 `.d2` 文件并编写 D2 代码
   - 使用 `d2 input.d2 output.svg` 生成图表

5. **应用主题**
   - 参考 [THEMES.md](./THEMES.md) 了解主题系统
   - 使用 `d2 --theme 300 input.d2 output.svg` 应用主题

## 主要功能

### 支持的图表类型
- 流程图
- 架构图
- 组织结构图
- 网络图
- 时序图
- 序列图
- 状态机图
- 类图

### 核心特性
- **21 种内置主题**：从经典到现代，从亮色到暗色
- **多种布局引擎**：DAGRE、ELK、TALA
- **网格布局**：创建结构化的网格布局
- **丰富的形状库**：矩形、圆形、椭圆、菱形、圆柱体等
- **图标支持**：使用在线图标库，自动嵌入到 SVG
- **样式控制**：填充、边框、字体、透明度等
- **导出格式**：SVG、PNG、PDF

### 高级功能
- 类和继承：使用 `classes` 定义可重用的样式
- Markdown 支持：在标签中使用 Markdown 语法
- 变量系统：使用 `vars` 定义全局变量
- 嵌套结构：创建复杂的层次结构
- 连接样式：自定义连接的外观和行为

## 使用示例

### 最简单的示例

```d2
# hello.d2
x -> y
```

生成图表：
```bash
d2 hello.d2 hello.svg
```

### 带样式的示例

```d2
# styled.d2
classes: {
  server: {
    style: {
      fill: "#E1F5FE"
      stroke: "#0288D1"
    }
  }
}

web: Web 服务器 {
  class: server
}

db: 数据库 {
  shape: cylinder
}

web -> db: 查询
```

生成图表：
```bash
d2 styled.d2 styled.svg
```

### 使用主题

```d2
# themed.d2
vars: {
  d2-config: {
    theme-id: 300  # Terminal 主题
  }
}

start -> process -> end
```

生成图表：
```bash
d2 themed.d2 themed.svg
# 或者使用命令行参数
d2 --theme 300 themed.d2 themed.svg
```

## 工作流程

当用户请求创建图表时，按以下步骤操作：

### 步骤 1：理解需求 🎯

- 确定图表类型（流程图、架构图、组织结构图等）
- 明确关键元素和关系
- 确定样式偏好（主题、颜色等）

### 步骤 2：查阅文档 📚

根据需要查阅以下文档：

| 需求 | 查看文档 | 优先级 |
|------|----------|--------|
| 不熟悉 D2 语法 | quick-start.md | 高 |
| 需要查找特定语法 | SYNTAX.md | 高 |
| 参考类似示例 | EXAMPLES.md 或 examples/ | 高 |
| 需要使用图标 | ICONS.md | 中 |
| 需要设计指导 | BEST_PRACTICES.md | 中 |
| 选择合适的主题 | THEMES.md | 中 |
| 遇到安装问题 | INSTALL.md | 低 |

**重要提示**：
- **SYNTAX.md** 是最重要的文档，包含完整的语法参考
- **EXAMPLES.md** 和 **examples/** 目录提供了大量可直接参考的示例

### 步骤 3：编写 D2 代码 ✍️

- 创建 `.d2` 文件
- 参考 SYNTAX.md 中的语法
- 参考 EXAMPLES.md 中的示例
- 编写 D2 代码
- 添加适当的注释

### 步骤 4：生成图表 🎨

```bash
# 基本生成
d2 input.d2 output.svg

# 使用主题（参考 THEMES.md）
d2 --theme 300 input.d2 output.svg
```

### 步骤 5：迭代优化 🔄

- 根据需要调整 D2 代码
- 参考 BEST_PRACTICES.md 进行优化
- 检查生成的图表是否符合预期

### 快速参考

**常见任务的文档指引**：

| 任务 | 主要文档 | 辅助文档 |
|------|----------|----------|
| 学习基础 | quick-start.md | SYNTAX.md, examples/basic/ |
| 创建流程图 | SYNTAX.md, EXAMPLES.md | examples/basic/flow-chart.d2 |
| 创建架构图 | SYNTAX.md, EXAMPLES.md | examples/real-world/ |
| 使用图标 | ICONS.md | SYNTAX.md |
| 选择主题 | THEMES.md | EXAMPLES.md |
| 优化代码 | BEST_PRACTICES.md | SYNTAX.md |
| 解决问题 | SYNTAX.md, BEST_PRACTICES.md | EXAMPLES.md |
| 安装 D2 | INSTALL.md | README.md |

## 常用命令

```bash
# 基本转换
d2 input.d2 output.svg

# 使用主题
d2 --theme 300 input.d2 output.svg

# 导出为 PNG
d2 input.d2 output.png

# 导出为 PDF
d2 input.d2 output.pdf

# 设置布局引擎
d2 --layout elk input.d2 output.svg
```

## 📚 文档导航

本 skill 包含以下文档，按重要性和使用场景分类：

### ⭐ 核心文档（必读）

**[SYNTAX.md](./SYNTAX.md)** - D2 语法完整参考
- **作用**：完整的 D2 语法手册，包含所有语法元素和用法
- **何时查看**：
  - 需要查找特定语法（如形状、样式、布局）
  - 忘记如何使用某个功能
  - 需要了解语法细节
- **重要性**：★★★★★ 最重要

### 🚀 入门文档

**[quick-start.md](./quick-start.md)** - 5 分钟快速入门
- **作用**：快速上手指南，包含最基础的示例
- **何时查看**：
  - 第一次使用 D2
  - 需要快速回顾基础知识
- **重要性**：★★★★☆ 初学者必读

**[README.md](./README.md)** - 项目总览
- **作用**：项目介绍、快速开始、资源链接
- **何时查看**：
  - 需要了解项目概况
  - 查找资源链接
- **重要性**：★★★☆☆

### 💡 实用文档

**[ICONS.md](./ICONS.md)** - 图标参考清单
- **作用**：完整的图标分类和使用说明
- **何时查看**：
  - 需要为节点添加图标
  - 查找可用的图标类型
- **重要性**：★★★☆☆ 视觉增强

**[EXAMPLES.md](./EXAMPLES.md)** - 示例集合
- **作用**：从基础到真实场景的完整示例，每个示例都有详细说明
- **何时查看**：
  - 需要参考具体示例
  - 学习如何实现特定类型的图表
  - 寻找灵感
- **重要性**：★★★★☆ 实践必备

**[BEST_PRACTICES.md](./BEST_PRACTICES.md)** - 最佳实践
- **作用**：设计原则、命名规范、代码组织、常见错误和解决方案
- **何时查看**：
  - 需要创建高质量图表
  - 遇到设计或组织问题
  - 想要改进代码质量
- **重要性**：★★★☆☆ 进阶使用

**[THEMES.md](./THEMES.md)** - 主题系统
- **作用**：21 种内置主题的详细介绍、使用方法、选择指南
- **何时查看**：
  - 需要选择合适的主题
  - 想要了解主题效果
  - 需要自定义主题
- **重要性**：★★★☆☆ 视觉设计

### 🔧 工具文档

**[INSTALL.md](./INSTALL.md)** - 安装指南
- **作用**：D2 的详细安装步骤、故障排除
- **何时查看**：
  - 需要安装 D2
  - 遇到安装问题
- **重要性**：★★☆☆☆ 一次性使用

- **作用**：便捷的 D2 编译脚本，支持主题切换
- **何时使用**：
  - 需要批量编译
  - 需要频繁切换主题
- **重要性**：★☆☆☆☆ 可选工具

### 📁 示例文件

**examples/** 目录包含可直接运行的示例：
- `examples/basic/` - 基础示例（3个）
- `examples/intermediate/` - 中级示例（3个）
- `examples/advanced/` - 高级示例（2个）
- `examples/real-world/` - 真实场景示例（3个）

### 📖 文档使用建议

**学习顺序**（推荐）：
1. quick-start.md - 快速了解 D2
2. examples/basic/ - 运行基础示例
3. SYNTAX.md - 深入学习语法
4. EXAMPLES.md - 学习更多示例
5. BEST_PRACTICES.md - 提升代码质量

**工作时的查阅顺序**：
1. 遇到语法问题 → SYNTAX.md
2. 需要参考示例 → EXAMPLES.md 或 examples/
3. 需要使用图标 → ICONS.md
4. 设计决策 → BEST_PRACTICES.md
5. 选择主题 → THEMES.md
6. 安装问题 → INSTALL.md

## 示例目录

- `examples/basic/` - 基础示例
  - `flow-chart.d2` - 简单流程图
  - `tree.d2` - 树形结构
  - `network.d2` - 网络图

- `examples/intermediate/` - 中级示例
  - `with-classes.d2` - 使用类
  - `grid-layout.d2` - 网格布局
  - `styled.d2` - 样式自定义

- `examples/advanced/` - 高级示例
  - `complex-nested.d2` - 复杂嵌套结构
  - `vector-grid.d2` - 向量网格

- `examples/real-world/` - 真实场景示例
  - `cicd-pipeline.d2` - CI/CD 流程
  - `system-architecture.d2` - 系统架构
  - `org-structure.d2` - 组织结构

## 常见问题

### Q: D2 和其他图表工具（如 Mermaid、PlantUML）有什么区别？

A: D2 是专门为现代软件架构图设计的，具有以下优势：
- 更简洁的语法
- 更好的布局引擎
- 更丰富的主题系统
- 更好的可读性和可维护性

### Q: 可以导出哪些格式？

A: D2 支持 SVG（默认）、PNG 和 PDF 格式。SVG 是推荐格式，因为它是矢量格式，可以无损缩放。

### Q: 如何选择合适的主题？

A: 参考 [THEMES.md](./THEMES.md)，其中列出了所有 21 个主题及其适用场景。一般来说：
- 技术文档：使用 Terminal 主题（ID: 300）
- 商业演示：使用 Flagship Terrastruct 主题（ID: 2）
- 打印文档：使用 Cool Classics 主题（ID: 3）

### Q: 如何创建复杂的布局？

A: 使用网格布局和嵌套结构：
- 网格布局：`grid-columns: 3`, `grid-rows: 3`
- 嵌套结构：`parent: { child: Child }`
- 方向控制：`direction: down|right|up|left`

## 资源链接

- D2 官方网站：https://d2lang.com
- D2 文档：https://d2lang.com/tour/
- D2 GitHub：https://github.com/terrastruct/d2
- 图标库：https://icons.terrastruct.com

## 技巧和建议

1. **从简单开始**：先创建基本结构，再逐步添加样式和细节
2. **使用类**：通过 `classes` 重用样式，保持代码整洁
3. **添加注释**：使用 `#` 添加注释，提高代码可读性
4. **参考示例**：查看 `examples/` 目录中的示例文件
6. **选择合适的主题**：根据使用场景选择合适的主题
7. **保持简洁**：避免过度复杂化，保持图表清晰易懂
