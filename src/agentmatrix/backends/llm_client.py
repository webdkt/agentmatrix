import requests
import json
import traceback
from typing import Dict, Union, List
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
                                    max_retries: int = 3, **parser_kwargs) -> any:
        """
        A generic micro-agent that interacts with an LLM in a loop until the
        output is successfully parsed.

        Args:
            initial_messages (list): The starting list of messages for the conversation.
            parser (callable): A function that takes a raw LLM reply string and
                            returns a dict following the Parser Contract.
            max_retries (int): The maximum number of attempts before failing.

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
        self.logger.debug(f"Micro-Agent: Initial messages: {messages}")
        for attempt in range(max_retries):
            self.logger.debug(f"Micro-Agent: Invoking LLM, attempt {attempt + 1}/{max_retries}.")
            
            try:
                response = await self.think(messages=messages)
                raw_reply = response['reply']

                # Delegate parsing to the provided parser function
                parsed_result = parser(raw_reply, **parser_kwargs)

                if parsed_result.get("status") == "success":
                    self.logger.debug("Micro-Agent: Parser reported SUCCESS.")
                    return parsed_result["data"]
                
                elif parsed_result.get("status") == "error":
                    feedback = parsed_result.get("feedback", "Your previous response was invalid. Please try again.")
                    self.logger.warning(f"Micro-Agent: Parser reported ERROR. Feedback: {feedback}")
                    
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

    def no_stream_think(self, messages: list[dict[str, str]], **kwargs) -> Dict[str, str]:
        """
        调用大模型API
        
        Args:
            messages (list[dict[str, str]]): 对话消息列表，每个消息包含role和content字段
            **kwargs: 其他可选参数
            
        Returns:
            Dict[str, str]: 包含reasoning_content和content的字典
            
        Raises:
            Exception: 当API调用失败时抛出异常
        """
        try:
            # 构建请求数据
            data = {
                "messages": messages,
                "model": self.model_name,
                "stream": False,
                **kwargs
            }
            
            # 发送请求
            response = requests.post(
                self.url,
                headers=self.headers,
                json=data,
                timeout=30
            )
            
            # 检查响应状态
            response.raise_for_status()
            
            # 解析响应
            result = response.json()
            
            # 提取所需内容
            return {
                "reasoning_content": result.get("reasoning_content", ""),
                "content": result.get("content", "")
            }
            
        except requests.exceptions.RequestException as e:
            raise Exception(f"API请求失败: {str(e)}")
        except json.JSONDecodeError:
            raise Exception("API响应解析失败")
        except KeyError as e:
            raise Exception(f"API响应格式错误，缺少必要字段: {str(e)}")
        except Exception as e:
            self.logger.exception("未知错误")
            self.logger.debug(messages)
            raise Exception(f"未知错误: {str(e)}")

    def stream_think(self, messages: list[dict[str, str]], **kwargs) -> Dict[str, str]:
        """
        流式调用大模型API，实时打印响应内容
        
        Args:
            messages (list[dict[str, str]]): 对话消息列表，每个消息包含role和content字段
            **kwargs: 其他可选参数
            
        Returns:
            Dict[str, str]: 包含reasoning_content和content的字典
            
        Raises:
            Exception: 当API调用失败时抛出异常
        """
        try:
            # 构建请求数据
            data = {
                "messages": messages,
                "model": self.model_name,
                "stream": True
            }
            
            # 初始化响应内容
            final_reasoning_content = ""
            final_content = ""
            #print(self.url)
            #print(self.headers)
            # 发送流式请求
            response = requests.post(
                self.url,
                headers=self.headers,
                json=data,
                stream=True,
                timeout=120
            )
            think_started = False
            content_started= False
            buffer = ""
            for chunk in response.iter_content(decode_unicode=True):
                if chunk:
                    buffer += chunk
                    lines = buffer.split('\n')
                    buffer = lines[-1]  # Keep incomplete line in buffer
                    
                    for line in lines[:-1]:
                        if line.strip():
                            try:
                                # Parse SSE data
                                if line.startswith('data: '):
                                    data_str = line[6:]  # Remove "data: " prefix
                                    if data_str.strip() == '[DONE]':
                                        continue
                                    elif data_str.strip():
                                        try:
                                            data = json.loads(data_str)
                                            if 'choices' in data and data['choices']:
                                                delta = data['choices'][0].get('delta', {})

                                                # Handle think mode streaming
                                                reasoning_content = delta.get('reasoning_content', '')
                                                content = delta.get('content', '')

                                                if reasoning_content:
                                                    if not think_started:
                                                        print("Reasoning: ")
                                                        think_started = True
                                                    print(reasoning_content, end='', flush=True)
                                                    final_reasoning_content += reasoning_content
                                                if content:
                                                    if not content_started:
                                                        print("Content: ")
                                                        content_started = True
                                                    print(content, end='', flush=True)
                                                    final_content += content
                                        except json.JSONDecodeError:
                                            continue
                            except:
                                continue
            
           
            
            
            
            
            return {
                "reasoning": final_reasoning_content,
                "reply": final_content
            }
            
        except requests.exceptions.RequestException as e:
            traceback.print_exc()
            raise Exception(f"API请求失败: {str(e)}")
            
        except Exception as e:
            traceback.print_exc()
            raise Exception(f"未知错误: {str(e)}")


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


