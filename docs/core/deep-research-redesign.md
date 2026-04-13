# Deep Researcher Agent 应该包括的skill有：

file (基本的文件读写)
simple_web_search (基本的搜索和浏览)
deep_researcher (top level actions for this skill)


# deep_researcher skill 应该包括的action

和目前设计相比，要进行大幅的简化和扁平化，及除非必要，不再进行复杂的嵌套调用，而是把主要工具在top level micro agent这里罗列，让top level micro agent对总体进度有清晰的全局把握。利用自动的压缩机制来保持上下文的紧凑。

同时，把目前散落在各个地方的

在top level 应该有的tool action（也就是deep_researcher 直接包含的）
* set_mindset(planning/research/writing)
* take_note 
* search_note_w_keyword
* search_note_w_natural_lang
* organize_content
* write_chapter(chaptern_name)
* finalize_report


# 文件结构和note database


文件结构也进行修改，总的原则： 计划->文件， 研究->database, 写作/Output -> 文件。 
研究的蓝图、计划等等，继续放在research_state 目录，使用md 文件。
有几个重要文件
- Research Blueprint: 总体的研究蓝图
- Current Status Summary - 目前进展summary, what has been done
- Plan:  todos and pending tasks 
- Chapter Outline:  输出物标题大纲
- Writing Schema: 写作思路、结构安排、每个大章节的目的、内容组织等等


研究的note，放在sqlite数据库，即note.db ,并且明确的告诉Agent，note.db 的数据结构：
- ID: 自然增长的数字
- note_text:   note文本
- chapter_name:  打算用于什么chapter， allow empty （只是一季chapter_name)
- tags:  逗号分隔的keywords。每个note最多3个tag， tags全部小写，一定的标准化（不用下划线和空格，可以用-，不允许特殊字符等等）， tags 按字母顺序排列。

**Agent is allowed to direct access note database**
但是我们提供了`take_note`, `search_note_w_keyword`, `search_note_w_natural_lang` action toool, 方便agent快速使用，并且在action的short_desc里解释清楚这些方法的优点和额外功能

### teak_research_note
接受参数： note_text, chapter_name, tags
功能
（1）自动 verify 数据规范，包括，tags的数量， 标准化规范，自动标准化（大小写、顺序）
（2）自动的进行重复检查。逻辑： 找有同样tags的 note，或者partial match(即A的tags全部在B的tags里，或者反过来，都算), 然后用LLM (调用cerebullum.backend.think_with_retry)来确认，是否重复。判断为重复的note,就返回有重复note的信息给Agent。

### search_note_w_keyword
就是对note进行全文搜索，搜索note_text和tags字段，tags要完全match某一个tag. 返回match的top 10 note list，按某种score 排列


### search_note_w_natural_lang
对note进行自然语言搜索，接受一个“问题”作为参数。这个action 的动作是：
- step 1:  根据问题，生成list of 搜索组合。每个搜索组合是一个或多个keyword。
- step 2:  对于每一个搜索组合 进行搜索、判断然后loop，
- 搜索和判断：对于每个组合内的关键词，进行AND的搜索（search_note_w_keyword 一样的逻辑），如果只有一个关键词就是等于search_note_w_keyword。 搜索出来的结果，依次用 cerebellum.backend.think_with_retry 进行思考，（a)能否回答最初的搜索“问题”，如果可以，返回。(b)如果不能回答，该note是否对回答这个问题很有用。如果有用，就记录到一个内存list。每一次判断的时候，都会带上已有的“有用note list“一起。
- 直到问题得到回答，或者所有搜索结果都结束/或者没有搜索到任何内容，分别返回 答案 or "现有note无法解答该问题"


### write_chapter(chapter_name)

要实现一个 sub skill:  deep_researcher.writer
里面action有2个： revise_chapter(chapter_name, note), merge_chapter_drafts 

write_chapter action 会 loop through chapter outline里的每一个top level chapter， 对每个chapter，启动一个MicroAgent（writer agent) 来进行写作， 这个micro agent具有file 和 deep_researcher.wrtier skill， 并且用merge_chatper_drafts 来作为exit action.

它的persona prompt 会给他一个工作的流程约定，包括：
* 对于每个chapter, 在一个约定draft目录下工作，并且按照子章节结构创建子目录结构，即每一层目录都是该层的章节名，目录深度是章节层次深度。目录名前面用数字序号来进行顺序区分。创建子章节就是创建子目录节点。每个节点目录下如果有段落，可以用 {index}-paragraph.md 。如果每个节点下有段落和子节点混合，使用统一连续的index来表明他们的顺序（可以给点例子）
* 工作的要求是按照 research blueprint, writing schema 的指引，知道自己目前在写作哪一个 {chapter}，之前的已经写完后面的还没写。 所有的note在note的database里（schema介绍也都说明），写作流程就是go through all the notes that 属于这个chapter, 以及那些没有确定属于什么chapter的note。然后进行写作，即创建节点和节点内容。 如果遇到note读完后认为应该用到之前已经写完的chapter，就用revise_chapter(chapter_name,note)来修改。如果认为这个note应该用于后面的章节，就可以自己去update database.
* 每个paragraph 不应超过一定大小

### finalize_report
把所有chapter 文稿，组装成完整report。 这个是top level agent的exit action.

### organize_content
在介绍里要提示Agent，经常使用，目的是整理note和草稿。并且强烈建议写作开始前用。他有几个功能
（1）根据chapter outline, verify DB 里是不是有错误的chapter_name 字段值，有的话列出来那些note的chapter_name 写错了
(2) 对写作的草稿目录进行规范检查，例如是不是目录名和item 名都有序号，序号是否连续。目录名和chapter outline是否吻合，给出提示，帮助Agent 在写作过程中发现有不规范的地方。

### set_mindset （plan/research/write)
参见后面的说明。用来设置agent的mind set，即在计划阶段、研究阶段、写作阶段，有不同的system prompt需要注入，让agent可以运行时动态调整system prompt。他的工作是根据不同阶段，

## deep_researcher.writer skill

里面action有2个： revise_chapter(chapter_name, note), merge_chapter_drafts 



### revise_chapter

这个动作就是再启动一个MicroAgent， 和writer_chapter 启动的基本一样，也是 file 和 deep_researcher.wrtier skill, 但是task指示不同，总体persona和上面类似，但是具体工作是现在有一个新的note，要revise一下xxx章节的内容，revise完毕后，merge_chatper_drafts (同样是exit action)
agent会自己根据draft的目录结构去找该修改的地方，然后merge_chapter_drafts，返回。

### merge_chapter_drafts
就是把draft的目录结构和所有子节点，组装成chapter的完整md文件。

# Top Level Agent 的persona

也就是deep researcher的 persona，要讲清楚 research state的目录结构，note 的数据库结构，重要的是有一个[Mindset]...[End of Mindset] 块。一开始默认是：当前Mindset 没有设置，需要按照目前的工作阶段启用不同的mindset (计划、研究、写作)。 根据选择的mindset，替换micro agent 现有system prompt（以及self.persona，确保每次_build_system_prompt不会变)中的这块区域，用有针对性的思路、工作方式和注意点来替换。因为不同阶段需要关注不同的东西，有不同的流程。
