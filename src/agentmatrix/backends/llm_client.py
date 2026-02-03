import json
import traceback
from typing import Dict, Union, List, Optional
import aiohttp
from ..core.log_util import AutoLoggerMixin
import logging

class LLMClient(AutoLoggerMixin):

    _custom_log_level = logging.DEBUG
    def __init__(self, url: str, api_key: str,model_name: str):
        """
        初始化LLM客户端
        
        Args:
            url (str): 大模型API的URL
            api_key (str): API密钥
        """
        self.url = url
        self.api_key = api_key
        self.model_name = model_name
        self.headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json"
        }
        self.gemini_headers = {
            "Content-Type": "application/json",
            "x-goog-api-key": self.api_key
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
                    feedback = parsed_result.get("feedback", "Your previous response was invalid. Please try again.")
                    # Append the failed response and the corrective feedback for the next attempt
                    messages.append({"role": "assistant", "content": raw_reply})
                    messages.append({"role": "user", "content": feedback})

                    if attempt == max_retries - 1:
                        # Final attempt failed
                        raise ValueError("LLM failed to produce a valid response after all retries.")

                else:
                    # The parser itself is faulty
                    raise TypeError("Parser function returned an invalid contract response.")

            except Exception as e:
                self.logger.exception(f"Micro-Agent: An unexpected error occurred during invocation attempt {attempt + 1}.")
                raise
                
                
        # This line should theoretically be unreachable
        raise RuntimeError("Micro-Agent loop exited unexpectedly.")

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

        except Exception as e:
            self.logger.exception("Gemini调用失败")
            raise Exception(f"Gemini调用失败: {str(e)}")

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

            timeout = aiohttp.ClientTimeout(total=120)
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

        except aiohttp.ClientError as e:
            traceback.print_exc()
            raise Exception(f"API请求失败: {str(e)}")
        except Exception as e:
            traceback.print_exc()
            raise Exception(f"未知错误: {str(e)}")


