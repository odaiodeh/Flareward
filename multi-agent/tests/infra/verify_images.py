"""Compare installed platform/receiver Python sources with the exact local build inputs."""

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
import shutil
from importlib.util import find_spec
from pathlib import Path

from mas.domain.programs.models import ProgramDefinition
from mas.application.programs.service import ProgramService
from mas.domain.execution.context import ExecutionContext
from mas.application.execution.context import ExecutionContextHolder
from mas.application.execution.service import ExecutionService

expected = json.load(sys.stdin)
site = Path(sysconfig.get_paths()['purelib'])
different = [name for name, digest in expected.items()
             if not (site / name).is_file()
             or hashlib.sha256((site / name).read_bytes()).hexdigest() != digest]
if different:
    raise SystemExit('Missing or changed installed sources: ' + ', '.join(different))
assert ProgramDefinition.__module__ == 'mas.domain.programs.models'
assert ProgramService.__module__ == 'mas.application.programs.service'
assert ExecutionContext.__module__ == 'mas.domain.execution.context'
assert ExecutionContextHolder.__module__ == 'mas.application.execution.context'
assert ExecutionService.__module__ == 'mas.application.execution.service'
assert find_spec('mas.programs') is None, 'Replaced Program namespace is still installed'
assert find_spec('mas.core.execution_preferences') is None, 'Replaced placement module is installed'
assert find_spec('mas.execution') is None, 'Replaced execution namespace is still installed'
assert find_spec('mas.core.execution_context') is None, 'Replaced execution context is installed'
assert find_spec('bootstrap.cli') is None, 'Replaced CLI is still installed'
assert find_spec('mas.application.capabilities.workload_capable') is None
assert find_spec('mas.application.capabilities.iem_capable') is None
assert find_spec('mas.core.iem.factory') is None
assert find_spec('mas.core.iem.messenger') is None
assert find_spec('mas.core.iem.utils') is None
assert find_spec('mas.statistics') is None, 'Replaced statistics service is still installed'
assert find_spec('mas.resources.builtin_service') is None
assert shutil.which('mas') is None, 'Replaced console command is still installed'
print(json.dumps({'matched_python_files': len(expected), 'retired_paths_absent': True}))
"""


def main() -> None:
    application = Path(__file__).resolve().parents[3]
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run-engine", type=Path, default=application.parent / "run-engine")
    parser.add_argument("--image", action="append")
    parser.add_argument(
        "--platform",
        action="store_true",
        help="Check a production image without receiver test fixtures",
    )
    arguments = parser.parse_args()
    mappings = {
        arguments.run_engine.resolve() / "src/runengine": "runengine",
        application / "global_utils/src/global_utils": "global_utils",
        application / "multi-agent/lib/mas": "mas",
        application / "multi-agent/plugins/mas_plugins": "mas_plugins",
        application / "multi-agent/bootstrap": "bootstrap",
        application / "multi-agent/config": "config",
        application / "multi-agent/adapters/inbound": "inbound",
        application / "multi-agent/adapters/outbound": "outbound",
        application / "multi-agent/adapters/run_engine": "run_engine",
    }
    if not arguments.platform:
        mappings[application / "multi-agent/tests/support"] = "/opt/test-fixtures/support"
    expected = {}
    for source, package in mappings.items():
        if not source.is_dir():
            parser.error(f"Missing build source directory: {source}")
        for path in source.rglob("*.py"):
            expected[str(Path(package) / path.relative_to(source))] = hashlib.sha256(
                path.read_bytes()
            ).hexdigest()
    images = arguments.image or [
        "unifai-receiver:program-boundaries-20261103",
        "unifai-sandbox:program-boundaries-20261103",
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
