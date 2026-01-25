# Release Notes - v0.1.5

## 🎉 Major Release: Dual-Layer Agent Architecture

Version 0.1.5 introduces **fundamental architectural improvements** that significantly enhance the framework's robustness, maintainability, and ease of use. This release represents a major milestone in the evolution of AgentMatrix.

## 🚀 Major Features

### 1. **New: MicroAgent System** (Core Architecture Change)

**Problem Solved**: 
- Previously, BaseAgent mixed session management and task execution in one place
- This led to messy state management and unclear responsibilities

**Solution - Dual-Layer Architecture**:
- **BaseAgent (Session Layer)**: Manages conversation state across multiple user interactions
  - Can maintain multiple independent sessions
  - Each session has isolated conversation history
  - Owns skills, actions, and capabilities (global, shared across sessions)
  
- **MicroAgent (Execution Layer)**: Temporary executor for single tasks
  - Inherits all BaseAgent capabilities (brain, cerebellum, action registry)
  - Has independent execution context (task, history, step count)
  - Terminates when task completes or exceeds step limit
  - **Key**: Not a separate agent class, but a "temporary execution context"

**Benefits**:
- ✅ **Clear Responsibilities**: Session vs. execution, easier to understand and debug
- ✅ **State Isolation**: Session history not polluted by execution steps
- ✅ **Concurrency**: One BaseAgent can maintain multiple sessions simultaneously
- ✅ **Robustness**: Task failure doesn't break the session

**Files Added**:
- `src/agentmatrix/agents/micro_agent.py` - MicroAgent implementation
- Updated `src/agentmatrix/agents/base.py` - Added `_run_micro_agent()` method

### 2. **New: Think-With-Retry Pattern** (Major Enhancement)

**Problem Solved**:
- Extracting structured data from LLM outputs required strict format constraints
- This imposed a "cognition tax" - LLMs wasted mental energy on format compliance instead of reasoning

**Solution**:
- **Loose Format Requirements**: Use natural markers like `[Section Name]` instead of strict JSON
- **Intelligent Retry**: Automatic retry with specific, actionable feedback
- **Conversational Flow**: Retries feel like natural clarification requests

**Key Addition**:
- `LLMClient.think_with_retry()` - Generic micro-agent that loops until LLM output is successfully parsed
  - Supports any parser following the parser contract
  - Provides specific feedback on parse failures
  - Graceful error handling

**Benefits**:
- ✅ **Preserves Cognitive Capacity**: LLMs focus on reasoning, not format
- ✅ **Handles Edge Cases**: Automatic retry with feedback handles deviations
- ✅ **Natural Interaction**: Conversational retries align with LLM training

### 3. **New: Multi-Section Parser**

**Feature**: Robust parser for extracting multiple sections from LLM output

**Capabilities**:
- Extract multiple named sections (e.g., `[Plan]`, `[Timeline]`, `[Budget]`)
- Two match modes: `"ALL"` (all sections required) or `"ANY"` (at least one required)
- Performance optimizations:
  - Reverse iteration for faster content discovery
  - Early termination when all sections found
  - Fast pre-check for missing sections
- Backward compatible with single-section mode

**Files Added**:
- `src/agentmatrix/skills/parser_utils.py` - Multi-section parser implementation
- `src/agentmatrix/skills/search_results_parser.py` - Example parser for HTML search results

### 4. **Enhanced: Web Searcher**

**Improvements**:
- Comprehensive test cases to validate functionality
- Better error handling and edge case coverage
- Integration with new parser system

### 5. **Bug Fixes**

- ✅ Fixed new session ID bug
- ✅ Implemented Chrome browser port isolation for different agents
  - Each agent now has its own isolated browser instance
  - Prevents port conflicts and state pollution

## 📚 Comprehensive Documentation

This release includes **6 new bilingual documentation files** explaining the architecture and design:

1. **Agent and Micro Agent Design** (English & Chinese)
   - Dual-layer architecture philosophy
   - Session vs. execution layer separation
   - Skill system and action registration
   - Communication mechanisms

2. **Matrix World Architecture** (English & Chinese)
   - Complete project structure
   - Core components and initialization
   - Runtime execution flow
   - YAML configuration format

