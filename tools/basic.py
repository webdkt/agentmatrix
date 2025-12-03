def read_file(path):
    # Mock
    return f"Contents of {path}: [Row1: 100, Row2: 200]"

TOOL_MAP = {
    "read_file": read_file
}