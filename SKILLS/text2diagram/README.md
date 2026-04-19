# Text2Diagram - D2 图表技能包

这是一个基于 D2 的图表创建技能包，专门为 Claude Code Agent 设计，帮助快速学习和使用 D2 语言创建各种类型的图表。

## 什么是 D2？

D2 是一种现代化的图表脚本语言，可以将文本描述转换为美观的图表。它支持流程图、架构图、组织结构图、网络图等多种图表类型。

## 快速开始

### 1. 安装 D2

```bash
# 使用官方安装脚本
curl -fsSL https://d2lang.com/install.sh | sh -s --

# 验证安装
d2 --version
```

### 2. 创建第一个图表

```bash
# 创建示例文件
echo 'x -> y -> z' > hello.d2

# 生成图表
d2 hello.d2 hello.svg
```

## 项目结构

```
text2diagram/
├── SKILL.md                       # Claude Code skill 定义文件
├── SYNTAX.md                      # D2 语法完整参考（核心文档）
├── EXAMPLES.md                    # 示例集合和说明
├── BEST_PRACTICES.md              # 最佳实践和设计原则
├── THEMES.md                      # 主题系统完整指南
├── quick-start.md                 # 5 分钟快速入门
├── README.md                      # 本文件
└── examples/                      # 示例文件目录
    ├── basic/                     # 基础示例
    ├── intermediate/              # 中级示例
    ├── advanced/                  # 高级示例
    └── real-world/                # 真实场景示例
```

## 核心文档

### SKILL.md
Claude Code skill 的定义文件，包含技能的触发条件和使用说明。

### SYNTAX.md ⭐
**最重要的文档** - D2 语言的完整语法参考，包含：
- 基础语法
- 对象和连接
- 形状和样式
- 布局控制
- 类和继承
- 高级功能

### EXAMPLES.md
丰富的示例集合，从基础到真实场景，每个示例都有详细说明。

### BEST_PRACTICES.md
设计原则和最佳实践，帮助你创建高质量的图表。

### THEMES.md
完整的主题系统指南，介绍所有 21 种内置主题及其使用方法。

### quick-start.md
5 分钟快速入门指南，适合初学者。

## 使用方法

### 方法 1：使用 Claude Code skill

当需要创建图表时，Claude Code 会自动调用此 skill，提供专业的图表创建支持。

### 方法 2：手动使用 D2

```bash
# 基本用法
d2 input.d2 output.svg

# 使用主题
d2 --theme 300 input.d2 output.svg
```

## 示例

### 基础示例

```d2
# 简单流程图
start: 开始
process: 处理
end: 结束

start -> process -> end
```

### 中级示例

```d2
# 使用类和样式
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

### 高级示例

查看 `examples/` 目录中的完整示例。

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
- **丰富的形状库**：矩形、圆形、菱形、圆柱体等
- **图标支持**：使用 URL 添加图标
- **样式控制**：填充、边框、字体、透明度等
- **导出格式**：SVG、PNG、PDF

## 学习路径

### 初学者
1. 阅读 [quick-start.md](./quick-start.md)
2. 参考 [examples/basic/](./examples/basic/) 中的基础示例
3. 参考 [SYNTAX.md](./SYNTAX.md) 学习语法

### 中级学习者
1. 学习 [examples/intermediate/](./examples/intermediate/) 中的中级示例
2. 阅读 [BEST_PRACTICES.md](./BEST_PRACTICES.md)
3. 实践使用类和布局

### 高级学习者
1. 研究 [examples/advanced/](./examples/advanced/) 和 [examples/real-world/](./examples/real-world/)
2. 深入学习 [THEMES.md](./THEMES.md)
3. 创建复杂的自定义图表

## 常用命令

```bash
# 基本转换
d2 input.d2 output.svg

# 使用主题
d2 --theme 300 input.d2 output.svg

# 导出 PNG
d2 input.d2 output.png

# 导出 PDF
d2 input.d2 output.pdf

# 设置布局引擎
d2 --layout elk input.d2 output.svg
```

## 主题选择

| ID | 主题名称 | 适用场景 |
|----|----------|----------|
| 0 | Neutral Default | 通用、默认 |
| 3 | Flagship Terrastruct | 商业演示 |
| 4 | Cool Classics | 技术文档、打印 |
| 100 | Vanilla Nitro Cola | 现代 Web |
| 300 | Terminal | 技术文档、代码 |
| 301 | Terminal Grayscale | 黑白打印 |
| 200 | Dark Mauve | 暗色环境 |

完整主题列表请参考 [THEMES.md](./THEMES.md)。


## 常见问题

### Q: D2 和其他图表工具有什么区别？

A: D2 专为现代软件架构设计，具有更简洁的语法、更好的布局引擎和更丰富的主题系统。

### Q: 可以导出哪些格式？

A: D2 支持 SVG（默认）、PNG 和 PDF 格式。

### Q: 如何选择合适的主题？

A: 参考 [THEMES.md](./THEMES.md)，根据使用场景选择：
- 技术文档：Terminal (300)
- 商业演示：Flagship Terrastruct (3)
- 打印文档：Cool Classics (4)

### Q: 如何创建复杂的布局？

A: 使用网格布局和嵌套结构：
```d2
grid: 网格 {
  grid-columns: 3
  grid-rows: 3
  # ...
}
```

## 资源链接

- **D2 官方网站**: https://d2lang.com
- **D2 Playground**: https://play.d2lang.com
- **D2 文档**: https://d2lang.com/tour/
- **D2 GitHub**: https://github.com/terrastruct/d2
- **图标库**: https://icons.terrastruct.com

## 贡献

这个项目是从 D2 官方项目提炼出的技能包，专注于让 Agent 能够快速学习和使用 D2。

如需贡献改进建议，请参考 D2 官方项目：https://github.com/terrastruct/d2

## 许可证

本项目基于 D2 项目，遵循 Mozilla Public License 2.0。

D2 项目地址：https://github.com/terrastruct/d2

## 作者

本项目由 Claude Code Agent 创建，旨在帮助 Agent 和用户快速掌握 D2 图表创建技能。

---

**提示**: 参考 [SYNTAX.md](./SYNTAX.md) 和 [EXAMPLES.md](./EXAMPLES.md) 学习 D2 的最佳方式！
