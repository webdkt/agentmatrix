现在我们要对src/agentmatrix/skills/deep_researcher.py 里的writing_loop 做一个重大、全面的重构。

开始之前，先要充分的理解原有代码，以及agent and micro agent 架构（参考 docs/agent-and-micro-agent-design-cn.md）以及think_with_retry 模式（参考：docs/think-with-retry-pattern-cn.md）（注：文档略有过时，以代码为准）

##writing loop的目的：

是让‘研究员’根据研究的笔记，完成报告编写(md文件）

##基本概念流程

  1. 先从章节大纲，生成 Markdown heading.

原先的章节大纲，没有要求用Markdown格式。先用一次think_with_retry 转换成Markdown heading 格式的版本（内存里保存好mapping，这样根据原来的章节名字，可以对应到markdown的格式的章节头，应该是一一对应的）

  2. 生成每个一级章节的草稿版本。

有了heading之后，对于每个一级heading，生成对应的草稿文件（.md），应该统一放到一个目录（session folder的draft 目录）
然后每个章节的草稿一开始就包含该章节的 子章节目录。

  3. 对每个章节进行循环。告诉micro agent, 研究的背景等等，开始编辑第x章，目前的草稿（一开始基本空白的），然后开始循环看和该章节相关的notebook里面的summary（通过章节->有关的页->该页的summary)。对micro agent的要求是，根据背景和当前草稿，以及这个note，先尽量写完这个章节的结构，对于缺乏的内容或未定的内容，先用Placeholder。后面每看一个summary都是一个merge/fill in的过程。所以这是一个双层循环，外层是循环chapter, chapter 内又是一个note summary一个note summary的循环。LLM每次对话的上下文控制在 背景+当前草稿+ 当前看的summary， 输出一版新草稿。新草稿会及时存盘。


