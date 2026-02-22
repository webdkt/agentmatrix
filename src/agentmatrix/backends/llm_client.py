import json
import traceback
from typing import Dict, Union, List, Optional, TYPE_CHECKING
import aiohttp
from ..core.log_util import AutoLoggerMixin
import logging
from ..core.exceptions import (
    LLMServiceUnavailableError,
    LLMServiceTimeoutError,
    LLMServiceConnectionError,
    LLMServiceAPIError
)

if TYPE_CHECKING:
    from ..core.log_config import LogConfig

class LLMClient(AutoLoggerMixin):

    _custom_log_level = logging.DEBUG
    def __init__(self, url: str, api_key: str, model_name: str,
                 parent_logger: Optional[logging.Logger] = None,
                 log_config: Optional['LogConfig'] = None):
        """
        初始化LLM客户端

        Args:
            url (str): 大模型API的URL
            api_key (str): API密钥
            model_name (str): 模型名称
            parent_logger (Optional[logging.Logger]): 父组件的logger（用于共享日志）
            log_config (Optional[LogConfig]): 日志配置
        """
        self.url = url
        self.api_key = api_key
        self.model_name = model_name

        # 使用父 logger（不创建独立日志文件）
        self._parent_logger = parent_logger
        self._log_config = log_config
        self._log_prefix_template = log_config.prefix if log_config else ""

        self.headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json"
        }
        self.gemini_headers = {
            "Content-Type": "application/json",
            "x-goog-api-key": self.api_key
        }

    def _get_log_context(self) -> dict:
        """提供日志上下文变量"""
        return {
            "model": self.model_name,
            "name": self.model_name
        }

    # In AdvancedMarkdownEditingMixin class

    async def think_with_retry(self,
                                    initial_messages: Union[str, List[str]],
                                    parser: callable,
                                    max_retries: int = 3,
                                    debug: bool = True,
                                    **parser_kwargs) -> any:
        """
        A generic micro-agent that interacts with an LLM in a loop until the
        output is successfully parsed.

        Args:
            initial_messages (list): The starting list of messages for the conversation.
            parser (callable): A function that takes a raw LLM reply string and
                            returns a dict following the Parser Contract.
            max_retries (int): The maximum number of attempts before failing.
            debug (bool): If True, output detailed debug information including LLM input/output.

        Returns:
            The "data" field from the successful parser result.

        Raises:
            ValueError: If the LLM fails to produce a parsable response after all retries.
        """

        if isinstance(initial_messages, str):
            #如果messages 是string,就包装成open ai chat messages 的格式
            messages =[{"role": "user", "content": initial_messages}]
        else:
            messages = initial_messages

        if debug:
            self.logger.debug(f"=== think_with_retry DEBUG START ===")
            self.logger.debug(f"Initial messages ({len(messages)} messages):")
            for i, msg in enumerate(messages):
                self.logger.debug(f"  [{i}] {msg.get('role')}: {msg.get('content')[:200]}{'...' if len(msg.get('content', '')) > 200 else ''}")
        
        for attempt in range(max_retries):
            try:
                response = await self.think(messages=messages)
                raw_reply = response['reply']

                if debug:
                    self.logger.debug(f"\nLLM Response (raw_reply):")
                    self.logger.debug(f"  {raw_reply[:500]}...")
                    

                # Delegate parsing to the provided parser function
                parsed_result = parser(raw_reply, **parser_kwargs)

                if debug:
                    self.logger.debug(f"\nParser result:")
                    self.logger.debug(f"  {parsed_result}")
                    

                if parsed_result.get("status") == "success":
                    
                    # 统一返回格式：{"status": "success", "content": ...}
                    if "content" in parsed_result:
                        return parsed_result["content"]
                    else:
                        # 没有内容字段，返回空字典
                        return {}

                elif parsed_result.get("status") == "error":
                    if attempt == max_retries - 1:
                        # Final attempt failed
                        raise ValueError("LLM failed to produce a valid response after all retries.")

                    # 🔥 重试策略：增强原始 prompt（不累积历史）
                    # 提取原始 user message（第一条）
                    original_prompt = messages[0]["content"]
                    feedback = parsed_result.get("feedback", "请检查输出格式")

                    # 在原始 prompt 末尾添加 feedback（强调格式）
                    enhanced_prompt = f"{original_prompt}\n\n{feedback}"

                    # 重置 messages（不保留错误历史）
                    messages = [{"role": "user", "content": enhanced_prompt}]

                else:
                    # The parser itself is faulty
                    raise TypeError("Parser function returned an invalid contract response.")

            except Exception as e:
                self.logger.exception(f"Micro-Agent: An unexpected error occurred during invocation attempt {attempt + 1}.")
                raise
                
                
        # This line should theoretically be unreachable
        raise RuntimeError("Micro-Agent loop exited unexpectedly.")

    async def look_and_retry(self,
                            prompt: str,
                            image: str,
                            parser: callable,
                            max_retries: int = 3,
                            debug: bool = True,
                            **parser_kwargs) -> any:
        """
        Vision version of think_with_retry - interacts with a Vision LLM in a loop
        until the output is successfully parsed.

        Almost identical to think_with_retry, but:
        - Uses think_with_image() instead of think()
        - User messages must use format: {"role": "user", "content": [{"type": "text", "text": "..."}]}
          (to match the multi-modal content format expected by vision APIs)

        Args:
            prompt (str): The text prompt to send to the Vision LLM.
            image (str): Base64 encoded image string.
            parser (callable): A function that takes a raw LLM reply string and
                            returns a dict following the Parser Contract.
            max_retries (int): The maximum number of attempts before failing.
            debug (bool): If True, output detailed debug information including LLM input/output.

        Returns:
            The "content" field from the successful parser result.

        Raises:
            ValueError: If the Vision LLM fails to produce a parsable response after all retries.
        """
        # Initial message with proper multi-modal format
        messages = [{"role": "user", "content": [{"type": "text", "text": prompt}]}]

        if debug:
            print(f"\n{'='*80}")
            print(f"🔄 look_and_retry 开始 (最多 {max_retries} 次尝试)")
            print(f"{'='*80}")
            print(f"📝 Prompt (前200字符): {prompt[:200]}{'...' if len(prompt) > 200 else ''}")
            print(f"📸 图片大小: {len(image)} bytes (base64)")
            print(f"{'='*80}\n")

        for attempt in range(max_retries):
            try:
                if debug:
                    print(f"\n{'─'*80}")
                    print(f"🔄 第 {attempt + 1}/{max_retries} 次尝试")
                    print(f"{'─'*80}")

                # Always use think_with_image (it handles the multi-modal format)
                raw_reply = await self.think_with_image(
                    messages=messages,
                    image=image
                )

                if debug:
                    print(f"📥 Vision LLM 原始回复:")
                    print(f"{'─'*80}")
                    print(raw_reply[:500] + ('...' if len(raw_reply) > 500 else ''))
                    print(f"{'─'*80}\n")

                # Delegate parsing to the provided parser function
                parsed_result = parser(raw_reply, **parser_kwargs)

                if debug:
                    print(f"🔍 Parser 解析结果:")
                    print(f"{'─'*80}")
                    for key, value in parsed_result.items():
                        print(f"  {key}: {value}")
                    print(f"{'─'*80}\n")

                if parsed_result.get("status") == "success":
                    if debug:
                        print(f"✅ 解析成功！")
                        print(f"{'='*80}\n")
                    # 统一返回格式：{"status": "success", "content": ...}
                    if "content" in parsed_result:
                        return parsed_result["content"]
                    else:
                        # 没有内容字段，返回空字典
                        return {}

                elif parsed_result.get("status") == "error":
                    feedback = parsed_result.get("feedback", "Your previous response was invalid. Please try again.")

                    if debug:
                        print(f"❌ 解析失败")
                        print(f"📝 错误反馈: {feedback[:300]}{'...' if len(feedback) > 300 else ''}")
                        print(f"🔄 准备重试...\n")

                    # Append assistant response (plain text)
                    messages.append({"role": "assistant", "content": raw_reply})
                    # Append user feedback (must use multi-modal format with only text, no image)
                    messages.append({
                        "role": "user",
                        "content": [{"type": "text", "text": feedback}]
                    })

                    if attempt == max_retries - 1:
                        # Final attempt failed
                        if debug:
                            print(f"\n{'='*80}")
                            print(f"❌ 达到最大重试次数 ({max_retries})，仍然失败")
                            print(f"最后错误: {feedback}")
                            print(f"{'='*80}\n")
                        raise ValueError(f"Vision LLM failed to produce a valid response after {max_retries} retries. Last error: {feedback}")

                else:
                    # The parser itself is faulty
                    raise TypeError("Parser function returned an invalid contract response.")

            except ValueError:
                # Re-raise ValueError (from final attempt failure)
                raise
            except Exception as e:
                if debug:
                    print(f"⚠️  意外错误: {str(e)}")
                    print(f"🔄 准备重试...\n")
                self.logger.exception(f"look_and_retry: An unexpected error occurred during invocation attempt {attempt + 1}.")
                if attempt == max_retries - 1:
                    if debug:
                        print(f"\n{'='*80}")
                        print(f"❌ 达到最大重试次数，发生异常")
                        print(f"异常: {str(e)}")
                        print(f"{'='*80}\n")
                    raise
                # If not the last attempt, add feedback and continue
                messages.append({
                    "role": "user",
                    "content": [{"type": "text", "text": f"Error occurred: {str(e)}. Please try again."}]
                })

        # This line should theoretically be unreachable
        raise RuntimeError("look_and_retry loop exited unexpectedly.")

    async def dialog_with_retry(
        self,
        producer_task: str,
        producer_persona: str,
        verifier_task_template: str,
        verifier_persona: str,
        producer_parser: Optional[callable] = None,
        approver_parser: Optional[callable] = None,
        max_rounds: int = 3
    ) -> dict:
        """
        Dialog-based retry with two-layer validation (structure + semantics).

        Layer 1 - Structural validation (producer_parser):
        - Ensures A's output format is correct (e.g., has required sections)
        - Validated by code rules (parser function)
        - B only sees structurally correct outputs

        Layer 2 - Semantic validation (approver_parser):
        - Ensures A's output quality is good enough
        - Validated by LLM intelligence (Verifier B)
        - Deep evaluation and improvement

        Args:
            producer_task: A's initial task
            producer_persona: A's persona
            verifier_task_template: B's evaluation task template with {producer_output}
            verifier_persona: B's persona
            producer_parser: Optional parser to validate A's output structure.
                            If provided, A uses think_with_retry internally.
            approver_parser: Optional parser to check if B approves.
                            Returns {"status": "success"} if approved.
            max_rounds: Maximum dialog rounds

        Returns:
            {
                "status": "success",
                "content": Parsed data from A (if producer_parser) or raw text,
                "rounds_used": int,
                "max_rounds_exceeded": bool,
                "last_feedback": str (only if exceeded)
            }

        Example:
            result = await llm_client.dialog_with_retry(
                producer_task="Write a research plan",
                producer_persona="You are a researcher",
                verifier_task_template="Review:\\n{producer_output}",
                verifier_persona="You are a director",
                producer_parser=research_plan_parser,  # Validates structure
                approver_parser=director_approval_parser,  # Validates approval
                max_rounds=3
            )
            # result["content"] is already parsed: {"[研究计划]": "...", ...}
        """
        last_a_output_raw = None
        last_a_output_parsed = None
        last_b_feedback = None

        self.logger.info(f"🎭 Dialog-With-Retry: Starting (max {max_rounds} rounds)")

        for round_num in range(1, max_rounds + 1):
            self.logger.info(f"🎭 Round {round_num}:")

            # ========== Phase 1: Producer (A) generates output ==========
            if round_num == 1:
                a_messages = [{"role": "user", "content": producer_task}]
            else:
                a_messages = [
                    {"role": "user", "content": producer_task},
                    {"role": "assistant", "content": last_a_output_raw},
                    {"role": "user", "content": last_b_feedback}
                ]

            # Call A with structural validation
            if producer_parser:
                try:
                    # Use think_with_retry to ensure structure is correct
                    parsed_result = await self.think_with_retry(
                        messages=a_messages,
                        parser=producer_parser,
                        max_retries=2
                    )
                    last_a_output_parsed = parsed_result

                    # Get raw output for B to see and for history
                    temp_response = await self.think(messages=a_messages)
                    last_a_output_raw = temp_response['reply']

                    self.logger.debug(f"🎭 A output (validated): {str(parsed_result)[:200]}...")

                except Exception as e:
                    # Structural validation failed
                    self.logger.warning(f"A failed structural validation: {e}")
                    temp_response = await self.think(messages=a_messages)
                    last_a_output_raw = temp_response['reply']
                    last_a_output_parsed = last_a_output_raw
            else:
                # No structural validation
                a_response = await self.think(messages=a_messages)
                last_a_output_raw = a_response['reply']
                last_a_output_parsed = last_a_output_raw
                self.logger.debug(f"🎭 A output: {last_a_output_raw[:200]}...")

            # ========== Phase 2: Verifier (B) evaluates ==========
            # Show B the formatted output if available, otherwise raw
            b_input = str(last_a_output_parsed) if producer_parser else last_a_output_raw

            b_task = verifier_task_template.format(producer_output=b_input)
            b_messages = [
                {"role": "system", "content": verifier_persona},
                {"role": "user", "content": b_task}
            ]

            b_response = await self.think(messages=b_messages)
            b_output = b_response['reply']
            self.logger.debug(f"🎭 B output: {b_output[:200]}...")

            # ========== Phase 3: Check if B approves ==========
            if approver_parser:
                parser_result = approver_parser(b_output)

                if parser_result.get("status") == "success":
                    # B approves!
                    self.logger.info(f"✅ Dialog approved at round {round_num}")
                    return {
                        "status": "success",
                        "content": last_a_output_parsed,  # Return parsed data
                        "rounds_used": round_num,
                        "max_rounds_exceeded": False
                    }
                else:
                    # B doesn't approve
                    last_b_feedback = parser_result.get(
                        "feedback",
                        f"{b_output}"
                    )
                    self.logger.info(f"❌ Dialog feedback: {last_b_feedback[:200]}...")
            else:
                # No approver, single round mode
                self.logger.info(f"✅ Dialog completed (no approver)")
                return {
                    "status": "success",
                    "content": last_a_output_parsed,
                    "rounds_used": round_num,
                    "max_rounds_exceeded": False
                }

        # Reached max_rounds without approval
        self.logger.warning(f"⚠️ Dialog reached max_rounds ({max_rounds}) without approval")
        return {
            "status": "success",
            "content": last_a_output_parsed,  # Return parsed data
            "rounds_used": max_rounds,
            "max_rounds_exceeded": True,
            "last_feedback": last_b_feedback
        }

    async def think(self, messages:  Union[str, List[Dict[str, str]]], **kwargs) -> Dict[str, str]:
        if isinstance(messages, str):
            #如果messages 是string,就包装成open ai chat messages 的格式
            messages =[{"role": "user", "content": messages}]
        if "googleapis.com" in self.url or "gemini" in self.model_name.lower():
            return await self._async_stream_think_gemini(messages, **kwargs)
        return await self.async_stream_think(messages, **kwargs)

    async def think_with_image(
        self,
        messages: Union[str, List[Dict[str, str]]],
        image: str,
        **kwargs
    ) -> str:
        """
        带图片的异步调用大模型API（支持视觉的模型，如 GPT-4V, Claude 3.5 Sonnet, Gemini Pro Vision）

        Args:
            messages: 消息列表（OpenAI 格式）或单个字符串
            image: base64 编码的图片数据（不含 data:image/... 前缀）
            **kwargs: 额外的参数（temperature, max_tokens 等）

        Returns:
            str: LLM 的文本回复

        Raises:
            Exception: 如果 API 调用失败

        Example:
            result = await llm_client.think_with_image(
                messages="描述这张图片",
                image="iVBORw0KGgoAAAANSUhEUgAAAAUA..."
            )
        """
        # 统一消息格式
        if isinstance(messages, str):
            # 单个字符串，直接使用
            text_content = messages
            is_multi_turn = False
        else:
            # 检查是否是多轮对话（有多条消息，且包含 assistant 消息）
            has_assistant = any(msg.get("role") == "assistant" for msg in messages)
            is_multi_turn = has_assistant and len(messages) > 1

            if is_multi_turn:
                # 多轮对话：直接传递给 _think_with_image_openai_multi_turn
                is_gemini = "googleapis.com" in self.url or "gemini" in self.model_name.lower()
                if is_gemini:
                    return await self._think_with_image_gemini_multi_turn(messages, image, **kwargs)
                else:
                    return await self._think_with_image_openai_multi_turn(messages, image, **kwargs)
            else:
                # 单轮对话：检查是否是 multi-modal 格式
                first_msg = messages[0]
                content = first_msg.get("content", "")

                if isinstance(content, list):
                    # 已经是 multi-modal 格式 [{"type": "text", "text": "..."}]
                    # 直接传递给多轮方法处理
                    is_gemini = "googleapis.com" in self.url or "gemini" in self.model_name.lower()
                    if is_gemini:
                        return await self._think_with_image_gemini_multi_turn(messages, image, **kwargs)
                    else:
                        return await self._think_with_image_openai_multi_turn(messages, image, **kwargs)
                else:
                    # 普通字符串格式，合并所有文本内容（向后兼容）
                    text_content = "\n".join([
                        msg.get("content", "") for msg in messages
                    ])

        # 检测是 Gemini 还是 OpenAI 格式（单轮）
        if not is_multi_turn:
            is_gemini = "googleapis.com" in self.url or "gemini" in self.model_name.lower()
            if is_gemini:
                return await self._think_with_image_gemini(text_content, image, **kwargs)
            else:
                return await self._think_with_image_openai(text_content, image, **kwargs)

    async def _think_with_image_openai(
        self,
        text_prompt: str,
        image_base64: str,
        **kwargs
    ) -> str:
        """
        使用 OpenAI Vision API 格式调用（兼容 GPT-4V, Claude 等）
        """
        try:
            # 构造支持图片的消息格式
            message_content = [
                {
                    "type": "text",
                    "text": text_prompt
                },
                {
                    "type": "image_url",
                    "image_url": {
                        "url": f"data:image/png;base64,{image_base64}",
                        "detail": kwargs.get("detail", "high")  # low, high, auto
                    }
                }
            ]

            messages = [{"role": "user", "content": message_content}]

            # 构造请求数据
            data = {
                "messages": messages,
                "model": self.model_name,
                "stream": True,
                **{k: v for k, v in kwargs.items() if k != "detail"}
            }

            final_content = ""
            buffer = ""

            timeout = aiohttp.ClientTimeout(total=120)

            async with aiohttp.ClientSession(headers=self.headers, timeout=timeout, trust_env=True) as session:
                async with session.post(self.url, json=data) as resp:
                    if resp.status != 200:
                        error_text = await resp.text()
                        raise Exception(f"Vision API Error {resp.status}: {error_text}")

                    # 流式解析
                    async for chunk in resp.content.iter_chunked(1024):
                        if not chunk:
                            continue
                        text = chunk.decode("utf-8", errors="ignore")
                        buffer += text
                        lines = buffer.split("\n")
                        buffer = lines[-1]

                        for line in lines[:-1]:
                            line = line.strip()
                            if not line or not line.startswith("data: "):
                                continue

                            data_str = line[6:].strip()
                            if data_str == "[DONE]":
                                continue

                            try:
                                payload = json.loads(data_str)
                            except json.JSONDecodeError:
                                continue

                            if "choices" in payload and payload["choices"]:
                                delta = payload["choices"][0].get("delta", {})
                                content = delta.get("content", "")
                                if content:
                                    final_content += content

            return final_content

        except aiohttp.ClientConnectorError as e:
            self.logger.exception(f"Vision API connection error: {str(e)}")
            raise LLMServiceConnectionError(f"Vision API connection failed: {str(e)}")
        except asyncio.TimeoutError as e:
            self.logger.exception(f"Vision API timeout")
            raise LLMServiceTimeoutError(f"Vision API timeout: {str(e)}")
        except aiohttp.ClientError as e:
            self.logger.exception(f"Vision API network error: {str(e)}")
            raise LLMServiceConnectionError(f"Vision API network error: {str(e)}")
        except Exception as e:
            self.logger.exception(f"Vision API 调用失败")
            # 检查是否是服务不可用相关的错误
            error_msg = str(e).lower()
            if any(code in error_msg for code in ['502', '503', '504']):
                raise LLMServiceAPIError(
                    f"Vision API service unavailable: {str(e)}",
                    status_code=int(error_msg.split()[-1]) if error_msg.split()[-1].isdigit() else None
                )
            raise Exception(f"Vision API 调用失败: {str(e)}")

    async def _think_with_image_openai_multi_turn(
        self,
        messages: List[Dict],
        image_base64: str,
        **kwargs
    ) -> str:
        """
        使用 OpenAI Vision API 格式进行多轮对话

        Args:
            messages: 消息列表，格式为:
                [
                    {"role": "user", "content": [{"type": "text", "text": "..."}]},
                    {"role": "assistant", "content": "..."},
                    {"role": "user", "content": [{"type": "text", "text": "..."}]}
                ]
            image_base64: Base64 编码的图片（只在第一条 user 消息中添加）
            **kwargs: 额外参数
        """
        try:
            # 转换消息格式：为第一条 user 消息添加图片
            formatted_messages = []
            first_user_done = False

            for msg in messages:
                role = msg.get("role")
                content = msg.get("content")

                if role == "user":
                    if isinstance(content, list):
                        # 已经是 multi-modal 格式
                        if not first_user_done:
                            # 第一条 user 消息，添加图片
                            content.append({
                                "type": "image_url",
                                "image_url": {
                                    "url": f"data:image/png;base64,{image_base64}",
                                    "detail": kwargs.get("detail", "high")
                                }
                            })
                            first_user_done = True
                        formatted_messages.append({"role": role, "content": content})
                    else:
                        # 纯文本，转换为 multi-modal 格式
                        if not first_user_done:
                            # 第一条 user 消息，添加图片
                            formatted_messages.append({
                                "role": role,
                                "content": [
                                    {"type": "text", "text": content},
                                    {
                                        "type": "image_url",
                                        "image_url": {
                                            "url": f"data:image/png;base64,{image_base64}",
                                            "detail": kwargs.get("detail", "high")
                                        }
                                    }
                                ]
                            })
                            first_user_done = True
                        else:
                            # 后续 user 消息，只有文本
                            formatted_messages.append({
                                "role": role,
                                "content": [{"type": "text", "text": content}]
                            })
                else:
                    # assistant 或 system 消息，直接添加
                    formatted_messages.append({"role": role, "content": content})

            # 构造请求数据
            data = {
                "messages": formatted_messages,
                "model": self.model_name,
                "stream": True,
                **{k: v for k, v in kwargs.items() if k != "detail"}
            }

            final_content = ""
            buffer = ""
            timeout = aiohttp.ClientTimeout(total=120)
            async with aiohttp.ClientSession(headers=self.headers, timeout=timeout, trust_env=True) as session:
                async with session.post(self.url, json=data) as resp:
                    if resp.status != 200:
                        error_text = await resp.text()
                        raise Exception(f"Vision API Error {resp.status}: {error_text}")

                    # 流式解析
                    async for chunk in resp.content.iter_chunked(1024):
                        if not chunk:
                            continue
                        text = chunk.decode("utf-8", errors="ignore")
                        buffer += text
                        lines = buffer.split("\n")
                        buffer = lines[-1]
                        for line in lines[:-1]:
                            line = line.strip()
                            if not line or not line.startswith("data: "):
                                continue
                            data_str = line[6:].strip()
                            if data_str == "[DONE]":
                                continue
                            try:
                                payload = json.loads(data_str)
                            except json.JSONDecodeError:
                                continue
                            if "choices" in payload and payload["choices"]:
                                delta = payload["choices"][0].get("delta", {})
                                content = delta.get("content", "")
                                if content:
                                    final_content += content

            return final_content

        except aiohttp.ClientConnectorError as e:
            self.logger.exception(f"Vision API multi-turn connection error: {str(e)}")
            raise LLMServiceConnectionError(f"Vision API multi-turn connection failed: {str(e)}")
        except asyncio.TimeoutError as e:
            self.logger.exception(f"Vision API multi-turn timeout")
            raise LLMServiceTimeoutError(f"Vision API multi-turn timeout: {str(e)}")
        except aiohttp.ClientError as e:
            self.logger.exception(f"Vision API multi-turn network error: {str(e)}")
            raise LLMServiceConnectionError(f"Vision API multi-turn network error: {str(e)}")
        except Exception as e:
            self.logger.exception(f"Vision API 多轮对话调用失败")
            # 检查是否是服务不可用相关的错误
            error_msg = str(e).lower()
            if any(code in error_msg for code in ['502', '503', '504']):
                raise LLMServiceAPIError(
                    f"Vision API multi-turn service unavailable: {str(e)}",
                    status_code=int(error_msg.split()[-1]) if error_msg.split()[-1].isdigit() else None
                )
            raise Exception(f"Vision API 多轮对话调用失败: {str(e)}")

    async def _think_with_image_gemini(
        self,
        text_prompt: str,
        image_base64: str,
        **kwargs
    ) -> str:
        """
        使用 Gemini Vision API 格式调用
        """
        try:
            # Gemini 格式：parts 数组，包含文本和图片
            content_parts = [
                {"text": text_prompt},
                {
                    "inline_data": {
                        "mime_type": "image/png",
                        "data": image_base64
                    }
                }
            ]

            data = {
                "contents": [
                    {
                        "role": "user",
                        "parts": content_parts
                    }
                ],
                "generationConfig": self._construct_gemini_config(**kwargs)
            }

            final_content = ""
            buffer = ""
            brace_count = 0
            in_string = False
            escape = False

            timeout = aiohttp.ClientTimeout(total=120)

            async with aiohttp.ClientSession(headers=self.gemini_headers, timeout=timeout, trust_env=True) as session:
                async with session.post(self.url, json=data) as resp:
                    if resp.status != 200:
                        error_text = await resp.text()
                        raise Exception(f"Gemini Vision Error {resp.status}: {error_text}")

                    # Gemini 流式解析（JSON Array Stream）
                    async for chunk in resp.content.iter_chunked(1024):
                        if not chunk:
                            continue
                        text = chunk.decode("utf-8", errors="ignore")

                        for char in text:
                            # 简易 JSON 对象提取器
                            if char == '[' and brace_count == 0:
                                continue
                            if char == ']' and brace_count == 0:
                                continue
                            if char == ',' and brace_count == 0:
                                continue

                            buffer += char

                            if char == '"' and not escape:
                                in_string = not in_string
                            if char == '\\' and not escape:
                                escape = True
                            else:
                                escape = False

                            if not in_string:
                                if char == '{':
                                    brace_count += 1
                                elif char == '}':
                                    brace_count -= 1

                                if brace_count == 0 and buffer.strip():
                                    try:
                                        obj = json.loads(buffer)
                                        candidates = obj.get("candidates", [])
                                        if candidates:
                                            content_obj = candidates[0].get("content", {})
                                            parts = content_obj.get("parts", [])

                                            for part in parts:
                                                part_text = part.get("text", "")
                                                final_content += part_text

                                    except json.JSONDecodeError:
                                        pass
                                    finally:
                                        buffer = ""

            return final_content

        except aiohttp.ClientConnectorError as e:
            self.logger.exception(f"Gemini Vision API connection error: {str(e)}")
            raise LLMServiceConnectionError(f"Gemini Vision API connection failed: {str(e)}")
        except asyncio.TimeoutError as e:
            self.logger.exception(f"Gemini Vision API timeout")
            raise LLMServiceTimeoutError(f"Gemini Vision API timeout: {str(e)}")
        except aiohttp.ClientError as e:
            self.logger.exception(f"Gemini Vision API network error: {str(e)}")
            raise LLMServiceConnectionError(f"Gemini Vision API network error: {str(e)}")
        except Exception as e:
            self.logger.exception(f"Gemini Vision API 调用失败")
            # 检查是否是服务不可用相关的错误
            error_msg = str(e).lower()
            if any(code in error_msg for code in ['502', '503', '504']):
                raise LLMServiceAPIError(
                    f"Gemini Vision API service unavailable: {str(e)}",
                    status_code=int(error_msg.split()[-1]) if error_msg.split()[-1].isdigit() else None
                )
            raise Exception(f"Gemini Vision API 调用失败: {str(e)}")
    
    def _to_gemini_messages(self, messages: list[dict[str, str]]) -> dict:
        """
        OpenAI 格式 -> Gemini 格式转换
        """
        gemini_contents = []
        system_instruction = None

        for msg in messages:
            role = msg.get("role")
            content = msg.get("content", "")
            
            if role == "system":
                # Gemini system instruction 是顶层字段
                system_instruction = {"parts": [{"text": content}]}
            elif role == "user":
                gemini_contents.append({"role": "user", "parts": [{"text": content}]})
            elif role == "assistant":
                gemini_contents.append({"role": "model", "parts": [{"text": content}]})
        
        return {
            "contents": gemini_contents,
            "systemInstruction": system_instruction
        }

    def _construct_gemini_config(self, **kwargs) -> dict:
        """
        构建符合官方规范的 generationConfig，处理 thinkingConfig 的嵌套
        """
        config = {}
        
        # 提取 Thinking 相关的参数并封装
        thinking_config = {}
        if "thinking_level" in kwargs:
            thinking_config["thinkingLevel"] = kwargs.pop("thinking_level")
        if "include_thoughts" in kwargs:
            thinking_config["includeThoughts"] = kwargs.pop("include_thoughts")
            
        # 其他常见参数映射 (OpenAI命名 -> Gemini命名)
        if "max_tokens" in kwargs:
            config["maxOutputTokens"] = kwargs.pop("max_tokens")
        if "temperature" in kwargs:
            config["temperature"] = kwargs.pop("temperature")
        if "top_p" in kwargs:
            config["topP"] = kwargs.pop("top_p")
            
        # 将剩余的 kwargs 也放入 config
        config.update(kwargs)
        
        # 如果有 thinking 配置，按照官方格式嵌套
        if thinking_config:
            config["thinkingConfig"] = thinking_config
            
        return config

    async def _async_stream_think_gemini(self, messages: list[dict[str, str]], **kwargs) -> Dict[str, str]:
        """
        Gemini 专用异步流式方法
        """
        try:
            # 1. 消息格式转换
            payload_parts = self._to_gemini_messages(messages)
            
            # 2. 构建 Request Body (匹配官方结构)
            generation_config = self._construct_gemini_config(**kwargs)
            
            data = {
                "contents": payload_parts["contents"],
                "generationConfig": generation_config
            }
            
            if payload_parts["systemInstruction"]:
                data["systemInstruction"] = payload_parts["systemInstruction"]

            # 3. 处理 Tools (如果 kwargs 里传了 tools，按照官方结构放入顶层)
            # 注意：这里的实现假设 kwargs 里的 'tools' 已经是 Gemini 格式，或者你可以加转换逻辑
            if "tools" in kwargs:
                data["tools"] = kwargs.pop("tools")

            final_content = ""
            final_reasoning = ""

            timeout = aiohttp.ClientTimeout(total=120)
            
            async with aiohttp.ClientSession(headers=self.gemini_headers, timeout=timeout, trust_env=True) as session:
                async with session.post(self.url, json=data) as resp:
                    if resp.status != 200:
                        error_text = await resp.text()
                        raise Exception(f"Gemini Error {resp.status}: {error_text}")
                    
                    # Gemini 流式解析 (JSON Array Stream)
                    buffer = ""
                    brace_count = 0
                    in_string = False
                    escape = False
                    
                    async for chunk in resp.content.iter_chunked(1024):
                        if not chunk: continue
                        text = chunk.decode("utf-8", errors="ignore")
                        
                        for char in text:
                            # 简易 JSON 对象提取器
                            if char == '[' and brace_count == 0: continue
                            if char == ']' and brace_count == 0: continue
                            if char == ',' and brace_count == 0: continue
                            
                            buffer += char
                            
                            if char == '"' and not escape: in_string = not in_string
                            if char == '\\' and not escape: escape = True
                            else: escape = False
                            
                            if not in_string:
                                if char == '{': brace_count += 1
                                elif char == '}': brace_count -= 1
                                    
                                if brace_count == 0 and buffer.strip():
                                    try:
                                        obj = json.loads(buffer)
                                        # 解析 candidates
                                        candidates = obj.get("candidates", [])
                                        if candidates:
                                            content_obj = candidates[0].get("content", {})
                                            parts = content_obj.get("parts", [])
                                            
                                            # 遍历 parts (Gemini 可能在一个 chunk 返回多个 part)
                                            for part in parts:
                                                part_text = part.get("text", "")
                                                
                                                # 尝试识别 Reasoning/Thought
                                                # 目前 Gemini API 尚未统一 "thought" 字段，
                                                # 但如果官方将来在 part 里加了 "thought": true，可以在这里捕获
                                                is_thought = part.get("thought", False) 
                                                
                                                if is_thought:
                                                    final_reasoning += part_text
                                                else:
                                                    final_content += part_text

                                    except json.JSONDecodeError:
                                        pass
                                    finally:
                                        buffer = ""

            return {
                "reasoning": final_reasoning,
                "reply": final_content
            }

        except aiohttp.ClientConnectorError as e:
            # Gemini 连接错误
            self.logger.error(f"Gemini connection error: {str(e)}")
            raise LLMServiceConnectionError(
                f"Failed to connect to Gemini service: {str(e)}"
            )
        except asyncio.TimeoutError as e:
            # Gemini 超时
            self.logger.error(f"Gemini request timeout")
            raise LLMServiceTimeoutError(
                f"Gemini request timeout: {str(e)}"
            )
        except aiohttp.ClientError as e:
            # 其他 Gemini 网络错误
            self.logger.error(f"Gemini client error: {str(e)}")
            raise LLMServiceConnectionError(
                f"Gemini network error: {str(e)}"
            )
        except Exception as e:
            self.logger.exception("Gemini调用失败")
            # 检查是否是服务不可用相关的错误
            error_msg = str(e).lower()
            if any(code in error_msg for code in ['502', '503', '504']):
                raise LLMServiceAPIError(
                    f"Gemini service unavailable: {str(e)}",
                    status_code=int(error_msg.split()[-1]) if error_msg.split()[-1].isdigit() else None
                )
            raise Exception(f"Gemini调用失败: {str(e)}")

    async def _think_with_image_gemini_multi_turn(
        self,
        messages: List[Dict],
        image_base64: str,
        **kwargs
    ) -> str:
        """
        使用 Gemini Vision API 格式进行多轮对话

        Args:
            messages: 消息列表，格式为:
                [
                    {"role": "user", "content": [{"type": "text", "text": "..."}]},
                    {"role": "assistant", "content": "..."},
                    {"role": "user", "content": [{"type": "text", "text": "..."}]}
                ]
            image_base64: Base64 编码的图片（只在第一条 user 消息中添加）
            **kwargs: 额外参数
        """
        try:
            # 转换消息格式：为第一条 user 消息添加图片
            contents = []
            first_user_done = False

            for msg in messages:
                role = msg.get("role")
                content = msg.get("content")

                # Gemini 的 role 映射: user -> user, assistant -> model
                gemini_role = "model" if role == "assistant" else role

                if role == "user":
                    parts = []
                    if isinstance(content, list):
                        # 已经是 multi-modal 格式
                        if not first_user_done:
                            # 第一条 user 消息，添加图片
                            parts.extend(content)  # 复制所有 parts（text）
                            parts.append({
                                "inline_data": {
                                    "mime_type": "image/png",
                                    "data": image_base64
                                }
                            })
                            first_user_done = True
                        else:
                            # 后续 user 消息，只有文本
                            parts.extend(content)
                    else:
                        # 纯文本
                        parts.append({"text": content})
                        if not first_user_done:
                            # 第一条 user 消息，添加图片
                            parts.append({
                                "inline_data": {
                                    "mime_type": "image/png",
                                    "data": image_base64
                                }
                            })
                            first_user_done = True

                    contents.append({
                        "role": gemini_role,
                        "parts": parts
                    })
                else:
                    # assistant (model) 消息
                    contents.append({
                        "role": gemini_role,
                        "parts": [{"text": content}]
                    })

            data = {
                "contents": contents,
                "generationConfig": self._construct_gemini_config(**kwargs)
            }

            final_content = ""
            final_reasoning = ""
            buffer = ""
            brace_count = 0
            in_string = False
            escape = False
            timeout = aiohttp.ClientTimeout(total=120)
            async with aiohttp.ClientSession(headers=self.gemini_headers, timeout=timeout, trust_env=True) as session:
                async with session.post(self.url, json=data) as resp:
                    if resp.status != 200:
                        error_text = await resp.text()
                        raise Exception(f"Gemini Vision Error {resp.status}: {error_text}")

                    # Gemini 流式解析（JSON Array Stream）
                    async for chunk in resp.content.iter_chunked(1024):
                        if not chunk:
                            continue
                        text = chunk.decode("utf-8", errors="ignore")
                        for char in text:
                            # 简易 JSON 对象提取器
                            if char == '[' and brace_count == 0:
                                continue
                            if char == ']' and brace_count == 0:
                                continue
                            if char == ',' and brace_count == 0:
                                continue
                            buffer += char

                            if char == '\\' and not escape:
                                escape = True
                                continue

                            if char == '"' and not escape:
                                in_string = not in_string
                            else:
                                escape = False

                            if not in_string:
                                if char == '{':
                                    brace_count += 1
                                elif char == '}':
                                    brace_count -= 1
                                    if brace_count == 0:
                                        try:
                                            obj = json.loads(buffer)
                                            buffer = ""

                                            candidate = obj.get("candidates", [{}])[0]
                                            content = candidate.get("content", {})
                                            parts = content.get("parts", [])

                                            for part in parts:
                                                if "text" in part:
                                                    final_content += part["text"]
                                                elif "thought" in part:
                                                    final_reasoning += part["thought"]

                                        except json.JSONDecodeError:
                                            pass

            return final_content

        except aiohttp.ClientConnectorError as e:
            self.logger.exception(f"Gemini Vision multi-turn connection error: {str(e)}")
            raise LLMServiceConnectionError(f"Gemini Vision multi-turn connection failed: {str(e)}")
        except asyncio.TimeoutError as e:
            self.logger.exception(f"Gemini Vision multi-turn timeout")
            raise LLMServiceTimeoutError(f"Gemini Vision multi-turn timeout: {str(e)}")
        except aiohttp.ClientError as e:
            self.logger.exception(f"Gemini Vision multi-turn network error: {str(e)}")
            raise LLMServiceConnectionError(f"Gemini Vision multi-turn network error: {str(e)}")
        except Exception as e:
            self.logger.exception(f"Gemini Vision 多轮对话调用失败")
            # 检查是否是服务不可用相关的错误
            error_msg = str(e).lower()
            if any(code in error_msg for code in ['502', '503', '504']):
                raise LLMServiceAPIError(
                    f"Gemini Vision multi-turn service unavailable: {str(e)}",
                    status_code=int(error_msg.split()[-1]) if error_msg.split()[-1].isdigit() else None
                )
            raise Exception(f"Gemini Vision 多轮对话调用失败: {str(e)}")

    async def async_stream_think(self, messages: list[dict[str, str]], **kwargs) -> Dict[str, str]:
        """
        异步流式调用大模型API，实时打印响应内容（使用 aiohttp）
        """
        
        try:
            data = {
                "messages": messages,
                "model": self.model_name,
                "stream": True,
                **kwargs
            }

            final_reasoning_content = ""
            final_content = ""

            buffer = ""

            # 超时配置：
            # - total=None: 不限制总时间，LLM 输出多久都可以（只要在持续输出）
            # - sock_read=300: 单次读取超时 5 分钟，如果 5 分钟内没有收到任何数据 chunk，才认为超时
            timeout = aiohttp.ClientTimeout(
                total=None,      # 不限制总时长，允许 LLM 长时间输出
                sock_read=300    # 单次读取超时 5 分钟（宽容的网络容错）
            )
            async with aiohttp.ClientSession(headers=self.headers, timeout=timeout, trust_env=True) as session:
                async with session.post(self.url, json=data) as resp:
                    if resp.status != 200:
                        error_text = await resp.text()
                        raise Exception(f"API请求失败: {resp.status}, message='{error_text}', url='{self.url}'")
                    resp.raise_for_status()
                    async for chunk in resp.content.iter_chunked(1024):
                        if not chunk:
                            continue
                        text = chunk.decode("utf-8", errors="ignore")
                        buffer += text
                        lines = buffer.split("\n")
                        buffer = lines[-1]  # 不完整行保留在 buffer
                        for line in lines[:-1]:
                            line = line.strip()
                            if not line:
                                continue
                            if line.startswith("data: "):
                                data_str = line[6:].strip()
                                if data_str == "[DONE]":
                                    continue
                                try:
                                    payload = json.loads(data_str)
                                except json.JSONDecodeError:
                                    continue

                                if "choices" in payload and payload["choices"]:
                                    delta = payload["choices"][0].get("delta", {})
                                    reasoning_content = delta.get("reasoning_content", "")
                                    content = delta.get("content", "")

                                    if reasoning_content:
                                        final_reasoning_content += reasoning_content

                                    if content:
                                        final_content += content

            #print()  # 确保换行
            return {
                "reasoning": final_reasoning_content,
                "reply": final_content
            }

        except aiohttp.ClientConnectorError as e:
            # 连接错误（DNS 失败、连接被拒绝等）
            self.logger.error(f"LLM connection error: {str(e)}")
            raise LLMServiceConnectionError(
                f"Failed to connect to LLM service: {str(e)}"
            )
        except asyncio.TimeoutError as e:
            # 超时错误
            self.logger.error(f"LLM request timeout")
            raise LLMServiceTimeoutError(
                f"LLM request timeout: {str(e)}"
            )
        except aiohttp.ClientError as e:
            # 其他 aiohttp 错误
            self.logger.error(f"LLM client error: {str(e)}")
            raise LLMServiceConnectionError(
                f"LLM network error: {str(e)}"
            )
        except Exception as e:
            # 其他未知错误
            traceback.print_exc()
            # 检查是否是服务不可用相关的错误
            error_msg = str(e).lower()
            if any(code in error_msg for code in ['502', '503', '504']):
                raise LLMServiceAPIError(
                    f"LLM service unavailable: {str(e)}",
                    status_code=int(error_msg.split()[-1]) if error_msg.split()[-1].isdigit() else None
                )
            raise Exception(f"Unknown error: {str(e)}")


