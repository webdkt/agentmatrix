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
        module_name = profile["module"]
        class_name = profile["class_name"]

        #remove module_name and class_name from profile
        del profile["module"]
        del profile["class_name"]

        # 2. 动态导入 (Reflection)
        try:
            module = importlib.import_module(module_name)
            agent_class = getattr(module, class_name)
        except (ImportError, AttributeError) as e:
            raise ImportError(f"无法加载 Agent 类: {module_name}.{class_name}. 错误: {e}")

        # 3. 准备初始化参数
        

        # 5. 实例化
        # 这里的关键是：Agent 的 __init__ 必须能接收这些参数
        agent_instance = agent_class(profile)
        
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