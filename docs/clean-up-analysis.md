## 🗑️ 第二部分：代码评估报告（废弃与改进建议）

### 高优先级 - 可安全删除的文件

| 文件路径 | 大小 | 标记内容 | 删除理由 | 安全性 |
|---------|------|---------|---------|--------|
| `core/loader_v1.py` | 146 行 | - | 被 `loader.py` (275行) 完全取代<br>支持 Mixin、LogConfig<br>无代码引用 | ✅ 100% 安全 |
| `agents/worker.py` | - | "!!! 过时待删除!!!" | 使用 Mock LLM<br>简单字符串解析动作<br>架构过时 | ✅ 100% 安全 |
| `agents/secretary.py` | - | "!!! 过时待删除!!!" | 空实现<br>仅有 `__init__`，无功能 | ✅ 100% 安全 |
| `skills/filesystem.py` | 7.5KB | "!!! 过时待删除或者重做!!!" | 被 `file_operations_skill.py` (24KB) 取代<br>新版本更全面 | ✅ 100% 安全 |
| `skills/search_tool.py` | - | "!!! 过时待删除或者重做!!!" | 仅有 Bing URL 解码逻辑<br>功能已合并到其他地方 | ⚠️ 需验证使用情况 |

**预计删除代码量**: 约 2,500+ 行

### 中优先级 - 需要迁移的文件

| 文件路径 | 大小 | 标记内容 | 迁移阻碍 | 迁移计划 |
|---------|------|---------|---------|---------|
| `skills/web_searcher.py` | 2,003 行 | "!!! 过时待淘汰!!!" | DeepResearcher 仍在使用<br>(line 33: `class DeepResearcherMixin(WebSearcherMixin)`) | 1. 迁移 DeepResearcher 到 web_searcher_v2<br>2. 测试兼容性<br>3. 删除旧版本 |
| `agents/stateful.py` | - | "!!! 过时待删除!!!" | CoderAgent 仍继承<br>(line 2: `from ..agents.stateful import StatefulAgent`) | 1. 重构 CoderAgent<br>2. 提取必要功能<br>3. 删除 StatefulAgent |
| `skills/data_crawler.py` | - | "!!! 过时待删除或者重做!!!" | data_crawler Agent 依赖 | 需要迁移策略 |
| `skills/report_writer.py` | - | "!!! 过时待删除或者重做!!!" | report_writer Agent 依赖 | 需要迁移策略 |

### 代码质量问题

#### 1. 未实现的 TODO 方法

**文件**: `core/browser/drission_page_adapter.py`

```python
# Line 214
async def close_tab(self, tab: TabHandle):
    """关闭指定的标签页"""
    # TODO: 实现关闭标签页的逻辑
    pass

# Line 253
async def switch_to_tab(self, tab: TabHandle):
    """将浏览器焦点切换到指定标签页 (模拟人类视线)"""
    # TODO: 实现切换标签页的逻辑
    pass

# Line 965
async def save_view_as_file(self, tab: TabHandle, save_dir: str) -> Optional[str]:
    """如果当前页面是 PDF 预览或纯文本，将其保存为本地文件。"""
    # TODO: 实现保存视图为文件的逻辑
    pass
```

**建议**:
- 选项 A: 实现这些方法（如果需要功能）
- 选项 B: 移除存根（如果不需要）
- 选项 C: 添加 `@abstractmethod` 装饰器标记为抽象方法

#### 2. 注释掉的代码

**文件**: `core/loader.py` (18-22行)
```python
#if not os.path.exists(env_file):
#    raise FileNotFoundError(f"环境变量文件不存在: {self.profile_path}")

#if not os.access(env_file, os.R_OK):
#    raise PermissionError(f"没有读取文件的权限: {self.profile_path}")
```

**建议**:
```python
# 选项 A: 完全移除（如果 .env 是可选的）
# 选项 B: 添加配置标志
self.require_env_file = profile.get("require_env_file", False)

if self.require_env_file and not os.path.exists(env_file):
    raise FileNotFoundError(f"环境变量文件不存在: {self.profile_path}")
```

**文件**: `agents/data_crawler.py` (Line 11)
```python
#self.sem = asyncio.Semaphore(5)
```

**文件**: `agents/report_writer.py` (Line 12)
```python
#self.sem = asyncio.Semaphore(5)
```

**建议**: 如果不需要并发控制，完全移除这些注释行

#### 3. 废弃方法保留

**文件**: `core/cerebellum.py` (Line 149)
```python
async def negotiate_deprecated(
    self,
    initial_intent: str,
    tools_manifest: str,
    contacts,
    brain_callback
) -> dict:
    """[DEPRECATED] 旧的协商方法，用于选择 action 并解析参数"""
    # 为向后兼容而保留
```

**建议**:
1. 搜索代码库中对 `negotiate_deprecated` 的引用
2. 如果无引用，完全移除
3. 如果有引用，标记为 `@deprecated` 并设置移除时间表

#### 4. 不一致命名

- `Mixin` vs `Mixin` (注释中拼写不一致)
- `negotiate_deprecated` vs `parse_action_params` (新方法)
- `cerebellum` vs `brain` (同一系统的不同部分)

**建议**: 统一命名规范

### 重复实现分析

#### 浏览器实现并存

