# Server.py 冷启动逻辑适配新架构

## 概述

更新了 `server.py` 的冷启动逻辑以适配新的目录结构重构。主要改动包括模板目录结构重组和配置路径更新。

## 改动详情

### 1. 模板目录结构调整 ✅

#### 旧结构
```
web/matrix_template/
├── agents/              # Agent配置在根目录
│   └── User.yml
├── workspace/
│   └── .matrix/         # 系统目录在workspace下
│       └── user_sessions.json
└── README.md
```

#### 新结构
```
web/matrix_template/
├── .matrix/                    # 系统目录在根目录
│   ├── configs/                # 所有配置集中管理
│   │   ├── agents/             # Agent配置文件
│   │   │   └── User.yml
│   │   ├── system_config.yml   # 系统配置
│   │   └── matrix_config.yml   # Matrix全局配置
│   ├── database/               # 数据库目录
│   ├── logs/                   # 日志目录
│   ├── sessions/               # Session目录
│   └── user_sessions.json      # User sessions
├── workspace/                  # 工作区
│   ├── agent_files/            # Agent工作文件
│   └── SKILLS/                 # 用户技能
└── README.md
```

### 2. 配置路径更新 ✅

#### server.py 顶部配置变量
```python
# 旧代码
agents_dir = matrix_world_dir / "agents"
llm_config_path = agents_dir / "llm_config.json"

# 新代码
system_dir = matrix_world_dir / ".matrix"
configs_dir = system_dir / "configs"
agents_dir = configs_dir / "agents"           # .matrix/configs/agents
llm_config_path = agents_dir / "llm_config.json"  # .matrix/configs/agents/llm_config.json
system_config_path = configs_dir / "system_config.yml"  # .matrix/configs/system_config.yml
matrix_config_path = configs_dir / "matrix_config.yml"  # .matrix/configs/matrix_config.yml
```

#### app.state.config 更新
```python
app.state.config = {
    "matrix_world_dir": matrix_world_dir,
    "workspace_dir": workspace_dir,
    "system_dir": system_dir,                    # 🆕
    "configs_dir": configs_dir,                  # 🆕
    "agents_dir": agents_dir,
    "llm_config_path": llm_config_path,
    "system_config_path": system_config_path,    # 🆕
    "matrix_config_path": matrix_config_path,    # 🆕
    "host": args.host,
    "port": args.port,
    "reload": args.reload
}
```

### 3. 函数更新 ✅

#### `load_user_agent_name()` 函数
```python
def load_user_agent_name(matrix_world_dir: Path) -> str:
    """Load user agent name from matrix_config.yml configuration file"""
    # 新架构：从 .matrix/configs/matrix_config.yml 读取
    config_path = matrix_world_dir / ".matrix" / "configs" / "matrix_config.yml"

    # 向后兼容：尝试从旧的位置读取
    old_config_path = matrix_world_dir / "matrix_world.yml"
    if not config_path.exists() and old_config_path.exists():
        print("⚠️  Warning: Using old matrix_world.yml, please migrate to new structure")
        # 从旧文件读取
    ...
```

**改进：**
- 支持新架构的配置文件路径
- 保持向后兼容，可以从旧位置读取
- 更清晰的错误提示

#### `create_world_config()` 函数
```python
def create_world_config(matrix_world_dir: Path, user_name: str):
    """创建 matrix_config.yml 配置文件（新架构）"""
    config = {
        "user_agent_name": user_name,
        "matrix_version": "1.0.0",
        "description": "AgentMatrix World",
        "timezone": "UTC"
    }

    # 新架构：保存到 .matrix/configs/matrix_config.yml
    config_path = matrix_world_dir / ".matrix" / "configs" / "matrix_config.yml"
    config_path.parent.mkdir(parents=True, exist_ok=True)
    ...
```

**改进：**
- 创建完整的 Matrix 配置文件
- 包含更多配置项（version, description, timezone）
- 保存到新的配置目录

#### `create_directory_structure()` 函数
```python
def create_directory_structure(matrix_world_dir: Path, user_name: str):
    """创建 Matrix World 目录结构并复制模板，并替换 User agent 名称"""
    ...
    # 新架构：User.yml 在 .matrix/configs/agents/User.yml
    user_yml_path = matrix_world_dir / ".matrix" / "configs" / "agents" / "User.yml"
    ...
```

**改进：**
- 更新 User.yml 路径以匹配新架构
- 模板已经是正确的结构，直接复制即可

### 4. 新增配置文件模板 ✅

#### `system_config.yml` 模板
```yaml
# AgentMatrix System Configuration
email_proxy:
  enabled: false
  matrix_mailbox: ""
  user_mailbox: ""
  imap:
    host: "imap.gmail.com"
    port: 993
    user: ""
    password: ""
  smtp:
    host: "smtp.gmail.com"
    port: 587
    user: ""
    password: ""
```

#### `matrix_config.yml` 模板
```yaml
# AgentMatrix Configuration
user_agent_name: "User"
matrix_version: "1.0.0"
description: "AgentMatrix World"
timezone: "UTC"
```

## 向后兼容性

所有改动都保持了向后兼容性：

1. **配置文件加载** - 支持从旧位置和新位置读取
2. **目录结构** - 迁移工具可以转换旧结构到新结构
3. **冷启动流程** - 自动检测并使用新结构

## 测试清单

- [ ] 冷启动创建新的目录结构
- [ ] User.yml 中的 {{USER_NAME}} 占位符正确替换
- [ ] 配置文件正确创建在新的位置
- [ ] 从旧位置加载配置仍然有效（向后兼容）
- [ ] Agent 运行时正确使用新的路径
- [ ] Web 界面可以正常配置和启动

## 影响范围

### 修改的文件
1. `server.py` - 配置路径和函数更新
2. `web/matrix_template/` - 目录结构重组
3. `web/matrix_template/.matrix/configs/system_config.yml` - 新增
4. `web/matrix_template/.matrix/configs/matrix_config.yml` - 新增

### 不影响的部分
- AgentMatrix 运行时初始化（已在之前重构）
- PostOffice 和 SessionManager（已在之前重构）
- 迁移工具（独立工具，不受影响）

## 验证步骤

### 1. 测试冷启动
```bash
# 删除旧的 Matrix World
rm -rf ./MyWorld

# 启动服务器
python server.py --matrix-world ./MyWorld

# 访问 web 界面完成配置
open http://localhost:8000
```

### 2. 验证目录结构
```bash
# 检查新结构
ls -la ./MyWorld/.matrix/configs/
# 应该看到: agents/, system_config.yml, matrix_config.yml, llm_config.json
```

### 3. 测试向后兼容
```bash
# 如果有旧的 Matrix World，应该仍然可以正常启动
python server.py --matrix-world ./OldMyWorld
```

## 总结

这次更新完成了冷启动逻辑对新架构的适配，主要改进：

1. ✅ **统一的配置管理** - 所有配置集中在 `.matrix/configs/`
2. ✅ **清晰的目录结构** - 系统目录与工作区分离
3. ✅ **向后兼容** - 支持旧格式的配置文件
4. ✅ **更好的用户体验** - 冷启动自动创建完整结构

用户在第一次访问时会自动获得新的目录结构，无需手动干预。
