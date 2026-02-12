"!!! 过时待删除或者重做 !!!"
# Think-With-Retry Pattern

## Overview

### The Challenge: Natural Language vs. Structured Data

When working with LLMs, we face a fundamental tension: **we need to extract structured information from LLM outputs, but we want the LLM to focus on reasoning, not format compliance.**

If we impose rigid formatting constraints (strict JSON schemas, precise template structures), the LLM expends cognitive capacity on format adherence rather than problem-solving—essentially a **"cognition tax"** that reduces reasoning quality. This is especially problematic for complex tasks requiring deep thinking.

If we use no formatting at all, we get natural, flowing responses but cannot reliably extract the data we need for programmatic execution.

Even when we specify moderate formatting guidelines, LLMs occasionally deviate—missing sections, reordering content, or introducing unexpected variations. These "edge cases" are inevitable when working with probabilistic language models.

### The Solution: Think-With-Retry Pattern

The **Think-With-Retry** pattern resolves this tension by providing a **loose but robust** mechanism that bridges uncertain natural language output and deterministic structured extraction, while minimizing cognitive overhead on format maintenance.

**How it works conceptually:**

1. **Request with Soft Format Guidelines**: Ask the LLM to provide information with gentle structural hints (e.g., "Please organize your response into these sections: [Plan], [Timeline], [Budget]"). The LLM focuses primarily on content quality.

2. **Parse with Validation**: Attempt to extract structured data using a parser that validates the output. The parser checks for required elements and returns either:
   - **Success**: Extracted structured data
   - **Error**: Specific feedback about what's missing or malformed

3. **Intelligent Retry**: If parsing fails, the pattern automatically feeds the error feedback back to the LLM in a conversational manner: *"Your previous response was helpful, but it's missing the [Timeline] section. Could you add that?"* The LLM then corrects its output naturally, without rigid constraint enforcement.

4. **Loop Until Success**: Repeat steps 2-3 until valid structured data is extracted or maximum retries are reached.

**Key Design Philosophy:**

- **Loose Format Requirements**: We use natural section markers like `[Research Plan]` or `=====` rather than strict JSON schemas. This feels natural to LLMs and minimizes format friction.
- **Specific Feedback**: When parsing fails, the parser provides precise, actionable feedback (e.g., *"Missing section: [Timeline]"*). The LLM understands and corrects naturally.
- **Conversation Flow**: Retries are conversational—append the LLM's previous output and the error message to the conversation history, then ask for a revision. This mirrors human collaboration.
- **Graceful Degradation**: If the LLM consistently fails to provide valid output after several attempts, the pattern raises an exception rather than proceeding with bad data.

**Why This Works:**

- **Preserves Cognitive Capacity**: LLMs focus on reasoning, not rigid format compliance
- **Handles Edge Cases**: Automatic retry with feedback handles the inevitable deviations
- **Natural Interaction**: Conversational retries align with how LLMs are trained to interact
- **Deterministic Extraction**: Despite the loose input format, the output is always validated and structured
- **Minimal Prompt Overhead**: No need for lengthy format instructions or complex JSON schemas

The pattern transforms the inherent uncertainty of LLM natural language output into reliable, structured data through a lightweight, conversational feedback loop—essentially treating the LLM as an intelligent collaborator who occasionally needs clarification rather than a rigid template-filling system.

## LLM Client Encapsulation

**Location**: `src/agentmatrix/backends/llm_client.py`

The `LLMClient` class provides a unified interface for interacting with various LLM providers (OpenAI, Gemini, etc.).

### Core Features

```python
class LLMClient(AutoLoggerMixin):
    def __init__(self, url: str, api_key: str, model_name: str):
        self.url = url
        self.api_key = api_key
        self.model_name = model_name

    async def think(self, messages: List[Dict]) -> Dict[str, str]:
        """
        Call LLM and return response with reasoning and reply

        Returns:
            {
                "reasoning": "Chain of thought (if available)",
                "reply": "Main response content"
            }
        """
```

### Async Streaming Support

The client supports async streaming responses for both OpenAI and Gemini APIs.

## Think-With-Retry Pattern

**Location**: `src/agentmatrix/backends/llm_client.py` (lines 33-101)

The `think_with_retry()` method implements a generic micro-agent that loops until LLM output is successfully parsed.

### Core Mechanism

