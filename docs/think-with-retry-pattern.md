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

The client supports async streaming responses for both OpenAI and Gemini APIs:

**OpenAI Streaming** (lines 268-335):

```python
async def _stream_openai_response(self, messages, model):
    async for chunk in openai_completion.stream(...):
        if chunk.choices[0].delta.content:
            yield chunk.choices[0].delta.content
```

**Gemini Streaming** (lines 170-266):

```python
async def _stream_gemini_response(self, messages, model):
    async for chunk in await gemini_model.generate_content_async(...):
        yield chunk.text
```

### Reasoning Content Extraction

For models that support chain-of-thought (like o1), the client extracts reasoning content:

```python
# Extract reasoning from o1 models
if hasattr(response, 'reasoning') and response.reasoning:
    reasoning = response.reasoning
else:
    reasoning = None

return {
    "reasoning": reasoning,
    "reply": content
}
```

## Think-With-Retry Pattern

**Location**: `src/agentmatrix/backends/llm_client.py` (lines 33-105)

The `think_with_retry()` method implements a generic micro-agent that loops until LLM output is successfully parsed.

### Core Mechanism

```python
async def think_with_retry(
    self,
    initial_messages: Union[str, List[str]],
    parser: callable,          # Parser function
    max_retries: int = 3,
    **parser_kwargs
) -> any:
    """
    Generic micro-agent that loops until LLM output is successfully parsed

    Args:
        initial_messages: Initial user messages
        parser: Parser function to extract structured output
        max_retries: Maximum number of retry attempts
        **parser_kwargs: Additional arguments for parser

    Returns:
        Parsed data (from parser["data"] or parser["sections"])
    """
    messages = self._prepare_messages(initial_messages)

    for attempt in range(max_retries):
        # 1. Call LLM
        response = await self.think(messages=messages)
        raw_reply = response['reply']

        # 2. Parse with provided parser
        parsed_result = parser(raw_reply, **parser_kwargs)

        # 3. Check result
        if parsed_result.get("status") == "success":
            # Success - return data
            return (
                parsed_result.get("data") or
                parsed_result.get("sections")
            )

        elif parsed_result.get("status") == "error":
            # 4. Append feedback and retry
            feedback = parsed_result.get("feedback")
            messages.append({
                "role": "assistant",
                "content": raw_reply
            })
            messages.append({
                "role": "user",
                "content": feedback
            })
            # Continue loop with feedback

    # Max retries exceeded
    raise Exception(f"Max retries ({max_retries}) exceeded")
```

### Parser Contract

Parsers must follow this interface:

```python
def parser(raw_reply: str, **kwargs) -> dict:
    """
    Parse LLM output and return status dict

    Returns:
        {
            "status": "success" | "error",
            "data": ...,              # Optional: single parsed data
            "sections": {...},        # Optional: multiple sections
            "feedback": str           # Required if status=error
        }
    """
```

**Success Response**:

```python
{
    "status": "success",
    "data": "Parsed result"        # For single value
    # OR
    "sections": {                  # For multi-section
        "Section 1": "Content 1",
        "Section 2": "Content 2"
    }
}
```

**Error Response**:

```python
{
    "status": "error",
    "feedback": "Missing required field: [行动计划]. Please include this section."
}
```

### Retry Flow

```
┌─────────────────────────────────────────────┐
│  1. Call LLM with messages                  │
└─────────────────┬───────────────────────────┘
                  │
                  ▼
        ┌─────────────────────┐
        │  2. Parse output    │
        └─────────┬───────────┘
                  │
                  ▼
        ┌─────────────────────┐
        │  Status = success?  │
        └─────────┬───────────┘
             │    │
      Yes    │    │   No
             ▼    │
    ┌────────────┐ │
    │ Return     │ │
    │ data       │ │
    └────────────┘ │
                  │
                  ▼
        ┌─────────────────────┐
        │  3. Append feedback │
        │     to messages     │
        └─────────┬───────────┘
                  │
                  ▼
        ┌─────────────────────┐
        │  4. Retry LLM call  │
        └─────────┬───────────┘
                  │
                  └──────► Loop back to step 1
```

