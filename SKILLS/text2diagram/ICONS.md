# D2 图标参考清单

D2 图标库位于 https://icons.terrastruct.com

使用时图标会自动嵌入到生成的 SVG 中。

## 使用方法

```d2
# 基本用法
server: 服务器 {
  icon: https://icons.terrastruct.com/essentials/044-server.svg
}

# 图标 + 标签
database: 数据库 {
  icon: https://icons.terrastruct.com/essentials/117-database.svg
  label: 主数据库
}
```

## 常用图标分类

### Essentials（基础图标）

**服务器和基础设施**
- `009-desktop.svg` - 桌面电脑
- `044-server.svg` - 服务器
- `056-network.svg` - 网络
- `037-cloud.svg` - 云
- `031-database.svg` - 数据库
- `117-database.svg` - 数据库（备选）
- `220-layers.svg` - 层级结构

**开发和代码**
- `050-code.svg` - 代码
- `052-terminal.svg` - 终端
- `051-console.svg` - 控制台

**文件和文档**
- `001-file.svg` - 文件
- `002-file-text.svg` - 文本文件
- `003-folder.svg` - 文件夹
- `004-folder-open.svg` - 打开的文件夹

**安全**
- `065-lock.svg` - 锁
- `066-unlock.svg` - 解锁
- `067-shield.svg` - 盾牌
- `068-key.svg` - 密钥

**用户和人员**
- `072-user.svg` - 用户
- `073-users.svg` - 多用户
- `074-user-add.svg` - 添加用户

**操作**
- `085-settings.svg` - 设置
- `086-gear.svg` - 齿轮
- `087-tool.svg` - 工具

**箭头**
- `096-arrow-right.svg` - 右箭头
- `097-arrow-left.svg` - 左箭头
- `098-arrow-up.svg` - 上箭头
- `099-arrow-down.svg` - 下箭头

### Development（开发图标）

**版本控制**
- `024-git-commit.svg` - Git 提交
- `025-git-branch.svg` - Git 分支
- `026-git-merge.svg` - Git 合并
- `011-github.svg` - GitHub
- `012-gitlab.svg` - GitLab

**编程语言**
- `001-js.svg` - JavaScript
- `002-ts.svg` - TypeScript
- `003-python.svg` - Python
- `004-go.svg` - Go
- `005-rust.svg` - Rust
- `006-java.svg` - Java

### Infrastructure（基础设施）

**容器和编排**
- `004-docker.svg` - Docker
- `001-kubernetes.svg` - Kubernetes
- `008-server-rack.svg` - 服务器机架
- `010-container.svg` - 容器

**监控**
- `015-dashboard.svg` - 仪表板
- `016-chart.svg` - 图表
- `017-metrics.svg` - 指标

### Social（社交图标）

- `002-github.svg` - GitHub
- `003-twitter.svg` - Twitter
- `004-linkedin.svg` - LinkedIn
- `013-twitter-1.svg` - Twitter（备选）

### Cloud（云服务）

**主要云服务商**
- `001-aws.svg` - AWS
- `002-azure.svg` - Azure
- `003-gcp.svg` - Google Cloud

**Azure 具体服务**
- `azure/Web Service Color/App Service Domains.svg` - 应用服务域名

### Emojis（表情符号）

- 常见 emoji 图标用于装饰和强调

## 如何查找更多图标

1. 访问 https://icons.terrastruct.com 浏览完整图标库
2. 使用浏览器开发者工具查看图标 URL
3. 或使用常见图标名称模式：
   - Essentials: `essentials/XXX-name.svg`
   - Development: `development/XXX-name.svg`
   - Infrastructure: `infrastructure/XXX-name.svg`
   - Social: `social/XXX-name.svg`
   - Cloud: `cloud/XXX-name.svg`

## 图标在 SVG 中的处理

使用在线图标时，D2 会：
1. 自动下载图标内容
2. 嵌入到生成的 SVG 中
3. 图标成为 SVG 的一部分，无需额外依赖

## 使用自定义图标

```d2
# 使用其他网络图片
custom: 自定义 {
  icon: https://example.com/icon.png
}

# 使用图像节点
image: 图像节点 {
  shape: image
  icon: https://example.com/image.png
  width: 100
  height: 100
}
```

## 最佳实践

1. **使用图标增强可读性**：为常见元素添加图标
2. **保持一致性**：同类元素使用相同图标
3. **不要过度使用**：太多图标会显得混乱
4. **图标 + 标签**：重要节点应同时使用图标和文字标签
