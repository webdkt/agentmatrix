首先需要了解本项目的结构，阅读 docs/ 目录下的 agent-and-micro-agent-design.md，特别要熟悉think-with-retry-pattern.md 
然后需要了解agent 和 skill开发的流程，阅读 docs/agent-developer-guide-cn.md

完全了解开发规范后，开始阅读本需求文档

本次工作的需求如下
（1） 要实现一个 deep researcher 的skill
(2) deep researcher skill的工作过程，非常类似 skills/web_searcher.py 里的web_search skill。本质上也是浏览、获取信息、提取记录需要的信息。但是会增加一些其他步骤，包括制定研究大纲，撰写报告等等。

原来的程序员已经开发了一点 skills/deep_researcher.py，但是没有完成，他突然离职了，需要你挽救这个项目。所以需要的打起12分的精神来完成。原有的代码质量很乱，需要非常小心的甄别，千万不能当作是正确的。

Deep Researcher会用番茄笔记法记笔记。应该已经在 src/agentmatrix/skills/deep_researcher_helper.py 里实现了番茄笔记的功能（但是不确定是不是完整的）。

番茄笔记的使用流程是这样：
- 按页来组织笔记
- 每一页可以有多条笔记
- 每一条笔记包含文本（text）以及对应的目录章节（大纲章节）
- 每一页还有一个本页summary （Summary 也就自然的拥有了对应章节，就等于该页所有笔记所对应的章节，即summary可能对应多个大纲章节）
- 所以从数据结构上，可以获取每个章节所涉及的笔记（以及Page,以及Summary）
- 阅读笔记，可以按章节得到所有相关Summary list，或者相关笔记 list，或者相关页list



Deep Researcher 核心逻辑
    主流程：目标理解->人设生成（高级研究员，研究导师）->研究计划制定-> 研究循环 -> 写报告循环 

    每一个步骤都是一个micro agent 的执行过程。通过研究context来传递信息。研究的context 包括研究的基本信息（原始purpose)、report title、研究blueprint、章节大纲、task list, 笔记、question list （what else?)
    把所有研究工作包装成action method，提供给不同的micro agent。
    所以有哪些action method,需要定义好（目标理解和人设生成，应该用think-with-retry来实现，因为这个过程不是让micro agent自由选择action，而是非常明确的流程顺序）。后面的action就有比较大的自由度让“研究员”来自主选择
    应该有的action包括(不同的stage不同的micro agent会配备不同的action list  )：
        - 制定研究blueprint（总原则总体方案）
        - 制定章节大纲
        - 制定task list
        - 制定question list
        - do research task
        - web search
        - browse and find
        - take note
        - summarize page
        - update blueprint
        - update question list
        - update task list
        - check notebook
        - write draft
        - 润色draft, create final version

    基本流程：
        * 目标理解 -> （得到purse , 记录到 context)（think-with-retry)
        * 人设生成 -> （得到研究员人设，记录到context) (this-with-retry)
        * micro agent: research planner [actions: 制定研究blueprint,制定章节大纲, 制定task list, 制定question list， web_search, browse_n_find]:
            * each action is a micro agent execution 
            * micro agent: research plan maker -> 制定研究blueprint -> （得到研究blueprint，记录到context) 
            * micro agent: outline maker -> 制定章节大纲 -> （得到章节大纲，记录到context)
            * micro agent: task maker -> 制定task list -> （得到task list，记录到context)
            * 在这个阶段是允许planner 上网浏览的
            * finish_task 要求研究方案必须完整
        * micro agent: researcher [actions: do_research_task]:
            * micro agent: researcher[actions: web_search, browse_n_find, take_note, summarize_page, update_blueprint, update_question_list, update_task_list, check_notebook] 完成一个research task,
               更新都在context(包括notebook)里
            直到没有新的research task
        * micro agent: report writer [actions: write_draft,润色draft, create_final_version]
            研究循环完成后，进入写报告循环
            番茄钟拼接法：对每一个章节：找到所有相关页的Summary，组成章节草稿，然后扩写润色，不要在写的时候查文献，在文档里打三个大大的 XXX 或者 [待查]， 写完了统一回去补数据。
            最后汇总成报告


Deep Researcher 需要上网浏览和阅读的能力。很可能需要借助web_searcher skill。需要评估是否需要开发一个更高级的web_searcher skill，或者直接用web_searcher skill。


任务：
- 理解项目开发规范
- 理解本deep researcher 的需求
- 做好设计（需要什么方法和数据结构，那些放skill file，哪些放helper file，如何尽量简短和简洁，尽量模块化）
- 制定开发计划，代码精炼简洁，每一个方法都考虑是否必要，是否需要独立做成方法
    
    
    


    