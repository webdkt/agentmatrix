"""
Knowledge Base Skill — 知识库管理与查询

Actions:
- create_kb:           创建知识库
- list_kbs:            列出所有知识库
- update_schema:       更新知识库 Schema
- scan_source_changes: 扫描源目录变更
- ingest_source:       接入资料到知识库
- query_knowledge:     查询知识库
- search_wiki:         搜索知识库页面
- list_wiki:           列出知识库结构
- update_page:         创建/更新 wiki 页面
- lint_wiki:           健康检查知识库
- evolve_schema:       演化知识库结构
"""

import os
import json
import re
import logging
from pathlib import Path
from typing import Optional
from datetime import datetime

from agentmatrix.core.action import register_action
from agentmatrix.core.exceptions import LLMServiceUnavailableError
from agentmatrix.core.micro_agent import MicroAgent
from .prompts import KnowledgePrompts
from ._shared import (
    KBRegistry,
    KBInstance,
    resolve_user_path,
    BINARY_EXTENSIONS_WARN,
)

logger = logging.getLogger(__name__)


def _pass_through_parser(raw_reply: str, **kwargs) -> dict:
    return {"status": "success", "content": raw_reply}


def _json_parser(raw_reply: str, **kwargs) -> dict:
    result = _parse_json_from_llm(raw_reply)
    if result is not None:
        return {"status": "success", "content": result}
    return {"status": "error", "feedback": "请返回有效的 JSON 格式。确保输出以 { 开头，以 } 结尾。"}


def _parse_json_from_llm(text: str) -> Optional[dict]:
    json_block_match = re.search(r'```(?:json)?\s*(.*?)\s*```', text, re.DOTALL)
    if json_block_match:
        block_content = json_block_match.group(1)
        start = block_content.find('{')
        end = block_content.rfind('}')
        if start != -1 and end != -1 and end > start:
            try:
                return json.loads(block_content[start:end + 1])
            except json.JSONDecodeError:
                pass

    brace_start = text.find('{')
    brace_end = text.rfind('}')
    if brace_start != -1 and brace_end != -1 and brace_end > brace_start:
        try:
            return json.loads(text[brace_start:brace_end + 1])
        except json.JSONDecodeError:
            pass
    return None


