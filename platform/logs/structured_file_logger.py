import json
from datetime import datetime, timezone
from logs.logger_interface import LoggerInterface

class StructuredFileLogger(LoggerInterface):
    def __init__(self, file_path="logs/graph_run.jsonl"):
        self.file_path = file_path
        with open(self.file_path, "w") as f:
            pass  # Clear file

    def _log(self, data):
        data["timestamp"] = str(datetime.now(timezone.utc))
        with open(self.file_path, "a") as f:
            f.write(json.dumps(data) + "\n")

    def log_node_start(self, node_name):
        self._log({"type": "node_start", "node": node_name})

    def log_node_end(self, node_name, output=None):
        self._log({"type": "node_end", "node": node_name, "output": output})

    def log_tool_use(self, tool_name, input_data):
        self._log({"type": "tool", "tool": tool_name, "input": input_data})

    def get_logs(self):
        with open(self.file_path, "r") as f:
            return [json.loads(line) for line in f]