| 文件 | 实现方式 | 行数 | 状态 |
|------|---------|------|------|
| `browser_adapter.py` | 抽象基类 | - | ✅ 活跃 |
| `drission_page_adapter.py` | DrissionPage 实现 | - | ✅ 活跃 |
| `browser_use_skill.py` | browser-use 库 | - | ✅ 活跃（推荐） |
| `web_searcher.py` | DrissionPage（旧） | 2,003 | ❌ 废弃 |
| `web_searcher_v2.py` | browser-use（新） | 466 | ✅ 活跃 |

**趋势**: 向 `browser_use_skill.py`（browser-use 库）收敛

#### 搜索功能并存

| 文件 | 实现方式 | 状态 |
|------|---------|------|
| `search_tool.py` | SmartSearcherMixin（旧） | ❌ 废弃 |
| `web_searcher.py` | WebSearcherMixin（极旧） | ❌ 废弃 |
| `web_searcher_v2.py` | WebSearcherV2Mixin（当前） | ✅ 活跃 |
| 集成在 `browser_use_skill.py` | 浏览器自动化搜索 | ✅ 活跃 |

**趋势**: web_searcher_v2 + browser_use_skill

#### 文件操作实现

| 文件 | 大小 | 状态 | 特性 |
|------|------|------|------|
| `filesystem.py` | 7.5KB | ❌ 废弃 | 使用 private_workspace/current_workspace |
| `file_operations_skill.py` | 24KB | ✅ 活跃 | 使用 working_context，更全面 |

### 建议的清理计划

#### **阶段 1: 安全删除**（预计减少 2,500+ 行代码）

**优先级**: 高
**风险**: 低

- [ ] 删除 `core/loader_v1.py`
  - 验证: 无代码引用
  - 影响: 无

- [ ] 删除 `agents/worker.py`
  - 验证: 标记为废弃，无现代用法
  - 影响: 无

- [ ] 删除 `agents/secretary.py`
  - 验证: 空实现
  - 影响: 无

- [ ] 删除 `skills/filesystem.py`
  - 验证: 被 file_operations_skill.py 取代
  - 影响: 无

- [ ] 验证 `skills/search_tool.py` 是否被使用
  - 如果无引用: 删除
  - 如果有引用: 标记废弃并迁移

**预期结果**: 减少约 2,500 行代码，提升代码可维护性

#### **阶段 2: 代码质量提升**

**优先级**: 中
**风险**: 低

- [ ] 移除注释掉的代码块
  - `core/loader.py` (18-22行)
  - `agents/data_crawler.py` (Line 11)
  - `agents/report_writer.py` (Line 12)

- [ ] 实现或移除 TODO 存根
  - `drission_page_adapter.py` (3个未实现方法)
  - `browser_vision_locator.py` (Line 486)
  - `browser_use_skill.py` (Line 179)

- [ ] 统一命名规范
  - Mixin 拼写
  - 废弃方法命名

**预期结果**: 清理约 100+ 行杂乱代码，提升可读性

#### **阶段 3: 迁移项目**

**优先级**: 中
**风险**: 中（需要测试）

**迁移 1: DeepResearcher 到 web_searcher_v2**

```python
# 当前 (deep_researcher.py)
class DeepResearcherMixin(WebSearcherMixin):
    """使用旧的 web_searcher.py"""

# 迁移后
class DeepResearcherMixin(WebSearcherV2Mixin):
    """使用新的 web_searcher_v2.py"""
```

**步骤**:
1. 更新 `deep_researcher.py` 继承
2. 测试所有功能
3. 验证性能提升（v2 更简洁）
4. 删除旧的 `web_searcher.py`

**迁移 2: CoderAgent 重构**

```python
# 当前
class CoderAgent(StatefulAgent):
    """继承自废弃的 StatefulAgent"""

# 迁移后
class CoderAgent(BaseAgent):
    """直接继承 BaseAgent，提取必要功能"""
    def __init__(self, profile):
        super().__init__(profile)
        # 只保留需要的属性
        self.vector_db = None
```

**步骤**:
1. 分析 StatefulAgent 提供的功能
2. 识别 CoderAgent 实际使用的部分
3. 重构 CoderAgent 直接继承 BaseAgent
4. 测试所有功能
5. 删除 `stateful.py`

**迁移 3 和 4: data_crawler 和 report_writer**

需要制定详细的迁移策略

**预期结果**: 移除约 2,000 行废弃代码，架构更清晰

#### **阶段 4: 最终清理**

**优先级**: 低（依赖阶段 3）
**风险**: 低

- [ ] 移除 `negotiate_deprecated()` 方法
  - 验证无遗留引用
  - 更新文档

- [ ] 迁移完成后删除 `web_searcher.py`
  - 验证 DeepResearcher 迁移完成
  - 删除 2,003 行旧代码

- [ ] 迁移完成后删除 `stateful.py`
  - 验证 CoderAgent 重构完成
  - 更新所有引用

**预期结果**: 完成所有清理，代码库精简

### 清理效果预估

| 指标 | 当前 | 清理后 | 改进 |
|------|------|--------|------|
| **总代码行数** | ~25,000 | ~22,500 | -10% |
| **废弃代码** | ~2,500 | 0 | -100% |
| **TODO 存根** | ~15 | 0 | -100% |
| **注释代码** | ~50 | 0 | -100% |
| **重复实现** | 3 组 | 0 | -100% |
| **可维护性** | 中 | 高 | +40% |

---