class Knowledge_baseSkillMixin:
    """知识库管理技能"""

    _skill_description = "维护和查询持久化知识库（wiki）"
    _skill_dependencies = ["file", "markdown"]

    # ==================== 辅助方法 ====================

    def _get_wiki_base(self) -> Path:
        return self.root_agent.runtime.paths.wiki_dir

    async def _ensure_kb(self, kb_name: str = "") -> Optional[KBInstance]:
        name = kb_name or getattr(self, '_current_kb', '') or ''
        if not name:
            return None
        return await KBRegistry.get_or_create(name, self._get_wiki_base())

    _BLOCKED_PATHS = {"/", "/etc", "/root", "/sys", "/proc", "/dev", "/boot",
                      "/private/etc", "/private/var", "/private/tmp"}
    _BLOCKED_PREFIXES = ("/etc/", "/sys/", "/proc/", "/dev/", "/boot/", "/root/",
                         "/private/etc/", "/private/var/", "/private/tmp/")

    def _is_blocked_path(self, abs_path: str) -> bool:
        resolved = str(Path(abs_path).resolve())
        if resolved in self._BLOCKED_PATHS:
            return True
        return any(resolved.startswith(p) for p in self._BLOCKED_PREFIXES)

    async def _ensure_schema_dirs(self, ns: KBInstance, schema_content: str):
        """用 MicroAgent + file skill 按 Schema 创建目录结构。"""
        micro = MicroAgent(
            parent=self,
            name=f"kb-dir-setup-{ns.name}",
            available_skills=["file"],
            system_prompt=(
                "你是目录初始化助手。你的任务是根据知识库 Schema 创建目录结构。\n"
                "只创建目录，不写入任何文件内容。完成后返回创建结果。"
            ),
        )
        try:
            await micro.execute(
                run_label=f"create-dirs-{ns.name}",
                task=(
                    f"知识库目录：`{ns.wiki_root}`\n\n"
                    f"以下是此知识库的 Schema：\n\n{schema_content}\n\n"
                    f"请根据 Schema 中「目录结构及用途」部分定义的目录，在知识库目录下创建所有目录。"
                    f"用 list_dir 确认当前结构，然后用 bash 的 mkdir -p 创建。"
                ),
                simple_mode=True,
            )
        except Exception as e:
            logger.warning(f"MicroAgent 创建目录失败: {e}")

    # ==================== 知识库管理 ====================

    @register_action(
        short_desc="创建知识库",
        description=(
            "创建一个新的知识库。"
            "如果提供 draft_path，从文件读取 Schema 并创建知识库（清理草稿文件）。"
            "如果不提供 draft_path，生成初始 Schema 供用户 review。"
        ),
        param_infos={
            "name": "知识库名称（如 work, personal, reading）",
            "description": "描述此知识库的用途和关注领域",
            "draft_path": "Schema 草稿文件路径（可选，提供则直接创建）",
        },
    )
    async def create_kb(self, name: str, description: str = "", draft_path: str = "") -> str:
        import re as _re
        if not name or len(name) < 2 or name.startswith('.') or name.startswith('_') or '..' in name:
            return f"无效的知识库名称 '{name}'。名称至少2个字符，不能以点号或下划线开头，不能包含 '..'。"
        if not _re.match(r'^[a-zA-Z0-9_\-]+$', name):
            return f"无效的知识库名称 '{name}'。只允许字母、数字、下划线和连字符。"

        wiki_base = self._get_wiki_base()
        ns = KBRegistry.get(name)
        if ns:
            if ns.wiki_manager.has_schema():
                return f"知识库 '{name}' 已存在且已有 Schema。使用 update_schema 来修改。"

        ns = await KBRegistry.get_or_create(name, wiki_base)

        if ns.wiki_manager.has_schema():
            return f"知识库 '{name}' 已有 Schema。如需修改，使用 update_schema。"

        # 如果提供了 draft_path，从文件读取 Schema
        if draft_path:
            try:
                draft_file = resolve_user_path(draft_path)
                if not draft_file.exists():
                    return f"草稿文件不存在: {draft_path}"
                schema_content = draft_file.read_text(encoding="utf-8")
                if not schema_content.strip():
                    return f"草稿文件为空: {draft_path}"
            except Exception as e:
                return f"读取草稿文件失败: {e}"

            ns.wiki_manager.init_with_schema(schema_content)
            ns.wiki_manager.append_log("create_kb", name, f"描述: {description}")
            self.root_agent._current_kb = name

            # 清理草稿文件
            try:
                draft_file.unlink()
            except Exception:
                pass

            # 按 Schema 目录结构创建缺失目录
            await self._ensure_schema_dirs(ns, schema_content)

            return (
                f"已创建知识库 '{name}'。\n\n"
                f"Schema 已从草稿文件加载并保存。\n\n"
                f"你现在可以：\n"
                f"- 使用 ingest_source 接入资料\n"
                f"- 使用 register_source 注册源目录\n"
                f"- 使用 update_schema 修改 Schema"
            )

        # 没有 draft_path，生成 Schema 供 review
        prompt = KnowledgePrompts.SCHEMA_GENERATION_PROMPT.format(
            name=name,
            description=description or "通用知识库",
        )

        schema_content = await self.root_agent.brain.think_with_retry(
            prompt,
            _pass_through_parser,
            max_retries=2,
        )

        if not schema_content or not isinstance(schema_content, str):
            return f"生成 Schema 失败，请重试 create_kb '{name}'。"

        ns.wiki_manager.init_with_schema(schema_content)
        ns.wiki_manager.append_log("create_kb", name, f"描述: {description}")

        self.root_agent._current_kb = name

        # 按 Schema 目录结构创建缺失目录
        await self._ensure_schema_dirs(ns, schema_content)

        return (
            f"已创建知识库 '{name}'，初始 Schema 已生成。\n\n"
            f"请 review 以下 Schema，如需修改使用 update_schema：\n\n"
            f"{schema_content}"
        )

    @register_action(
        short_desc="列出所有知识库",
        description="列出所有已创建的知识库及其状态。",
    )
    async def list_kbs(self) -> str:
        wiki_base = self._get_wiki_base()
        names = KBRegistry.list_all(wiki_base)

        if not names:
            return "暂无知识库。使用 create_kb 创建第一个知识库。"

        lines = ["# 知识库列表\n"]
        for name in names:
            ns = KBRegistry.get(name)
            if ns:
                has_schema = ns.wiki_manager.has_schema()
                status = "已就绪" if has_schema else "未初始化"
                try:
                    stats = await ns.db.get_stats()
                    total = stats.get("total", 0)
                except Exception:
                    total = 0
                line = f"- **{name}** ({status}, {total} 个页面)"
            else:
                line = f"- **{name}** (未加载)"
            lines.append(line)

        return "\n".join(lines)

    @register_action(
        short_desc="更新知识库 Schema",
        description=(
            "更新指定知识库的 Schema。"
            "Schema 定义了知识库关注的信息类型、类型之间的关系和目录结构。"
            "更新后会重新创建 schema 中定义的目录。"
        ),
        param_infos={
            "kb_name": "知识库名称",
            "content": "新的 Schema 内容（Markdown 格式）",
        },
    )
    async def update_schema(self, kb_name: str, content: str) -> str:
        ns = await self._ensure_kb(kb_name)
        if not ns:
            return f"知识库 '{kb_name}' 不存在。请先使用 create_kb 创建。"

        if not content or not content.strip().startswith("#"):
            return "Schema 内容无效：必须是非空的 Markdown 文档，以 # 标题开头。"

        ns.wiki_manager.init_with_schema(content)
        ns.wiki_manager.append_log("update_schema", kb_name, "用户更新了 Schema")

        return f"已更新知识库 '{kb_name}' 的 Schema。"

    # ==================== 源管理 ====================

    async def register_source(self, path: str, description: str = "",
                               kb_name: str = "") -> str:
        """注册外部目录为知识源（用户直接调用，非 agent action）。

        用户决定哪些目录作为知识库的一部分。
        """
        ns = await self._ensure_kb(kb_name)
        if not ns:
            return "没有活动的知识库。请先使用 create_kb 创建知识库。"
        db = ns.db
        wiki = ns.wiki_manager

        abs_path = str(resolve_user_path(path))
        if not os.path.exists(abs_path):
            return f"路径不存在: {abs_path}"

        source_type = "directory" if os.path.isdir(abs_path) else "file"
        source_id = await db.register_source(abs_path, description, source_type)

        if source_type == "directory":
            changed = await db.scan_source_directory(source_id, abs_path)
            files = await db.get_source_files(source_id)
            total = len(files)
            new_count = len([f for f in changed if f["status"] == "new"])
            changed_count = len([f for f in changed if f["status"] == "changed"])

            wiki.append_log(
                "source_register", abs_path,
                f"ID={source_id}, {total} 个文件, {new_count} 新增, {changed_count} 变更"
            )
            await db.update_source_timestamps(source_id, scanned=True)

            return (
                f"已注册源 (ID={source_id}): {abs_path}\n"
                f"扫描发现 {total} 个文件（{new_count} 新增, {changed_count} 变更）\n"
                f"使用 scan_source_changes 或 ingest_source 来处理这些文件。"
            )
        else:
            wiki.append_log("source_register", abs_path, f"ID={source_id}, 文件")
            return f"已注册源 (ID={source_id}): {abs_path} (文件)"

    @register_action(
        short_desc="扫描源目录变更",
        description=(
            "扫描已注册的源目录，返回新增或修改过的文件列表。"
            "可选指定 source_id 只扫描特定源，否则扫描所有 auto_scan=1 的源。"
        ),
        param_infos={
            "source_id": "源的 ID（可选，空字符串表示扫描所有）",
            "kb_name": "知识库名称（可选）",
        },
    )
    async def scan_source_changes(self, source_id: str = "",
                                   kb_name: str = "") -> str:
        ns = await self._ensure_kb(kb_name)
        if not ns:
            return "没有活动的知识库。请先使用 create_kb 创建知识库。"
        db = ns.db

        if source_id:
            try:
                sid = int(source_id)
                sources = [await db.get_source_by_id(sid)]
            except (ValueError, TypeError):
                return f"无效的 source_id: {source_id}"
        else:
            sources = await db.get_all_sources()

        results = []
        for src in sources:
            if not src:
                continue
            if not src.get("auto_scan", 1):
                continue

            abs_path = src["path"]
            if not os.path.exists(abs_path):
                results.append(f"[跳过] 源 ID={src['id']}: 路径不存在 ({abs_path})")
                continue

            changed = await db.scan_source_directory(src["id"], abs_path)
            if not changed:
                results.append(f"[无变更] 源 ID={src['id']}: {abs_path}")
            else:
                lines = [f"[有变更] 源 ID={src['id']}: {abs_path}"]
                for f in changed:
                    status_icon = "+" if f["status"] == "new" else "~"
                    lines.append(f"  {status_icon} {f['rel_path']} ({f['size']} bytes)")
                results.append("\n".join(lines))

        if not results:
            return "没有已注册的源。使用 register_source 注册源目录。"

        return "\n\n".join(results)

    # ==================== 核心操作 ====================

    @register_action(
        short_desc="接入资料到知识库",
        description=(
            "读取源资料，提取关键信息，创建或更新 wiki 页面，"
            "更新 index.md 和 log.md。这是知识的主要入口。"
            "source_path 可以是已注册源中的文件路径，也可以是任意可访问的文件路径。"
        ),
        param_infos={
            "source_path": "源文件路径（绝对路径或已注册源中的相对路径）",
            "instructions": "关于如何处理此资料的可选指示",
            "kb_name": "知识库名称（可选）",
        },
    )
    async def ingest_source(self, source_path: str, instructions: str = "",
                             kb_name: str = "") -> str:
        ns = await self._ensure_kb(kb_name)
        if not ns:
            return "没有活动的知识库。请先使用 create_kb 创建知识库。"
        db = ns.db
        wiki = ns.wiki_manager

        abs_path = str(resolve_user_path(source_path))
        if not os.path.exists(abs_path):
            return f"文件不存在: {abs_path}"

        if self._is_blocked_path(abs_path):
            return f"不允许读取系统路径: {abs_path}"

        ext = Path(abs_path).suffix.lower()
        if ext in BINARY_EXTENSIONS_WARN:
            return f"不支持二进制文件格式: {ext}。目前仅支持文本文件。"

        try:
            file_size = Path(abs_path).stat().st_size
            if file_size > 50 * 1024 * 1024:
                return f"文件过大（{file_size // 1024 // 1024}MB），超过 50MB 限制。"
            with open(abs_path, "r", encoding="utf-8", errors="replace") as f:
                source_content = f.read(30000)
        except Exception as e:
            return f"读取文件失败: {e}"

        max_chars = 30000
        truncated = False
        if len(source_content) >= max_chars:
            source_content = source_content[:max_chars] + "\n\n[... 内容已截断 ...]"
            truncated = True

        schema = wiki.read_schema()
        schema_section = schema if schema else "（知识库尚无 Schema）"

        instructions_section = ""
        if instructions:
            instructions_section = f"\n【处理指示】\n{instructions}"

        prompt = KnowledgePrompts.EXTRACT_KNOWLEDGE.format(
            schema_section=schema_section,
            source_content=source_content,
            instructions_section=instructions_section,
        )

        all_pages = await db.get_all_pages()
        page_list = "\n".join(
            f"- {p['rel_path']}: {p.get('summary', '') or p.get('title', '')}"
            for p in all_pages
        ) if all_pages else "知识库暂无页面"

        prompt += f"\n\n【当前知识库页面】\n{page_list}"

        knowledge_json = await self._call_brain_json(prompt)

        if not knowledge_json or "knowledge_points" not in knowledge_json:
            return f"无法从文件中提取知识。请检查文件内容或提供更详细的处理指示。\n文件: {abs_path}"

        knowledge_points = knowledge_json.get("knowledge_points", [])
        if not knowledge_points:
            return f"文件中未发现可提取的知识点。\n文件: {abs_path}"

        created = []
        updated = []

        for idx, kp in enumerate(knowledge_points):
            if not isinstance(kp, dict):
                logger.warning(f"跳过非字典类型的知识点 [{idx}]: {type(kp)}")
                continue
            page_path = kp.get("suggested_page", "")
            category = re.sub(r'[/\\:*?"<>|\x00-\x1f]', '', kp.get("suggested_category", "")).strip()
            title = kp.get("summary", "").split("。")[0] if kp.get("summary") else ""
            if not title:
                title = os.path.basename(page_path).replace(".md", "") if page_path else f"entry_{idx}"
            summary = kp.get("summary", "")
            source_ref = kp.get("source_ref", abs_path)
            content = kp.get("content", "")

            if not page_path:
                safe_title = title.replace("/", "-").replace(" ", "_")[:50] or f"entry_{idx}"
                if category:
                    page_path = f"{category}/{safe_title}.md"
                else:
                    page_path = f"uncategorized/{safe_title}.md"

            page_content = f"# {title}\n\n{summary}\n\n{content}\n\n> 来源: {source_ref}\n> 更新: {datetime.now().strftime('%Y-%m-%d')}\n"

            existing_source_refs = [source_ref]
            if wiki.page_exists(page_path):
                existing = wiki.read_page(page_path) or ""
                existing_page = await db.get_page(page_path)
                if existing_page and existing_page.get("source_refs"):
                    try:
                        parsed = json.loads(existing_page["source_refs"])
                        if isinstance(parsed, list) and parsed:
                            existing_source_refs = parsed
                    except (json.JSONDecodeError, TypeError):
                        pass
                    if source_ref not in existing_source_refs:
                        existing_source_refs.append(source_ref)

                additional_section = f"\n\n### 补充信息\n\n{content}\n"
                now_str = datetime.now().strftime('%Y-%m-%d')
                if "> 来源:" in existing:
                    last_source_idx = existing.rfind("> 来源:")
                    line_end = existing.find("\n", last_source_idx)
                    if line_end == -1:
                        line_end = len(existing)
                    old_sources_line = existing[last_source_idx:line_end]
                    if source_ref in old_sources_line:
                        new_sources_line = old_sources_line
                    else:
                        new_sources_line = old_sources_line.rstrip() + f"; {source_ref}"
                    remaining = existing[line_end:]
                    update_line_re = re.compile(r'^(\n?> 更新:.*?)$', re.MULTILINE)
                    remaining = update_line_re.sub(f"\n> 更新: {now_str}", remaining, count=1)
                    if not update_line_re.search(remaining):
                        remaining = f"\n> 更新: {now_str}" + remaining
                    page_content = existing[:last_source_idx] + additional_section + "\n" + new_sources_line + remaining
                else:
                    page_content = existing + additional_section + f"\n\n> 来源: {source_ref}\n> 更新: {now_str}\n"
                updated.append(page_path)
            else:
                created.append(page_path)

            try:
                await wiki.create_page(
                    rel_path=page_path,
                    content=page_content,
                    title=title,
                    summary=summary,
                    category=category,
                    source_refs=existing_source_refs,
                )
            except ValueError as e:
                logger.warning(f"跳过无效页面路径 '{page_path}': {e}")
                continue

        log_parts = [f"接入: {abs_path}"]
        if created:
            log_parts.append(f"创建页面: {', '.join(created)}")
        if updated:
            log_parts.append(f"更新页面: {', '.join(updated)}")
        if truncated:
            log_parts.append("(内容已截断)")

        wiki.append_log("ingest", os.path.basename(abs_path), "; ".join(log_parts))

        source_file_rows = await db.get_source_files_by_path(abs_path)
        source_ids = set()
        if created or updated:
            for sf_row in source_file_rows:
                await db.claim_and_mark_done(sf_row["id"], [p for p in created + updated])
                source_ids.add(sf_row["source_id"])
        for sid in source_ids:
            await db.update_source_timestamps(sid, processed=True)

        result_parts = [f"已接入资料: {abs_path}"]
        if created:
            result_parts.append(f"创建 {len(created)} 个页面: {', '.join(created)}")
        if updated:
            result_parts.append(f"更新 {len(updated)} 个页面: {', '.join(updated)}")

        return "\n".join(result_parts)

    # TODO: Phase 2 — 改为 SubAgent agent loop
    # 每个 iteration: SubAgent 读取片段 → 自主决定 action
    # action set: read_next_chunk, update_page, search_wiki, finish_reading
    # context: schema + accumulated_notes + current_chunk + wiki_page_list

    @register_action(
        short_desc="查询知识库",
        description=(
            "在知识库中搜索相关信息并综合回答。"
            "返回带引用的回答。"
        ),
        param_infos={
            "question": "要查询的问题",
            "context": "查询的上下文（可选）",
            "kb_name": "知识库名称（可选）",
        },
    )
    async def query_knowledge(self, question: str, context: str = "",
                               kb_name: str = "") -> str:
        ns = await self._ensure_kb(kb_name)
        if not ns:
            return "没有活动的知识库。请先使用 create_kb 创建知识库。"
        db = ns.db
        wiki = ns.wiki_manager

        schema = wiki.read_schema()
        schema_section = schema if schema else "（知识库尚无 Schema）"

        keywords = [w for w in question.replace("?", "").replace("？", "").split() if len(w) > 1]
        db_results = await db.search_pages(keywords[:5]) if keywords else []

        pages_content = ""
        for p in db_results[:5]:
            content = wiki.read_page(p["rel_path"])
            if content:
                pages_content += f"\n### {p['rel_path']}\n{content[:2000]}\n"

        context_section = ""
        if pages_content:
            context_section = f"\n【知识库相关页面】\n{pages_content}"
        if context:
            context_section += f"\n\n【查询上下文】\n{context}"

        prompt = KnowledgePrompts.QUERY_KNOWLEDGE.format(
            schema_section=schema_section,
            question=question,
            context_section=context_section,
        )

        response = await self.root_agent.brain.think_with_retry(
            prompt,
            _pass_through_parser,
            max_retries=2,
        )
        return response if isinstance(response, str) else str(response)

    # ==================== 维护操作 ====================

    @register_action(
        short_desc="搜索知识库",
        description="在 wiki 页面中搜索关键词，返回匹配的页面列表和摘要",
        param_infos={
            "keywords": "搜索关键词，多个用空格分隔",
            "kb_name": "知识库名称（可选）",
        },
    )
    async def search_wiki(self, keywords: str, kb_name: str = "") -> str:
        ns = await self._ensure_kb(kb_name)
        if not ns:
            return "没有活动的知识库。请先使用 create_kb 创建知识库。"
        db = ns.db
        wiki = ns.wiki_manager

        kw_list = keywords.split()
        results = await db.search_pages(kw_list)

        db_rel_set = {r["rel_path"] for r in results}
        file_matches = []
        all_md_files = []
        for md_file in wiki.wiki_root.rglob("*.md"):
            if md_file.name.startswith("_") or md_file.parent.name == "log_archive":
                continue
            if md_file.name in ("index.md", "log.md"):
                continue
            all_md_files.append(md_file)

        file_contents = {}
        for md_file in all_md_files:
            try:
                file_contents[md_file] = md_file.read_text(encoding="utf-8", errors="replace").lower()
            except Exception:
                pass

        for md_file, content_lower in file_contents.items():
            rel = str(md_file.relative_to(wiki.wiki_root))
            if rel in db_rel_set:
                continue
            if all(kw.lower() in content_lower for kw in kw_list):
                file_matches.append(rel)

        lines = []
        if results:
            lines.append(f"数据库匹配 ({len(results)} 条):")
            for r in results:
                lines.append(f"  - [{r['category']}] {r['rel_path']}: {r.get('summary', '') or r.get('title', '')}")

        if file_matches:
            lines.append(f"\n文件内容匹配 ({len(file_matches)} 个页面):")
            for fm in sorted(set(file_matches)):
                lines.append(f"  - {fm}")

        if not results and not file_matches:
            return f"未找到与 '{keywords}' 相关的内容"

        return "\n".join(lines)

    @register_action(
        short_desc="列出知识库结构",
        description="返回知识库的完整目录和每个页面的简要描述（从数据库查询）",
        param_infos={"kb_name": "知识库名称（可选）"},
    )
    async def list_wiki(self, kb_name: str = "") -> str:
        ns = await self._ensure_kb(kb_name)
        if not ns:
            return "没有活动的知识库。请先使用 create_kb 创建知识库。"
        db = ns.db

        stats = await db.get_stats()
        pages = await db.get_all_pages()

        lines = [f"# 知识库概览 (共 {stats.get('total', 0)} 个页面)\n"]

        all_categories = set(stats.keys()) - {"total"}

        for cat_key in sorted(all_categories):
            cat_count = stats.get(cat_key, 0)
            lines.append(f"\n## {cat_key}/ — {cat_count} 个页面")
            if cat_key == "(uncategorized)":
                cat_pages = [p for p in pages if not p.get("category")]
            else:
                cat_pages = [p for p in pages if p.get("category") == cat_key]
            for p in cat_pages:
                summary = p.get("summary", "") or ""
                summary_line = f": {summary}" if summary else ""
                lines.append(f"  - {p['rel_path']}{summary_line}")

        return "\n".join(lines)

    @register_action(
        short_desc="更新知识库页面",
        description="创建或更新一个 wiki 页面。更新后自动刷新 index.md。",
        param_infos={
            "page_path": "wiki/ 下相对路径，如 {目录名}/{页面名}.md",
            "content": "页面内容（Markdown）",
            "summary": "用于 index.md 的一句话摘要（可选）",
            "category": "分类目录名（可选，自动从页面路径推断）",
            "source_ref": "来源标注（可选）",
            "kb_name": "知识库名称（可选）",
        },
    )
    async def update_page(self, page_path: str, content: str,
                           summary: str = "", category: str = "",
                           source_ref: str = "", kb_name: str = "") -> str:
        if '..' in page_path or page_path.startswith('/'):
            return f"无效的页面路径: {page_path}"

        ns = await self._ensure_kb(kb_name)
        if not ns:
            return "没有活动的知识库。请先使用 create_kb 创建知识库。"
        wiki = ns.wiki_manager

        if not category:
            parent = Path(page_path).parent
            category = str(parent) if parent != Path('.') else ""

        title = ""
        for line in content.split("\n"):
            if line.startswith("# "):
                title = line[2:].strip()
                break
        if not title:
            title = Path(page_path).stem

        source_refs = [source_ref] if source_ref else []
        await wiki.create_page(
            rel_path=page_path,
            content=content,
            title=title,
            summary=summary,
            category=category,
            source_refs=source_refs,
        )

        wiki.append_log("update", page_path, f"标题: {title}")
        return f"已更新页面: {page_path}"

    @register_action(
        short_desc="健康检查知识库",
        description=(
            "检查知识库完整性：矛盾、过时信息、孤立页面、"
            "缺失概念、日志归档。返回检查报告。"
        ),
        param_infos={"kb_name": "知识库名称（可选）"},
    )
    async def lint_wiki(self, kb_name: str = "") -> str:
        ns = await self._ensure_kb(kb_name)
        if not ns:
            return "没有活动的知识库。请先使用 create_kb 创建知识库。"
        db = ns.db
        wiki = ns.wiki_manager

        stats = await db.get_stats()
        pages = await db.get_all_pages()
        schema = wiki.read_schema()

        log_path = wiki.wiki_root / "log.md"
        try:
            log_content = log_path.read_text(encoding="utf-8") if log_path.exists() else ""
        except OSError:
            log_content = ""
        log_entry_count = log_content.count("## [")

        pages_content = ""
        for p in pages[:20]:
            content = wiki.read_page(p["rel_path"])
            if content:
                pages_content += f"\n### {p['rel_path']}\n{content[:1500]}\n"

        page_list = "\n".join(
            f"- {p['rel_path']}: {p.get('summary', '') or p.get('title', '')}"
            for p in pages
        ) if pages else "知识库暂无页面"

        prompt = KnowledgePrompts.LINT_WIKI.format(
            stats=json.dumps(stats, ensure_ascii=False, indent=2),
            page_list=page_list,
            schema_section=schema or "(暂无 Schema)",
            pages_content=pages_content if pages_content else "(暂无页面内容)",
        )

        result = await self.root_agent.brain.think_with_retry(
            prompt,
            _pass_through_parser,
            max_retries=2,
        )

        if log_entry_count > wiki.LOG_MAX_ENTRIES:
            wiki.append_log("lint", "自动归档", f"日志 {log_entry_count} 条，触发归档")
            wiki._check_log_archive()

        sources = await db.get_all_sources()
        source_reports = []
        for src in sources:
            if src.get("auto_scan", 1) and os.path.exists(src["path"]):
                changed = await db.get_changed_files(src["id"])
                if changed:
                    source_reports.append(f"源 ID={src['id']} 有 {len(changed)} 个未处理变更")

        result_text = result if isinstance(result, str) else str(result)

        lint_json = _parse_json_from_llm(result_text)
        if lint_json:
            report = "## 健康检查报告\n\n"
            report += f"**整体状态**: {lint_json.get('overall_health', 'unknown')}\n\n"
            report += f"**总结**: {lint_json.get('summary', '')}\n\n"

            for key in ["contradictions", "orphan_pages", "missing_concepts", "outdated_info",
                         "structure_suggestions", "cross_reference_suggestions", "schema_alignment_issues"]:
                items = lint_json.get(key, [])
                if items:
                    label = {
                        "contradictions": "矛盾检测",
                        "orphan_pages": "孤立页面",
                        "missing_concepts": "缺失概念",
                        "outdated_info": "过时信息",
                        "structure_suggestions": "结构优化建议",
                        "cross_reference_suggestions": "交叉引用建议",
                        "schema_alignment_issues": "Schema 对齐问题",
                    }.get(key, key)
                    report += f"**{label}**:\n"
                    for item in items:
                        report += f"  - {item}\n"
                    report += "\n"
        else:
            report = f"## 健康检查报告\n\n{result_text}"

        if source_reports:
            report += "\n**源目录变更**:\n"
            for sr in source_reports:
                report += f"  - {sr}\n"

        if log_entry_count > wiki.LOG_MAX_ENTRIES:
            report += f"\n**日志归档**: 已归档旧日志条目（原有 {log_entry_count} 条）\n"

        wiki.append_log("lint", "健康检查", f"页面: {stats.get('total', 0)}")
        return report

    @register_action(
        short_desc="演化知识库结构",
        description=(
            "审视当前 wiki 的结构和 Schema，提出演进建议。"
            "Schema 只包含信息类型、类型关系和目录结构。"
        ),
        param_infos={
            "direction": "演化方向提示（可选，如'增加项目管理分类'）",
            "kb_name": "知识库名称（可选）",
        },
    )
    async def evolve_schema(self, direction: str = "", kb_name: str = "") -> str:
        ns = await self._ensure_kb(kb_name)
        if not ns:
            return "没有活动的知识库。请先使用 create_kb 创建知识库。"
        db = ns.db
        wiki = ns.wiki_manager

        stats = await db.get_stats()
        current_schema = wiki.read_schema()

        if not current_schema:
            current_schema = "（暂无 Schema — 请先使用 create_kb 创建知识库）"

        log_path = wiki.wiki_root / "log.md"
        recent_changes = ""
        if log_path.exists():
            try:
                log_content = log_path.read_text(encoding="utf-8")
                entries = [line for line in log_content.split("\n") if line.startswith("## [")]
                recent_changes = "\n".join(entries[-10:])
            except OSError:
                pass

        direction_section = ""
        if direction:
            direction_section = f"\n【演化方向提示】\n{direction}"

        prompt = KnowledgePrompts.EVOLVE_SCHEMA.format(
            current_schema=current_schema,
            stats=json.dumps(stats, ensure_ascii=False, indent=2),
            recent_changes=recent_changes,
            direction_section=direction_section,
        )

        result = await self.root_agent.brain.think_with_retry(
            prompt,
            _pass_through_parser,
            max_retries=2,
        )

        result_text = result if isinstance(result, str) else str(result)

        def _normalize(s: str) -> str:
            return "\n".join(line.rstrip() for line in s.strip().splitlines() if line.strip())

        if _normalize(result_text) != _normalize(current_schema):
            if not result_text.strip().startswith("#"):
                return "LLM 返回的内容不是有效的 Schema 文档（缺少 # 标题）。请重试或手动编辑 _schema.md。"
            backup_path = wiki.wiki_root / "_schema.md.bak"
            backup_path.write_text(current_schema, encoding="utf-8")
            wiki.init_with_schema(result_text)
            wiki.append_log("evolve_schema", "Schema 演化", "已更新知识库 Schema")
            return "知识库 Schema 已演化，_schema.md 已更新。\n\n" + result_text[:500] + "\n\n...(完整内容已写入 _schema.md)"
        else:
            return "当前知识库 Schema 无需调整。"

    # ==================== LLM 调用辅助 ====================

    async def _call_brain_json(self, prompt: str) -> Optional[dict]:
        try:
            result = await self.root_agent.brain.think_with_retry(
                prompt,
                _json_parser,
                max_retries=2,
            )
            if isinstance(result, dict):
                return result
            return None
        except LLMServiceUnavailableError:
            raise
        except Exception as e:
            logger.warning(f"_call_brain_json failed: {e}")
            return None