# Email Proxy Service - 设计文档

## 概述

Email Proxy Service 是 AgentMatrix 系统中的邮件代理服务，连接外部标准邮件系统（IMAP/SMTP）和内部消息传递系统。

**实现文件**：`src/agentmatrix/services/email_proxy_service.py`

---

## 设计目的

### 1. 用户可访问性

- 用户可以使用任何邮件客户端（Gmail, Outlook, Apple Mail 等）与 Agent 交互
- 无需打开专门的 AgentMatrix Web UI
- 支持从任何设备（手机、平板、电脑）发送任务

### 2. 异步通信

- 邮件天然支持异步通信
- 用户发送邮件后可以离线
- Agent 处理完成后通过邮件通知用户
- 适合长时间运行的任务

### 3. 远程访问

- 仅需要邮件客户端即可访问
- 适合低带宽环境
- 不依赖网络浏览器

### 4. 通知推送

- Agent 可以发送邮件到用户邮箱
- 用户收到邮件后会被邮件客户端通知
- 支持附件（报告、文件等）

### 5. 工作流集成

- 用户可以在邮件标题中@Agent
- 外部邮件会自动被convert并保留为内部邮件，无缝接入现有工作信息流
- 保持现有邮件工作习惯

---

## 架构设计

### 数据流

Emial Proxy 有两个sub 服务。一个是收信，一个是发信。

本质上，是把内部Email (src/agentmatrix/core/message.py) 和外部的邮件进行映射，使得用户可以通过外部邮箱和AgentMatrix里的Agent进行工作交互，和使用agentmatrix desktop app是一样的效果。这就需要同一个信息，即在内部email db里有（可以从desktop app里看到），也要在外部邮箱里有（才能在外部看到），然后要实现一系列的规则，使得系统能够通过一些字段mapping，知道外部邮件应该map到哪一个内部session里去。

我们会配置两个外部邮箱。一个是User_mailbox, 是代表用户的邮箱，凡事从这个外部邮箱发来的信，都被认为是用户发出的。这个邮箱，我们应用只是用来判断识别邮箱地址，不会访问。
另一个邮箱是 系统邮箱地址，是代表整个AgentMatrix系统, Email Proxy Config里面配置了收发信的地址和认证信息。

当Agent 给 User发信的时候，这封信会由PostOffice 服务投递到User的系统内邮箱（物理存放在数据库），如果启用了EmailProxy服务，那PostOffice也会把这封邮件投递给 user_mailbox.

当用户通过外部邮箱（user_mailbox) 向某个Agent发邮件（它需要向 系统邮箱地址 写信）, 然后会被我们的收件流程接受。这封邮件，会被转换成内部邮件格式，投递给内部邮箱（在内部数据库生成记录，发件人User，收件人Agent )


由于系统有多个Agent，但只有一个 系统邮箱地址，并且不同的邮件属于不同的session_id 和 task_id， 因此就需要一套机制来维护这些信息的流转，确保用户无论是在app内回答还是通过邮件回答，都是一样的效果。

对于内部信息的流转架构，参考 docs/core/message-system.md 

可以把用户邮箱，看作是和desktop app（以及未来的其他客户端）一样的客户端。信息从不同客户端发出，但是都在内部会归入同一个流程。Email Proxy Service就是外部邮件进出这个流程的proxy,进行数据格式的转换和映射。

#### 流程示意






#### 基本的数据结构

对于外部邮件，我们主要通过邮件的subject来维护我们需要的metadata:  agent name, task_id, 和 session_id

1. 对于用户发出的首封邮件（非回复，无前置，相当于启动新session)
用户需要在Subject 的开头写上 `@{agent_name}` ， 例如 `@Mark 新任务` ， 对于这样的邮件，系统会识别为一封发给 `Mark` 的新邮件，并且尽量直接使用该邮件自身的message id 等信息，当Agent回复的时候，in_reply_to 可以就是这封外部邮件的原始id

2. 对于Agent发出的邮件
subject 格式是 `...(subject内容)... #{agent_name}#{task_id}#{user_session_id}#{agent_session_id}#` ，即最后一部分是一个固定的格式串。当用户reply的时候，会自动继续带上这个串，我们收到邮件就可以自动识别出它对应的 agent_name, task_id 以及 session_id（Agnet的session_id 以及 User的session id）。