```python
async def think_with_retry(
    self,
    initial_messages: Union[str, List[Dict]],
    parser: callable,          # Parser function
    max_retries: int = 3,
    **parser_kwargs
) -> any:
    """
    Generic micro-agent that loops until LLM output is successfully parsed

    Args:
        initial_messages: Initial user message (string or message list)
        parser: Parser function to extract structured output
        max_retries: Maximum number of retry attempts
        **parser_kwargs: Additional arguments for parser

    Returns:
        The value of parser's "content" field (type depends on parser)
        - If parser returns single value: returns that value
        - If parser returns multi-section dict: returns dict
        - If no content field: returns empty dict {}

    Raises:
        ValueError: If max retries exceeded without success
    """
    # 1. Prepare messages
    if isinstance(initial_messages, str):
        messages = [{"role": "user", "content": initial_messages}]
    else:
        messages = initial_messages

    # 2. Retry loop
    for attempt in range(max_retries):
        # Call LLM
        response = await self.think(messages=messages)
        raw_reply = response['reply']

        # Parse with provided parser
        parsed_result = parser(raw_reply, **parser_kwargs)

        # Check result
        if parsed_result.get("status") == "success":
            # Success - return "content" field
            if "content" in parsed_result:
                return parsed_result["content"]
            else:
                return {}

        elif parsed_result.get("status") == "error":
            # Failure - append feedback and retry
            feedback = parsed_result.get("feedback")
            messages.append({"role": "assistant", "content": raw_reply})
            messages.append({"role": "user", "content": feedback})
            # Continue loop

    # Max retries exceeded
    raise ValueError("LLM failed to produce a valid response after all retries.")
```

### Key Points

#### 1. Parser Return Format

All parsers must follow a unified format:

```python
{
    "status": "success" | "error",
    "content": ...,      # On success: extracted content
    "feedback": str      # On failure: error feedback
}
```

**Success Examples**:
```python
# Return single value
{
    "status": "success",
    "content": "This is extracted text content"
}

# Return multiple sections (dict)
{
    "status": "success",
    "content": {
        "[Research Plan]": "Plan content...",
        "[Chapter Outline]": "Outline content..."
    }
}

# Return list
{
    "status": "success",
    "content": ["item1", "item2", "item3"]
}
```

**Error Examples**:
```python
{
    "status": "error",
    "feedback": "Missing required section: [Research Plan]. Please include this section."
}
```

#### 2. think_with_retry Return Value

`think_with_retry` **only returns** the parser's `"content"` field, not the entire dict:

```python
# If parser returns {"status": "success", "content": "text"}
# think_with_retry returns: "text"

# If parser returns {"status": "success", "content": {"key": "value"}}
# think_with_retry returns: {"key": "value"}

# If parser returns {"status": "success", "content": [...]}
# think_with_retry returns: [...]
```

This design makes calling code cleaner—no need to access `["content"]` every time.

#### 3. Retry Flow

```
┌─────────────────────────────────────────────┐
│  1. Call LLM (messages)                     │
└─────────────────┬───────────────────────────┘
                  │
                  ▼
        ┌─────────────────────┐
        │  2. Parser parse   │
        │     parser(raw_reply)│
        └─────────┬───────────┘
                  │
                  ▼
        ┌─────────────────────┐
        │  status == "success"?│
        └─────────┬───────────┘
             │    │
      Yes    │    │   No
             ▼    │
    ┌────────────┐ │
    │ Return     │ │
    │ content    │ │
    └────────────┘ │
                  │
                  ▼
        ┌─────────────────────┐
        │  3. Append to messages│
        │     - assistant: raw_reply
        │     - user: feedback │
        └─────────┬───────────┘
                  │
                  ▼
        ┌─────────────────────┐
        │  4. Retry LLM call  │
        └─────────┬───────────┘
                  │
                  └──────► Back to step 1
```

### Usage Examples

#### Example 1: Extract Single Value

```python
# Define parser
def extract_plan(raw_reply: str) -> dict:
    if "[Research Plan]" not in raw_reply:
        return {
            "status": "error",
            "feedback": "Missing [Research Plan] section. Please include it."
        }
    # Extract content
    content = raw_reply.split("[Research Plan]")[1].strip()
    return {
        "status": "success",
        "content": content  # Note: use "content" field
    }

# Use think_with_retry
result = await llm_client.think_with_retry(
    initial_messages="Create a research plan for AI safety",
    parser=extract_plan,
    max_retries=3
)

# result is the extracted plan text (string)
# Because parser's content is string, think_with_retry returns string directly
print(result)  # "1. Literature review\n2. Experiment design..."
```

