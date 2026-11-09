from abc import ABC, abstractmethod

class LoggerInterface(ABC):
    @abstractmethod
    def log_node_start(self, node_name: str): pass

    @abstractmethod
    def log_node_end(self, node_name: str, output: any = None): pass

    @abstractmethod
    def log_tool_use(self, tool_name: str, input_data: any): pass

    @abstractmethod
    def get_logs(self) -> list: pass
