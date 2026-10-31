"""Compare installed receiver Python sources with the exact local build inputs."""

import argparse
import hashlib
import json
import subprocess
from pathlib import Path

CHECK = """
import hashlib
import json
import sys
import sysconfig
from pathlib import Path

expected = json.load(sys.stdin)
site = Path(sysconfig.get_paths()['purelib'])
different = [name for name, digest in expected.items()
             if not (site / name).is_file()
             or hashlib.sha256((site / name).read_bytes()).hexdigest() != digest]
if different:
    raise SystemExit('Missing or changed installed sources: ' + ', '.join(different))
print(json.dumps({'matched_python_files': len(expected)}))
"""


def main() -> None:
    application = Path(__file__).resolve().parents[3]
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run-engine", type=Path, default=application.parent / "run-engine")
    parser.add_argument("--image", action="append")
    arguments = parser.parse_args()
    mappings = {
        arguments.run_engine.resolve() / "src/runengine": "runengine",
        application / "global_utils/src/global_utils": "global_utils",
        application / "multi-agent/lib/mas": "mas",
        application / "multi-agent/bootstrap": "bootstrap",
        application / "multi-agent/config": "config",
        application / "multi-agent/adapters/inbound": "inbound",
        application / "multi-agent/adapters/outbound": "outbound",
        application / "multi-agent/adapters/run_engine": "run_engine",
        application / "multi-agent/tests/support": "/opt/test-fixtures/support",
    }
    expected = {}
    for source, package in mappings.items():
        if not source.is_dir():
            parser.error(f"Missing build source directory: {source}")
        for path in source.rglob("*.py"):
            expected[str(Path(package) / path.relative_to(source))] = hashlib.sha256(
                path.read_bytes()
            ).hexdigest()
    images = arguments.image or [
        "unifai-receiver:platform-20261029",
        "unifai-sandbox:platform-20261029",
    ]
    for name in images:
        identity = subprocess.check_output(
            ["docker", "image", "inspect", "--format", "{{.Id}}", name], text=True
        ).strip()
        result = subprocess.run(
            ["docker", "run", "--rm", "-i", "--entrypoint", "python", name, "-c", CHECK],
            input=json.dumps(expected),
            text=True,
            capture_output=True,
            check=False,
        )
        if result.returncode:
            raise SystemExit(f"{name}: {result.stderr.strip()}")
        print(json.dumps({"image": name, "identity": identity, **json.loads(result.stdout)}))


if __name__ == "__main__":
    main()
