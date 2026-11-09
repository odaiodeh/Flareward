class LogContext:
    current_logger = None

    @classmethod
    def set_logger(cls, logger):
        cls.current_logger = logger

    @classmethod
    def get_logger(cls):
        return cls.current_logger
