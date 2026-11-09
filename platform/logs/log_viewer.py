import json

def view_logs(path="logs/graph_run.jsonl"):
    with open(path) as f:
        for line in f:
            entry = json.loads(line)
            print(f"[{entry['timestamp']}] {entry['type']} - {entry.get('node') or entry.get('tool')}")
