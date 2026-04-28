"""
Config Verifier - Connection tests for configuration validation

Provides verification tests that run before writing config files:
- LLM API connection test
- SMTP connection test
- IMAP connection test
"""

import asyncio
import logging
from typing import Dict, Any, Optional
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)


@dataclass
class VerifyResult:
    success: bool
    test_type: str
    message: str
    details: Optional[Dict[str, Any]] = None

    def to_dict(self) -> dict:
        d = {
            "success": self.success,
            "test_type": self.test_type,
            "message": self.message,
        }
        if self.details:
            d["details"] = self.details
        return d


async def verify_llm_connection(config: dict) -> VerifyResult:
    """
    Test LLM API connectivity.

    Sends a minimal request to verify the endpoint is reachable and the API key is valid.

    Args:
        config: LLM model config dict with url, API_KEY, model_name

    Returns:
        VerifyResult
    """
    import aiohttp

    url = config.get("url", "")
    api_key = config.get("API_KEY", "")
    model_name = config.get("model_name", "")

    if not url or not api_key or not model_name:
        return VerifyResult(
            success=False,
            test_type="llm_connection",
            message="Missing required fields: url, API_KEY, or model_name",
        )

    try:
        # Normalize URL
        base_url = url.rstrip("/")
        chat_url = f"{base_url}/chat/completions"

        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {api_key}",
        }

        payload = {
            "model": model_name,
            "messages": [{"role": "user", "content": "hi"}],
            "max_tokens": 5,
        }

        async with aiohttp.ClientSession() as session:
            async with session.post(
                chat_url,
                json=payload,
                headers=headers,
                timeout=aiohttp.ClientTimeout(total=15),
            ) as resp:
                if resp.status == 200:
                    return VerifyResult(
                        success=True,
                        test_type="llm_connection",
                        message=f"Connected to {model_name} successfully",
                    )
                elif resp.status == 401:
                    return VerifyResult(
                        success=False,
                        test_type="llm_connection",
                        message="Authentication failed (401). Check your API_KEY.",
                    )
                elif resp.status == 404:
                    return VerifyResult(
                        success=False,
                        test_type="llm_connection",
                        message=f"Model '{model_name}' not found (404). Check model_name.",
                    )
                else:
                    body = await resp.text()
                    return VerifyResult(
                        success=False,
                        test_type="llm_connection",
                        message=f"API returned status {resp.status}: {body[:200]}",
                    )

    except aiohttp.ClientConnectorError as e:
        return VerifyResult(
            success=False,
            test_type="llm_connection",
            message=f"Connection failed: {str(e)}. Check the URL.",
        )
    except asyncio.TimeoutError:
        return VerifyResult(
            success=False,
            test_type="llm_connection",
            message="Connection timed out after 15s. Check the URL and network.",
        )
    except Exception as e:
        return VerifyResult(
            success=False,
            test_type="llm_connection",
            message=f"Unexpected error: {str(e)}",
        )


async def verify_smtp_connection(config: dict) -> VerifyResult:
    """
    Test SMTP server connectivity.
    Skip verification if fields are blank (user hasn't configured yet).

    Args:
        config: SMTP config dict with host, port, user, password

    Returns:
        VerifyResult
    """
    host = config.get("host", "")
    port = config.get("port", 587)
    user = config.get("user", "")
    password = config.get("password", "")

    # 如果字段为空，跳过验证（用户尚未配置）
    if not host or not user or not password:
        return VerifyResult(
            success=True,
            test_type="smtp_connection",
            message="Skipped (fields not configured yet)",
        )

    try:
        import smtplib

        def _test_smtp():
            if port == 465:
                server = smtplib.SMTP_SSL(host, port, timeout=10)
            else:
                server = smtplib.SMTP(host, port, timeout=10)
                server.starttls()
            server.login(user, password)
            server.quit()

        loop = asyncio.get_event_loop()
        await loop.run_in_executor(None, _test_smtp)

        return VerifyResult(
            success=True,
            test_type="smtp_connection",
            message=f"Connected to {host}:{port} as {user}",
        )

    except smtplib.SMTPAuthenticationError:
        return VerifyResult(
            success=False,
            test_type="smtp_connection",
            message=f"Authentication failed for {user}. Check user/password.",
        )
    except smtplib.SMTPConnectError as e:
        return VerifyResult(
            success=False,
            test_type="smtp_connection",
            message=f"Connection refused to {host}:{port}. Check host/port.",
        )
    except Exception as e:
        return VerifyResult(
            success=False,
            test_type="smtp_connection",
            message=f"SMTP test failed: {str(e)}",
        )


async def verify_imap_connection(config: dict) -> VerifyResult:
    """
    Test IMAP server connectivity.
    Skip verification if fields are blank (user hasn't configured yet).

    Args:
        config: IMAP config dict with host, port, user, password

    Returns:
        VerifyResult
    """
    host = config.get("host", "")
    port = config.get("port", 993)
    user = config.get("user", "")
    password = config.get("password", "")

    # 如果字段为空，跳过验证（用户尚未配置）
    if not host or not user or not password:
        return VerifyResult(
            success=True,
            test_type="imap_connection",
            message="Skipped (fields not configured yet)",
        )

    try:
        import imaplib

        def _test_imap():
            server = imaplib.IMAP4_SSL(host, port, timeout=10)
            server.login(user, password)
            server.logout()

        loop = asyncio.get_event_loop()
        await loop.run_in_executor(None, _test_imap)

        return VerifyResult(
            success=True,
            test_type="imap_connection",
            message=f"Connected to {host}:{port} as {user}",
        )

    except imaplib.IMAP4.error as e:
        error_msg = str(e)
        if "authentication" in error_msg.lower():
            return VerifyResult(
                success=False,
                test_type="imap_connection",
                message=f"Authentication failed for {user}. Check user/password.",
            )
        return VerifyResult(
            success=False,
            test_type="imap_connection",
            message=f"IMAP error: {error_msg}",
        )
    except Exception as e:
        return VerifyResult(
            success=False,
            test_type="imap_connection",
            message=f"IMAP test failed: {str(e)}",
        )


async def verify_email_proxy_config(config: dict) -> list:
    """
    Verify both SMTP and IMAP for email proxy config.

    Args:
        config: Full email proxy config dict

    Returns:
        List of VerifyResult
    """
    results = []

    smtp_config = config.get("smtp")
    if smtp_config:
        if isinstance(smtp_config, dict):
            results.append(await verify_smtp_connection(smtp_config))
        else:
            results.append(
                VerifyResult(
                    success=False,
                    test_type="smtp_connection",
                    message="smtp config must be a dict",
                )
            )

    imap_config = config.get("imap")
    if imap_config:
        if isinstance(imap_config, dict):
            results.append(await verify_imap_connection(imap_config))
        else:
            results.append(
                VerifyResult(
                    success=False,
                    test_type="imap_connection",
                    message="imap config must be a dict",
                )
            )

    return results
