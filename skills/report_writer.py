import os
from pathlib import Path
from dataclasses import dataclass, field
from typing import List, AsyncIterator, Optional
import fitz  # PyMuPDF

import torch
import textwrap
from skills.report_writer_utils import *
from core.action import register_action


@dataclass
class ResearchState:
    """研究状态数据结构，在整个流程中流转"""
    main_subject: str                       # 研究主题
    main_purpose: str                     # 研究目的
    input_dir : str
    output_dir: str
    blueprint: str = ""             # 调查蓝图（大纲、核心问题清单、预设章节）
    concept_notes: str = ""         # 概念笔记（Markdown格式，包含实体定义、关系、来源）
    draft_content: str = ""         # 正文草稿（Markdown格式，分章节填充的内容）
    scrachpad: str = ""              # 临时草稿（Markdown格式，用于临时保存的笔记）
    processed_files: List[str] = field(default_factory=list)  # 进度记录


class ReportWriterSkillMixin:
    def convert_pdf_to_markdown(pdf_path: str, start_page: int = None, end_page: int = None):
        """
        使用 Marker 将 PDF 文件中指定页码范围的内容转换为 Markdown。

        如果不指定开始和结束页，默认转换整个文档。

        Args:
            pdf_path (str): 输入 PDF 文件的完整路径。
            start_page (int, optional): 转换的起始页码 (从 1 开始计数)。默认为 None (第一页)。
            end_page (int, optional): 转换的结束页码 (包含此页)。默认为 None (最后一页)。
        """
        # --- 1. 验证输入并设置路径 ---
        pdf_file = Path(pdf_path)
        if not pdf_file.is_file():
            self.logger.error(f"错误：文件不存在于 {pdf_path}")
            return
        
        # --- 2. 使用 PyMuPDF 处理页面范围 ---
        temp_pdf_path = None
        pdf_to_process = str(pdf_file)

        try:
            doc = fitz.open(pdf_file)
            total_pages = doc.page_count
            
            # 确定实际要处理的页面范围
            # 如果用户未指定，则默认为整个文档
            actual_start = start_page if start_page is not None else 1
            actual_end = end_page if end_page is not None else total_pages
            actual_end = min(actual_end, total_pages)  # 确保结束页码不超过总页数
            
            # 验证页码范围的有效性
            if not (1 <= actual_start <= actual_end <= total_pages):
                self.logger.debug(f"错误：无效的页码范围。开始页: {actual_start}, 结束页: {actual_end}, 总页数: {total_pages}")
                doc.close()
                return
            
            # 如果用户指定的不是整个文档，则创建一个包含指定页面的临时 PDF
            is_full_document = (actual_start == 1 and actual_end == total_pages)
            if not is_full_document:
                #self.logger.debug(f"正在从PDF中提取第 {actual_start} 页到 {actual_end} 页...")
                temp_pdf = fitz.open()
                # PyMuPDF 的页面索引是从 0 开始的
                temp_pdf.insert_pdf(doc, from_page=actual_start - 1, to_page=actual_end - 1)
                
                temp_pdf_path = output_path / f"{pdf_file.stem}_pages_{actual_start}-{actual_end}_temp.pdf"
                temp_pdf.save(str(temp_pdf_path))
                temp_pdf.close()
                pdf_to_process = str(temp_pdf_path)
                #self.logger.debug(f"已创建临时PDF文件: {temp_pdf_path}")
            
            doc.close()

            # --- 3. 加载并运行 Marker ---
            # 检查可用的设备 (MPS, CUDA, or CPU)
            if torch.cuda.is_available():
                device = "cuda"
            elif torch.backends.mps.is_available():
                device = "mps"
            else:
                device = "cpu"
            self.logger.debug(f"正在使用 {device.upper()} 设备加载 Marker 模型...")

            model_lst, lang_processor_map, ocr_processor_map = marker_pdf.load_all_models()
            
            self.logger.debug(f"正在将 '{Path(pdf_to_process).name}' 转换为 Markdown...")
            full_text, out_meta = marker_pdf.convert_single_pdf(pdf_to_process, model_lst, 
                                                                lang_processor_map=lang_processor_map,
                                                                ocr_processor_map=ocr_processor_map,
                                                                device=device)
            
            
            
            return full_text
                
            

        except Exception as e:
            self.logger.exception(f"发生错误: {e}")
            
        finally:
            # --- 5. 清理临时文件 ---
            if temp_pdf_path and Path(temp_pdf_path).exists():
                Path(temp_pdf_path).unlink()
                self.logger.debug(f"已删除临时文件: {temp_pdf_path}")
    
    async def ask_ai(self, prompt:str, sys_prompt:str = None) -> str:
        messages =[]
        if sys_prompt:
            messages.append({"role": "system", "content": sys_prompt})
        messages.append({"role": "user", "content": prompt})
        response = await self.brain.think(messages)
        self.logger.debug(f"AI Think: {response['reasoning']}")
        self.logger.debug(f"AI Reply: {response['reply']}")
        return response['reply']

    @register_action(
        "编写报告blueprint，需要提供报告主题和研究目的说明，生成研究方案",
        param_infos={
            
            "main_subject": "报告主题",
            "main_purpose": "研究目的，要解决或者研究的问题",
            "src_dir": "可选非必须，输入资料目录",
            "output_dir": "可选非必须，报告输出目录",
            
        }
    )
    async def write_report(self, main_subject: str, main_purpose: str, src_dir: str =".", output_dir: str="."):
        """
        阅读分析src_dir中的资料，撰写主题为main_subject、目的为main_purpose的报告，保存到output_dir中。
        """
        # 初始化状态
        state = ResearchState(main_subject=main_subject, main_purpose= main_purpose, input_dir=src_dir, output_dir=output_dir)

        # Phase 0: 先验生成
        blueprint = await self._phase0_theorist(state)
        return blueprint
        '''
        # Phase 1: 侦察与校准
        state = await self._phase1_scout(state, src_dir)

        # Phase 2: 全量迭代
        state = await self._phase2_execution_loop(state, src_dir)

        # Phase 3: 终稿润色
        final_report = await self._phase3_finalizer(state)

        # 保存最终报告
        self._save_final_report(final_report, output_dir)
        '''

    # ========== Phase 0: The Theorist ==========
    async def _phase0_theorist(self, state: ResearchState) -> ResearchState:
        main_subject = state.main_subject
        main_purpose = state.main_purpose
        #第一步，先生成人设prompt:
        persona_prompt = textwrap.dedent(PERSONA_DESIGNER).replace("{{main_subject}}", main_subject).replace("{{main_purpose}}", main_purpose)
        persona= await self.ask_ai(persona_prompt)
        #第二步，生成blueprint prompt:
        sys_prompt = textwrap.dedent(BLUEPRINT_DESIGNER).replace("{{persona}}", persona)
        user_input = f"""
        请基于以下主题和目标，生成一份 **Deep Research Blueprint**。

        ### 用户输入
        **研究主题**: {main_subject}
        **研究动机/目标**: 
            {main_purpose}
        """
        blueprint = await self.ask_ai(user_input, sys_prompt)


        return blueprint
        
        

        

    # ========== Phase 1: The Scout ==========
    async def _phase1_scout(self, state: ResearchState, src_dir: str) -> ResearchState:
        """采样文档，修正蓝图"""
        pass

    async def _sample_and_analyze(self, state: ResearchState, src_dir: str, sample_count: int = 5):
        """并行采样分析文档，生成Delta Reports"""
        pass

    async def _synthesize_blueprint(self, state: ResearchState, delta_reports: List[str]) -> str:
        """主编合成：汇总Delta Reports，生成专用蓝图"""
        pass

    # ========== Phase 2: The Execution Loop ==========
    async def _phase2_execution_loop(self, state: ResearchState, src_dir: str) -> ResearchState:
        """流式阅读所有文档，迭代更新笔记和草稿"""
        async for chunk in self._document_stream_generator(src_dir):
            # Step A: 更新知识库
            state.concept_notes = await self._update_concept_notes(state.concept_notes, chunk)

            # Step B: 更新草稿
            state.draft_content = await self._update_draft(state.blueprint, state.draft_content,
                                                          state.concept_notes, chunk)

        return state

    async def _update_concept_notes(self, current_notes: str, new_text: str) -> str:
        """识别新实体/新定义，或更新旧实体的属性/关系"""
        pass

    async def _update_draft(self, blueprint: str, current_draft: str, notes: str, new_text: str) -> str:
        """判断new_text是否回答了蓝图中的问题，整合进草稿"""
        pass

    # ========== Phase 3: The Finalizer ==========
    async def _phase3_finalizer(self, state: ResearchState) -> str:
        """润色正文，生成附录"""
        pass

    # ========== Utility Functions ==========
    async def _document_stream_generator(self, src_dir: str) -> AsyncIterator[str]:
        """文档流生成器：封装文件读取，提供统一的yield chunk接口"""
        pass

    def _save_checkpoint(self, state: ResearchState, output_dir: str, phase_name: str):
        """保存检查点：每个阶段结束时保存State为Markdown文件"""
        pass

    def _load_checkpoint(self, checkpoint_path: str) -> Optional[ResearchState]:
        """加载检查点：从Markdown文件恢复State"""
        pass

    def _save_final_report(self, report: str, output_dir: str):
        """保存最终报告"""
        pass
         

