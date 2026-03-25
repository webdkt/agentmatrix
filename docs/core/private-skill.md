目前的skill 系统分两个部分
一个是内置的Python skill, 通过mixin 方式加载，是MicroAgent的一部分（自身方法）。
另一个是 md skill （就是通过skill.md 加载的文本说明型的skill)

加载的机制略复杂，

现在想改成这样的架构。

目前每个Agent 都有自己的container， 并且会被动态的加载两个路径， /home ,  /work_files ，实际在宿主机上的路径分别对应 agent_home_dir和 agent_work_base_dir（参见 src/agentmatrix/core/paths.py 里的定义）。然后还有一个加载的路径，/SKILLS,对应 skills_dir ，是只读方式加载，所有agent 共享的一个目录。

现在我们要修改一下这个共享skill的目录结构，变成每个Agent 有自己独立的Skills

对Agent来说，就用它容器内的目录。/home/SKILLS ， 也就是说，在 agent_home_dir 对应的宿主机目录下增加一个“SKILLS" 目录。
每个Agent的skill 相关prompt 要修改，同时 paths.py 里的 get_skills_dir 方法要增加一个agent name的参数，然后逻辑也完全不同了。

但是注入的基本流程不变，只是原来从所有Agent 共享的SKILL 目录，变成每个人自己独立的。


那么在Matrix View 的Resource tab 里，要增加一个 “打开Skill目录“的功能，打开Agent的 skill 目录

然后MicroAgent的 _build_system_prompt 里注入md skill说明的部分，要能实现动态，即每次都是根据实际的skill目录里有的skill子目录和里面的skill.md 内容来进行加载，效果就是用户打开skill 目录，拖进去一个下载的skill，就相当于生效了。

然后Profile Tab 里，最好再增加一个显示区块，列出此类md文件Skills（以及基本描述）。
