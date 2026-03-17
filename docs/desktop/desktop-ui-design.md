# AgentMatrix Desktop UI 重构计划

## 📋 Phase 0 完成状态

**✅ Phase 0: UI Design & Style Guide - 已完成**

完成日期: 2025-03-17

**交付物:**
- ✅ `docs/desktop/ui-design-guide.md` - 完整的设计系统文档
- ✅ `docs/desktop/ui-quick-reference.md` - 开发者快速参考指南
- ✅ `agentmatrix-desktop/src/styles/tokens.css` - CSS 设计变量
- ✅ `agentmatrix-desktop/src/styles/global.css` - 全局样式和工具类
- ✅ 已集成到 `main.js`

**设计亮点:**
- 🎨 精致的商务感设计语言（Apple + Outlook 风格融合）
- 🌈 完整的色彩系统（主色、中性色、语义色）
- 📐 一致的间距和排版系统
- 🎯 独特的圆角半径（6px, 10px, 14px, 18px）
- 💫 优雅的动画和过渡效果
- 🌙 完整的深色模式支持
- ♿ 无障碍设计考虑

**设计哲学:**
- **清晰胜于复杂** - 每个元素都有其目的
- **精致的商务美学** - 专业而不冷漠
- **视觉层次** - 清晰的信息架构
- **响应式与自适应** - 流畅的布局

**下一步:** Phase 1 - 基础框架改造

---

## Concepts
核心概念参见 docs/concepts/CONCEPTS.md

## UI布局

### 总体布局
采取类似于新的Microsoft Outlook for Mac的布局。

总体上会分成几种不同的View, 就像Outlook可以有email, calendar, todo等等，完全不同的功能面板或者说功能视图。 我们的AgentMatrix Desktop 计划有这几个功能视图：

- Overall Dashboard
- Email (本次实现，目前已有基本形态）
- Matrix
- Magic
- Settings (在Email之后实现)

以后还可能增加，或者改变。目前先实现整体框架 以及 Email 和 Settings 两个功能视图。

**总体框架**

就是最左边，是一个垂直的、比较窄的View Selector。 用几个小图标来实现View 之间的切换
在View Selector的右侧，就是具体的View。根据选择不同，显示不同的View。

现在的顶部的条，都不要了。

**多语言支持**
要能从基础上支持多语言。先支持中文和英文

**其他**
app的内容应该占据整个app的可见宽度，两边不应该有留白。

### Email View

Email View 大体上就是现在的agentmatrix desktop 选择sessions所展现的。左边是session list，右边是选中的session的email list.
但是在视觉效果和功能上，要在现有基础上做加大的改进，具体如下。
#### Session List
顶部有比较大和醒目的"新邮件"按钮，基本和session list宽度接近，一个扁长的按钮。代替现在的小图标。
搜索框在"新邮件"按钮下面，也是扁长
再往下就是session list。session item 之间的间隔再紧凑一点。整体风格更像 Outlook，有一种商务感，但是又不完全一样，苹果商务感。文字在圆圈圈右边，应该左对齐。session item内部也紧凑一点。
点击后的逻辑和现在一样，刷新右边的email list
#### Email List
**注意** 一般都应该左对齐，现在很多都是居中对齐，都要改。

Email list 顶部有一个始终可见的工具条（现在也有，但是不需要显示subject文字了），最右边是现在那样的三个点，出菜单："删除"（功能是删除整个session，等改完UI再实现，先放placeholder），"刷新"Icon(功能是reload 这个session)
工具条左侧的区域，就变成Agent Status Info Area（原来在list 底部的）。

基本功能（包括agent status info)和现在功能一样。但是同样的，item 和 item 之间要紧凑得多，更Email 风格（整体风格都要这样变化，和session list是统一的，当然具体大小不一样）。信息摆放紧凑、又可视性极佳，不容易混淆。
可以取消 "头像"+"信息卡片"的布局。直接是卡片接卡片的形态。

原来底部的agent status就不需要了。

#### Email 编辑有关的组件 ####
一个是新邮件对话框，要有几个变化：
1. 大一些
2. 附件上传能不能像outlook一样，整个邮件编辑区域（至少大部分）都可以被拖拉放入文件，不需要单独的drag n drop 区域。上传后，文件名也紧凑显示，总之按我们风格，更类似邮件。

在Session内：

邮件编辑组件，是在底部的回复控件。要有这样一些变化
1. 邮件回复控件默认悬浮显示在email list 底部，默认回复当前session最后一个非用户发件人。
2. 每个邮件都有自己的小工具条，包括"回复"，点击邮件卡片的回复，在该邮件下方，出现一个inline的邮件回复控件（可以复用底部的那个，是一样的样子，一样的功能，只是回复的具体邮件不一样，也就是in_reply_to, to 等参数不同。当有inline的回复控件出现的时候，底部的回复控件应该隐藏。总之不会同时出现。

还有一个 回答Agent问题 组件。
当session 需要回答用户问题时候，session内应该不能做其他动作（回复邮件等等），必须回答完才能做别的。所以一旦发现session需要Agent问题，底部回复控件隐去，换成 "回答Agent"控件（悬浮效果，醒目），不需要弹窗了。不回答，该session 不能做的事情。他虽然多了问题部分，但是大小、风格和回复控件是一致的。要有家族感。

总之，Session内 底部的回复控件、Inline的回复控件还有回答问题控件，三者每次只能出现一个。

另外，回复控件还要有小按钮可以上传附件（功能上和新邮件是一样的）

** 一个重要的功能增强 **
因为现在Agent提问，用户回答后，就几乎看不出来，session里看不出来问过答过，用户体验不好。打算做这样一个机制来弥补。
在前端，在当前最后一封邮件后面，插入这个问答显示—— 这个是不持久的，刷新session，就没了，只是暂时在dom tree里。
在后端，在用户回答后，即Agent收到回答的地方，做2个额外的数据库操作，直接生成一来一回两封邮件插入数据库（不走post office，不会触发process email过程，但是以后加载会话记录能看到。
（1）在email表里插入一条 email, 发件人是Agent，收件人是用户，subject是"问题"，body是刚才问的问题。task_id 就是Agent当前task_id，但是sender_session_id是Agent那边的self.current_session_id，receipient_session_id是Agent那边的self.current_user_session_id
 (2) 在email表里再插入一条email，这次发件人是用户，就是回答的内容。sender_session_id 是 Agent那边的 current_user_session_id, receipient_session_id是Agent那边的self.current_session_id
 这样前端如果刷新，或者以后再进app，都能在session里看到这个问题和回答，只是看起来像是邮件。
 通过直接插入数据库，保留了信息，但是不触发email的相关处理流程


### Setting View

待设计


### 其他 View
待设计
