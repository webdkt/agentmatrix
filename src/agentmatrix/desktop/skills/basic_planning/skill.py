"""
Basic Planning Skill - Whiteboard + Todo List 管理工具

包含 actions：
- set_whiteboard: 操作白板（section/key/content 结构）
- set_todo: 操作任务清单（index/item/status 结构）

这两个功能是顶层 agent 的关注点，不应出现在嵌套 micro agent 中。
通过 self.root_agent 直接访问 WhiteboardManager / TodoManager。
"""

from agentmatrix.core.action import register_action


class Basic_planningSkillMixin:
    """
    Whiteboard + Todo List 管理技能。

    通过 root_agent 访问对应的 Manager，不依赖 MicroAgent 回调。
    """

    _skill_description = """项目规划工具。你可以使用 set_whiteboard 维护白板，用 set_todo 维护任务清单。

白板（whiteboard）是你和用户进行项目协作时的实时协作工具，也是你自己备忘、记录、规划的工具。
白板按 section 分组，每个 section 内的条目用 key 标识。

任务清单（todo list）记录任务进度，每条有编号、描述和状态。
状态有：planned（计划中）、working（进行中）、done（已完成）、canceled（已取消）。
"""

    _skill_dependencies = ["base"]

    @register_action(
        short_desc="(section, key, content) 设置/删除whiteboard条目, 要删除条目，content留空；要删除整个section，key和content都留空",
        description="操作白板（whiteboard）。按 section 分组，每条有 key 和 content。"
        "section+key+content 写入；section+key+空content 删除该条目；"
        "section+空key+空content 删除整个 section。白板持久化到文件，压缩后不清空。",
        param_infos={
            "section": "分组名称（必填）",
            "key": "条目标识（可选，留空表示操作整个 section）",
            "content": "要记录的内容，留空或不填则删除",
        },
    )
    async def set_whiteboard(self, section: str, key: str = "", content: str = "") -> str:
        return self.root_agent.whiteboard_manager.handle_action(self, section, key, content)

    @register_action(
        short_desc="(index, todo_str, status='planned|working|canceled|done', mode='replace|insert_after|insert_before') 添加/修改/删除todo条目,status默认planned, mode默认replace.如果要删除，todo_str留空即可。系统会自动调整编号以保持连续。",
        description="操作 Todo List。index 是条目编号字符串，item 是任务描述，status 是状态(planned/working/canceled/done)。"
        "index+item+status 创建/更新条目（status 留空默认 planned）；"
        "index+空item 删除该条目（status 会被忽略）；"
        "全部为空则清空所有 todo。Todo 持久化到文件，压缩后不清空。",
        param_infos={
            "index": "条目编号（如 '1', '2'）",
            "todo_str": "任务描述文本",
            "status": "状态：planned / working / canceled / done",
            "mode": "操作模式：replace / append / insert_before",
        },
    )
    async def set_todo(self, index: str = "", todo_str: str = "", status: str = "", mode: str = "replace") -> str:
        return self.root_agent.todo_manager.handle_action(self, index, todo_str, status, mode)