#### Example 2: Extract Multiple Sections

```python
from parser_utils import multi_section_parser

# Use multi_section_parser
result = await llm_client.think_with_retry(
    initial_messages="""
    Please generate the following:
    1. [Research Plan] - Research steps
    2. [Chapter Outline] - Report chapters
    """,
    parser=multi_section_parser,  # Direct function reference
    section_headers=['[Research Plan]', '[Chapter Outline]'],
    match_mode="ALL",
    max_retries=3
)

# result is a dict: {"[Research Plan]": "...", "[Chapter Outline]": "..."}
# Because multi_section_parser's content is dict
print(result["[Research Plan]"])   # Access research plan
print(result["[Chapter Outline]"])  # Access chapter outline
```

#### Example 3: Using in deep_researcher

```python
# In update_blueprint action
generate_prompt = f"""
{ctx['researcher_persona']}

Research Topic: {ctx['research_title']}
Research Purpose: {ctx['research_purpose']}

Current research approach:
{current_blueprint}

Modification feedback:
{modification_feedback}

Please generate updated research approach based on feedback.
Use [Formal Draft] as separator.
"""

result = await self.brain.think_with_retry(
    generate_prompt,
    multi_section_parser,
    section_headers=["[Formal Draft]"],
    match_mode="ALL"
)

# result is: {"[Formal Draft]": "Updated content..."}
# Directly access dict to get content
new_blueprint = result["[Formal Draft]"].strip()
```

## Parser Design

### Standard Parser Contract

```python
def parser(
    raw_reply: str,
    **kwargs  # Parser-specific arguments
) -> dict:
    """
    Parse LLM output

    Args:
        raw_reply: Raw text returned by LLM
        **kwargs: Parser-specific parameters

    Returns:
        {
            "status": "success" | "error",
            "content": ...,      # On success: extracted content (any type)
            "feedback": str      # On failure: error feedback
        }
    """
```

### Error Reporting Best Practices

```python
# Bad example - not specific enough
return {
    "status": "error",
    "feedback": "Parse failed"  # Too vague
}

# Good example - specific and actionable
return {
    "status": "error",
    "feedback": "Missing required section: [Research Plan]. "
                "Please format your response with this section header."
}
```

### Parser Design Principles

1. **Be Specific**: Tell LLM exactly what's wrong
2. **Provide Examples**: Show expected format in feedback
3. **Check Requirements**: Validate all required fields
4. **Handle Edge Cases**: Empty output, malformed content, etc.
5. **Use "content" Field**: Always use "content" to return extracted content

## Multi-Section Parser (multi_section_parser)

**Location**: `src/agentmatrix/skills/parser_utils.py` (lines 10-186)

`multi_section_parser()` is a powerful generic parser for extracting multiple sections from LLM output.

### Function Signature

```python
def multi_section_parser(
    raw_reply: str,
    section_headers: List[str] = None,
    regex_mode: bool = False,
    match_mode: str = "ALL"  # "ALL" or "ANY"
) -> dict:
    """
    Multi-section text parser

    Returns:
        {
            "status": "success" | "error",
            "content": {...}  (multi-section mode) or "..." (single-section mode),
            "feedback": str   (on failure)
        }
    """
```

### Two Operation Modes

#### Mode 1: Multi-Section Parsing

When `section_headers` is provided, extract multiple sections:

```python
text = """
[Research Plan]
1. Literature review on AI safety
2. Interview experts
3. Conduct experiments

[Chapter Outline]
# Introduction
# Background
# Methodology
"""

result = multi_section_parser(
    text,
    section_headers=['[Research Plan]', '[Chapter Outline]'],
    match_mode="ALL"  # All sections must be present
)

# parser returns:
# {
#     "status": "success",
#     "content": {
#         "[Research Plan]": "1. Literature review on AI safety\n2. Interview experts\n3. Conduct experiments",
#         "[Chapter Outline]": "# Introduction\n# Background\n# Methodology"
#     }
# }

# think_with_retry returns content field (dict):
sections = await brain.think_with_retry(
    "Generate research plan and chapter outline",
    multi_section_parser,
    section_headers=['[Research Plan]', '[Chapter Outline]'],
    match_mode="ALL"
)

# sections is a dict:
print(sections["[Research Plan]"])   # Access research plan
print(sections["[Chapter Outline]"])  # Access chapter outline
```

