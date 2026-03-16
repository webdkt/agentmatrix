"""
ConfigService - 统一的配置管理服务

职责：
1. Agent 配置管理（CRUD）
2. LLM 配置管理（CRUD）
3. Email Proxy 配置管理
4. 配置验证和备份
"""

from typing import Dict, List, Optional, Any
from pathlib import Path
import yaml
import json
import shutil
from datetime import datetime

try:
    from ..core.log_util import AutoLoggerMixin
    from ..core.paths import MatrixPaths
except ImportError:
    # Fallback for direct imports
    import sys
    from pathlib import Path
    sys.path.insert(0, str(Path(__file__).parent.parent))
    from core.log_util import AutoLoggerMixin
    from core.paths import MatrixPaths


class ConfigService(AutoLoggerMixin):
    """
    配置管理服务

    提供统一的配置管理接口，包括：
    - Agent profiles 管理
    - LLM 配置管理
    - Email Proxy 配置管理
    """

    def __init__(self, paths: MatrixPaths, max_backups: int = 5):
        """
        初始化配置服务

        Args:
            paths: MatrixPaths 实例
            max_backups: 最大备份数量
        """
        self.paths = paths
        self.max_backups = max_backups
        self._ensure_config_directories()

    # === Agent Profile 管理 ===

    def list_agents(self) -> List[Dict[str, Any]]:
        """列出所有 Agent profiles"""
        agents = []
        for yml_file in self.paths.agent_config_dir.glob("*.yml"):
            try:
                with open(yml_file, 'r', encoding='utf-8') as f:
                    profile = yaml.safe_load(f)
                    if profile:
                        agents.append({
                            "name": profile.get("name"),
                            "description": profile.get("description"),
                            "file_path": str(yml_file)
                        })
            except Exception as e:
                self.logger.warning(f"Failed to load {yml_file}: {e}")
        return agents

    def get_agent_profile(self, name: str) -> Dict[str, Any]:
        """获取指定 Agent 的完整 profile"""
        profile_path = self.paths.agent_config_dir / f"{name}.yml"
        if not profile_path.exists():
            raise FileNotFoundError(f"Agent profile not found: {name}")

        with open(profile_path, 'r', encoding='utf-8') as f:
            return yaml.safe_load(f)

    def create_agent_profile(self, name: str, profile: Dict[str, Any]) -> str:
        """创建新的 Agent profile"""
        profile_path = self.paths.agent_config_dir / f"{name}.yml"

        if profile_path.exists():
            raise FileExistsError(f"Agent profile already exists: {name}")

        # 备份（如果有旧文件）
        self._backup_file(profile_path)

        # 保存新 profile
        with open(profile_path, 'w', encoding='utf-8') as f:
            yaml.dump(profile, f, allow_unicode=True, default_flow_style=False)

        self.logger.info(f"✅ Created agent profile: {name}")
        return str(profile_path)

    def update_agent_profile(self, name: str, profile: Dict[str, Any]) -> str:
        """更新 Agent profile"""
        profile_path = self.paths.agent_config_dir / f"{name}.yml"

        if not profile_path.exists():
            raise FileNotFoundError(f"Agent profile not found: {name}")

        # 备份
        self._backup_file(profile_path)

        # 保存更新
        with open(profile_path, 'w', encoding='utf-8') as f:
            yaml.dump(profile, f, allow_unicode=True, default_flow_style=False)

        self.logger.info(f"✅ Updated agent profile: {name}")
        return str(profile_path)

    def delete_agent_profile(self, name: str):
        """删除 Agent profile"""
        profile_path = self.paths.agent_config_dir / f"{name}.yml"

        if not profile_path.exists():
            raise FileNotFoundError(f"Agent profile not found: {name}")

        # 备份
        self._backup_file(profile_path)

        # 删除
        profile_path.unlink()
        self.logger.info(f"✅ Deleted agent profile: {name}")

    # === LLM 配置管理 ===

    def list_llm_models(self) -> Dict[str, Dict[str, Any]]:
        """列出所有 LLM 配置"""
        llm_config_path = self.paths.llm_config_path

        if not llm_config_path.exists():
            return {}

        with open(llm_config_path, 'r', encoding='utf-8') as f:
            return json.load(f)

    def get_llm_model(self, name: str) -> Dict[str, Any]:
        """获取指定 LLM 的配置"""
        configs = self.list_llm_models()

        if name not in configs:
            raise KeyError(f"LLM config not found: {name}")

        return configs[name]

    def add_llm_model(self, name: str, config: Dict[str, Any]) -> str:
        """添加新的 LLM 配置"""
        llm_config_path = self.paths.llm_config_path

        # 备份
        self._backup_file(llm_config_path)

        # 读取现有配置
        configs = self.list_llm_models()

        # 添加新配置
        if name in configs:
            raise KeyError(f"LLM config already exists: {name}")

        configs[name] = config

        # 保存
        with open(llm_config_path, 'w', encoding='utf-8') as f:
            json.dump(configs, f, ensure_ascii=False, indent=2)

        self.logger.info(f"✅ Added LLM config: {name}")
        return str(llm_config_path)

    def update_llm_model(self, name: str, config: Dict[str, Any]) -> str:
        """更新 LLM 配置"""
        llm_config_path = self.paths.llm_config_path

        # 备份
        self._backup_file(llm_config_path)

        # 读取现有配置
        configs = self.list_llm_models()

        if name not in configs:
            raise KeyError(f"LLM config not found: {name}")

        # 更新配置
        configs[name] = config

        # 保存
        with open(llm_config_path, 'w', encoding='utf-8') as f:
            json.dump(configs, f, ensure_ascii=False, indent=2)

        self.logger.info(f"✅ Updated LLM config: {name}")
        return str(llm_config_path)

    def delete_llm_model(self, name: str) -> str:
        """删除 LLM 配置"""
        llm_config_path = self.paths.llm_config_path

        # 备份
        self._backup_file(llm_config_path)

        # 读取现有配置
        configs = self.list_llm_models()

        if name not in configs:
            raise KeyError(f"LLM config not found: {name}")

        # 检查是否是必需配置
        if name in ["default_llm", "default_slm"]:
            raise ValueError(f"Cannot delete required LLM config: {name}")

        # 删除配置
        del configs[name]

        # 保存
        with open(llm_config_path, 'w', encoding='utf-8') as f:
            json.dump(configs, f, ensure_ascii=False, indent=2)

        self.logger.info(f"✅ Deleted LLM config: {name}")
        return str(llm_config_path)

    def set_default_llm(self, name: str):
        """设置默认 LLM（通过重命名实现）"""
        configs = self.list_llm_models()

        if name not in configs:
            raise KeyError(f"LLM config not found: {name}")

        # 备份
        self._backup_file(self.paths.llm_config_path)

        # 交换配置
        old_default = configs.get("default_llm")
        configs["default_llm"] = configs[name]
        configs[name] = old_default

        # 保存
        with open(self.paths.llm_config_path, 'w', encoding='utf-8') as f:
            json.dump(configs, f, ensure_ascii=False, indent=2)

        self.logger.info(f"✅ Set default_llm to: {name}")

    def set_default_slm(self, name: str):
        """设置默认 SLM（通过重命名实现）"""
        configs = self.list_llm_models()

        if name not in configs:
            raise KeyError(f"LLM config not found: {name}")

        # 备份
        self._backup_file(self.paths.llm_config_path)

        # 交换配置
        old_default = configs.get("default_slm")
        configs["default_slm"] = configs[name]
        configs[name] = old_default

        # 保存
        with open(self.paths.llm_config_path, 'w', encoding='utf-8') as f:
            json.dump(configs, f, ensure_ascii=False, indent=2)

        self.logger.info(f"✅ Set default_slm to: {name}")

    # === Email Proxy 配置管理 ===

    def get_email_proxy_config(self) -> Dict[str, Any]:
        """获取 Email Proxy 配置"""
        email_proxy_config_path = self.paths.email_proxy_config_path

        if not email_proxy_config_path.exists():
            return {}

        with open(email_proxy_config_path, 'r', encoding='utf-8') as f:
            return yaml.safe_load(f)

    def update_email_proxy_config(self, config: Dict[str, Any]) -> str:
        """更新 Email Proxy 配置"""
        email_proxy_config_path = self.paths.email_proxy_config_path

        # 备份
        self._backup_file(email_proxy_config_path)

        # 保存
        with open(email_proxy_config_path, 'w', encoding='utf-8') as f:
            yaml.dump(config, f, allow_unicode=True, default_flow_style=False)

        self.logger.info(f"✅ Updated email proxy config")
        return str(email_proxy_config_path)

    def enable_email_proxy(self):
        """启用 Email Proxy"""
        config = self.get_email_proxy_config()
        config['email_proxy'] = config.get('email_proxy', {})
        config['email_proxy']['enabled'] = True
        self.update_email_proxy_config(config)
        self.logger.info("✅ Email proxy enabled")

    def disable_email_proxy(self):
        """禁用 Email Proxy"""
        config = self.get_email_proxy_config()
        config['email_proxy'] = config.get('email_proxy', {})
        config['email_proxy']['enabled'] = False
        self.update_email_proxy_config(config)
        self.logger.info("✅ Email proxy disabled")

    def add_user_mailbox(self, email: str):
        """添加用户邮箱地址"""
        config = self.get_email_proxy_config()
        config['email_proxy'] = config.get('email_proxy', {})

        # TODO: 支持多个用户邮箱（当前只支持单个）
        config['email_proxy']['user_mailbox'] = email

        self.update_email_proxy_config(config)
        self.logger.info(f"✅ Added user mailbox: {email}")

    def remove_user_mailbox(self, email: str):
        """移除用户邮箱地址"""
        config = self.get_email_proxy_config()
        config['email_proxy'] = config.get('email_proxy', {})

        if config['email_proxy'].get('user_mailbox') == email:
            config['email_proxy']['user_mailbox'] = ''
            self.update_email_proxy_config(config)
            self.logger.info(f"✅ Removed user mailbox: {email}")

    # === 辅助方法 ===

    def _ensure_config_directories(self):
        """确保配置目录存在"""
        self.paths.agent_config_dir.mkdir(parents=True, exist_ok=True)
        self.paths.config_dir.mkdir(parents=True, exist_ok=True)

    def _backup_file(self, file_path: Path):
        """备份文件（如果存在）"""
        if not file_path.exists():
            return

        # 生成备份文件名
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        backup_path = file_path.parent / f"{file_path.stem}.bak.{timestamp}{file_path.suffix}"

        # 复制文件
        shutil.copy2(file_path, backup_path)

        # 清理旧备份（保留最近 N 个）
        self._cleanup_old_backups(file_path)

        self.logger.debug(f"💾 Backed up: {file_path.name} → {backup_path.name}")

    def _cleanup_old_backups(self, original_path: Path):
        """清理旧备份文件，保留最近 max_backups 个"""
        backups = sorted(
            original_path.parent.glob(f"{original_path.stem}.bak.*{original_path.suffix}"),
            reverse=True
        )

        # 删除超出数量的备份
        for old_backup in backups[self.max_backups:]:
            old_backup.unlink()
            self.logger.debug(f"🗑️  Cleaned up old backup: {old_backup.name}")
