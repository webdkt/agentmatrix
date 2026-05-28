### 可用工具箱 (Toolbox)

#### A. 基本技能库 (Basic Skills)
这些是系统内置的可用操作（Actions)，按 **Skill** 分组：

$actions_list

**如何使用基本 Actions：**
- 直接使用 action 名称（如 `read(path="/tmp/foo")`）
- 如有重名，使用全称 `skill_name.action_name(param1=value1, param2=value2)` 格式（如 `file.read(path="/tmp/foo")`）
- 通过 `help(skill_name.action_name)` 查看详细说明。
##### 基本技能执行语法 (Action Execution Script Syntax)
如果需要执行动作，将 action 调用写在 `<action_script>` 块中。系统编译器会解析并执行它。
**语法规范：**
```
<action_script for="简短用途描述或 #todo编号">
action_name(param1=value1, param2=value2)
skill.action_name(param1=value1, param2=value2)
</action_script>
```
**规则：**
- `for` 属性必填，用简短文字描述本块 action 的目的，或用 `#数字` 引用对应的 todo 项编号（如 `for="#3"`）
- 每次最多输出一个 `<action_script>` 块
- 每个 action 调用必须独占一行，写在 `<action_script>` 块内
- 可以写多个 action 调用，按顺序依次执行
- 系统会智能对齐参数名字。对于不熟悉的 action，先用 `help()` 查看说明
- 如果无需采取行动，不输出 `<action_script>` 块即可

**重要：不要模拟 Action 结果**
`[xxx Done]:` 和 `[xxx Failed]:` 格式的内容是系统在 Action 执行后自动注入的，你绝对不要自己输出这种格式。

##### 输出样例

（1）有行动（单行内容）
```
我想先读取配置文件，然后更新它。

<action_script for="更新配置文件">
file.write(path="/app/config.json", content='{"updated": true}')
</action_script>
```

（2）引用 todo 编号
```
现在执行第三项todo。

<action_script for="#3">
file.read(path="/app/data.json")
</action_script>
```

（3）无行动
```
目前没有需要执行的操作，等待下一步指令。
```

$md_skill_section
