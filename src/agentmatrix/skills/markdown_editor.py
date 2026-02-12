"!!! 过时待 Review!!!"
# skills/markdown_editor.py
import os
import textwrap
import asyncio
import json
import re
from ..core.action import register_action

from .skill_helpers import SkillHelpers

# 一个简单的数据类来管理文档的“页”
class DocumentChunk:
    def __init__(self, content, original_index):
        self.original_content = content
        self.modified_content = content  # 初始化时，修改内容等于原始内容
        self.original_index = original_index # 它在原始块列表中的索引

class AdvancedMarkdownEditingMixin:




    EDITOR_PROMPT_TEMPLATE = textwrap.dedent("""
        You are a precision 'Text Manipulator'. You have been assigned with the a new editing task. You need to carefully read the current page and decide whether and edition is applicable to this page. If yes, perform the edition and produce a new page.

        **Edit Instruction:**
            {edit_instruction}
        
        **Current Page Location:**
            {context_header}
        

        **Content of This Page:**
        
        {page_content}

        =====END OF PAGE CONTENT=====
        
        **YOUR RESPONSE STRUCTURE - YOU MUST Generate ALL 3 PARTS:**

        1.  **[REASONING]:** First, briefly explain your thought process. Did task apply to this page? What changes did you decide to make, and why?
        2.  **[SEPARATOR]:** After your reasoning, on a completely new line, write the exact separator: `{seperator}`
        3.  **[CONTENT]:** After the separator, provide the complete, rewritten text for the page.
            - If you made changes, this will be the new version of the entire page.
            - If the task did NOT apply to this page and NO changes were made, write the single word `{no_change_signal}` after the separator.

        **Example 1: A change is made**
        [REASONING]: Your thoughts about the task and how it applies to the page.
        {seperator}
        New full version of the page content, with changes made.

        **Example 2: No change is made**
        [REASONING]: Your thoughts about the task and decides no change is needed.
        {seperator}
        {no_change_signal}
        """)

    LOCATION_JUDGER_PROMPT_TEMPLATE = textwrap.dedent("""
        You are a navigation assistant. Your job is to determine if a given document page is relevant to a specific editing task, based on a rich context description of that page.

        **The Editing Task I Want to Perform:**
        "{task}"

        **Context Description of the Current Page:**
        - The page begins in the section: "{start_breadcrumb}"
        - The page ends in the section: "{end_breadcrumb}"
        - New headings introduced on this page are: {contained_headings}

        **Question:**
        Based on the task and the full context of this page, is it plausible that this page contains content relevant to the editing task?

        **Answer (ONLY "YES" or "NO"):**
    """)

    def _parse_judger_output(self, raw_reply: str) -> dict:
        """Parser for the LocationJudger's YES/NO output."""
        reply = raw_reply.strip().upper()
        #取reply最后一行的最后一个单词
        reply = reply.split('\n')[-1].split()[-1]
        reply.replace("'", "").replace('"','')
        if reply == "YES":
            return {"status": "success", "content": True}
        elif reply == "NO":
            return {"status": "success", "content": False}
        else:
            return {"status": "error", "feedback": 'Invalid response. Please answer with only "YES" or "NO".'}

    # 定义常量以便复用
    SEPARATOR = "=====EDITED FULL VERSION===="
    NO_CHANGE_SIGNAL = "NO CHANGE"
    FORMAT_CORRECTION_MESSAGE = "Your output format was incorrect. Please review the instructions and provide edited full version under: \n" + SEPARATOR


    



    @register_action(
        "编辑txt和Markdown格式文件，处理一个逻辑上独立完整的编辑任务。",
        param_infos={
            "file_path": "要编辑的Markdown文档的完整路径。",
            "edit_instruction": "对文档进行修改的自然语言指令。"
        }
    )
    async def advanced_edit_markdown(self, file_path: str, edit_instruction: str) -> str:
        full_path = self._resolve_real_path(file_path)
        # ... 文件存在性检查 ...
        original_content = await asyncio.to_thread(self._read_file_content, full_path)
        
        
        # 将文档分块
        chunks = self._chunk_document(original_content)
        
        # === EXECUTION ===
        
        # 执行统一的文档遍历
        
        self.logger.info("Starting unified, stable-state-cached document traversal...")
        page_iterator = self._iterate_chunks_with_rich_context(chunks)

        # 缓存现在以稳定的breadcrumb字符串为key
        stable_breadcrumb_cache = {} 

        for chunk_index, chunk, context_info in page_iterator:
            self.logger.debug(f"Processing Chunk {chunk_index}, Context: {context_info}")
            
            is_stable_context = context_info["start_breadcrumb"] == context_info["end_breadcrumb"]
            do_task = False

            if is_stable_context:
                # 这是一个稳定的上下文，我们可以使用缓存
                stable_breadcrumb = context_info["start_breadcrumb"]
                
                if stable_breadcrumb in stable_breadcrumb_cache:
                    # 缓存命中！
                    do_task = stable_breadcrumb_cache[stable_breadcrumb]
                    self.logger.debug(f"Stable context cache HIT for '{stable_breadcrumb}': {do_task}")
                else:
                    # 缓存未命中，需要调用LLM，然后将结果存入缓存
                    self.logger.debug(f"Stable context cache MISS for '{stable_breadcrumb}'. Invoking Judger...")
                    do_task = await self._is_in_correct_location(edit_instruction, context_info)
                    stable_breadcrumb_cache[stable_breadcrumb] = do_task
            else:
                # 这是一个过渡的、不稳定的上下文（边界！）。
                # 永远不要使用缓存，总是重新判断。
                self.logger.debug("Transitional context detected. Forcing Judger invocation.")
                do_task = await self._is_in_correct_location(edit_instruction, context_info)
            if do_task:

                context_header = (
                    f"Location starts at '{context_info['start_breadcrumb']}' "
                    f"and ends at '{context_info['end_breadcrumb']}'"
                )
                edit_result = await self._editor_edit_chunk(
                    edit_instruction, chunk.modified_content, context_header
                )
                if edit_result['change_made']:
                    chunk.modified_content = edit_result['content']
                    self.logger.debug(f"Modified: {chunk.modified_content[:500]}...")
                if edit_result['is_done']:
                    self.logger.info("Editor reported task is done. Terminating traversal.")
                    break

        # === FINAL STAGE: MERGE & SAVE ===
        final_content = "".join([c.modified_content for c in chunks])
        self.logger.debug(f"Final content: {final_content[:500]}...")
        await asyncio.to_thread(self._write_file_content, full_path, final_content)

        return f"Successfully edited document '{file_path}'."

    async def _is_in_correct_location(self, task: str, context_info: dict) -> bool:
        """
        Uses an LLM to judge if the current breadcrumb matches the target section.
        """
        prompt = self.LOCATION_JUDGER_PROMPT_TEMPLATE.format(
            task=task,
            start_breadcrumb=context_info["start_breadcrumb"],
            end_breadcrumb=context_info["end_breadcrumb"],
            contained_headings=str(context_info["contained_headings"]) or "None"
        )
        initial_messages = [{"role": "user", "content": prompt}]
        
        # We can be aggressive with retries here as it's a simple, critical task
        is_match = await self.cerebellum.backend.think_with_retry(
            initial_messages=initial_messages,
            parser=self._parse_judger_output,
            max_retries=5
        )
        return is_match

    

    # In AdvancedMarkdownEditingMixin class

    def _iterate_chunks_with_rich_context(self, chunks: list, start_chunk_index: int = 0):
        """
        A stateful generator that yields a rich context object for each chunk,
        describing all structural transitions within it.

        Yields:
            tuple: (chunk_index, chunk, context_info_dict)
        """
        heading_stack = []

        for i in range(start_chunk_index, len(chunks)):
            chunk = chunks[i]
            
            # 1. 捕获进入该Chunk之前的上下文
            start_breadcrumb = " > ".join([h[1] for h in heading_stack]) if heading_stack else "Document Start"
            
            # 2. 正常处理该Chunk内部的所有标题
            headings_in_chunk = self._extract_headings(chunk.original_content)
            if headings_in_chunk:
                for heading in headings_in_chunk:
                    level = heading.count('#')
                    while heading_stack and heading_stack[-1][0] >= level:
                        heading_stack.pop()
                    heading_stack.append((level, heading.lstrip('#').strip()))
            
            # 3. 捕获离开该Chunk之后的上下文
            end_breadcrumb = " > ".join([h[1] for h in heading_stack]) if heading_stack else "Document Start"

            # 4. 构建并yield丰富的上下文对象
            context_info = {
                "start_breadcrumb": start_breadcrumb,
                "end_breadcrumb": end_breadcrumb,
                "contained_headings": [h.lstrip('#').strip() for h in headings_in_chunk]
            }
            
            yield i, chunk, context_info

    

    def _extract_headings(self, content: str) -> list:
        """Helper to find all markdown headings in a piece of text."""
        return re.findall(r'^#+ .+$', content, re.MULTILINE)
    

    async def _editor_edit_chunk(self, edit_instruction, page_content, context_header) -> str:
        """
        Orchestrates the editing of a single chunk by preparing the prompt and
        invoking the generic micro-agent with a specific parser.
        """
        prompt = self.EDITOR_PROMPT_TEMPLATE.format(
            edit_instruction=edit_instruction,
            context_header=context_header,
            page_content=page_content,
            seperator = self.SEPARATOR,
            no_change_signal = self.NO_CHANGE_SIGNAL
        )
        initial_messages = [{"role": "user", "content": prompt}]

        # Invoke the micro-agent with our specific parser
        edit_result = await self.cerebellum.backend.think_with_retry(
            initial_messages=initial_messages,
            parser=self._parse_editor_output
        )

        #edit_result = editor_result['content']

        prompt2 = "现在判断一下编辑任务是否**全部**完成了，如果确定全部完成不再需要继续阅读，就回答'YES'，不确定或者还没有完成，就回答'NO'。只回答 YES 或者 NO"
        messages_round2 = [
            {"role": "user", "content": prompt},
            {"role": "assistant", "content": edit_result["full_reply"]},
            {"role": "user", "content": prompt2}
        ]

        is_done = await self.cerebellum.backend.think_with_retry(messages_round2, self._parse_judger_output)

        edit_result["is_done"] = is_done
        return edit_result

        

    def _parse_editor_output(self, raw_reply: str) -> dict:
        """
        A specific parser for the Editor's output format.
        Adheres to the Parser Contract.
        """
        if self.SEPARATOR not in raw_reply:
            return {
                "status": "error",
                "feedback": self.FORMAT_CORRECTION_MESSAGE
            }
        
        try:
            _, content_part = raw_reply.split(self.SEPARATOR, 1)
            new_content = content_part.strip()
            
            if new_content == self.NO_CHANGE_SIGNAL:
                return {
                    "status": "success",
                    "content": {"change_made": False, "content": None, "full_reply":raw_reply}
                }
            else:
                return {
                    "status": "success",
                    "content": {"change_made": True, "content": new_content, "full_reply":raw_reply}
                }
                
        except Exception:
            # Catch any other parsing errors
            self.logger.exception("Error parsing Editor's output")
            return {
                "status": "error",
                "feedback": f"Could not parse the response even though separator was present. {self.FORMAT_CORRECTION_MESSAGE}"
            }

    def _chunk_document(self, content, chunk_size=2000): # chunk_size in characters
        # 按段落分割，然后组合成大小合适的块
        paragraphs = content.split('\n\n')
        chunks_content = []
        current_chunk = ""
        for p in paragraphs:
            if len(current_chunk) + len(p) > chunk_size:
                chunks_content.append(current_chunk)
                current_chunk = p
            else:
                current_chunk += '\n\n' + p
        chunks_content.append(current_chunk)
        return [DocumentChunk(content, i) for i, content in enumerate(chunks_content)]



    # 辅助的同步IO方法
    def _read_file_content(self, path):
        with open(path, 'r', encoding='utf-8') as f:
            return f.read()

    def _write_file_content(self, path, content):
        with open(path, 'w', encoding='utf-8') as f:
            f.write(content)