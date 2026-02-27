# Think-With-Retry Pattern

**Document Version**: v0.2.0 | **Last Updated**: 2026-02-26 | **Status**: ✅ Implemented

## Overview

### Core Idea

Let LLM output naturally through **soft constraints**, then use parser to extract and **automatically retry** until output meets expectations.

### Why We Need It

Traditional approach requiring LLM to output strict JSON format has two problems:

1. **High error probability**: Complex structures are prone to errors
2. **Occupies attention**: Format constraints occupy LLM's "brainpower", leading to degraded output quality

**Think-With-Retry advantages**:
- ✅ LLM thinks in natural language, free from format constraints
- ✅ Parser responsible for parsing and validation
- ✅ Automatic retry mechanism, conversational error correction
- ✅ Doesn't pollute main conversation history

### Use Cases

**Suitable for Think-With-Retry**:
- Need structured output (plans, lists, fields, etc.)
- Output format is relatively fixed
- Can tolerate small retry cost

**Not suitable for**:
- Simple Q&A conversations
- No structured output needed
- Extremely latency-sensitive

## Core Concepts

### Soft Constraint Output

**Idea**: Let LLM output in natural way, use lightweight markers to distinguish content boundaries

**Recommended format**:

```markdown
[Research Plan]
1. Research AI safety technical solutions
2. Investigate existing implementations
3. Assess risks

[Timeline]
Week 1: Technical solutions
Week 2: Investigation
Week 3: Assessment
```

**Key points**:
- Use `[SECTION NAME]` or `====` to separate
- Provide **examples** for LLM to imitate
- Don't say "only output what", allow free expression

### Parser Contract

All parsers must follow unified format:

```python
{
    "status": "success" | "error",
    "content": ...,      # On success: extracted content
    "feedback": str      # On failure: error feedback
}
```

**Success examples**:

```python
# Return single value
{"status": "success", "content": "extracted text"}

# Return multiple sections (dict)
{"status": "success", "content": {"[Research Plan]": "...", "[Timeline]": "..."}}
```

**Failure examples**:

```python
{"status": "error", "feedback": "Missing required section: [Research Plan]"}
```

**Best practices**:
- Error messages should be specific and actionable
- Tell LLM **what's missing** and **how to fix**
- Don't just say "parsing failed"

### Automatic Retry Mechanism

**Flow**:

```
1. Call LLM
   ↓
2. Parser parses
   ↓
3. status == "success"?
    ├─ Yes → Return content
    └─ No  → Append feedback to messages → Retry LLM
                ↓
            At most max_retries times
```

**Key**:
- On failure, automatically append LLM's output and feedback to conversation history
- LLM sees "its own output + error hint", naturally corrects
- Entire process transparent to caller

## Usage

### Basic Usage

```python
from agentmatrix.backends.llm_client import LLMClient
from agentmatrix.skills.parser_utils import multi_section_parser

# Initialize client
llm_client = LLMClient(...)

# Call think_with_retry
result = await llm_client.think_with_retry(
    initial_messages="your prompt",
    parser=multi_section_parser,
    section_headers=["[Research Plan]", "[Timeline]"],
    match_mode="ALL",
    max_retries=3
)

# result is the content returned by parser
print(result["[Research Plan]"])
```

