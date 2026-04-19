# D2 示例目录

本文档列出了所有可用的 D2 示例文件，按难度和用途分类。每个示例都是完整的、可运行的 D2 代码。

## 如何使用这些示例

### 查看示例

```bash
# 查看示例文件
cat examples/basic/flow-chart.d2

# 或使用编辑器打开
vim examples/basic/flow-chart.d2
```

### 运行示例

```bash
# 生成图表
d2 examples/basic/flow-chart.d2 output.svg
```

### 学习示例

1. **查看源代码**：直接阅读 `.d2` 文件
2. **理解语法**：参考 [SYNTAX.md](./SYNTAX.md) 了解语法
3. **运行修改**：修改文件并查看效果
4. **参考注释**：示例文件中有详细的注释说明

## 示例分类

### 📁 基础示例（Basic）

**位置**: `examples/basic/`

适合初学者，展示最基本的 D2 语法和概念。

#### 1. 简单流程图

**文件**: `examples/basic/flow-chart.d2`

**内容**: 最基础的流程图，展示基本连接关系

**关键语法**:
- 节点定义: `name: Label`
- 基本连接: `A -> B`
- 带标签连接: `A -> B: label`
- 样式: `A -> B: label { style.stroke-dash: 3 }`

**适用场景**: 了解 D2 基本语法

**运行**:
```bash
d2 examples/basic/flow-chart.d2 flow.svg
```

#### 2. 树形结构

**文件**: `examples/basic/tree.d2`

**内容**: 展示嵌套对象和层次结构

**关键语法**:
- 嵌套结构: `parent: { child: Child }`
- 多层嵌套
- 层次关系

**适用场景**: 组织结构、分类体系

**运行**:
```bash
d2 examples/basic/tree.d2 tree.svg
```

#### 3. 网络图

**文件**: `examples/basic/network.d2`

**内容**: 简单的网络拓扑图

**关键语法**:
- 形状: `shape: cylinder`
- 图标: `icon: URL`
- 多对多连接
- 连接标签

**适用场景**: 网络架构、系统拓扑

**运行**:
```bash
d2 examples/basic/network.d2 network.svg
```

---

### 📁 中级示例（Intermediate）

**位置**: `examples/intermediate/`

展示更高级的语法和设计模式。

#### 1. 使用类（Classes）

**文件**: `examples/intermediate/with-classes.d2`

**内容**: 使用 classes 定义可重用的样式

**关键语法**:
- 类定义: `classes: { name: { ... } }`
- 类应用: `class: name`
- 样式继承

**适用场景**: 需要保持样式一致性的大型图表

**学习要点**:
- 如何定义类
- 如何应用类
- 避免重复代码

**运行**:
```bash
d2 examples/intermediate/with-classes.d2 classes.svg
```

#### 2. 网格布局

**文件**: `examples/intermediate/grid-layout.d2`

**内容**: 使用网格系统创建结构化布局

**关键语法**:
- 网格定义: `grid-columns: 3`, `grid-rows: 3`
- 间距设置: `grid-gap: 10`
- 批量样式: `*.style.fill: color`

**适用场景**: 需要规则排列的元素

**学习要点**:
- 网格布局的使用
- 批量样式设置
- 方向控制

**运行**:
```bash
d2 examples/intermediate/grid-layout.d2 grid.svg
```

#### 3. 样式自定义

**文件**: `examples/intermediate/styled.d2`

**内容**: 展示各种样式选项的使用

**关键语法**:
- 基本样式: `fill`, `stroke`, `stroke-width`
- 虚线: `stroke-dash`
- 透明度: `opacity`
- 不同形状: `shape: circle`, `shape: cylinder`

**适用场景**: 需要自定义外观

**学习要点**:
- 样式属性
- 颜色表示
- 形状选择

**运行**:
```bash
d2 examples/intermediate/styled.d2 styled.svg
```

---

### 📁 高级示例（Advanced）

**位置**: `examples/advanced/`

展示复杂的高级技巧和特殊功能。

#### 1. 复杂嵌套结构

**文件**: `examples/advanced/complex-nested.d2`

**内容**: 多层嵌套和复杂关系

**关键语法**:
- 多层嵌套
- Markdown 文本: `label: |md ... |`
- 复杂引用
- 链接定义: `link: path.to.node`

**适用场景**: 复杂的层次结构、图表组合

**学习要点**:
- 深层嵌套的使用
- Markdown 文本的应用
- 复杂关系的表示

**运行**:
```bash
d2 examples/advanced/complex-nested.d2 complex.svg
```

#### 2. 向量网格

**文件**: `examples/advanced/vector-grid.d2`

**内容**: 数学可视化和复杂网格布局

**关键语法**:
- 复杂网格
- 嵌套网格
- 形状组合
- 数学概念可视化

**适用场景**: 数学图表、数据可视化

**学习要点**:
- 高级网格布局
- 多层网格嵌套
- 抽象概念的视觉化

**运行**:
```bash
d2 examples/advanced/vector-grid.d2 vector.svg
```

---

### 📁 真实场景示例（Real-World）

**位置**: `examples/real-world/`

来自实际项目的真实示例，展示 D2 在现实中的应用。

#### 1. CI/CD 流程图

**文件**: `examples/real-world/cicd-pipeline.d2`

**内容**: 完整的 CI/CD 流程

**关键语法**:
- 类的定义和应用
- 图标和图像的使用
- 网格布局在流程图中的应用
- 现实场景的抽象

**适用场景**: DevOps、持续集成/部署

**学习要点**:
- 真实项目的图表设计
- 复杂流程的组织
- 图标的使用

**运行**:
```bash
d2 examples/real-world/cicd-pipeline.d2 cicd.svg
```

#### 2. 系统架构图

