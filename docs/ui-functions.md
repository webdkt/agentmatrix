# AgentMatrixUI的功能

概念：
* Matrix World: 就是对应一个目录。server 启动的时候必须制定一个运行根目录作为Matrix World目录。这个目录下会被自动创建两个子目录：agents 和 workspace。

## Server 启动流程
* 启动server，指定一个运行根目录作为Matrix World目录。  


## 第一次冷启动，Wizard引导用户配置大模型

### 冷启动Ste 1 创建目录
*如果目录不存在，就创建目录，并且创建`agents`和`workspace`两个子目录。并且创建在`agents`子目录下创建默认agent的配置yml文件。以及llm_config.json文件。

默认的Agent有：User.yml
```yaml
#You should always have one USER agent
name: User
description: Master of world
module: agentmatrix.agents.user_proxy
class_name: UserProxyAgent

# 动态 Mixin 组合
mixins:
  - skills.filesystem.FileSkillMixin

# 属性初始化
attribute_initializations:
  on_mail_received: null

instruction_to_caller: "要精炼不要啰嗦"
system_prompt: ""
backend_model: default_llm
```
后面还会增加其他的默认Agent（会从一批模版里copy）

###  冷启动Step 2 LLM配置
第一次冷启动，如果没有llm_config，就要求用户创建两个llm 配置：default_llm 和 default_slm。  可以增加更多。例子：

```json
{
    "default_llm": {
        "url": "https://api.deepseek.com/chat/completions",
        "API_KEY": "DEEPSEEK_API_KEY",
        "model_name": "deepseek-reasoner"
    },
    "default_slm": {
        "url": "https://api.deepseek.com/chat/completions",
        "API_KEY": "DEEPSEEK_API_KEY",
        "model_name": "deepseek-reasoner"
    }
}
```

## 正常启动
冷启动配置wizard结束后也一样进入正常启动流程
就是调用agentmatrix 的runtime，用agents目录和workspace目录作为初始化参数，启动agentmatrix的runtime。


## Main UI 布局

是Tab布局，Tab的顺序是：
* Master User View
* World View
* Matrix Setting

### Master User View
这是用户工作视角。类似于邮箱界面，界面分成三列：
* 左侧是Conversation Topic List, （也就是User Session List）
* 中间是Conversation History View，是当前选中的Session的相关邮件列表
* 右侧是File View，显示当前Session 共享目录的文件树结构和文件列表

#### Conversation Topic List

* 每一个User Session 对应一个user session id 和 topic name。 在Matrix World目录里有 `workspace/.matrix/user_sessions.json` ,格式如下：
```json
{
  "e4362eb8-9394-4284-8546-566a20bc935d": {
    "name": "能力询问 2026-01-04",
    "last_email_time": "2026-01-04 19:03:50.301214"
  },
  "bfb4d2fb-fe59-4cb0-a87a-63a57626fcb1": {
    "name": "查询14117法案背景 2026-01-04",
    "last_email_time": "2026-01-04 19:07:11.320544"
  }
}
```
他是 user session id 和name以及 时间戳的对应。Conversation Topic list，就是列出这些name（显示name和时间戳，实际上所有数据会返回）

* 点击某个Topic，中间的Conversation History View会显示这个User Session的邮件列表，右侧的File View会显示这个Session的共享目录的文件树结构和文件列表。

### Conversation History View

* 显示当前选中的User Session的相关邮件列表。但是以聊天对话方式显示。即每个Email是一个类似对话的卡片（但是带有邮件的格式，from/subject/date等等）。
整个对话是`User`视角，即用户发出的邮件，卡片显示靠左边一点，用户头像（名字）在左边，卡片看起来像用户说出的话。用户收到的邮件卡片，靠右边一点，发信人的名字在右边，
卡片看起来像发信人说话。然后按时间顺序排列。

后台API需要返回的是： 根据User Session ID，返回所有发件人或者收件人是`User`的邮件，并按照时间戳排序。

对收到的邮件，用户可以选择"Reply"，然后会弹出输入框，用户输入回复内容，然后点击发送，就会发送邮件。
在Session内也可以新建邮件，选择发给谁（发送邮件功能晚点再实现，先留好UI入口）

### Session File View

User Session 有ID，对应的在MatriWorld的workspace目录下，有`{session_id}`目录（名字就是session id的值），然后下面还有一个`shared`目录，这个目录就是共享目录。
在Agent工作的时候，这个目录里面的内容会变化。Session File View就是显示这个目录的文件树结构和文件列表。双击可以打开文件。也可以拖拽上传文件到这个目录。