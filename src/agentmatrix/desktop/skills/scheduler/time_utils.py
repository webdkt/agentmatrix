"""
Time Utilities - 时间解析工具

提供本地时间和UTC时间之间的转换功能。
"""

from datetime import datetime, timezone


def parse_local_time(time_str: str) -> datetime:
    """
    解析本地时间字符串，返回UTC datetime

    支持多种格式：
    - YYYY-MM-DD HH:MM:SS
    - YYYY-MM-DD HH:MM
    - YYYY-MM-DDTHH:MM:SS
    - YYYY/MM/DD HH:MM:SS

    Args:
        time_str: 时间字符串

    Returns:
        datetime: UTC时间对象（无时区信息）

    Raises:
        ValueError: 如果无法解析时间格式
    """
    # 支持多种格式
    formats = [
        "%Y-%m-%d %H:%M:%S",
        "%Y-%m-%d %H:%M",
        "%Y-%m-%dT%H:%M:%S",
        "%Y/%m/%d %H:%M:%S",
    ]

    for fmt in formats:
        try:
            local_dt = datetime.strptime(time_str, fmt)
            # 转换为UTC（去掉时区信息）
            return local_dt.astimezone(timezone.utc).replace(tzinfo=None)
        except ValueError:
            continue

    raise ValueError(f"无法解析时间格式: {time_str}")


def format_utc_for_display(utc_dt: datetime) -> str:
    """
    将UTC时间格式化为本地时间显示

    Args:
        utc_dt: UTC时间对象

    Returns:
        str: 格式化的本地时间字符串
    """
    if utc_dt.tzinfo is None:
        utc_dt = utc_dt.replace(tzinfo=timezone.utc)
    return utc_dt.astimezone().strftime("%Y-%m-%d %H:%M:%S")