#### 收信流程

外部来自User邮件 -> Email Proxy Service (收件）-> [识别转换] -> 投入Post Office(通过调用 UserProxyAgent.speak)


收到外部邮件，要判断发件人的地址，是不是配置好的user_mailbox（是才代表用户）。如果是，就认为这是用户发的。可以理解为用户“说话了”。
收到后，要做的事情，就是解析好参数然后调用 UserProxyAgent.speak 方法。因为他们的功能本质是一样(speak的工作就是生成Email对象，投入Post office）。 
调用 UserProxyAgent.speak 的时候，具体参数设置规则是：
session_id = subject 中识别出来的 user_session_id
task_id = subject中识别出来的 task_id
其他的（subject, content等）看名字就知道怎么处理额了。

要注意的是, subject里的 user_session_id 可能是空白。这时候要去数据库里做一个查询，规则如下：

去email 表里，找  receipient = 收件Agent名字， sender= user agent名字，  并且 task_id = task_id, receipient_session_id = {agent_session_id} 的记录(多条取最新）。找到的话，用这个记录的"sender_session_id“ 作为user_session_id的值。


对于新会话的邮件，subject 只有 `@{agent_name}`，没有task_id, sesison_id等等，就生成一个新的task_id和session_id。
优先识别 ` #{agent_name}#{task_id}#{user_session_id}#{agent_session_id}#` 的格式，没有再看 `@{agent_name}`, 都识别失败，就放弃这个邮件（可以回信说格式不能识别）

要从系统里找到目前运行的UserProxyAgent，而不是创建一个新的。

然后收到的邮件有附件。还需要进行附件的copy，逻辑 server.py 里面的 send_email 方法对附件的处理（在speak之前，因为要生成attachments metadata)

注意，如果是ASK USER特殊邮件，要不同流程。参见下面的对应章节


### 发信流程

Agent 发邮件给User -> Post Office -> [Post Office 内部发信动作不变] -> [发现是给User的，并且启用了Email Proxy Service] -> Email Proxy Service（发件） -> [识别转换] -> 外发

Post Office 发信，如果配置了Email Proxy Service ,并且是发给用户的，说明需要copy一份到外部邮箱，就要进行外发。

外发的核心在于生成正确的Subject中的结构化信息字符串，

因为 Post Office的dispatch中只能看到Email 对象(src/agentmatrix/core/message.py)，从中参数获取方法如下：

新的Subject 需要4个信息： agent_name, task_id, user_session_id, agent_session_id

其中：
agent_name 就是 email.sender
task_id 就是email.task_id
agent_session_id 就是 email.sender_session_id

user_session_id 在 email 中不存在，需要去email db里做一次数据库查询。
过程如下：
（1）去email数据库里，查找 receipient = user agent name 并且 task_id = task_id 并且 receipient_session_id = agent_session_id 的邮件 （如果有多个，只要最新的即可）。用找到的邮件的 sender_session_id 作为 user_session_id 参数。
（2）如果找不到，user_session_id 可以是空白。 

如果有附件，需要根据附件的路径规则(参考 docs/developer/reference/directory-structure.md），把附件加进去。



# ASK USER 特殊邮件

在系统中，支持Agent 向用户提问，并进入等待状态，等待回答。这时候，app前端会弹出对话框等待用户回答，但是外部email是无法实现这种功能的。所以我们使用了特殊的ASK USER邮件。

即，当Agent 调用ask_user的时候，会调用 也会直接调用Email Proxy 服务（如果启用了），就调用 _send_ask_user_email， 发出一个到 外部邮箱（user_mailbox) 都有邮件，并且用特殊的Subject 格式来区分

Subject 为： `请回答问题 #ASK_USER#{agent_name}#{agent_session_id}`

其中agent_session_id ，就是当前Agent的 self.current_session.get('session_id')

当用户回复此类邮件，即在Email Proxy Service的收件流程中，发现 #ASK_USER 邮件，做的动作是：

- 找到对应Agent
- 调用Agent的submit_user_input