### Usage Example

```python
# Define parser
def extract_plan(raw_reply: str) -> dict:
    if "[研究计划]" not in raw_reply:
        return {
            "status": "error",
            "feedback": "Missing [研究计划] section. Please include it."
        }
    # Extract content
    content = raw_reply.split("[研究计划]")[1].strip()
    return {
        "status": "success",
        "data": content
    }

# Use think_with_retry
result = await llm_client.think_with_retry(
    initial_messages="Create a research plan for AI safety",
    parser=extract_plan,
    max_retries=3
)

# result contains the parsed plan
```

## Parser Design

### Parser Signature

```python
def parser(
    raw_reply: str,
    **kwargs  # Parser-specific arguments
) -> dict:
    # Implementation
    pass
```

### Error Reporting

Parsers should provide specific, actionable feedback:

```python
# Bad example
return {
    "status": "error",
    "feedback": "Parse failed"  # Not helpful
}

# Good example
return {
    "status": "error",
    "feedback": "Missing required section: [研究计划]. "
                "Please format your response with this section header."
}
```

### Parser Best Practices

1. **Be Specific**: Tell LLM exactly what's wrong
2. **Provide Examples**: Show expected format in feedback
3. **Check Requirements**: Validate all required fields
4. **Handle Edge Cases**: Empty output, malformed content, etc.

## Multi-Section Parser

**Location**: `src/agentmatrix/skills/parser_utils.py` (lines 10-186)

The `multi_section_parser()` is a powerful utility for extracting multiple sections from LLM output.

### Function Signature

```python
def multi_section_parser(
    raw_reply: str,
    section_headers: List[str] = None,
    regex_mode: bool = False,
    match_mode: str = "ALL"  # or "ANY"
) -> dict
```

### Two Modes of Operation

#### 1. Multi-Section Mode

When `section_headers` is provided:

```python
text = """
[研究计划]
1. Literature review on AI safety
2. Interview experts
3. Conduct experiments

[章节大纲]
Chapter 1: Introduction
Chapter 2: Background
Chapter 3: Methodology
"""

result = multi_section_parser(
    text,
    section_headers=['[研究计划]', '[章节大纲]'],
    match_mode="ALL"  # All headers must be present
)

# Returns:
{
    "status": "success",
    "sections": {
        "[研究计划]": "1. Literature review on AI safety\n2. Interview experts\n3. Conduct experiments",
        "[章节大纲]": "Chapter 1: Introduction\nChapter 2: Background\nChapter 3: Methodology"
    }
}
```

**Match Modes**:
- `"ALL"`: All specified headers must be present (default)
- `"ANY"`: At least one header must be present

**Error Example**:

```python
# Missing [章节大纲]
result = multi_section_parser(
    text,
    section_headers=['[研究计划]', '[章节大纲]'],
    match_mode="ALL"
)

# Returns:
{
    "status": "error",
    "feedback": "Missing required sections: ['[章节大纲]']"
}
```

#### 2. Single-Section Mode

When `section_headers` is `None` (backward compatible):

```python
text = """
Some introductory text...
===========
Content to extract
More content...
===========

Footer text
"""

result = multi_section_parser(text)

# Returns:
{
    "status": "success",
    "data": "Content to extract\nMore content..."
}
```

Finds the last `"====="` divider and extracts content between it and the next divider.

### Performance Optimizations

The parser includes several optimizations for efficiency:

**1. Reverse Iteration** (lines 101-136):

```python
# Iterate backwards from end of text
for i in range(len(lines) - 1, -1, -1):
    line = lines[i]
    # Check for section headers
    # ...
```

Benefits:
- Finds content faster (typically near end)
- Enables early termination

**2. Early Termination** (line 132):

```python
if len(found_sections) == len(required_headers):
    break  # All sections found
```

