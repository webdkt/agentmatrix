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

#### Email View

Email View 大体上就是现在的agentmatrix desktop 选择sessions所展现的。左边是session list，右边是选中的session的email list.
但是在视觉效果和功能上，要在现有基础上做加大的改进，具体如下。
##### Session List
 顶部有比较大和醒目的“新邮件“按钮，基本和session list宽度接近，一个扁长的按钮。代替现在的小图标。
 搜索框在“新邮件”按钮下面，也是扁长
 再往下就是session list。session item 之间的间隔再紧凑一点。整体风格更像 Outlook，有一种商务感，但是又不完全一样，苹果商务感。文字在圆圈圈右边，应该左对齐。session item内部也紧凑一点。
 点击后的逻辑和现在一样，刷新右边的email list
### Email List
**注意** 一般都应该左对齐，现在很多都是居中对齐，都要改。

Email list 顶部有一个始终可见的工具条（现在也有，但是不需要显示subject文字了），最右边是现在那样的三个点，出菜单：“删除”（功能是删除整个session，等改完UI再实现，先放placeholder），"刷新"Icon(功能是reload 这个session)
工具条左侧的区域，就变成Agent Status Info Area（原来在list 底部的）。

基本功能（包括agent status info)和现在功能一样。但是同样的，item 和 item 之间要紧凑得多，更Email 风格（整体风格都要这样变化，和session list是统一的，当然具体大小不一样）。信息摆放紧凑、又可视性极佳，不容易混淆。
可以取消 “头像”+“信息卡片”的布局。直接是卡片接卡片的形态。

原来底部的agent status就不需要了。

#### Email 编辑有关的组件 ####
一个是新邮件对话框