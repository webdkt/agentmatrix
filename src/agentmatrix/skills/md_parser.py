"""
Markdown Skill Parser - 解析 skill.md 文件

支持：
- Frontmatter 元数据解析
- Action 定义提取
- 生成渐进式披露内容（摘要 + 完整文档）
"""

import re
import logging
from dataclasses import dataclass, field
from typing import List, Dict, Optional
from pathlib import Path

logger = logging.getLogger(__name__)


@dataclass
class MDActionDescriptor:
    """MD Skill 中的 Action 描述符"""
    name: str
    description: str
    content: str  # 完整的步骤说明
    section_start: int  # 在文档中的起始位置


@dataclass
class MDSkillMetadata:
    """MD Skill 元数据（符合行业标准：Claude Code / OpenSkills）"""
    name: str  # 技能标识符（如 git-workflow）
    description: str  # 技能描述（用于显示和匹配）

    # 可选字段
    license: Optional[str] = None  # 许可证
    version: Optional[str] = None  # 版本号
    compatibility: Optional[str] = None  # 环境要求
    allowed_tools: List[str] = field(default_factory=list)  # 预授权工具

    # Action 列表
    actions: List[MDActionDescriptor] = field(default_factory=list)

    # 渐进式披露内容
    brief_summary: str = ""  # 用于 system prompt 的简短摘要
    full_content: str = ""  # 完整 markdown 内容

    # 文件路径信息
    skill_dir: Optional[Path] = None  # skill 目录路径
    workspace_path: Optional[Path] = None  # workspace 中的路径


