我们的系统，like any other system, 提供系统服务，目前主要实现在config_service.

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

目前cnofig_service 有自动保存备份的机制，这个机制要**完全**保留，包括目录命名规则等。


# 重构目标

让面板变得更清晰好用， 并扩展系统服务的能力。调整config_service, 分拆matrix_admin skill，实现下面的完整功能




## 系统服务的功能

在重构后，系统的功能会分成几个大类，每个类别都有具体的配置和管理项以及可以进行的操作

1. 系统管理

    功能列表：
    - 系统重启


2. Agent管理

    功能列表：
    - Create Agent (保存一个新profile, runtime中加载，并注册到邮局)。输入:agent 名字，profile全文。输出：成功or错误提示
    - Stop Agent （如果Agent正在process_email，中断它的会话提前返回 —— 这个功能不确定还有没有，需要研究实现。）输入：agent名字，输出：成功or错误提示
    - Reload Agent (重新加载Agent)，输入：agent名字，输出：成功or错误提示
    - Update Agent Profile (全文)，输入:agent 名字，profile全文。输出：成功or错误提示
    - Clone Agent (完全复制一个profile,但是要用不同的名字)，输入：from_agent名字，new_agent名字，=输出：成功or错误提示
    - List Agent （不要列出user agent，包括他们的status），输入不需要，输出:list

    Agent管理的几个“基本规则”：不能修改、控制 User Agent(代表用户的Agent，名字不一定是“User")。 Agent名字必须唯一。Agent的名字不能叫“User"或者“用户”

3. LLM 配置管理

    功能：
    - 更新整个 llm_config (全文更新）, 输入，config file content.
    - 增加单个 llm endpoint entry , 输入， end point piece , 用于插入到config file
    - 删除单个 llm endpoint entry (不能删除default_llm 和 default_slm， 这个只需要提供entry 的名字就行)
    - 修改单个 llm endpoint entry ，输入，endpoint name, end point piece
    - read整个 llm_config

4. Email Proxy 服务配置
    功能：
    - Read Email Proxy config , 
    - Update Email Proxy Config （全文）, 输入config file content
    - Change Email Proxy Service Status(Enable, Disable) enable会自动启动服务，disable会自动停止服务

5. 通用功能
   - list_agent_history(agent_name) 
   - list_config_history(config_type = "llm" or "email_proxy") 

**Note**:  因为read config和update config，基本就是从配置json or yml 文件加载，或者更新。所以config service 实现了通用的读写方法。


## Skill 提供的能力

skill 提供的能力，基本就是对上述管理能力的封装（或者说提供接口）。
为了Admin Agent 便于理解，我们实现两个skill。 一个是 Agent Admin Skill,  一个是System Admin Skill

### Agent Admin Skill

提供这样几个方法

（1）readme_first

用来返回一大段说明，介绍Agent profile的组成结构和格式要求，以及有哪些

(2) 其他Agent管理的功能，包括list_agent_history


### System Admin Skill

提供这样的几个方法

（1）llm_config_manual() 返回说明，用来介绍llm config 的格式要求
（2）email_proxy_config_manual() 用来返回说明，用来介绍 email proxy config的格式要求
（3）上面提到的 系统管理、LLM配置以及Email Proxy配置功能, 以及list_config_history