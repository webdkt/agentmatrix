我们的系统，like any other system, 提供系统服务，目前主要是config_service.

# 总体思路和定位
如果把系统想象成一个精密的机器，那么系统服务就是对系统进行调整和调节的一系列功能。
我们是一个智能体Agent System，对于系统服务的操作，创新性的使用Agent的skill 机制，即让Agent（SysAdmin Agent）通过skill来具备对系统进行控制和调节的能力。
如果说Agent是管理员，系统是机器，系统服务就是机器的调节机制和功能，那么这些skill，就相当于系统这台机器的调节控制面板，它提供了一系列简单易用的“按钮”，让Agent管理员可以轻松的完成配置管理工作。
那么从架构上来说，skill只需要提供一个简单的interface，并去call under the hood的系统服务。具体的dirty work，都是系统服务模块去做的。

**特别重要的是**，因为Agent依靠LLM，是有“智能”，是可以识别文本格式的。所以skill和config service 之间，可以直接交换格式化的配置文本，即config service的输入输出（只要是涉及配置文件的）大部分情况下可以直接输入输出
配置全文或者部分的文本（例如yml的一部分，json的合格片段等等）。好处是，skill暴露的方法（即LLM需要发出的tool call）可以参数很简单，只要提前告知Agent，期望的格式是什么样的，就能自动生成。当然，config service需要检验，是否符合格式要求。不符合的，就正常反馈，告知具体错误和期望的格式，Agent看到会自动进行调整。


# 目前的现状
目前我们提供了一个config_service , 运行时会挂载runtime下。
然后提供了一个matrix_admin skill， 里面有一系列action方法可以去调用config_service。



# 重构目标

让面板变得更清晰好用， 并扩展系统服务的能力




## 系统服务的功能

在重构后，系统的功能会分成几个大类，每个类别都有具体的配置和管理项以及可以进行的操作

1. 系统管理

    功能列表：
    - 系统重启
    - 

2. Agent管理

    功能列表：
    - 创建Agent (保存一个新profile, runtime中加载，并注册到邮局)
    - Stop Agent （如果Agent正在process_email，中断它的会话提前返回 —— 这个功能不确定还有没有，需要研究实现。）
    - Reload Agent (重新加载Agent)
    - 更新Agent Profile
    - Clone Agent (完全复制一个profile,但是要用不同的名字)
    - 列出Agent （不要列出user agent，包括他们的status）

    Agent管理的几个“基本规则”：不能修改、控制 User Agent(代表用户的Agent，名字不一定是“User")。 Agent名字必须唯一。Agent的名字不能叫“User"或者“用户”

3. LLM 配置管理

    功能：
    - 更新整个 llm_config (全文更新）
    - 增加单个 llm endpoint entry 
    - 删除单个 llm endpoint entry (不能删除default_llm 和 default_slm， 这个只需要提供entry 的名字就行)
    - 修改单个 llm endpoint entry
    - read整个 llm_config

4. Email Proxy 服务配置