Stops searching once all required sections are found.

**3. Fast Pre-Check** (lines 89-94):

```python
if match_mode == "ALL":
    # Quick check if all headers exist
    for header in section_headers:
        if header not in raw_reply:
            return {
                "status": "error",
                "feedback": f"Missing required section: {header}"
            }
```

Avoids expensive iteration if headers are missing.

### Implementation Details

```python
def multi_section_parser(
    raw_reply: str,
    section_headers: List[str] = None,
    regex_mode: bool = False,
    match_mode: str = "ALL"
) -> dict:
    # Single-section mode
    if section_headers is None:
        # Find last "=====" divider
        divider_count = raw_reply.count("=====")
        if divider_count < 2:
            return {"status": "error", "feedback": "No content divider found"}

        # Extract content between last two dividers
        parts = raw_reply.split("=====")
        content = parts[-2].strip()
        return {"status": "success", "data": content}

    # Multi-section mode
    if match_mode == "ALL":
        # Fast pre-check
        for header in section_headers:
            if header not in raw_reply:
                return {
                    "status": "error",
                    "feedback": f"Missing required section: {header}"
                }

    # Reverse iteration to extract sections
    lines = raw_reply.split('\n')
    found_sections = {}

    for i in range(len(lines) - 1, -1, -1):
        line = lines[i].strip()

        # Check if line is a section header
        if line in section_headers:
            # Extract content until next header
            content = []
            for j in range(i + 1, len(lines)):
                next_line = lines[j].strip()
                if next_line in section_headers:
                    break
                content.append(lines[j])

            found_sections[line] = '\n'.join(content).strip()

            # Early termination
            if match_mode == "ALL" and len(found_sections) == len(section_headers):
                break

    # Validate results
    if match_mode == "ALL" and len(found_sections) != len(section_headers):
        return {
            "status": "error",
            "feedback": f"Missing sections: {set(section_headers) - set(found_sections.keys())}"
        }

    if match_mode == "ANY" and len(found_sections) == 0:
        return {
            "status": "error",
            "feedback": "No sections found"
        }

    return {
        "status": "success",
        "sections": found_sections
    }
```

## Example: Search Results Parser

**Location**: `src/agentmatrix/skills/search_results_parser.py`

A practical example of a custom parser for extracting structured data from HTML search results.

### Data Structure

```python
@dataclass
class SearchResultItem:
    title: str       # Result title
    url: str         # Result URL
    snippet: str     # Result snippet
    site_info: str   # Site information
    link_id: str     # Unique link ID
```

### Parser Features

```python
def parse_search_results(html_content: str) -> dict:
    """
    Parse HTML search results (Google/Bing)

    Extracts:
    - Featured snippet
    - Organic results (title, url, snippet)
    - Next page link
    - Bing redirect URLs (decoding)
    """
```

**Key Features**:
1. **HTML Parsing**: Uses BeautifulSoup to parse HTML
2. **Featured Snippet Extraction**: Identifies special featured result
3. **URL Filtering**: Filters out visited/evaluated links
4. **Next Page Detection**: Finds pagination link
5. **Bing Redirect Decoding** (lines 24-73): Handles Bing's redirected URLs

```python
# Decode Bing redirect URLs
if "bing.com/ck/a?" in url:
    # Extract u parameter
    u_param = extract_u_param(url)
    # Decode base64
    decoded_url = base64.b64decode(u_param).decode('utf-8')
    # Extract real URL
    real_url = extract_real_url(decoded_url)
    return real_url
```

### Usage Example

```python
# In MicroAgent action
@register_action(description="Search the web")
async def web_search(self, query: str, num_results: int = 10) -> str:
    # Call search API
    html = await self._search_api(query, num_results)

    # Parse results
    result = await self.brain.think_with_retry(
        initial_messages=f"Parse these search results:\n{html}",
        parser=parse_search_results,
        max_retries=2
    )

    # result is list of SearchResultItem
    return format_results(result)
```

## Creating Custom Parsers

