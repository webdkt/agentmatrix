import re
def sanitize_filename(name: str, max_length: int = 200) -> str:
        """
        清洗字符串，使其可以作为合法的文件名/目录名，同时保留中文。
        
        规则:
        1. 去除 Windows/Linux 非法字符
        2. 去除不可见字符 (换行、Tab等)
        3. 去除首尾的空格和点 (Windows 不喜欢文件名以点或空格结尾)
        4. 截断长度，防止路径过长
        """
        if not name:
            return "untitled"

        # 1. 替换文件系统非法字符为下划线
        # Windows非法字符: < > : " / \ | ? *
        name = re.sub(r'[<>:"/\\|?*]', '_', name)

        # 2. 替换不可见控制字符 (如换行符 \n, \r, \t) 为空格
        name = "".join(ch if ch.isprintable() else " " for ch in name)

        # 3. 将连续的空格或下划线合并为一个 (美观优化)
        name = re.sub(r'[\s_]+', '_', name)

        # 4. 去除首尾的空格和点 (Windows文件名不能以点结尾)
        name = name.strip(' .')

        # 5. 如果清洗后为空 (比如原文件名全是非法字符)，给个默认值
        if not name:
            name = "untitled_file"

        # 6. 截断长度 (通常文件系统限制 255 字节，考虑到路径长度，限制在 200 字符比较安全)
        return name[:max_length]