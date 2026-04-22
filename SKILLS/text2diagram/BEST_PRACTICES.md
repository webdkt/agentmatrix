# D2 最佳实践和设计原则

本文档提供了使用 D2 创建图表的最佳实践、设计原则和常见问题的解决方案。

## 目录

- [设计原则](#设计原则)
- [命名规范](#命名规范)
- [代码组织](#代码组织)
- [样式管理](#样式管理)
- [性能优化](#性能优化)
- [常见错误和解决方案](#常见错误和解决方案)
- [图表设计原则](#图表设计原则)

## 设计原则

### 1. 简洁性优先

**好的做法**:
```d2
# 简洁明了
user -> server -> database
```

**避免**:
```d2
# 过度复杂
user: 用户 {
  style: {
    fill: "#FF5722"
    stroke: "#BF360C"
    stroke-width: 2
    border-radius: 5
    font-size: 14
    font-weight: bold
  }
  icon: https://example.com/icon.svg
  width: 100
  height: 50
  label: 用户
  label.near: center
}
```

### 2. 渐进式复杂度

从简单开始，逐步添加复杂度：

```d2
# 步骤1：基本结构
A -> B -> C

# 步骤2：添加标签
A -> B: 开始
B -> C: 结束

# 步骤3：添加样式
A -> B: 开始 {
  style.stroke: blue
}
```

### 3. 保持一致性

使用类来保持样式一致：

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

## 命名规范

### 1. 节点命名

使用清晰、描述性的名称：

```d2
# 好的命名
user_service: 用户服务
payment_gateway: 支付网关
order_processor: 订单处理器

# 避免模糊的命名
s1: 服务
s2: 服务
x: 节点
```

### 2. 使用英文 ID 和中文标签

```d2
# 推荐
user_service: 用户服务 {
  icon: https://icons.terrastruct.com/essentials/009-desktop.svg
}

# 便于引用
user_service -> database
```

### 3. 连接命名

```d2
# 清晰的连接标签
user -> auth: 登录
auth -> database: 验证
database -> auth: 返回用户信息

# 避免无意义的标签
A -> B: 连接
A -> B: 关系
```

## 代码组织

### 1. 使用注释分区

```d2
# ============================================
# 系统架构图
# 作者：张三
# 日期：2024-01-01
# ============================================

# 前端层
frontend: 前端 {
  # ... 省略
}

# 后端层
backend: 后端 {
  # ... 省略
}

# 数据层
database: 数据库 {
  # ... 省略
}
```

### 2. 逻辑分组

```d2
# 将相关的节点放在一起
# 认证系统
auth_service: 认证服务
user_db: 用户数据库
session_cache: 会话缓存

# 支付系统
payment_service: 支付服务
payment_gateway: 支付网关
transaction_db: 交易数据库
```

### 3. 使用嵌套组织

```d2
system: 系统名称 {
  layer1: 第一层 {
    component1: 组件1
    component2: 组件2
  }

  layer2: 第二层 {
    component3: 组件3
    component4: 组件4
  }
}
```

## 样式管理

### 1. 使用类而不是内联样式

```d2
# 好的做法：使用类
classes: {
  important: {
    style: {
      fill: "#FFCDD2"
      stroke: "#D32F2F"
      stroke-width: 2
    }
  }
}

critical: 关键节点 {
  class: important
}

# 避免：重复的内联样式
node1: 节点1 {
  style.fill: "#FFCDD2"
  style.stroke: "#D32F2F"
  style.stroke-width: 2
}

node2: 节点2 {
  style.fill: "#FFCDD2"
  style.stroke: "#D32F2F"
  style.stroke-width: 2
}
```

### 2. 使用主题

```d2
# 使用内置主题
vars: {
  d2-config: {
    theme-id: 300  # Terminal 主题
  }
}

# 而不是自定义所有颜色
```

### 3. 批量样式设置

```d2
container: 容器 {
  # 批量设置子节点样式
  *.style.fill: "#E3F2FD"
  *.style.stroke: "#1976D2"
  *.style.font-size: 14

  node1: 节点1
  node2: 节点2
  node3: 节点3
}
```

## 性能优化

### 1. 避免过度嵌套

```d2
# 好的做法：扁平化结构
service_a: 服务A
service_b: 服务B
service_c: 服务C

service_a -> service_b
service_b -> service_c

# 避免：过深的嵌套
system: {
  layer1: {
    group1: {
      subgroup1: {
        service_a: 服务A
      }
    }
  }
}
```

### 2. 使用网格布局

```d2
# 对于规则排列的节点，使用网格
grid: "" {
  grid-columns: 3
  grid-rows: 3

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

### 3. 优化连接

```d2
# 避免过多的交叉连接
# 好的做法：清晰的层次
layer1 -> layer2
layer2 -> layer3

# 避免：混乱的连接
node1 -> node5
node1 -> node3
node2 -> node4
node3 -> node1
node4 -> node2
node5 -> node3
```

## 常见错误和解决方案

### 1. 语法错误

**错误**: 缺少引号
```d2
# 错误
node: 未闭合的标签

# 正确
node: "未闭合的标签"
```

**错误**: 缺少闭合括号
```d2
# 错误
parent: {
  child: 子节点

# 正确
parent: {
  child: 子节点
}
```

### 2. 布局问题

**问题**: 节点重叠
```d2
# 解决方案：使用网格布局
grid: "" {
  grid-columns: 2
  grid-rows: 2

  node1: 节点1
  node2: 节点2
  node3: 节点3
  node4: 节点4
}
```

**问题**: 布局方向不对
```d2
# 解决方案：设置方向
direction: right  # 或 down, up, left
```

### 3. 样式问题

**问题**: 样式不生效
```d2
# 检查语法
node: 节点 {
  style: {
    fill: red  # 确保使用正确的语法
  }
}

# 或使用类
classes: {
  styled: {
    style.fill: red
  }
}
```

**问题**: 颜色显示不对
```d2
# 使用十六进制颜色
style.fill: "#FF5722"

# 或使用颜色名称
style.fill: red

# 避免使用不支持的颜色格式
```

## 图表设计原则

### 1. 信息层次

建立清晰的视觉层次：

```d2
# 主要元素使用更明显的样式
primary: 主要组件 {
  style: {
    fill: "#FFCDD2"
    stroke-width: 3
  }
}

# 次要元素使用较轻的样式
secondary: 次要组件 {
  style: {
    fill: "#E1F5FE"
    stroke-width: 1
  }
}
```

### 2. 颜色使用

**选择合适的颜色方案**:
- 使用主题保持一致性
- 限制颜色数量（3-5种）
- 使用对比色突出重要元素

```d2
classes: {
  success: {
    style.fill: "#4CAF50"  # 绿色
  }
  warning: {
    style.fill: "#FF9800"  # 橙色
  }
  error: {
    style.fill: "#F44336"  # 红色
  }
}
```

### 3. 空间利用

```d2
# 合理使用空间，避免拥挤
container: 容器 {
  grid-gap: 10  # 设置间距

  node1: 节点1 {
    width: 100
    height: 50
  }
  node2: 节点2 {
    width: 100
    height: 50
  }
}
```

### 4. 标签和文本

```d2
# 使用清晰的标签
node: 清晰的标签

# 避免过长的标签
node: "这是一个非常非常长的标签"

# 使用多行标签
node: "第一行\n第二行"

# 或使用 Markdown
node: |md
  ## 标题
  - 项目1
  - 项目2
|
```

## 特定场景的最佳实践

### 1. 流程图

```d2
# 使用标准形状
start: 开始 {
  shape: circle
}

process: 处理 {
  shape: rectangle
}

decision: 判断 {
  shape: diamond
}

end: 结束 {
  shape: circle
}

# 清晰的流程
start -> process -> decision
decision -> end: 是
decision -> process: 否
```

### 2. 架构图

```d2
# 使用嵌套表示层次
system: 系统 {
  frontend: 前端层 {
    web: Web
    mobile: 移动端
  }

  backend: 后端层 {
    api: API
    service: 服务
  }

  database: 数据层 {
    primary: 主库
    replica: 从库
  }
}

# 清晰的数据流
frontend.web -> backend.api
backend.api -> backend.service
backend.service -> database.primary
```

### 3. 网络图

```d2
# 使用图标表示设备
router: 路由器 {
  icon: https://icons.terrastruct.com/essentials/056-network.svg
}

switch: 交换机 {
  icon: https://icons.terrastruct.com/essentials/093-switch.svg
}

server: 服务器 {
  icon: https://icons.terrastruct.com/essentials/044-server.svg
}

# 标注连接类型
router -> switch: 千兆
switch -> server: 百兆
```

## 维护和更新

### 1. 版本控制

```d2
# 在文件顶部添加元数据
# 架构图 v2.0
# 最后更新：2024-01-01
# 作者：张三
# 更新内容：添加了缓存层
```

### 2. 文档化

```d2
# 添加说明性注释
# 用户认证流程
# 1. 用户提交凭证
# 2. 系统验证凭证
# 3. 返回认证结果

user -> auth: 提交凭证
auth -> database: 验证
database -> auth: 返回结果
auth -> user: 认证结果
```

### 3. 模块化

```d2
# 将大型图表分解为模块
# 可以单独维护和测试

module1: 模块1 {
  # ... 内容
}

module2: 模块2 {
  # ... 内容
}

module3: 模块3 {
  # ... 内容
}

# 连接模块
module1 -> module2
module2 -> module3
```

## 测试和验证

### 1. 验证语法

```bash
# 检查语法错误
d2 diagram.d2 /dev/null

# 或使用格式化
d2 fmt diagram.d2
```

### 2. 验证语法

```bash
# 检查语法错误
d2 diagram.d2 /dev/null

# 或使用格式化
d2 fmt diagram.d2
```

### 3. 检查输出

```bash
# 生成 SVG 并检查
d2 diagram.d2 diagram.svg
```

## 工作流建议

### 1. 创建新图表的步骤

1. **规划**: 手绘草图，确定主要元素和关系
2. **基础结构**: 创建基本节点和连接
3. **添加细节**: 添加标签、样式和注释
4. **优化**: 调整布局和样式
5. **验证**: 生成图表并检查
6. **迭代**: 根据需要调整

### 2. 修改现有图表的步骤

1. **备份**: 复制原文件
2. **理解**: 查看现有结构和样式
3. **修改**: 进行必要的修改
4. **测试**: 生成图表验证
5. **文档**: 更新注释和版本信息

### 3. 团队协作建议

- 建立命名规范
- 使用一致的样式
- 添加清晰的注释
- 版本控制
- 定期审查和更新

## 相关资源

- **[SYNTAX.md](./SYNTAX.md)** - 完整语法参考
- **[EXAMPLES.md](./EXAMPLES.md)** - 示例集合
- **[quick-start.md](./quick-start.md)** - 快速入门
- **[THEMES.md](./THEMES.md)** - 主题系统

## 总结

遵循这些最佳实践可以帮助你：

1. **创建更清晰的图表**: 通过良好的组织和命名
2. **提高代码可维护性**: 通过一致的样式和结构
3. **优化性能**: 通过避免过度复杂化
4. **减少错误**: 通过遵循最佳实践
5. **提升协作效率**: 通过标准化和文档化

记住：好的图表不仅要美观，更要清晰、准确地传达信息。
