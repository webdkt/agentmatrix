# Profile 文件清理清单

## 📋 需要清理的文件和属性

### 🔴 高优先级清理（立即执行）

#### 1. `src/agentmatrix/profiles/planner.yml`

**需要删除的配置：**
```yaml
❌ top_level_actions:  # 废弃的旧架构
  - "deep_research"

❌ system_prompt: |  # 未使用，应使用 persona.base
  你是一个任务规划助手...
```

**应该保留的配置：**
```yaml
✅ name: Planner
✅ description: 任务规划助手
✅ module: agentmatrix.agents.base
✅ class_name: BaseAgent
✅ persona:  # 保留或新增
   base: |
     你是一个任务规划助手...
✅ skills:  # 新增
   - file
```

#### 2. `src/agentmatrix/profiles/researcher.yml`

**需要删除的配置：**
```yaml
❌ system_prompt: |  # 未使用
  你是一个资深研究员...
```

**当前配置已经是正确的：**
```yaml
✅ skills:
  - file  # 已经使用新架构
```

#### 3. `src/agentmatrix/profiles/mark.yml`

**需要检查的配置：**
```yaml
❌ system_prompt: |  # 未使用，需要检查是否可以用 persona.base 替代
  你是 Mark，一个专业的研究助手...
```

**建议：**
- 如果 `system_prompt` 的内容和 `persona.base` 重复，删除 `system_prompt`
- 保留 `persona.base`

#### 4. `src/agentmatrix/profiles/user_proxy.yml`

**需要删除的配置：**
```yaml
❌ system_prompt: ""  # 空配置，未使用，直接删除
```

### 🟡 中优先级清理（检查后决定）

#### 1. `src/agentmatrix/profiles/researcher.yml`

**需要检查的配置：**
```yaml
⚠️ attribute_initializations:
  browser_adapter: null  # 如果已有 browser skill，可能不需要
  default_search_engine: "google"  # 检查是否确实需要
```

**建议：**
- 检查代码中是否实际使用了 `browser_adapter` 和 `default_search_engine`
- 如果未使用，删除这些配置

#### 2. `src/agentmatrix/profiles/mark.yml`

**需要检查的配置：**
```yaml
⚠️ class_attributes:
  _custom_log_level: 10  # 可以用 logging 配置替代
```

**建议：**
- 改用 `logging.level: DEBUG`
- 删除 `class_attributes`

### 🟢 低优先级（保留）

以下配置虽然使用不多，但建议保留：
- `instruction_to_caller` - UI 可能使用
- `cerebellum` - 如果需要 action 优化
- `vision_brain` - 如果需要图片理解
- `prompts` - 自定义 prompt 模板

## 🔧 清理步骤

### 步骤 1：备份现有配置
```bash
cp src/agentmatrix/profiles/planner.yml src/agentmatrix/profiles/planner.yml.backup
cp src/agentmatrix/profiles/researcher.yml src/agentmatrix/profiles/researcher.yml.backup
cp src/agentmatrix/profiles/mark.yml src/agentmatrix/profiles/mark.yml.backup
cp src/agentmatrix/profiles/user_proxy.yml src/agentmatrix/profiles/user_proxy.yml.backup
```

### 步骤 2：删除废弃配置

#### planner.yml
```yaml
# 删除这些行：
top_level_actions:
  - "deep_research"

system_prompt: |
  你是一个任务规划助手...
```

#### researcher.yml
```yaml
# 删除这些行：
system_prompt: |
  你是一个资深研究员...
```

#### mark.yml
```yaml
# 删除这些行：
system_prompt: |
  你是 Mark，一个专业的研究助手...
```

#### user_proxy.yml
```yaml
# 删除这些行：
system_prompt: ""
```

### 步骤 3：验证配置

运行测试确保配置仍然有效：
```bash
# 测试 profile 加载
python -c "
from agentmatrix.core.profiles import ProfileLoader
loader = ProfileLoader('src/agentmatrix/profiles')
profile = loader.load('planner')
print(f'✅ {profile.name} loaded successfully')
"
```

### 步骤 4：提交变更

```bash
git add src/agentmatrix/profiles/*.yml
git commit -m "🧹 清理 profile 配置中的废弃属性

- 删除 top_level_actions（已被 skills 替代）
- 删除 system_prompt（未使用，应使用 persona.base）
- 参考 docs/profile-configuration-guide.md"
```

## 📊 清理前后对比

### planner.yml 清理前后

**清理前（30+ 行）：**
```yaml
name: Planner
description: 任务规划助手
module: agentmatrix.agents.base
class_name: BaseAgent
top_level_actions:              # ❌ 废弃
  - "deep_research"
persona:
  base: |
    你是一个任务规划助手...
system_prompt: |               # ❌ 未使用
  你是一个任务规划助手...
```

**清理后（10 行）：**
```yaml
name: Planner
description: 任务规划助手
module: agentmatrix.agents.base
class_name: BaseAgent
persona:
  base: |
    你是一个任务规划助手...
skills:                        # ✅ 新增
  - file
```

## ⚠️ 注意事项

1. **不要同时修改多个文件**：一次修改一个文件，测试通过后再修改下一个
2. **保留备份**：清理前先备份原文件
3. **运行测试**：每次修改后都要运行相关测试
4. **检查依赖**：确认没有其他代码依赖这些配置

## ✅ 清理完成标志

当所有文件清理完成后：
- ✅ 没有 `top_level_actions` 配置
- ✅ 没有 `system_prompt` 配置
- ✅ 所有 agent 都使用 `skills` 配置
- ✅ 所有 agent 都使用 `persona` 配置
- ✅ 测试全部通过

---

**创建时间**: 2025-02-21
**状态**: 📝 待执行
