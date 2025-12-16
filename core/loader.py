import yaml
import importlib
import os
from typing import List, Any
from dotenv import load_dotenv
import json
from backends.llm_client import LLMClient
from core.cerebellum import Cerebellum 
from core.log_util import AutoLoggerMixin


class AgentLoader(AutoLoggerMixin):
    def __init__(self, profile_path):
        # Loader 持有运行时需要的公共资源 (如 LLM 客户端)
        # 这样实例化 Agent 时可以注入进去
        self.profile_path = profile_path
        #从profile path 下加载 .env
        #print(f"loading from : {profile_path}")
        env_file = os.path.join(profile_path, ".env")
        if not os.path.exists(env_file):
            raise FileNotFoundError(f"环境变量文件不存在: {self.profile_path}")
        
        # 检查文件权限
        if not os.access(env_file, os.R_OK):
            raise PermissionError(f"没有读取文件的权限: {self.profile_path}")
        

        vars = load_dotenv(env_file)
        #加载 profile_path 下的 llm_config.json 文件
        llm_config_file = os.path.join(profile_path, "llm_config.json")
        
        
    
        with open(llm_config_file, 'r', encoding='utf-8') as f:
            self.llm_config = json.load(f)

        # === 关键检查：必须存在 default_slm 配置 ===
        if "default_slm" not in self.llm_config:
            raise ValueError("llm_config.json 中必须包含 'default_slm' 配置，用于驱动默认小脑。")

        for config in self.llm_config.values():

            if "API_KEY" in config:
                api_key = config["API_KEY"]
                if os.getenv(api_key) is not None:
                    config["API_KEY"] = os.getenv(api_key)


        prompts_path = os.path.join(self.profile_path, "prompts")
        self.prompts = {}
        for prompt_txt in os.listdir(prompts_path):
            
            if prompt_txt.endswith(".txt"):
                self.logger.info(f">>> 加载Prompt模板 {prompt_txt}...")
                with open(os.path.join(prompts_path, prompt_txt), "r", encoding='utf-8') as f:
                    self.prompts[prompt_txt[:-4]] = f.read()

        self.logger.info(self.prompts)

        
        



    def load_from_file(self, file_path: str) -> Any:
        """从 JSON 文件加载并实例化一个 Agent"""
        self.logger.info(f">>> 加载Agent配置文件 {file_path}...")
        with open(file_path, 'r', encoding='utf-8') as f:
            profile = yaml.safe_load(f)

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

        # 注入 prompt template, 默认是"base"
        if "prompte_template" not in profile:
            profile["prompt_template"] = "base"
        prompt_template_name = profile.get("prompt_template")
        self.logger.info(f">>> 加载Prompt模板 {prompt_template_name}...")
        if prompt_template_name in self.prompts:
            prompt = self.prompts[prompt_template_name]
            profile["full_prompt"] = prompt
        else:
            raise ValueError(f"加载Agent {file_path} 失败，Prompt 模板 {prompt_template_name} 未找到。")

        # 3. 实例化
        agent_instance = agent_class(profile.copy())

        # 4. 设置LLM backend
        backend_model = agent_instance.backend_model
        agent_instance.brain  = self._create_llm_client(backend_model)
        print(f"Agent {agent_instance.name} brain set to {backend_model} / {backend_model}")
        
        # === 设置小脑 (Cerebellum) ===
        cerebellum_config = profile.get("cerebellum")
        slm_client = None
        
        if cerebellum_config:
            # A. 如果 Agent 定义了自己的小脑模型
            slm_model = cerebellum_config.get("backend_model", "default_slm")
            slm_client = self._create_llm_client(slm_model)
            print(f"[{agent_instance.name}] Using custom SLM: {slm_model}")
        else:
            # B. 如果没定义，强制使用 default_slm
            slm_client = self._create_llm_client("default_slm")
            print(f"[{agent_instance.name}] Using system default SLM.")
        
        # 注入小脑
        agent_instance.cerebellum = Cerebellum(slm_client, agent_instance.name)

    
        

        return agent_instance

    def _create_llm_client(self, model_name):
        llm_config = self.llm_config[model_name]
        url = llm_config['url']
        api_key = llm_config['API_KEY']
        model_name = llm_config['model_name']
        llm_client = LLMClient(url,api_key, model_name)
        return llm_client

    def load_all(self) -> List[Any]:
        agents = {}
        
        for filename in os.listdir(self.profile_path):
            if filename.endswith(".yml"):
                full_path = os.path.join(self.profile_path, filename)
                print(f"Loading agent from {filename}...")
                agent = self.load_from_file(full_path)
                agents[agent.name] = agent
                
        return agents