**文件**: `examples/real-world/system-architecture.d2`

**内容**: Twitter 系统的高级架构

**关键语法**:
- 复杂的系统架构表示
- Markdown 说明的使用
- 图标和形状的组合
- 容器和模块化

**适用场景**: 软件架构、系统设计

**学习要点**:
- 大型系统的组织
- 架构层次的表达
- 模块化设计

**运行**:
```bash
d2 examples/real-world/system-architecture.d2 architecture.svg
```

#### 3. 组织结构图

**文件**: `examples/real-world/org-structure.d2`

**内容**: 组织关系和利益相关者图

**关键语法**:
- 清晰的层次结构
- 复杂的关系表示
- 双向关系的使用
- 连接标签的应用

**适用场景**: 组织结构、利益相关者分析

**学习要点**:
- 组织关系的表示
- 多种关系的处理
- 清晰的层次设计

**运行**:
```bash
d2 examples/real-world/org-structure.d2 org.svg
```

---

## 示例文件列表

所有示例文件的完整列表：

```
text2diagram/
├── examples/
│   ├── basic/                    # 基础示例
│   │   ├── flow-chart.d2        # 简单流程图
│   │   ├── tree.d2              # 树形结构
│   │   └── network.d2           # 网络图
│   ├── intermediate/             # 中级示例
│   │   ├── with-classes.d2      # 使用类
│   │   ├── grid-layout.d2       # 网格布局
│   │   └── styled.d2            # 样式自定义
│   ├── advanced/                 # 高级示例
│   │   ├── complex-nested.d2    # 复杂嵌套
│   │   └── vector-grid.d2       # 向量网格
│   └── real-world/               # 真实场景
│       ├── cicd-pipeline.d2     # CI/CD 流程
│       ├── system-architecture.d2 # 系统架构
│       └── org-structure.d2     # 组织结构
```

## 学习路径

### 初学者路径

1. **开始**: `examples/basic/flow-chart.d2`
   - 了解基本语法
   - 理解节点和连接

2. **进阶**: `examples/basic/tree.d2`
   - 学习嵌套结构
   - 理解层次关系

3. **练习**: `examples/basic/network.d2`
   - 尝试修改代码
   - 添加新的节点和连接

### 中级学习者路径

1. **类**: `examples/intermediate/with-classes.d2`
   - 学习使用类
   - 理解样式重用

2. **布局**: `examples/intermediate/grid-layout.d2`
   - 掌握网格布局
   - 学习方向控制

3. **样式**: `examples/intermediate/styled.d2`
   - 深入样式系统
   - 自定义外观

### 高级学习者路径

1. **嵌套**: `examples/advanced/complex-nested.d2`
   - 学习复杂嵌套
   - 理解 Markdown 文本

2. **现实应用**: `examples/real-world/`
   - 研究真实场景
   - 学习最佳实践

## 按用途查找示例

### 流程图
- 基础: `examples/basic/flow-chart.d2`
- 真实: `examples/real-world/cicd-pipeline.d2`

### 架构图
- 基础: `examples/basic/network.d2`
- 真实: `examples/real-world/system-architecture.d2`

### 层次结构
- 基础: `examples/basic/tree.d2`
- 真实: `examples/real-world/org-structure.d2`

### 样式和布局
- 类: `examples/intermediate/with-classes.d2`
- 网格: `examples/intermediate/grid-layout.d2`
- 样式: `examples/intermediate/styled.d2`

## 技巧和建议

### 1. 查看示例代码

```bash
# 查看示例
cat examples/basic/flow-chart.d2

# 使用编辑器
vim examples/basic/flow-chart.d2

# 使用 less（可以滚动查看）
less examples/basic/flow-chart.d2
```

### 2. 修改和实验

```bash
# 复制示例
cp examples/basic/flow-chart.d2 my-diagram.d2

# 编辑修改
vim my-diagram.d2

# 生成图表
d2 my-diagram.d2 my-diagram.svg
```

### 3. 对比学习

```bash
# 查看基础和进阶版本的差异
diff examples/basic/network.d2 examples/real-world/system-architecture.d2
```

### 4. 批量运行

```bash
# 生成所有示例的图表
for f in examples/*/*.d2; do
  d2 "$f" "${f%.d2}.svg"
done
```

## 常见问题

### Q: 如何选择合适的示例？

A: 根据你的需求：
- **学习基础**: 从 `examples/basic/` 开始
- **实现特定功能**: 查找相似的真实示例
- **解决具体问题**: 参考最接近的示例

### Q: 示例可以直接使用吗？

A: 可以！所有示例都是完整的、可运行的。你可以：
- 直接运行查看效果
- 复制修改为你的需求
- 作为模板使用

### Q: 如何理解示例代码？

A: 建议步骤：
1. 运行示例，查看效果
2. 阅读代码和注释
3. 参考 [SYNTAX.md](./SYNTAX.md) 了解语法
4. 修改代码，观察变化

### Q: 示例不够怎么办？

A:
1. 参考 [SYNTAX.md](./SYNTAX.md) 学习语法
2. 访问 D2 Playground: https://play.d2lang.com
3. 查看 D2 官方文档: https://d2lang.com

## 相关资源

- **[SYNTAX.md](./SYNTAX.md)** - 完整语法参考
- **[quick-start.md](./quick-start.md)** - 快速入门
- **[BEST_PRACTICES.md](./BEST_PRACTICES.md)** - 最佳实践
- **[THEMES.md](./THEMES.md)** - 主题系统

## 下一步

1. 选择一个适合你的示例
2. 查看源代码
3. 运行并查看效果
4. 修改并实验
5. 应用于你的项目

**提示**: 参考 [SYNTAX.md](./SYNTAX.md) 和实验修改是学习 D2 的最佳方式！
