import json
import importlib
import os
from typing import List, Any

class AgentLoader:
    def __init__(self, backend_llm, backend_slm):
        # Loader 持有运行时需要的公共资源 (如 LLM 客户端)
        # 这样实例化 Agent 时可以注入进去
        self.llm = backend_llm
        self.slm = backend_slm

    def load_from_file(self, file_path: str) -> Any:
        """从 JSON 文件加载并实例化一个 Agent"""
        with open(file_path, 'r', encoding='utf-8') as f:
            profile = json.load(f)

        # 1. 解析实现类信息
        module_name = profile["implementation"]["module"]
        class_name = profile["implementation"]["class_name"]

        # 2. 动态导入 (Reflection)
        try:
            module = importlib.import_module(module_name)
            agent_class = getattr(module, class_name)
        except (ImportError, AttributeError) as e:
            raise ImportError(f"无法加载 Agent 类: {module_name}.{class_name}. 错误: {e}")

        # 3. 准备初始化参数
        # 基础参数 (所有 Agent 都有的)
        base_args = {
            "name": profile["identity"]["name"],
            "description": profile["identity"]["description"],
            "instructions": profile["protocol"].get("instruction_for_caller", ""),
            "profile_data": profile # 把原始配置也传进去，以防子类需要其他字段
        }

        # 4. 注入后端依赖 (根据 Agent 类型决定注入 LLM 还是 SLM)
        # 这里是一个简单的策略，你也可以在 json 里配置 "backend_type": "llm"
        if "Secretary" in class_name or "PostOffice" in class_name:
            base_args["backend"] = self.slm
        else:
            base_args["backend"] = self.llm

        # 5. 实例化
        # 这里的关键是：Agent 的 __init__ 必须能接收这些参数
        agent_instance = agent_class(**base_args)
        
        # 6. 处理额外的 config (如果有专门的 set_config 方法)
        if hasattr(agent_instance, "configure"):
            agent_instance.configure(profile.get("config", {}))

        return agent_instance

    def load_all(self, profiles_dir: str) -> List[Any]:
        agents = []
        for filename in os.listdir(profiles_dir):
            if filename.endswith(".json"):
                full_path = os.path.join(profiles_dir, filename)
                print(f"Loading agent from {filename}...")
                agents.append(self.load_from_file(full_path))
        return agents