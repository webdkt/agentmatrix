import asyncio
import yaml
from datetime import datetime
from typing import List

from agentmatrix.core.log_util import AutoLoggerMixin
from ..config_schemas import EmailProxyConfig as EmailProxyConfigSchema
from ..utils.backup import backup_file, cleanup_old_backups


class EmailProxyConfigService(AutoLoggerMixin):
    """Always-available config management for Email Proxy.

    Handles config file operations regardless of whether the EmailProxyService
    is running. Delegates service-level operations (start, stop, test_connection)
    to the running EmailProxyService instance when available.
    """

    def __init__(self, runtime):
        self.runtime = runtime
        self.paths = runtime.paths
        self.config = runtime.config

    # ── Raw config access ──

    def read_raw(self) -> str:
        ep_path = self.paths.email_proxy_config_path
        if not ep_path.exists():
            return ""
        return ep_path.read_text(encoding="utf-8")

    async def write_full_config(self, content: str) -> dict:
        try:
            parsed = yaml.safe_load(content) or {}
        except Exception as e:
            return {"success": False, "message": f"Invalid YAML: {e}"}

        try:
            EmailProxyConfigSchema(**parsed)
        except Exception as e:
            return {"success": False, "message": f"Schema validation failed: {e}"}

        ep_path = self.paths.email_proxy_config_path
        if ep_path.exists():
            backup_file(ep_path, self.paths.backup_dir, "email_proxy_config")

        ep_path.parent.mkdir(parents=True, exist_ok=True)
        with open(ep_path, "w", encoding="utf-8") as f:
            yaml.dump(parsed, f, allow_unicode=True, default_flow_style=False)

        cleanup_old_backups(self.paths.backup_dir, "email_proxy_config")

        self.config.reload()

        ep = self.runtime.email_proxy
        if ep:
            inner = parsed.get("email_proxy", parsed)
            ep.config = inner
            ep.matrix_mailbox = inner.get("matrix_mailbox", "")
            ep.user_mailbox = inner.get("user_mailbox", "")
            ep.imap_config = inner.get("imap", {})
            ep.smtp_config = inner.get("smtp", {})

        return {"success": True, "message": "Email proxy config updated"}

    # ── Service control ──

    async def enable(self) -> str:
        ep_path = self.paths.email_proxy_config_path
        content = self.read_raw()
        parsed = yaml.safe_load(content) if content else {}
        if parsed is None:
            parsed = {}

        inner = parsed.get("email_proxy", parsed)
        inner["enabled"] = True
        if "email_proxy" in parsed:
            parsed["email_proxy"] = inner

        backup_file(ep_path, self.paths.backup_dir, "email_proxy_config")
        with open(ep_path, "w", encoding="utf-8") as f:
            yaml.dump(parsed, f, allow_unicode=True, default_flow_style=False)

        self.config.reload()

        ep = self.runtime.email_proxy
        if ep and not ep._running:
            self.runtime.email_proxy_task = asyncio.ensure_future(ep.start())
            return "✅ Email proxy enabled and started"
        elif not ep:
            self.runtime._init_email_proxy()
            return "✅ Email proxy enabled and initialized"
        return "✅ Email proxy config updated (already running)"

    async def disable(self) -> str:
        ep = self.runtime.email_proxy
        if ep and ep._running:
            await ep.stop()

        ep_path = self.paths.email_proxy_config_path
        content = self.read_raw()
        parsed = yaml.safe_load(content) if content else {}
        if parsed is None:
            parsed = {}

        inner = parsed.get("email_proxy", parsed)
        inner["enabled"] = False
        if "email_proxy" in parsed:
            parsed["email_proxy"] = inner

        backup_file(ep_path, self.paths.backup_dir, "email_proxy_config")
        with open(ep_path, "w", encoding="utf-8") as f:
            yaml.dump(parsed, f, allow_unicode=True, default_flow_style=False)

        self.config.reload()

        return "✅ Email proxy disabled and stopped"

    async def test_connection(self) -> list:
        ep = self.runtime.email_proxy
        if not ep:
            raise ValueError("Email proxy service not running")
        return await ep.test_connection()

    # ── Mailbox management ──

    def add_user_mailbox(self, email_addr: str):
        import re
        if not re.match(r"^[^@\s]+@[^@\s]+\.[^@\s]+$", email_addr):
            raise ValueError(f"Invalid email address: {email_addr}")

        ep_path = self.paths.email_proxy_config_path
        if not ep_path.exists():
            raise FileNotFoundError("Email proxy config not found")

        content = ep_path.read_text(encoding="utf-8")
        config = yaml.safe_load(content) or {}

        inner = config.get("email_proxy", config)
        current = inner.get("user_mailbox", [])
        if isinstance(current, str):
            mailboxes = [current] if current else []
        elif isinstance(current, list):
            mailboxes = current[:]
        else:
            mailboxes = []

        if email_addr in mailboxes:
            raise ValueError(f"Email '{email_addr}' already exists")

        mailboxes.append(email_addr)
        inner["user_mailbox"] = mailboxes if len(mailboxes) > 1 else (mailboxes[0] if mailboxes else "")

        if "email_proxy" in config:
            config["email_proxy"] = inner
        else:
            config.update(inner)

        backup_file(ep_path, self.paths.backup_dir, "email_proxy_config")
        with open(ep_path, "w", encoding="utf-8") as f:
            yaml.dump(config, f, allow_unicode=True, default_flow_style=False)
        cleanup_old_backups(self.paths.backup_dir, "email_proxy_config")

        self.config.reload()
        ep = self.runtime.email_proxy
        if ep:
            ep.user_mailbox = inner.get("user_mailbox", "")

    def remove_user_mailbox(self, email_addr: str):
        ep_path = self.paths.email_proxy_config_path
        if not ep_path.exists():
            raise FileNotFoundError("Email proxy config not found")

        content = ep_path.read_text(encoding="utf-8")
        config = yaml.safe_load(content) or {}

        inner = config.get("email_proxy", config)
        current = inner.get("user_mailbox", [])
        if isinstance(current, str):
            mailboxes = [current] if current else []
        elif isinstance(current, list):
            mailboxes = current[:]
        else:
            mailboxes = []

        if email_addr not in mailboxes:
            raise ValueError(f"Email '{email_addr}' not found")

        mailboxes.remove(email_addr)
        inner["user_mailbox"] = mailboxes if len(mailboxes) > 1 else (mailboxes[0] if mailboxes else "")

        if "email_proxy" in config:
            config["email_proxy"] = inner
        else:
            config.update(inner)

        backup_file(ep_path, self.paths.backup_dir, "email_proxy_config")
        with open(ep_path, "w", encoding="utf-8") as f:
            yaml.dump(config, f, allow_unicode=True, default_flow_style=False)
        cleanup_old_backups(self.paths.backup_dir, "email_proxy_config")

        self.config.reload()
        ep = self.runtime.email_proxy
        if ep:
            ep.user_mailbox = inner.get("user_mailbox", "")

    # ── Backup ──

    def list_backups(self) -> List[dict]:
        backup_dir = self.paths.backup_dir
        if not backup_dir.exists():
            return []
        results = []
        for f in sorted(backup_dir.glob("email_proxy_config_*"), key=lambda p: p.stat().st_mtime, reverse=True):
            stat = f.stat()
            results.append({
                "name": f.name,
                "size": stat.st_size,
                "modified": datetime.fromtimestamp(stat.st_mtime).strftime("%Y-%m-%d %H:%M:%S"),
            })
        return results

    def read_backup(self, filename: str) -> str:
        path = self.paths.backup_dir / filename
        if not path.exists():
            raise FileNotFoundError(f"Backup not found: {filename}")
        return path.read_text(encoding="utf-8")