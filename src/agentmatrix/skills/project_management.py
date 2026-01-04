# skills/project_management.py
import os
import time
import textwrap
from datetime import datetime
from ..core.action import register_action

class ProjectManagementMixin:
    """
    赋予 Agent 项目经理的能力：
    1. 维护一个持久化的 Project Board (看板)。
    2. 能够主动压缩上下文 (Memory Compression)，只保留看板和最近的对话。
    3. 自动归档旧的历史记录到文件 (Audit Trail)。
    """

    def _get_board(self):
        """获取当前看板，如果没有则初始化"""
        if not hasattr(self, 'project_board') or self.project_board is None:
            self.project_board = "Project Initialized. Waiting for scope definition."
        return self.project_board

    def _archive_history(self, old_history, reason):
        """[Side Effect] 将被清理的对话记录归档到本地文件，防止永久丢失"""
        if not self.workspace_root:
            return

        archive_dir = os.path.join(self.workspace_root, self.name, "logs", "archives")
        os.makedirs(archive_dir, exist_ok=True)
        
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"{self.name}_archive_{timestamp}.log"
        filepath = os.path.join(archive_dir, filename)

        with open(filepath, "w", encoding='utf-8') as f:
            f.write(f"=== ARCHIVE REASON: {reason} ===\n")
            f.write(f"=== BOARD STATE ===\n{self.project_board}\n")
            f.write("=== CONVERSATION HISTORY ===\n")
            for msg in old_history:
                role = msg.get('role','')
                content = msg.get('content','')
                if role and content:
                    f.write(f"[{role}]: {content}\n{'-'*20}\n")
        
        if hasattr(self, 'logger'):
            self.logger.info(f"Old memory archived to {filename}")

    @register_action(
        "阶段总结，更新项目看板,Markdown格式。项目状态发生重要变化后或者处理了比较多封邮件后需要阶段性的总结。保留所有关键信息",
        param_infos={
            "summary": "最新的全局项目状态总结",
        }
    )
    async def update_board(self, summary: str):
        """
        Planner 的记忆重置操作。
        """
        # 1. 更新内存变量
        self.project_board = summary
        session = self.current_session
        
        # 2. 归档逻辑 (Archiving) - 这是一个好习惯，防止总结错了找不回原文
        # 我们归档除了 System Prompt 和 Anchor 之外的所有中间层

        # history 这个时候应该是这样的的
        # （1）system prompt
        # （2）第一个 user msg (anchor task, incoming email)
        # （3）第一个 assistant msg (intent + action )
        # (N 轮对话)
        # 【倒数第四】user msg
        # 【倒数第三】assistant msg
        # 【倒数第二】 user msg
        # [倒数第一】assistant msg (intent + action = update_board)


        if len(session.history) > 10:
            # history[0] = System, history[1] = Anchor
            # 切片范围：从索引 2 到 最后（不包含即将生成的 Feedback）
            msgs_to_archive = session.history[2:]
            self._archive_history(msgs_to_archive, reason=f"Board Update: {summary[:20]}...")

            # 3. 构造新的“中间层” (The Compressed State)
            # 用 System 角色或者 Assistant 角色都可以。
            # 用 System 角色更像“上帝视角的旁白”，用 Assistant 角色更像“我自己的笔记”。
            # 这里推荐用 System 格式，以此区隔于普通的对话。
            board_msg = {
                "role": "assistant", 
                "content": textwrap.dedent(f"""
                    Latest project status
                    
                    ### 📌 CURRENT PROJECT BOARD
                    {self.project_board}
                    
                """)
            }
            
            # 4. 重组 History
            # [System Prompt] + [Anchor Task] + [New Board]
            # 注意：这里我们只取前两个。如果 history 长度不足 2（比如刚开始就 update），要做保护
            base_history = session.history[:2] 
            #从
            # 覆盖 Session History
            session.history = base_history + [board_msg]
            
            # 5. 返回结果
            # 这个返回值会被 BaseAgent 追加到 history 的末尾，成为新的激活信号
            return "Project status reviewed."
        else:
            return "Status is up to date"
    


# skills/project_management.py

    