**Parameter explanation**:
- `initial_messages`: Initial prompt (can be string or message list)
- `parser`: Parser function (pass function reference directly, don't use lambda)
- `max_retries`: Maximum retry times (default 3)
- `**parser_kwargs`: Additional parameters passed to parser

### Complete Example

**Scenario**: Let LLM create project plan

```python
async def create_project_plan(topic: str) -> Dict:
    """Create project plan"""

    # 1. Design prompt (include examples)
    prompt = f"""
Please create a project plan for the following topic: {topic}

Please output in the following format (example):

[Research Plan]
1. First step
2. Second step
3. Third step

[Timeline]
- Week 1: ...
- Week 2: ...
- Week 3: ...

[Resource Requirements]
- Personnel: ...
- Equipment: ...
"""

    # 2. Call think_with_retry
    result = await llm_client.think_with_retry(
        initial_messages=prompt,
        parser=multi_section_parser,
        section_headers=["[Research Plan]", "[Timeline]", "[Resource Requirements]"],
        match_mode="ALL",  # All must exist
        max_retries=3
    )

    # 3. Use result
    # result = {
    #     "[Research Plan]": "1. ...\n2. ...",
    #     "[Timeline]": "- Week 1:...",
    #     "[Resource Requirements]": "- Personnel:..."
    # }

    return result

# Use
plan = await create_project_plan("AI Safety Research")
print(plan["[Research Plan]"])
```

### Advanced Usage

#### Usage 1: ANY mode (optional sections)

```python
result = await llm_client.think_with_retry(
    prompt="...",
    parser=multi_section_parser,
    section_headers=["[Plan A]", "[Plan B]", "[Plan C]"],
    match_mode="ANY",  # Return whatever exists, no error
    max_retries=3
)
# May return only {"[Plan A]": "...", "[Plan C]": "..."}
```

#### Usage 2: Single section mode

```python
result = await llm_client.think_with_retry(
    prompt="...",
    parser=multi_section_parser,
    # Don't pass section_headers, auto-find "====" separator
    max_retries=3
)
# Returns {"status": "success", "content": "content after separator"}
```

#### Usage 3: Custom Parser

```python
def my_custom_parser(raw_reply: str) -> dict:
    """Custom parser"""

    # First use multi_section_parser to extract
    sections = multi_section_parser(
        raw_reply,
        section_headers=["[Plan]", "[Checklist]"],
        match_mode="ALL"
    )

    if sections["status"] == "error":
        return sections

    # Then do additional validation and processing
    content = sections["content"]

    # Validate [Plan] has at least 3 items
    plan_items = [line for line in content["[Plan]"].split('\n') if line.strip()]
    if len(plan_items) < 3:
        return {
            "status": "error",
            "feedback": f"[Plan] needs at least 3 items, currently only {len(plan_items)}"
        }

    # Extract first item from [Checklist]
    first_item = content["[Checklist]"].split('\n')[0].strip()

    return {
        "status": "success",
        "content": {
            "plan": content["[Plan]"],
            "first_item": first_item
        }
    }

# Use
result = await llm_client.think_with_retry(
    prompt="...",
    parser=my_custom_parser,
    max_retries=3
)
```

## Parser Tools

### multi_section_parser

**Location**: `src/agentmatrix/skills/parser_utils.py`

Generic multi-section parser, supports two modes.

#### Mode 1: Multi-section parsing

```python
result = multi_section_parser(
    raw_reply,
    section_headers=['[Research Plan]', '[Timeline]'],
    match_mode="ALL"  # or "ANY"
)
```

**match_mode parameter**:
- `"ALL"` (default): All specified headers must exist
- `"ANY"`: Just match what's available, return however many found

#### Mode 2: Single-section parsing

```python
result = multi_section_parser(raw_reply)
```

Auto-find `=====` separator, extract content after last separator.

#### Advanced parameters

```python
result = multi_section_parser(
    raw_reply,
    section_headers=['[Research Plan]', '[Timeline]'],
    match_mode="ALL",
    regex_mode=False,      # Whether to use regex matching (default False)
    return_list=False,     # Whether to return line list (default False)
    allow_empty=False      # Whether to allow empty content (default False)
)
```

**Parameter explanation**:
- `regex_mode`:
  - `False` (default): Exact match, line must exactly equal header
  - `True`: Regular expression match
- `return_list`:
  - `False` (default): Return string
  - `True`: Return line list
- `allow_empty`:
  - `False` (default): Empty content returns error
  - `True`: Allow empty content

### Custom Parser

**Template**:

```python
def my_parser(raw_reply: str, **kwargs) -> dict:
    """
    Custom parser

    Args:
        raw_reply: LLM's raw output
        **kwargs: Additional parameters (passed from think_with_retry)

    Returns:
        {
            "status": "success" | "error",
            "content": ...,  # On success
            "feedback": str  # On failure
        }
    """

    # 1. Try to parse
    try:
        # Parsing logic
        content = parse_something(raw_reply)

        # 2. Validate
        if not validate(content):
            return {
                "status": "error",
                "feedback": "Validation failed: xxx"
            }

        # 3. Success
        return {
            "status": "success",
            "content": content
        }

    except Exception as e:
        return {
            "status": "error",
            "feedback": f"Parsing error: {str(e)}"
        }
```

**Best practices**:
1. **Combine usage**: First use `multi_section_parser` to extract, then custom validate
2. **Specific feedback**: Error messages should tell LLM exactly what's missing and how to fix
3. **Error handling**: Wrap parsing logic with try-except

## Implementation Mechanism

### think_with_retry Flow

**Code location**: `src/agentmatrix/backends/llm_client.py`

```python
async def think_with_retry(
    self,
    initial_messages: Union[str, List[str]],
    parser: callable,
    max_retries: int = 3,
    debug: bool = True,
    **parser_kwargs
) -> any:
    """
    Loop calling LLM until output successfully parsed

    Returns:
        content field returned by parser (not entire dict)
    """

    # 1. Normalize messages
    if isinstance(initial_messages, str):
        messages = [{"role": "user", "content": initial_messages}]
    else:
        messages = initial_messages

    # 2. Retry loop
    for attempt in range(max_retries):
        # 2.1 Call LLM
        response = await self.think(messages=messages)
        raw_reply = response['reply']

        # 2.2 Parser parses
        parsed_result = parser(raw_reply, **parser_kwargs)

        # 2.3 Check result
        if parsed_result["status"] == "success":
            # Success: return content
            return parsed_result["content"]
        else:
            # Failure: append feedback to messages, retry
            feedback = parsed_result["feedback"]
            messages.append({"role": "assistant", "content": raw_reply})
            messages.append({"role": "user", "content": f"Your response is helpful, but {feedback}"})

    # 3. Exceeded maximum retries
    raise ValueError(f"Unable to get valid output within {max_retries} retries")
```

### Return Value Convention

**Important**: `think_with_retry` only returns parser's `"content"` field, not entire dict.

```python
# If parser returns {"status": "success", "content": "text"}
# think_with_retry returns: "text"

# If parser returns {"status": "success", "content": {"key": "value"}}
# think_with_retry returns: {"key": "value"}
```

This makes calling code cleaner, no need to access `["content"]` every time.

### Error Handling

#### Retry Failure

After exceeding `max_retries`, raises exception:

```python
try:
    result = await llm_client.think_with_retry(
        prompt="...",
        parser=multi_section_parser,
        max_retries=3
    )
except ValueError as e:
    print(f"Parsing failed: {e}")
    # Handle failure
```

#### Parser Exception

Parser internally should catch all exceptions, return `{"status": "error"}`:

```python
def my_parser(raw_reply: str) -> dict:
    try:
        # Parsing logic
        return {"status": "success", "content": ...}
    except Exception as e:
        return {"status": "error", "feedback": str(e)}
```

### Performance Optimization

#### Reduce LLM calls

**Method 1**: Optimize prompt, reduce error probability

```python
# ❌ Bad: Missing examples
prompt = "Please output [Plan] and [Timeline] sections"

# ✅ Good: Complete examples
prompt = """
Please output project plan, format as follows:

[Plan]
1. First step
2. Second step

[Timeline]
Week 1: ...
Week 2: ...
"""
```

**Method 2**: Lower `match_mode` strictness

```python
# ❌ Strict: Must match all, easy to retry
match_mode="ALL"

# ✅ Relaxed: Partial match OK
match_mode="ANY"
```

#### Debug Mode

```python
# Enable debug to see detailed logs
result = await llm_client.think_with_retry(
    prompt="...",
    parser=multi_section_parser,
    debug=True  # Output LLM input/output
)
```

**Debug output example**:
```
=== think_with_retry DEBUG START ===
Initial messages (1 messages):
  [0] user: Please create plan...

LLM Response (raw_reply):
  [Plan]
  1. ...
  [Timeline]
  Week 1: ...

Parser result:
  {'status': 'success', 'content': {...}}
```

## Best Practices

### Prompt Design

#### ✅ Good Prompt

**Characteristics**:
1. Has complete format examples
2. Examples match actual requirements
3. Use lightweight separators
4. Clear but not overly constrained

```python
prompt = """
Please create a project plan for the following topic: {topic}

Output format (please strictly follow this format):

[Research Plan]
1. First step: description
2. Second step: description
3. Third step: description

[Timeline]
- Week 1: Task
- Week 2: Task
- Week 3: Task

[Resource Requirements]
- Personnel: Number
- Equipment: List
"""
```

#### ❌ Bad Prompt

```python
# ❌ Missing examples
prompt = "Please output research plan, timeline and resource requirements"

# ❌ Overly constrained
prompt = "Only output the following format, nothing else: [Research Plan]..."

# ❌ Using complex format (JSON)
prompt = "Please output JSON format: {'plan': [...], 'time': {...}}"
```

### Parser Design

#### Principles

1. **Extract first, validate later**: First use `multi_section_parser` to extract, then validate
2. **Specific feedback**: Error messages should be precise
3. **Error handling**: Catch all exceptions

#### Example

```python
def project_plan_parser(raw_reply: str) -> dict:
    """Project plan parser"""

    # 1. First extract sections
    sections = multi_section_parser(
        raw_reply,
        section_headers=["[Research Plan]", "[Timeline]", "[Resource Requirements]"],
        match_mode="ALL"
    )

    if sections["status"] == "error":
        return sections

    content = sections["content"]

    # 2. Validate [Research Plan]
    plan_text = content["[Research Plan]"]
    plan_items = [line for line in plan_text.split('\n') if line.strip() if line.strip()[0].isdigit()]

    if len(plan_items) < 3:
        return {
            "status": "error",
            "feedback": f"[Research Plan] needs at least 3 items, currently only {len(plan_items)}, please complete the plan"
        }

    # 3. Validate [Timeline]
    time_text = content["[Timeline]"]
    if "Week 1" not in time_text or "Week 2" not in time_text:
        return {
            "status": "error",
            "feedback": "[Timeline] must include Week 1 and Week 2 tasks, please add"
        }

    # 4. Success, return structured data
    return {
        "status": "success",
        "content": {
            "plan": plan_items,
            "timeline": time_text,
            "resources": content["[Resource Requirements]"]
        }
    }
```

### Common Errors

#### Error 1: Wrapping parser with lambda

```python
# ❌ Wrong
result = await llm_client.think_with_retry(
    prompt="...",
    parser=lambda x: multi_section_parser(x, section_headers=["[A]"]),
    max_retries=3
)
```

**Problem**: lambda affects error logs, hard to debug

**Correct approach**: Directly pass function reference, use `**parser_kwargs` for parameters

```python
# ✅ Correct
result = await llm_client.think_with_retry(
    prompt="...",
    parser=multi_section_parser,
    section_headers=["[A]"],
    max_retries=3
)
```

#### Error 2: Prompt missing examples

```python
# ❌ Only constraints, no examples
prompt = "Please output [Research Plan] section"
```

**Correct**: Provide complete examples

```python
# ✅ Has examples
prompt = """
Please output research plan, format as follows:

[Research Plan]
1. First step
2. Second step
"""
```

#### Error 3: Parser feedback not specific

```python
# ❌ Vague error message
return {"status": "error", "feedback": "Parsing failed"}
```

**Correct**: Tell LLM specifically what's missing

```python
# ✅ Specific error message
return {
    "status": "error",
    "feedback": "Missing [Timeline] section, please add Week 1 and Week 2 task arrangements"
}
```

#### Error 4: Overusing retries

```python
# ❌ max_retries too large, wastes cost
max_retries=10
```

**Recommendations**:
- Simple tasks: `max_retries=2`
- Complex tasks: `max_retries=3`
- Very complex: `max_retries=5`

### Practical Tips

#### Tip 1: Combine multiple parsers

```python
def combined_parser(raw_reply: str) -> dict:
    """First extract sections, then do business logic validation"""

    # 1. Extract
    sections = multi_section_parser(raw_reply, ...)
    if sections["status"] == "error":
        return sections

    # 2. Business logic
    content = sections["content"]

    # 3. Extract fields
    items = extract_items(content["[Checklist]"])
    if not items:
        return {"status": "error", "feedback": "[Checklist] cannot be empty"}

    # 4. Calculate derived fields
    total = calculate_total(items)

    # 5. Return structured data
    return {
        "status": "success",
        "content": {
            "items": items,
            "total": total
        }
    }
```

#### Tip 2: Get structured data in stages

```python
# Step 1: Get outline
outline = await llm_client.think_with_retry(
    prompt="Create outline...",
    parser=multi_section_parser,
    section_headers=["[Outline]"],
    max_retries=2
)

# Step 2: Get detailed content based on outline
detail = await llm_client.think_with_retry(
    prompt=f"Create detailed plan based on the following outline: {outline['[Outline]']}",
    parser=multi_section_parser,
    section_headers=["[Steps]", "[Timeline]"],
    max_retries=2
)
```

#### Tip 3: Use in Action

```python
@register_action(description="Create project plan")
async def create_project_plan(self, topic: str) -> str:
    """Use think_with_retry in action"""

    plan = await self.brain.think_with_retry(
        initial_messages=f"Create project plan for {topic}...",
        parser=multi_section_parser,
        section_headers=["[Research Plan]", "[Timeline]"],
        max_retries=3
    )

    # plan is dict: {"[Research Plan]": "...", "[Timeline]": "..."}

    return f"Plan created:\n{plan['[Research Plan]']}\n{plan['[Timeline]']}"
```

## Summary

### Core Points

1. **Pass function directly**: `think_with_retry(prompt, parser, arg=value)`, don't use lambda
2. **Prompt must include examples**: Provide format examples for LLM to imitate
3. **Combine validation**: `multi_section_parser` + additional validation (extract first, then validate)

### Usage Flow

```
1. Design prompt (include format examples)
   ↓
2. Choose or write parser
   ↓
3. Call think_with_retry
   ↓
4. Handle return value (parser's content)
```

### API Reference

```python
await llm_client.think_with_retry(
    initial_messages: Union[str, List[str]],  # prompt
    parser: callable,                          # parser function
    max_retries: int = 3,                     # maximum retry times
    debug: bool = True,                       # whether to output debug info
    **parser_kwargs                           # parameters passed to parser
) -> Any
```

### See Also

- **Implementation source**: `src/agentmatrix/backends/llm_client.py:think_with_retry()`
- **Generic parser**: `src/agentmatrix/skills/parser_utils.py:multi_section_parser()`
- **Usage examples**: `src/agentmatrix/skills/deep_researcher.py`
