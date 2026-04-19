# D2 快速开始指南

欢迎使用 D2！这是一个 5 分钟快速入门指南，帮助你快速上手创建图表。

## 前置条件

### 1. 安装 D2

```bash
# 使用官方安装脚本（推荐）
curl -fsSL https://d2lang.com/install.sh | sh -s --

# 或使用 Go
go install oss.terrastruct.com/d2@latest

# 或使用 Homebrew（macOS）
brew install d2

# 验证安装
d2 --version
```

### 2. 验证安装

```bash
$ d2 --version
D2 - A modern diagram scripting language
Version: vX.X.X
```

## 第一个图表

### 步骤 1：创建 D2 文件

创建一个名为 `hello.d2` 的文件，内容如下：

```d2
# 我的第一个 D2 图表
hello: Hello
world: World
hello -> world: D2
```

### 步骤 2：生成图表

```bash
d2 hello.d2 hello.svg
```

### 步骤 3：生成图表

`hello.svg` 文件已生成，这是一个简单的流程图！

## 3 分钟示例

### 示例 1：简单流程图（30 秒）

**flow.d2:**
```d2
start: 开始
process: 处理
end: 结束

start -> process -> end
```

**生成：**
```bash
d2 flow.d2 flow.svg
```

### 示例 2：添加样式（1 分钟）

**styled.d2:**
```d2
# 定义样式
classes: {
  important: {
    style: {
      fill: "#FFCDD2"
      stroke: "#D32F2F"
      stroke-width: 3
    }
  }
}

# 使用样式
start: 开始
process: 处理 {
  class: important
}
end: 结束

start -> process -> end
```

### 示例 3：嵌套结构（1.5 分钟）

**nested.d2:**
```d2
# 嵌套结构
company: 公司 {
  engineering: 工程部 {
    frontend: 前端团队
    backend: 后端团队
  }

  product: 产品部 {
    design: 设计团队
    pm: 产品经理
  }
}

engineering -> product: 协作
```

## 常用命令

### 基本转换

```bash
# SVG（默认）
d2 input.d2 output.svg

# PNG
d2 input.d2 output.png

# PDF
d2 input.d2 output.pdf
```

### 使用主题

```bash
# Terminal 主题
d2 --theme 300 input.d2 output.svg

# Dark 主题
d2 --theme 304 input.d2 output.svg
```

### 布局引擎

```bash
# ELK 布局
d2 --layout elk input.d2 output.svg

# DAGRE 布局（默认）
d2 --layout dagre input.d2 output.svg
```

## 核心概念

### 1. 对象

```d2
name: Label
```

### 2. 连接

```d2
# 单向
A -> B

# 带标签
A -> B: 连接标签

# 双向
A <-> B
```

### 3. 样式

```d2
node: 节点 {
  style: {
    fill: "#FF5722"
    stroke: "#BF360C"
    stroke-width: 2
  }
}
```

### 4. 形状

```d2
circle: 圆形 {
  shape: circle
}

database: 数据库 {
  shape: cylinder
}
```

### 5. 嵌套

```d2
parent: 父节点 {
  child1: 子节点1
  child2: 子节点2
}
```

## 下一步学习

### 1. 深入学习语法

查看 **[SYNTAX.md](./SYNTAX.md)** - 完整的 D2 语法参考

### 2. 查看示例

查看 **[EXAMPLES.md](./EXAMPLES.md)** - 丰富的示例集合

或直接查看 `examples/` 目录：
- `examples/basic/` - 基础示例
- `examples/intermediate/` - 中级示例
- `examples/advanced/` - 高级示例
- `examples/real-world/` - 真实场景示例

### 3. 学习最佳实践

查看 **[BEST_PRACTICES.md](./BEST_PRACTICES.md)** - 设计原则和技巧

### 4. 了解主题系统

查看 **[THEMES.md](./THEMES.md)** - 21 种内置主题

## 实用技巧

### 技巧 1：使用类重用样式

```d2
classes: {
  server: {
    style: {
      fill: "#E1F5FE"
      stroke: "#0288D1"
    }
  }
}

web1: Web 服务器 {
  class: server
}

web2: Web 服务器 {
  class: server
}
```

### 技巧 2：使用注释

```d2
# 这是一个流程图
# 作者：你的名字
# 日期：2024-01-01

start: 开始
process: 处理
end: 结束
```

### 技巧 3：使用网格布局

```d2
grid: 网格 {
  grid-columns: 3
  grid-rows: 2

  cell1: "1"
  cell2: "2"
  cell3: "3"
  cell4: "4"
  cell5: "5"
  cell6: "6"
}
```

### 技巧 4：使用图标

```d2
# 从 icons.terrastruct.com 获取图标
server: 服务器 {
  icon: https://icons.terrastruct.com/essentials/056-network.svg
}
```

## 常见问题

### Q: 如何创建复杂的图表？

A: 从简单开始，逐步添加复杂度：
1. 先创建基本结构和连接
2. 添加样式和类
3. 调整布局和细节

### Q: 如何选择合适的主题？

A: 参考 [THEMES.md](./THEMES.md)，常见选择：
- 技术文档：Terminal (300)
- 商业演示：Flagship Terrastruct (2)
- 打印文档：Cool Classics (3)

### Q: 如何调整布局？

A: 使用布局控制：
- `direction: down|right|up|left` - 控制方向
- `grid-columns: 3`, `grid-rows: 3` - 网格布局
- `--layout elk|dagre` - 切换布局引擎

```bash
# 使用 ELK 布局引擎
d2 --layout elk input.d2 output.svg
```

### Q: 如何创建大型图表？

A: 使用嵌套和模块化：
- 将大型图表分解为小的模块
- 使用嵌套结构组织内容
- 使用类重用样式
- 添加注释说明各部分

## 在线资源

- **D2 官方网站**：https://d2lang.com
- **D2 Playground**：https://play.d2lang.com（在线试用）
- **图标库**：https://icons.terrastruct.com
- **GitHub 仓库**：https://github.com/terrastruct/d2

## 快速参考

### 语法速查

| 语法 | 说明 |
|------|------|
| `#` | 注释 |
| `name: Label` | 对象定义 |
| `->` | 单向连接 |
| `<->` | 双向连接 |
| `shape: circle` | 设置形状 |
| `style.fill: red` | 设置填充颜色 |
| `class: name` | 应用类 |
| `direction: down` | 设置方向 |

### 常用形状

- `rectangle` - 矩形（默认）
- `circle` - 圆形
- `ellipse` - 椭圆
- `diamond` - 菱形
- `cylinder` - 圆柱体（数据库）
- `stored_data` - 存储数据

### 常用样式

- `fill` - 填充颜色
- `stroke` - 边框颜色
- `stroke-width` - 边框宽度
- `stroke-dash` - 虚线样式
- `font-size` - 字体大小
- `opacity` - 透明度

## 下一步

现在你已经掌握了 D2 的基础知识！接下来：

1. 查看 [SYNTAX.md](./SYNTAX.md) 学习完整的语法
2. 查看 [EXAMPLES.md](./EXAMPLES.md) 了解更多示例
3. 查看 [BEST_PRACTICES.md](./BEST_PRACTICES.md) 学习最佳实践
4. 开始创建你自己的图表！

**提示**：参考 [SYNTAX.md](./SYNTAX.md) 和 [EXAMPLES.md](./EXAMPLES.md) 是学习 D2 的最佳方式。
