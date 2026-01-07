import json
from typing import Any

class SkillHelpers:
    """
    A collection of static utility methods to support skill development.
    """
    @staticmethod
    def parse_llm_json_list(raw_reply: str) -> dict:
        """
        A specific parser 
        It uses a generic helper to parse the JSON, and then validates if it's json list of strings
        """
        try:
            # 1. Delegate the generic parsing task to the helper
            data = SkillHelpers.parse_llm_json(raw_reply)
            
            # 2. Focus ONLY on logic-specific validation
            if isinstance(data, list) and all(isinstance(item, str) for item in data):
                return {
                    "status": "success",
                    "data": data
                }
            else:
                # The JSON was valid, but its structure is wrong for our needs.
                error_message = (
                    "Invalid JSON structure. The output must be a JSON array "
                    "containing only strings (e.g., `[\"list item 1\", \"list item 2\"]`)."
                )
                return {"status": "error", "feedback": error_message}
                
        except json.JSONDecodeError:
            # The helper failed, meaning the raw string was not valid JSON.
            error_message = (
                "Invalid format. Your output must be a valid JSON array of strings. "
                "Please ensure there are no trailing commas and all strings are correctly quoted."
            )
            return {"status": "error", "feedback": error_message}

    @staticmethod
    def parse_llm_json_with_schema(raw_reply: str, allowed_schemas: list[dict]) -> dict:
        """
        验证返回的 JSON 是否符合允许的格式要求，只验证 key 的存在性。
        
        Args:
            raw_reply: LLM 返回的原始字符串
            allowed_schemas: 允许的 JSON 格式列表，每个元素是一个 dict，表示允许的 key 集合
                        例如: [{"key1": None, "key2": None}, {"some_key": None}]
                        表示允许两种格式：一种必须有 key1 和 key2，另一种只有 some_key
        
        Returns:
            dict: 包含 status 和 data 或 feedback 的字典
                - 成功时: {"status": "success", "data": parsed_data}
                - 失败时: {"status": "error", "feedback": error_message}
        """
        try:
            # 1. 使用通用解析器解析 JSON
            data = SkillHelpers.parse_llm_json(raw_reply)
            
            # 2. 验证数据格式
            if not isinstance(data, dict):
                return {
                    "status": "error",
                    "feedback": "Invalid JSON structure. Expected a JSON object."
                }
            
            # 3. 检查是否符合任一允许的格式
            data_keys = set(data.keys())
            for schema in allowed_schemas:
                required_keys = set(schema.keys())
                # 检查数据是否包含所有必需的 key
                if required_keys.issubset(data_keys):
                    return {
                        "status": "success",
                        "data": data
                    }
            
            # 4. 如果都不匹配，生成错误信息
            allowed_formats = ", ".join([f"{{{', '.join(schema.keys())}}}" for schema in allowed_schemas])
            return {
                "status": "error",
                "feedback": f"Invalid JSON structure. Expected one of these formats: {allowed_formats}"
            }
            
        except json.JSONDecodeError:
            return {
                "status": "error",
                "feedback": "Invalid JSON format. Please ensure your output is a valid JSON object."
            }


    @staticmethod
    def parse_llm_json(raw_reply: str) -> Any:
        """
        Parses a JSON object from an LLM's raw string output.

        This method is designed to be robust against common LLM quirks, such as:
        - Wrapping the JSON in markdown code blocks (e.g., ```json ... ```).
        - Leading/trailing whitespace.

        Args:
            raw_reply: The raw string response from the LLM.

        Returns:
            The parsed Python object (e.g., dict, list).

        Raises:
            json.JSONDecodeError: If the string cannot be parsed into a valid JSON object
                                  after cleaning.
        """
        if not raw_reply:
            raise json.JSONDecodeError("Input string is empty.", "", 0)

        cleaned_reply = raw_reply.strip()

        # Defensively strip markdown code fences
        if cleaned_reply.startswith("```json"):
            cleaned_reply = cleaned_reply[7:-3].strip()
        elif cleaned_reply.startswith("```"):
            cleaned_reply = cleaned_reply[3:-3].strip()

        # The json.loads() will raise JSONDecodeError on failure, which is the
        # desired behavior for the caller to catch.
        return json.loads(cleaned_reply)