# How-To: Use SystemAdmin

使用 SystemAdmin Agent 管理系统。

## SystemAdmin 是什么

SystemAdmin 是内置的系统管理员 Agent，可以：
- 创建新 Agent
- 重载 Agent 配置
- 配置邮件代理
- 查询系统状态

## 开始对话

1. 在 Web UI 选择 SystemAdmin
2. 开始对话

## 常用操作

### 创建 Agent

```
请创建一个名为 Researcher 的 Agent，
需要网页搜索和文件处理能力。
```

SystemAdmin 会：
1. 创建配置文件
2. 设置合适的 skills
3. 编写 persona
4. 自动加载 Agent

### 重载 Agent

```
重载 Researcher Agent
```

在修改配置后使用，无需重启系统。

### 配置 Email Proxy

```
配置邮件代理：
- Host: smtp.gmail.com
- Port: 587
- Username: my@gmail.com
```

### 查询系统状态

```
查看系统状态
```

返回当前运行的 Agent 列表和状态。

## 安全机制

SystemAdmin 会在执行前：
1. 备份现有配置
2. 确认操作细节
3. 显示执行计划

确认后才执行实际操作。