class MDSkillParser:
    """Markdown Skill 解析器"""

    # Frontmatter 提取正则
    FRONTMATTER_PATTERN = re.compile(r'^---\s*\n(.*?)\n---\s*\n(.*)$', re.DOTALL)

    # Action 提取正则（## Action: xxx）
    ACTION_PATTERN = re.compile(r'^##\s+Action:\s*(.+?)\s*$', re.MULTILINE)

    @classmethod
    def parse(cls, skill_md_path: Path) -> Optional[MDSkillMetadata]:
        """
        解析 skill.md 文件

        Args:
            skill_md_path: skill.md 文件路径

        Returns:
            Optional[MDSkillMetadata]: 解析后的元数据，失败则返回 None
        """
        try:
            # 读取文件
            with open(skill_md_path, 'r', encoding='utf-8') as f:
                content = f.read()

            # 提取 Frontmatter
            frontmatter_match = cls.FRONTMATTER_PATTERN.match(content)
            if not frontmatter_match:
                logger.warning(f"  ⚠️  {skill_md_path} 缺少 Frontmatter，无法解析")
                return None

            frontmatter_text = frontmatter_match.group(1)
            markdown_body = frontmatter_match.group(2)

            # 解析 Frontmatter
            frontmatter = cls._parse_yaml_frontmatter(frontmatter_text)

            # 提取基本信息（符合行业标准）
            name = frontmatter.get('name', skill_md_path.parent.name)
            description = frontmatter.get('description', '')
            license = frontmatter.get('license')
            version = frontmatter.get('version')
            compatibility = frontmatter.get('compatibility')
            allowed_tools = frontmatter.get('allowed-tools', frontmatter.get('allowed_tools', []))

            # 提取 Actions
            actions = cls._extract_actions(markdown_body)

            # 生成摘要
            brief_summary = cls._generate_summary(markdown_body, description)

            # 构建元数据对象
            metadata = MDSkillMetadata(
                name=name,
                description=description,
                license=license,
                version=version,
                compatibility=compatibility,
                allowed_tools=allowed_tools,
                actions=actions,
                brief_summary=brief_summary,
                full_content=content,
                skill_dir=skill_md_path.parent
            )

            logger.info(f"  ✅ 解析 MD Skill 成功: {name}")
            logger.debug(f"     - Description: {description[:100]}...")
            logger.debug(f"     - Actions: {len(actions)}")
            if license:
                logger.debug(f"     - License: {license}")

            return metadata

        except Exception as e:
            logger.error(f"  ❌ 解析 MD Skill 失败: {skill_md_path}, 错误: {e}")
            return None

    @classmethod
    def _parse_yaml_frontmatter(cls, text: str) -> Dict:
        """
        解析 YAML Frontmatter（简化版本，不依赖 PyYAML）

        支持的格式：
        - key: value
        - key: [item1, item2]
        - key:
          - item1
          - item2

        Args:
            text: Frontmatter 文本

        Returns:
            Dict: 解析后的键值对
        """
        result = {}
        lines = text.strip().split('\n')

        i = 0
        while i < len(lines):
            line = lines[i].strip()
            if not line or line.startswith('#'):
                i += 1
                continue

            if ':' in line:
                key, value = line.split(':', 1)
                key = key.strip()
                value = value.strip()

                # 处理列表格式（单行）[item1, item2]
                if value.startswith('[') and value.endswith(']'):
                    items = [v.strip().strip('"\'') for v in value[1:-1].split(',')]
                    # 过滤空字符串
                    result[key] = [item for item in items if item]
                    i += 1

                # 处理列表格式（多行）
                elif not value or value.startswith('-'):
                    list_items = []
                    # 当前行可能已经有第一个列表项
                    if value.startswith('-'):
                        list_items.append(value[1:].strip().strip('"\''))

                    # 继续读取后续行
                    i += 1
                    while i < len(lines):
                        next_line = lines[i].strip()
                        if next_line.startswith('-'):
                            list_items.append(next_line[1:].strip().strip('"\''))
                            i += 1
                        else:
                            # 不是列表项了，退出
                            break

                    result[key] = [item for item in list_items if item]

                # 处理字符串引号
                elif value.startswith('"') and value.endswith('"'):
                    result[key] = value[1:-1]
                    i += 1
                elif value.startswith("'") and value.endswith("'"):
                    result[key] = value[1:-1]
                    i += 1

                # 普通字符串
                else:
                    result[key] = value
                    i += 1
            else:
                i += 1

        return result

    @classmethod
    def _extract_actions(cls, markdown_body: str) -> List[MDActionDescriptor]:
        """
        从 Markdown 正文提取 Action 定义

        格式：
        ## Action: 初始化 Git 仓库
        **使用场景**：...
        **步骤**：
        ...

        Args:
            markdown_body: Markdown 正文（不含 Frontmatter）

        Returns:
            List[MDActionDescriptor]: Action 列表
        """
        actions = []

        # 查找所有 ## Action: 标记
        for match in cls.ACTION_PATTERN.finditer(markdown_body):
            action_name = match.group(1).strip()
            section_start = match.start()

            # 提取该 section 的内容（直到下一个 ## 或文件结尾）
            content_start = match.end()
            next_heading = cls.ACTION_PATTERN.search(markdown_body[content_start:])

            if next_heading:
                section_content = markdown_body[content_start:content_start + next_heading.start()]
            else:
                section_content = markdown_body[content_start:]

            # 提取描述（第一段非标题内容）
            description = cls._extract_action_description(section_content)

            actions.append(MDActionDescriptor(
                name=action_name,
                description=description,
                content=section_content.strip(),
                section_start=section_start
            ))

        logger.debug(f"     提取到 {len(actions)} 个 Actions")
        return actions

    @classmethod
    def _extract_action_description(cls, content: str) -> str:
        """
        从 Action 内容中提取描述

        优先级：
        1. **使用场景** 字段
        2. 第一段普通文本
        3. 默认："无描述"

        Args:
            content: Action section 内容

        Returns:
            str: 描述文本
        """
        # 尝试提取 **使用场景**
        scenario_match = re.search(r'\*\*使用场景\*\*:\s*(.+?)(?:\n|$)', content)
        if scenario_match:
            return scenario_match.group(1).strip()

        # 提取第一段文本（忽略标题行）
        lines = content.split('\n')
        for line in lines:
            line = line.strip()
            if line and not line.startswith('#') and not line.startswith('*'):
                # 取前100个字符作为描述
                return line[:100] + ('...' if len(line) > 100 else '')

        return "无描述"

    @classmethod
    def _generate_summary(cls, markdown_body: str, description: str) -> str:
        """
        生成技能摘要（用于 system prompt）

        规则：
        1. 优先使用 description 字段（行业标准）
        2. 其次使用 ## 概述 章节
        3. 限制在 200 字符以内

        Args:
            markdown_body: Markdown 正文
            description: 技能描述（来自 frontmatter）

        Returns:
            str: 摘要文本
        """
        # 优先使用 description
        if description:
            # 清理 markdown 格式
            summary = re.sub(r'[#*`]', '', description)
            # 限制长度
            if len(summary) > 200:
                summary = summary[:197] + "..."
            return summary

        # 尝试提取 ## 概述
        overview_match = re.search(r'^##\s+概述\s*\n(.+?)(?:\n##|$)', markdown_body, re.DOTALL)
        if overview_match:
            summary = overview_match.group(1).strip()
            # 清理 markdown 格式
            summary = re.sub(r'[#*`]', '', summary)
            # 限制长度
            if len(summary) > 200:
                summary = summary[:197] + "..."
            return summary

        # 默认摘要
        return "（查看 SKILLS 目录获取完整文档）"
