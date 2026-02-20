工作准备:

1. 先理解代码，了解：
 runtime.py 通过loader.py 初始化整个AgentMatrix的过程。

2. 理解Agent的运行机制，BaseAgent 创建 MicroAgent，并执行MicroAgent.execute 来进行循环。

3. 理解BaseAgent 和 MicroAgent之间的关系。 MicroAgent.root_agent 指向自己的base agent.

需要解决的问题：

整个AgentMatrix是依赖于大模型服务的，目前需要实现一种机制，在llm服务不可用的时候，整个matrix进行等待。matrix等待其实就是所有Agent等待。因为Agent总是在执行某个Micro Agent（然后发生嵌套调用，最终有一个当前正在运行的micro agent。).

即，我们需要当发现llm不可用时，所有Agent都能被通知到（知道一个全局状态）。而所有MicroAgent在运行/循环的时候，应该有某种方式获悉，LLM可用 or 变成不可用。当llm服务不可用时，micro agent 应该在execute中等待，直到服务可用。

现在需要研究下，如何实现这个机制。

目前有个初步的想法，
1. runtime 有一个类似ping的动作，每一分钟检查一下 llm 服务是否正常（包括针对default_llm和default_slm的）。如果不正常就somehow notify running Agent(或者不需要通知，如果Agent可以直接有self.runtime 来获取状态信息）
2 Micro Agent 在运行时(主要就是 _run_loop）如果发生llm 相关exception（需要能更好的识别），就去检查self.root_agent.runtime 的状态，如果llm服务终端，就进行等待（可能过一段时间再进行检查，直到发现恢复，再继续）。

评估一下最佳方案是什么