**match_mode parameter**:

- `"ALL"` (default): All specified section_headers must exist
- `"ANY"`: At least one header must exist

**Error Example**:

```python
# Missing [Chapter Outline]
result = multi_section_parser(
    text,
    section_headers=['[Research Plan]', '[Chapter Outline]'],
    match_mode="ALL"
)

# Returns:
# {
#     "status": "error",
#     "feedback": "ALL mode: Missing the following section headers: ['[Chapter Outline]']"
# }
```

#### Mode 2: Single-Section Parsing

When `section_headers` is `None`, use separator mode (backward compatible):

```python
text = """
Some introductory text...
===========
Content to extract
More content...
===========
"""

result = multi_section_parser(text)

# parser returns:
# {
#     "status": "success",
#     "content": "Content to extract\nMore content..."
# }
```

Finds the last `"====="` separator and extracts content after it.

### Performance Optimizations

`multi_section_parser` includes several efficiency optimizations:

**1. Fast Pre-Check** (lines 90-94):

```python
if match_mode == "ALL" and not regex_mode:
    # Use in operation for quick check if all headers exist
    missing = [h for h in section_headers if h not in raw_reply]
    if missing:
        return {"status": "error",
                "feedback": f"ALL mode: Missing the following section headers: {missing}"}
```

**2. Reverse Iteration + Early Termination** (lines 101-136):

```python
# Iterate backwards from end of text
for i in range(len(lines) - 1, -1, -1):
    line = lines[i].strip()

    if is_header and line not in found:
        # Extract section content
        sections[line] = ...
        found.add(line)

        # Early termination: found all needed headers
        if found == needed:
            break
```

**Advantages**:
- Content typically near end, reverse is faster
- Stop immediately when all sections found
- Avoid unnecessary traversal

## Key Points (Must Read)

### Function Signature

```python
async def think_with_retry(
    self,
    initial_messages: Union[str, List[Dict]],  # prompt
    parser: callable,                          # parser function
    max_retries: int = 3,
    **parser_kwargs                            # parser's extra arguments
) -> any:
```

### Correct Usage

```python
# ✅ Correct: parser's extra arguments passed via **parser_kwargs
result = await brain.think_with_retry(
    prompt,                      # positional argument
    multi_section_parser,        # positional argument
    section_headers=["[Formal Draft]"],  # keyword argument → **parser_kwargs
    match_mode="ALL"             # keyword argument → **parser_kwargs
)

# Equivalent to calling:
# multi_section_parser(raw_reply, section_headers=[...], match_mode="ALL")

# result is the value of parser's "content" field
```

### Incorrect Usage

```python
# ❌ Wrong: wrap with lambda
result = await brain.think_with_retry(
    prompt,
    lambda reply: parser(reply, arg=value)
)

# ❌ Wrong: construct argument dict yourself
result = await brain.think_with_retry(
    prompt,
    parser,
    {"section_headers": ["[A]"]}
)
```

### Prompt Design: Must Include Examples

```python
# ✅ Correct: section header + example
prompt = """
{context}

Please generate a new chapter outline.

Example format:
[Thought Process]
...your understanding and thinking...

[Formal Draft]
# Chapter 1 Introduction
# Chapter 2 Methodology

Please follow the format above.
"""

# ❌ Wrong: only constraints, no example
prompt = """
Please generate chapter outline, only output chapters, nothing else.
"""
```

**Why need examples?**
- LLM will mimic example format
- Constraints like "only output xxx" are hard to follow
- Examples are the most reliable format guarantee

### Parser Design: Combine and Validate

```python
# ✅ Correct: multi_section_parser + additional validation
def my_parser(raw_reply: str) -> dict:
    # 1. Extract with multi_section_parser first
    result = multi_section_parser(
        raw_reply,
        section_headers=["[Formal Draft]"],
        match_mode="ALL"
    )

    if result["status"] == "error":
        return result

    # 2. Extract and validate
    content = result["content"]["[Formal Draft]"]

    # Additional validation
    if not validate(content):
        return {
            "status": "error",
            "feedback": "Validation failed: ..."
        }

    return {
        "status": "success",
        "content": processed_data
    }
```

