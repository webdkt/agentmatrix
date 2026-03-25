Matrix View 是系统的一个主要View 之一

它的主要功能，是提供一个全局的视野来观察和检测系统内的所有Agent，看到他们的状态、设置他们的browser， 查看他们的虚拟机（container）， 查看他们日志（实时刷新），查看他们的文件夹，查看profile ，以及系统build system prompt 之后的完整prompt。查看timeline，查看长期记忆。

# 总体布局

分成左右两边，左边是导航栏（Agent List)，右边是Agent Dashboard。 点击Agent List中的某一个Agent, 右边显示该Agent的Dashboard

# Agent List

列出所有系统内Agent，不包括User（对应的Agent), 顶部有一个搜索filter

# Agent Dashboard

是一个Tab组织的结构，上部是Tab标签，用于选择不同的内容

Tab 有： 
- Profile
- Resources (里面几个卡片式按钮： Open Agent Browser, Open Agent Computer, Open Agent Home Folder, Open Agent Session Folder)
- Log
    实时的动态Log
- Memory
    todo, placeholder



# Notes

Profile 信息可以从后端API获取
Resources 里面打开浏览器、文件夹等操作，可以考虑下如何实现，是前端直接做，还是通过server.py？其实没有很复杂的逻辑，就是根据路径规则拼出路径，然后打开（包括browsrer profile）。对浏览器，重要的是使用Agent的profile, 并且联到已经打开的浏览器窗口（如果有）—— 这里我们可能有系统的bug，需要检查，就是我们的系统能不能让多个Agent同时打开各自不同的browser，互相不干扰。
Log，其实最好根据路径直接从文件读取，不要走后端