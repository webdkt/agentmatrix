# D2 语法完整参考

这是 D2 语言的完整语法参考文档。D2 是一种现代化的图表脚本语言，专门用于创建各种类型的图表。

## 目录

- [基础语法](#基础语法)
- [对象和连接](#对象和连接)
- [形状](#形状)
- [样式](#样式)
- [布局](#布局)
- [类和继承](#类和继承)
- [连接样式](#连接样式)
- [标签和文本](#标签和文本)
- [特殊功能](#特殊功能)
- [变量和配置](#变量和配置)

## 基础语法

### 注释

使用 `#` 添加单行注释：

```d2
# 这是一个注释
x -> y  # 行尾注释
```

### 对象定义

基本语法：`name: Label`

```d2
# 简单对象
user: 用户
server: 服务器

# 带空格的标签
database: 主数据库
```

### 嵌套对象

使用大括号创建嵌套结构：

```d2
company: 公司 {
  engineering: 工程部 {
    frontend: 前端团队
    backend: 后端团队
  }

  sales: 销售部
}
```

### 连接

使用 `->` 创建单向连接：

```d2
A -> B
A -> B: 标签
A -> B: {
  style.stroke-dash: 3
}
```

使用 `<->` 创建双向连接：

```d2
A <-> B: 双向关系
```

链式连接：

```d2
A -> B -> C -> D
```

## 对象和连接

### 多个连接

```d2
# 多个源到同一个目标
A -> C
B -> C

# 一个源到多个目标
A -> B
A -> C
A -> D
```

### 连接标签

```d2
# 简单标签
A -> B: 连接标签

# 多行标签
A -> B: "第一行\n第二行"

# 带样式的标签
A -> B: 标签 {
  style.stroke: red
}
```

### 连接到嵌套对象

```d2
# 连接到嵌套对象
company -> company.engineering.frontend

# 从嵌套对象连接
company.engineering.frontend -> external
```

## 形状

### 基本形状

```d2
# 矩形（默认）
rect1: 矩形

# 圆形
circle1: 圆形 {
  shape: circle
}

# 椭圆
ellipse1: 椭圆 {
  shape: ellipse
}

# 菱形
diamond1: 菱形 {
  shape: diamond
}

# 圆柱体（数据库）
db1: 数据库 {
  shape: cylinder
}

# 存储数据
storage1: 存储 {
  shape: stored_data
}

# 文本
text1: 文本节点 {
  shape: text
}

# 步骤（流程图）
step1: 步骤 {
  shape: step
}

# 六边形
hex1: 六边形 {
  shape: hexagon
}

# 平行四边形
parallelogram1: 平行四边形 {
  shape: parallelogram
}
```

### 图像和图标

```d2
# 使用图标
icon1: 图标节点 {
  icon: https://icons.terrastruct.com/essentials/009-desktop.svg
}

# 使用图像
image1: 图像节点 {
  shape: image
  icon: https://example.com/image.png
}
```

### 形状尺寸

```d2
# 设置宽度和高度
size1: 固定尺寸 {
  width: 100
  height: 50
}

# 只设置宽度（高度自动计算）
width1: 固定宽度 {
  width: 200
}
```

## 样式

### 基本样式属性

```d2
styled: 样式示例 {
  style: {
    # 填充颜色
    fill: "#FF5722"

    # 边框颜色
    stroke: "#BF360C"

    # 边框宽度
    stroke-width: 2

    # 虚线边框
    stroke-dash: 5

    # 圆角
    border-radius: 10

    # 字体大小
    font-size: 20

    # 字体样式
    font: mono  # mono, sans, serif

    # 透明度（0-1）
    opacity: 0.8

    # 多个实例
    multiple: true
  }
}
```

### 颜色表示

```d2
# 十六进制
color1: 示例 {
  style.fill: "#FF5722"
}

# RGB
color2: 示例 {
  style.fill: "rgb(255, 87, 34)"
}

# RGBA
color3: 示例 {
  style.fill: "rgba(255, 87, 34, 0.5)"
}

# 颜色名称
color4: 示例 {
  style.fill: red
}
```

### 边框样式

```d2
# 实线（默认）
solid: 实线 {
  style.stroke-width: 2
}

# 虚线
dashed: 虚线 {
  style.stroke-dash: 5
}

# 点线
dotted: 点线 {
  style.stroke-dash: 2
}
```

## 布局

### 方向

```d2
# 从上到下（默认）
direction: down

# 从左到右
direction: right

# 从下到上
direction: up

# 从右到左
direction: left
```

### 网格布局

```d2
grid: 网格 {
  grid-columns: 3
  grid-rows: 3
  grid-gap: 10

  cell1: "1"
  cell2: "2"
  cell3: "3"
  cell4: "4"
  cell5: "5"
  cell6: "6"
  cell7: "7"
  cell8: "8"
  cell9: "9"
}
```

### 位置控制

```d2
# 标签位置
label1: 标签在顶部 {
  label.near: top
}

label2: 标签在底部 {
  label.near: bottom
}

label3: 标签在左侧 {
  label.near: left
}

label4: 标签在右侧 {
  label.near: right
}

# 外部位置
label5: 外部标签 {
  label.near: outside-top
}
```

### 可用位置值

- `top`, `bottom`, `left`, `right`
- `top-center`, `top-left`, `top-right`
- `bottom-center`, `bottom-left`, `bottom-right`
- `outside-top`, `outside-bottom`, `outside-left`, `outside-right`
- `outside-top-left`, `outside-top-right`, `outside-bottom-left`, `outside-bottom-right`

## 类和继承

### 定义类

```d2
classes: {
  server: {
    style: {
      fill: "#E1F5FE"
      stroke: "#0288D1"
      stroke-width: 2
      font: mono
    }
  }

  database: {
    shape: cylinder
    style: {
      fill: "#FFF3E0"
      stroke: "#F57C00"
    }
  }

  highlight: {
    style: {
      fill: "#FFCDD2"
      stroke: "#D32F2F"
      stroke-width: 3
    }
  }
}
```

### 使用类

```d2
classes: {
  server: {
    style.fill: "#E1F5FE"
  }
}

# 应用单个类
web1: Web 服务器 {
  class: server
}

# 应用多个类
web2: Web 服务器 {
  class: server
  class: highlight
}
```

### 样式继承

```d2
# 使用通配符
container: 容器 {
  *.style.fill: "#E3F2FD"
  child1: 子节点1
  child2: 子节点2
  child3: 子节点3
}
```

## 连接样式

### 连接样式

```d2
# 基本连接样式
A -> B: 实线

# 虚线连接
A -> B: 虚线 {
  style.stroke-dash: 3
}

# 自定义颜色
A -> B: 彩色 {
  style.stroke: "#FF5722"
}

# 自定义宽度
A -> B: 粗线 {
  style.stroke-width: 3
}
```

### 连接标签位置

```d2
# 标签在起点
A -> B: 标签 {
  label.near: start
}

# 标签在终点
A -> B: 标签 {
  label.near: end
}
```

### 连接透明度

```d2
A -> B: 半透明连接 {
  style.opacity: 0.5
}
```

## 标签和文本

### 基本标签

```d2
# 简单标签
node1: 简单标签

# 带空格的标签
node2: 带空格的标签

# 多行标签
node3: "第一行\n第二行"
```

### Markdown 支持

```d2
# 使用 Markdown
description: |md
  ## 标题
  - 项目1
  - 项目2
  - 项目3
|
```

### 文本样式

```d2
# 设置字体样式
text1: 文本 {
  style: {
    font-size: 16
    font: mono  # mono, sans, serif
    font-weight: bold  # bold, normal
    font-style: italic  # italic, normal
  }
}
```

## 特殊功能

### 图标

```d2
# 使用图标
icon1: 图标示例 {
  icon: https://icons.terrastruct.com/essentials/009-desktop.svg
}

# 图标 + 标签
icon2: 带标签 {
  icon: https://icons.terrastruct.com/essentials/009-desktop.svg
  label: 服务器
}
```

### 图像

```d2
# 使用图像
image1: 图像示例 {
  shape: image
  icon: https://example.com/image.png
  width: 200
  height: 150
}
```

### 多个实例

```d2
# 表示可以有多个实例
servers: 服务器 {
  style.multiple: true
}
```

### SQL 表

```d2
# SQL 表格
users: 用户表 {
  shape: sql_table
  id: INTEGER
  name: VARCHAR
  email: VARCHAR
}
```

## 变量和配置

### D2 配置

```d2
vars: {
  d2-config: {
    # 设置主题
    theme-id: 300

    # 设置布局引擎
    layout-engine: elk  # dagre, elk, tala

    # 其他配置
    direction: down
  }
}

# 使用配置后的节点
x -> y
```

### 自定义变量

```d2
vars: {
  primary-color: "#FF5722"
  secondary-color: "#4CAF50"
}

# 使用变量（通过类）
classes: {
  primary: {
    style.fill: "${primary-color}"
  }
}
```

### 主题 ID 列表

常用主题：
- `0` - Neutral Default（默认）
- `2` - Flagship Terrastruct
- `3` - Cool Classics
- `300` - Terminal
- `301` - Terminal Grayscale
- `304` - Dark Mauve
- `305` - Dark Flagship Terrastruct

完整主题列表请参考 [THEMES.md](./THEMES.md)

## 高级技巧

### 条件样式

```d2
# 使用类实现条件样式
classes: {
  success: {
    style.fill: "#4CAF50"
  }
  error: {
    style.fill: "#F44336"
  }
  warning: {
    style.fill: "#FF9800"
  }
}

node1: 成功 {
  class: success
}

node2: 错误 {
  class: error
}
```

### 复杂嵌套

```d2
# 多层嵌套
system: 系统 {
  frontend: 前端 {
    web: Web 界面 {
      react: React 组件
      vue: Vue 组件
    }
    mobile: 移动端 {
      ios: iOS 应用
      android: Android 应用
    }
  }

  backend: 后端 {
    api: API 服务 {
      rest: REST API
      graphql: GraphQL API
    }
    database: 数据库 {
      primary: 主数据库
      replica: 从数据库
    }
  }
}
```

### 批量样式设置

```d2
# 使用通配符批量设置
container: 容器 {
  # 所有子节点的样式
  *.style.fill: "#E3F2FD"
  *.style.stroke: "#1976D2"

  node1: 节点1
  node2: 节点2
  node3: 节点3
}
```

### 动态标签

```d2
# 使用变量创建动态标签
vars: {
  app-name: "我的应用"
  version: "v1.0.0"
}

title: "${app-name} ${version}"
```

## 完整示例

```d2
# 一个完整的 D2 示例

# 定义配置
vars: {
  d2-config: {
    theme-id: 300
    direction: down
  }
}

# 定义类
classes: {
  server: {
    style: {
      fill: "#E1F5FE"
      stroke: "#0288D1"
      stroke-width: 2
      font: mono
    }
  }

  database: {
    shape: cylinder
    style: {
      fill: "#FFF3E0"
      stroke: "#F57C00"
    }
  }
}

# 定义结构
loadbalancer: 负载均衡器 {
  icon: https://icons.terrastruct.com/essentials/056-network.svg
}

web1: Web 服务器1 {
  class: server
}

web2: Web 服务器2 {
  class: server
}

app: 应用服务器 {
  class: server
}

cache: 缓存 {
  shape: cylinder
  style.fill: "#F3E5F5"
}

db: 主数据库 {
  class: database
}

# 定义连接
loadbalancer -> web1
loadbalancer -> web2
web1 -> app
web2 -> app
app -> cache
app -> db

# 添加连接标签
app -> db: 查询
app -> cache: 读取 {
  style.stroke-dash: 3
}
```

## 语法速查表

| 语法 | 说明 | 示例 |
|------|------|------|
| `#` | 注释 | `# 这是注释` |
| `name: Label` | 对象定义 | `server: 服务器` |
| `{ }` | 嵌套 | `parent: { child: Child }` |
| `->` | 单向连接 | `A -> B` |
| `<->` | 双向连接 | `A <-> B` |
| `shape:` | 形状 | `shape: circle` |
| `style.` | 样式 | `style.fill: red` |
| `class:` | 类应用 | `class: server` |
| `classes:` | 类定义 | `classes: { name: {...} }` |
| `direction:` | 方向 | `direction: down` |
| `grid-` | 网格 | `grid-columns: 3` |

## 最佳实践

1. **使用注释**：为复杂的图表添加注释说明
2. **使用类**：通过类重用样式，保持代码整洁
3. **命名规范**：使用清晰、描述性的名称
4. **保持简洁**：避免过度复杂化
5. **使用主题**：选择合适的主题，减少自定义样式
6. **分层结构**：使用嵌套来组织复杂的图表
7. **测试验证**：生成并检查结果

## 相关资源

- [EXAMPLES.md](./EXAMPLES.md) - 查看更多示例
- [THEMES.md](./THEMES.md) - 了解主题系统
- [BEST_PRACTICES.md](./BEST_PRACTICES.md) - 学习最佳实践
- [quick-start.md](./quick-start.md) - 快速入门