### Core Principles (3 Rules)

1. **Pass function directly**: `think_with_retry(prompt, parser, arg=value)`
2. **Must provide examples**: Prompt must have format examples for LLM to mimic
3. **Combine validation**: `multi_section_parser` + additional validation

Remember these 3 rules, you won't go wrong.

## Common Usage Patterns

### Pattern 1: Pass Parser Function Directly

```python
# ✅ Correct: Pass function reference directly
result = await brain.think_with_retry(
    prompt,
    multi_section_parser,  # Direct pass
    section_headers=["[Section1]", "[Section2]"],
    match_mode="ALL"
)
```

### Pattern 2: Pass parser_kwargs

```python
# ✅ Correct: Parser's extra arguments passed via **parser_kwargs
result = await brain.think_with_retry(
    prompt,
    multi_section_parser,
    section_headers=["[Research Plan]"],
    match_mode="ALL"  # These args get passed to multi_section_parser
)
```

### Pattern 3: Use Custom Parser

```python
# Custom parser
def my_parser(raw_reply: str, **kwargs) -> dict:
    # Parsing logic
    if validate(raw_reply):
        return {
            "status": "success",
            "content": extract_data(raw_reply)
        }
    else:
        return {
            "status": "error",
            "feedback": "Format error, please..."
        }

# Use it
result = await brain.think_with_retry(
    prompt,
    my_parser,  # Custom parser
    max_retries=3
)
```

## Common Mistakes

### Mistake 1: Using Lambda to Wrap Parser

```python
# ❌ Wrong: Don't wrap with lambda
result = await brain.think_with_retry(
    prompt,
    lambda reply: multi_section_parser(reply, ...),  # Wrong!
    ...
)

# ✅ Correct: Pass parser directly
result = await brain.think_with_retry(
    prompt,
    multi_section_parser,  # Correct
    section_headers=["[Section1]"],
    match_mode="ALL"
)
```

### Mistake 2: Wrong match_mode Value

```python
# ❌ Wrong: No such value as "EXACT"
result = await brain.think_with_retry(
    prompt,
    multi_section_parser,
    match_mode="EXACT"  # Wrong!
)

# ✅ Correct: Only "ALL" or "ANY"
result = await brain.think_with_retry(
    prompt,
    multi_section_parser,
    match_mode="ALL"  # or "ANY"
)
```

### Mistake 3: Misunderstanding Return Value Format

```python
# ❌ Wrong: Don't access ["data"] or ["sections"]
result = await brain.think_with_retry(...)
content = result["data"]  # Wrong!

# ✅ Correct: result is the content field value
sections = await brain.think_with_retry(
    prompt,
    multi_section_parser,
    section_headers=["[A]", "[B]"],
    match_mode="ALL"
)
# sections is directly a dict: {"[A]": "...", "[B]": "..."}
print(sections["[A]"])  # Direct access
```

## Summary

### Core Concepts

1. **Parser Unified Contract**: All parsers return `{"status": "...", "content": ..., "feedback": "..."}`
2. **think_with_retry Returns content**: Directly returns parser's `"content"` field value
3. **Multi-Section Parsing**: Use `multi_section_parser` to extract multiple sections
4. **Conversational Retry**: Auto feedback + retry until success or max retries reached

### Component Responsibilities

| Component | Location | Responsibility |
|-----------|----------|----------------|
| LLMClient | backends/llm_client.py | LLM API wrapper + think_with_retry |
| multi_section_parser | skills/parser_utils.py | Multi-section parser |
| Custom parser | Various skill files | Task-specific parsing logic |

### Best Practices

1. **Pass Parser Directly**: Don't wrap with lambda
2. **Use "content" Field**: Parser returns use "content", not "data" or "sections"
3. **Provide Specific Feedback**: Give clear, actionable error messages when parser fails
4. **Set Reasonable max_retries**: Usually 2-3 is sufficient
5. **Leverage Existing Parser**: Prioritize `multi_section_parser` over reinventing

The Think-With-Retry pattern transforms LLM uncertainty into reliable structured output through conversational feedback loops, making it a core pattern for building robust LLM applications.