### Step-by-Step Guide

**1. Define Parser Function**:

```python
def my_custom_parser(raw_reply: str, **kwargs) -> dict:
    # Validate input
    if not raw_reply or not raw_reply.strip():
        return {
            "status": "error",
            "feedback": "Empty response. Please provide output."
        }

    # Check for required markers
    if "[REQUIRED_SECTION]" not in raw_reply:
        return {
            "status": "error",
            "feedback": "Missing required section: [REQUIRED_SECTION]. "
                       "Please format your response with this section."
        }

    # Extract data
    content = extract_content(raw_reply)

    # Validate data
    if not content or len(content) < 10:
        return {
            "status": "error",
            "feedback": "Extracted content is too short. "
                       "Please provide more detailed information."
        }

    # Return success
    return {
        "status": "success",
        "data": content
    }
```

**2. Use with think_with_retry**:

```python
result = await llm_client.think_with_retry(
    initial_messages="Your task here...",
    parser=my_custom_parser,
    max_retries=3
)
```

### Parser Template

```python
def parser_template(raw_reply: str, **kwargs) -> dict:
    """
    Parser template

    Args:
        raw_reply: LLM output to parse
        **kwargs: Parser-specific arguments

    Returns:
        Status dict with success/error information
    """

    # 1. Validate input
    if not raw_reply:
        return {
            "status": "error",
            "feedback": "Empty response"
        }

    # 2. Check required structure
    required_markers = kwargs.get("required_markers", [])
    for marker in required_markers:
        if marker not in raw_reply:
            return {
                "status": "error",
                "feedback": f"Missing {marker}. Please include it."
            }

    # 3. Extract data
    try:
        data = extract_data(raw_reply, **kwargs)
    except Exception as e:
        return {
            "status": "error",
            "feedback": f"Parse error: {str(e)}. Please check format."
        }

    # 4. Validate extracted data
    if not validate_data(data, **kwargs):
        return {
            "status": "error",
            "feedback": "Invalid data. Please ensure all fields are present."
        }

    # 5. Return success
    return {
        "status": "success",
        "data": data
    }
```

## Summary

### Component Responsibilities

| Component | Location | Responsibility |
|-----------|----------|----------------|
| LLMClient | backends/llm_client.py | LLM API wrapper with streaming |
| think_with_retry | backends/llm_client.py | Generic retry loop for parsing |
| multi_section_parser | skills/parser_utils.py | Extract multiple sections |
| search_results_parser | skills/search_results_parser.py | Parse HTML search results |

### Key Benefits

1. **Robustness**: Automatic retries with specific feedback
2. **Flexibility**: Pluggable parser interface
3. **Efficiency**: Optimized parsing with early termination
4. **Reliability**: Clear error messages guide LLM to correct output
5. **Reusability**: Generic pattern works for any parsing task

### Best Practices

1. **Provide Specific Feedback**: Tell LLM exactly what's wrong
2. **Validate Thoroughly**: Check all requirements before returning success
3. **Use Multi-Section Parser**: Leverage existing parser when possible
4. **Handle Edge Cases**: Empty output, malformed content, etc.
5. **Limit Retries**: Set reasonable max_retries to avoid infinite loops

### Common Patterns

**Extract Single Value**:
```python
result = await brain.think_with_retry(
    messages="Extract the date...",
    parser=lambda text: extract_date(text),
    max_retries=2
)
```

**Extract Multiple Sections**:
```python
result = await brain.think_with_retry(
    messages="Create sections [Plan], [Timeline], [Budget]",
    parser=multi_section_parser,
    section_headers=['[Plan]', '[Timeline]', '[Budget]'],
    match_mode="ALL",
    max_retries=3
)
# result is dict of sections
```

**Parse Complex Data**:
```python
result = await brain.think_with_retry(
    messages="Extract structured data...",
    parser=custom_structured_parser,
    max_retries=3
)
```

This pattern ensures reliable extraction of structured output from LLM natural language responses.