3. **Think-With-Retry Pattern** (English & Chinese)
   - Natural language → structured data challenge
   - Parser design and implementation
   - Custom parser creation guide
   - Multi-section parser usage

**Documentation Philosophy**:
- Natural language explanations without jargon
- Focus on "why" before "how"
- Bilingual support (English & Chinese)
- File references with line numbers

## 🔄 Breaking Changes

**None** - All changes are backward compatible. Existing code will continue to work.

**Recommended Migration**:
- Review new documentation to understand architectural improvements
- Consider adopting MicroAgent for task execution in your agents
- Use `think_with_retry()` for new LLM integrations
- Leverage multi-section parser for complex outputs

## 📖 Migration Guide

### Before (v0.1.4)
```python
# BaseAgent handled everything
class MyAgent(BaseAgent):
    async def process_email(self, email):
        # Session management and task execution mixed together
        session = self.sessions.get(email.user_session_id)
        # ... lots of state management
```

### After (v0.1.5)
```python
# BaseAgent delegates to MicroAgent
class MyAgent(BaseAgent):
    async def process_email(self, email):
        # Restore or create session
        session = self._get_or_create_session(email)
        
        # Delegate to MicroAgent for task execution
        result = await self._run_micro_agent(
            persona=self.system_prompt,
            task=email.body,
            available_actions=self.actions_map.keys(),
            initial_history=session.history
        )
        
        # Update session and respond
        session.add_message(email.body, result)
        await self._send_reply(email, result)
```

### Using Think-With-Retry

**Before**:
```python
# Manual parsing with error-prone format constraints
response = await llm_client.think(prompt)
try:
    data = json.loads(response['reply'])
except:
    # Handle parsing errors manually
    pass
```

**After**:
```python
# Automatic retry with intelligent feedback
result = await llm_client.think_with_retry(
    initial_messages="Extract structured data...",
    parser=multi_section_parser,
    section_headers=['[Plan]', '[Timeline]'],
    match_mode="ALL",
    max_retries=3
)
```

## 🏗️ Architecture Improvements

### Key Design Principles (Now Formalized)

1. **Session and Execution Separation**
   - Session = conversation-level (long-lived)
   - Execution = task-level (ephemeral)
   - One conversation can contain multiple task executions

2. **Capability Inheritance, State Independence**
   - MicroAgent reuses BaseAgent capabilities
   - No state coupling between layers

3. **Natural Language Coordination**
   - Agents communicate via Email (natural language)
   - No rigid APIs - coordination through explanation

4. **Dual-Brain Architecture**
   - Brain (LLM): High-level reasoning
   - Cerebellum (SLM): Parameter negotiation
   - Right tool for each cognitive task

5. **Dynamic Skill Composition**
   - Skills are mixins loaded via YAML
   - Composable and extensible

## 📝 File Structure Changes

### New Files
```
src/agentmatrix/
├── agents/
│   └── micro_agent.py                 # NEW: MicroAgent implementation
├── skills/
│   ├── parser_utils.py                # NEW: Multi-section parser
│   └── search_results_parser.py       # NEW: Example parser
```

### Documentation
```
docs/
├── agent-and-micro-agent-design.md    # NEW: English
├── agent-and-micro-agent-design-cn.md # NEW: Chinese
├── matrix-world.md                    # NEW: English
├── matrix-world-cn.md                 # NEW: Chinese
├── think-with-retry-pattern.md        # NEW: English
├── think-with-retry-pattern-cn.md     # NEW: Chinese
└── v0.1/                              # NEW: Archived docs
    ├── Design.md
    ├── micro_agent_design.md
    ├── micro_agent_usage.md
    └── ...
```

## 🧪 Testing

- Added comprehensive test cases for web_searcher module
- Improved test coverage for parser utilities
- Validation of MicroAgent execution flow

## 🙏 Acknowledgments

Special thanks to all contributors who helped design and implement the dual-layer architecture!

## 📅 What's Next

Future releases will focus on:
- Enhanced multi-agent collaboration patterns
- More built-in skills
- Performance optimizations
- Additional backend integrations
- Enhanced UI for agent monitoring

---

**Full Changelog**: https://github.com/webdkt/agentmatrix/compare/v0.1.4...v0.1.5

**Upgrade Guide**: See "Migration Guide" section above

**Documentation**: https://github.com/webdkt/agentmatrix/tree/main/docs
