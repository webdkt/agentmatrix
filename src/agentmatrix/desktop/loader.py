import yaml
import importlib
import os
import logging
from typing import List, Any, Dict
from dotenv import load_dotenv
import json
from ..core.backends.llm_client import LLMClient
from ..core.cerebellum import Cerebellum
from ..core.log_util import AutoLoggerMixin
from ..core.log_config import LogConfig


class AgentLoader(AutoLoggerMixin):
    def __init__(self, profile_path, llm_config_path=None):
        self.profile_path = profile_path
        env_file = os.path.join(os.path.dirname(profile_path), ".env")
        # if not os.path.exists(env_file):
        # raise FileNotFoundError(f"环境变量文件不存在: {self.profile_path}")

        # if not os.access(env_file, os.R_OK):
        #    raise PermissionError(f"没有读取文件的权限: {self.profile_path}")
        if os.path.exists(env_file) and os.access(env_file, os.R_OK):
            load_dotenv(env_file)

        llm_config_file = llm_config_path or os.path.join(
            os.path.dirname(profile_path), "llm_config.json"
        )
        # llm_config_file = os.path.join(self.profile_path, "llm_config.json")

        with open(llm_config_file, "r", encoding="utf-8") as f:
            self.llm_config = json.load(f)

        if "default_slm" not in self.llm_config:
            raise ValueError(
                "llm_config.json 中必须包含 'default_slm' 配置，用于驱动默认小脑。"
            )

        for config in self.llm_config.values():
            if "API_KEY" in config:
                api_key = config["API_KEY"]
                if os.getenv(api_key) is not None:
                    config["API_KEY"] = os.getenv(api_key)

    def _parse_value(self, value):
        """
        解析配置文件中的值，支持基本类型
        YAML会自动解析类型，但我们需要确保一致性
        """
        if isinstance(value, str):
            # 尝试解析特殊字符串
            value_lower = value.lower()
            if value_lower == "null":
                return None
            elif value_lower == "true":
                return True
            elif value_lower == "false":
                return False
        return value

    def load_from_file(self, file_path: str) -> Any:
        """从 YAML 文件加载并实例化一个 Agent"""
        self.logger.info(f">>> 加载Agent配置文件 {file_path}...")
        with open(file_path, "r", encoding="utf-8") as f:
            profile = yaml.safe_load(f)

        # 1. 解析基础类信息（新格式：完整类路径）
        class_full_path = profile.get("class_name", "agentmatrix.desktop.base_agent.BaseAgent")

        # 支持向后兼容：如果存在旧的 module 字段，则合并
        if "module" in profile:
            module_name = profile["module"]
            class_name = profile["class_name"]
            class_full_path = f"{module_name}.{class_name}"
            self.logger.warning(
                f">>> ⚠️  配置文件使用旧格式 (module + class_name)，建议改为单一 class_name: {class_full_path}"
            )
            del profile["module"]
        else:
            # 新格式：从完整路径解析 module 和 class
            parts = class_full_path.rsplit(".", 1)
            if len(parts) != 2:
                raise ValueError(
                    f"class_name 格式错误: {class_full_path}，应为 'module.path.ClassName'"
                )
            module_name, class_name = parts

        # 2. 解析属性初始化配置
        attribute_inits = profile.pop("attribute_initializations", {})

        # 3. 解析类属性配置
        class_attrs = profile.pop("class_attributes", {})

        # 清理配置中的特殊字段
        if "class_name" in profile:
            del profile["class_name"]
        if "mixins" in profile:
            # ❌ 旧架构：mixins 已废弃（新架构使用 skills + Lazy Load）
            self.logger.warning(
                f">>> ⚠️  配置文件中包含已废弃的 'mixins' 字段，请使用 'skills' 代替"
            )
            del profile["mixins"]

        # 4. 动态导入 Agent 类
        try:
            module = importlib.import_module(module_name)
            agent_class = getattr(module, class_name)
        except (ImportError, AttributeError) as e:
            raise ImportError(f"无法加载 Agent 类: {class_full_path}. 错误: {e}")

        # 5. 设置类属性（如果有）
        if class_attrs:
            for attr_name, attr_value in class_attrs.items():
                setattr(agent_class, attr_name, attr_value)
            self.logger.info(f">>>    设置类属性: {class_attrs}")

        # 6. 实例化 Agent
        agent_instance = agent_class(profile.copy(), profile_path=file_path)

        # ========== 加载日志配置 ==========
        logging_config = profile.get("logging", {})
        component_configs = logging_config.get("components", {})

        # 🆕 9. 注入实例属性（Mixin 需要的属性）
        if attribute_inits:
            for attr_name, attr_value in attribute_inits.items():
                parsed_value = self._parse_value(attr_value)
                setattr(agent_instance, attr_name, parsed_value)
                self.logger.info(f">>> 🔧 初始化属性: {attr_name} = {parsed_value}")

        # ========== 10. 设置 Brain（带日志配置）==========
        backend_model = agent_instance.backend_model
        brain_config = LogConfig.from_dict(component_configs.get("brain"))
        brain_config.prefix = brain_config.prefix or "[BRAIN]"

        agent_instance.brain = self._create_llm_client(
            backend_model, parent_logger=agent_instance.logger, log_config=brain_config
        )
        print(f"Agent {agent_instance.name} brain set to {backend_model}")

        # ========== 11. 设置 Cerebellum（带日志配置）==========
        cerebellum_config_dict = profile.get("cerebellum")
        slm_client = None

        if cerebellum_config_dict:
            slm_model = cerebellum_config_dict.get("backend_model", "default_slm")
        else:
            slm_model = "default_slm"

        # 创建 Cerebellum 的日志配置
        cerebellum_log_config = LogConfig.from_dict(component_configs.get("cerebellum"))
        cerebellum_log_config.prefix = cerebellum_log_config.prefix or "[CEREBELLUM]"

        # 创建 SLM client
        slm_client = self._create_llm_client(
            slm_model,
            parent_logger=agent_instance.logger,
            log_config=cerebellum_log_config,
        )

        if cerebellum_config_dict:
            print(f"[{agent_instance.name}] Using custom SLM: {slm_model}")
        else:
            print(f"[{agent_instance.name}] Using system default SLM.")

        agent_instance.cerebellum = Cerebellum(
            slm_client,
            agent_instance.name,
            parent_logger=agent_instance.logger,
            log_config=cerebellum_log_config,
        )

        # ========== 12. 设置 Vision Brain（带日志配置）==========
        vision_config = profile.get("vision_brain")
        vision_client = None

        # 创建 Vision Brain 的日志配置
        vision_log_config = LogConfig.from_dict(component_configs.get("vision_brain"))
        vision_log_config.prefix = vision_log_config.prefix or "[VISION]"

        if vision_config:
            # 从 vision_brain 配置块中读取 backend_model
            vision_model = vision_config.get("backend_model", "default_vision")
            vision_client = self._create_llm_client(
                vision_model,
                parent_logger=agent_instance.logger,
                log_config=vision_log_config,
            )
            print(f"[{agent_instance.name}] Using custom Vision Brain: {vision_model}")
        else:
            # 如果没有配置 vision_brain，使用系统默认 "default_vision"
            try:
                vision_client = self._create_llm_client(
                    "default_vision",
                    parent_logger=agent_instance.logger,
                    log_config=vision_log_config,
                )
                print(
                    f"[{agent_instance.name}] Using system default Vision Brain (default_vision)."
                )
            except KeyError:
                # 如果 llm_config 中没有 default_vision，保持为 None
                print(
                    f"[{agent_instance.name}] No Vision Brain configured (default_vision not found in llm_config.json)."
                )

        agent_instance.vision_brain = vision_client

        # ========== 14. 设置 SessionManager（带日志配置，可选）==========
        # 这个会在 workspace_root 设置时创建，暂时跳过

        return agent_instance

    def _create_llm_client(
        self,
        model_name,
        parent_logger: logging.Logger = None,
        log_config: LogConfig = None,
    ):
        """
        创建 LLMClient 并注入 logger 配置

        Args:
            model_name: 模型名称（在 llm_config.json 中的 key）
            parent_logger: 父组件的 logger（用于共享日志）
            log_config: 日志配置

        Returns:
            LLMClient: 配置好的 LLMClient 实例
        """
        llm_config = self.llm_config[model_name]
        url = llm_config["url"]
        api_key = llm_config["API_KEY"]
        model_name = llm_config["model_name"]
        llm_client = LLMClient(
            url, api_key, model_name, parent_logger=parent_logger, log_config=log_config
        )
        return llm_client

    def load_all(self) -> Dict[str, Any]:
        agents = {}
        for filename in os.listdir(self.profile_path):
            if filename.endswith(".yml"):
                full_path = os.path.join(self.profile_path, filename)
                print(f"Loading agent from {filename}...")
                agent = self.load_from_file(full_path)
                agents[agent.name] = agent
        return agents