### 如何使用这个函数


if __name__ == '__main__':
    # ==================== 使用示例 ====================
    
    # 定义你的 PDF 文件路径和输出目录
    # 请确保将 'path/to/your/document.pdf' 替换为你的实际文件路径
    my_pdf = 'path/to/your/document.pdf'
    output_directory = 'output'
    
    # 示例1：转换整个 PDF 文档
    # 不提供 start_page 和 end_page 参数
    self.logger.debug("--- 任务1: 转换整个 PDF ---")
    if Path(my_pdf).exists():
        convert_pdf_to_markdown(my_pdf, output_directory)
    else:
        self.logger.debug(f"示例文件 '{my_pdf}' 不存在，请修改路径后重试。")
        
    # 示例2：只转换 PDF 的第 2 到 3 页
    self.logger.debug("\n--- 任务2: 转换 PDF 的第 2-3 页 ---")
    if Path(my_pdf).exists():
        convert_pdf_to_markdown(my_pdf, output_directory, start_page=2, end_page=3)
    else:
        self.logger.debug(f"示例文件 '{my_pdf}' 不存在，请修改路径后重试。")

    # 示例3：只转换第 5 页
    self.logger.debug("\n--- 任务3: 只转换 PDF 的第 5 页 ---")
    if Path(my_pdf).exists():
        convert_pdf_to_markdown(my_pdf, output_directory, start_page=5, end_page=5)
    else:
        self.logger.debug(f"示例文件 '{my_pdf}' 不存在，请修改路径后重试。")