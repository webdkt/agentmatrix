import requests
import json
import traceback
from typing import Dict, Any, Optional
import aiohttp
from core.log_util import AutoLoggerMixin
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

    async def think(self, messages: list[dict[str, str]], **kwargs) -> Dict[str, str]:
        #print(f'{self.model_name} thinking about: ')
        #print(messages[-1])
        #self.echo(f"{self.model_name} 正在思考...")
        return await self.async_stream_think(messages, **kwargs)

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
            async with aiohttp.ClientSession(headers=self.headers, timeout=timeout) as session:
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


