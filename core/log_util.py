import os
import logging
from logging.handlers import RotatingFileHandler
from typing import Optional


# 1. 定义过滤器：决定什么能上控制台
class ConsoleDisplayFilter(logging.Filter):
    def filter(self, record):
        # 规则 A: 错误(ERROR/CRITICAL) 必须显示
        if record.levelno >= logging.ERROR:
            return True
        
        # 规则 B: 如果日志携带了 'echo' 标记且为 True，则显示
        # 使用 getattr 安全获取，防止报错
        if getattr(record, 'echo', False):
            return True
            
        # 其他（普通的 INFO/DEBUG）都不显示
        return False

# ==========================================
# 1. LogFactory: 负责干活（创建 Logger 和 Handler）
# ==========================================
class LogFactory:
    _log_dir = "./logs"
    _formatter = logging.Formatter(
        '%(asctime)s - [%(threadName)s] - %(name)s - %(levelname)s - %(message)s'
    )
    _default_level = logging.INFO  # 全局默认日志级别

    @classmethod
    def set_log_dir(cls, path: str):
        cls._log_dir = path
        os.makedirs(cls._log_dir, exist_ok=True)

    @classmethod
    def set_level(cls, level: int):
        """【新增】设置全局默认日志级别"""
        cls._default_level = level

    @classmethod
    def get_logger(cls, logger_name: str, filename: str,level: int = None) -> logging.Logger:
        if not os.path.exists(cls._log_dir):
            os.makedirs(cls._log_dir, exist_ok=True)

        logger = logging.getLogger(logger_name)
        # 【关键修改】决定当前 logger 的级别
        target_level = level if level is not None else cls._default_level
        logger.setLevel(target_level)
        logger.propagate = False

        if logger.handlers:
            return logger

        # --- 1. 文件 Handler (保持不变: 收录所有 INFO+) ---
        file_path = os.path.join(cls._log_dir, filename)
        file_handler = RotatingFileHandler(
            file_path, maxBytes=10*1024*1024, backupCount=5, encoding='utf-8'
        )
        file_handler.setLevel(logging.DEBUG) 
        file_handler.setFormatter(cls._formatter)
        logger.addHandler(file_handler)

        # --- 2. 控制台 Handler (修改点) ---
        console_handler = logging.StreamHandler()
        
        # 【关键点 1】: 将级别降低到 INFO，否则 INFO 级别的日志根本进不来
        console_handler.setLevel(logging.INFO) 
        
        # 【关键点 2】: 添加过滤器，由过滤器来把关谁能显示
        console_handler.addFilter(ConsoleDisplayFilter())
        
        console_handler.setFormatter(cls._formatter)
        logger.addHandler(console_handler)

        return logger


# ==========================================
# 2. AutoLoggerMixin: 负责决策（决定文件名）
# ==========================================
class AutoLoggerMixin:
    """
    智能日志 Mixin。
    
    优先级策略：
    1. 如果设置了 _log_from_attr = "xxx"，则文件名取 self.xxx + ".log"
    2. 如果设置了 _custom_log_filename = "yyy.log"，则文件名为 "yyy.log"
    3. 默认使用 类名.log
    """
    
    # 【配置项 1】指定从哪个实例属性获取名字 (例如 "name", "id")
    _log_from_attr: Optional[str] = None
    
    # 【配置项 2】指定固定的文件名
    _custom_log_filename: Optional[str] = None

    _custom_log_level: Optional[int] = None

    @property
    def logger(self) -> logging.Logger:
        # 懒加载：只有第一次调用时才初始化
        if not hasattr(self, '_internal_logger'):
            self._init_logger()
        return self._internal_logger

    def _init_logger(self):
        filename = self._determine_log_filename()
        
        # 这里的 logger_name 很关键：
        # 如果是基于实例属性（如name='ABC'），logger_name 最好也叫 'ABC'，
        # 这样 logging 模块能正确区分不同的 logger 对象。
        # 如果是基于类名，就用类名。
        
        # 为了保证唯一性，我们使用 "类名_文件名" 作为 logger 内部的 key
        logger_name = f"{self.__class__.__name__}_{filename}"
        
        # 将 mixin 中定义的级别传给工厂
        self._internal_logger = LogFactory.get_logger(
            logger_name, 
            filename, 
            level=self._custom_log_level
        )

    def _determine_log_filename(self) -> str:
        """核心逻辑：决定日志文件名"""
        
        # 策略 1: 基于实例属性 (例如 self.name)
        if self._log_from_attr:
            if hasattr(self, self._log_from_attr):
                attr_value = getattr(self, self._log_from_attr)
                # 简单的清理，防止文件名非法字符
                safe_name = str(attr_value).strip().replace('/', '_').replace('\\', '_')
                return f"{safe_name}.log"
            else:
                # 如果指定的属性不存在，回退到默认
                print(f"[Warn] Attribute '{self._log_from_attr}' not found in {self}, fallback to class name.")

        # 策略 2: 固定文件名
        if self._custom_log_filename:
            return self._custom_log_filename

        # 策略 3: 默认类名
        return f"{self.__class__.__name__}.log"

    def echo(self, msg: str, *args, **kwargs):
        """
        专用方法：既写日志文件，也输出到控制台。
        用法: self.echo("Server started on port %s", 8080)
        """
        # 自动注入 extra={'echo': True}
        if 'extra' not in kwargs:
            kwargs['extra'] = {}
        kwargs['extra']['echo'] = True
        
        # 调用原生 logger
        self.logger.info(msg, *args, **kwargs)