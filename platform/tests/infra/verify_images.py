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

from lumora.programs.domain.models import ProgramDefinition
from lumora.programs.service import ProgramService
from lumora.executions.domain.context import ExecutionContext
from lumora.executions.context import ExecutionContextHolder
from lumora.executions.service import ExecutionService

expected = json.load(sys.stdin)
site = Path(sysconfig.get_paths()['purelib'])
different = [name for name, digest in expected.items()
             if not (site / name).is_file()
             or hashlib.sha256((site / name).read_bytes()).hexdigest() != digest]
if different:
    raise SystemExit('Missing or changed installed sources: ' + ', '.join(different))
assert ProgramDefinition.__module__ == 'lumora.programs.domain.models'
assert ProgramService.__module__ == 'lumora.programs.service'
assert ExecutionContext.__module__ == 'lumora.executions.domain.context'
assert ExecutionContextHolder.__module__ == 'lumora.executions.context'
assert ExecutionService.__module__ == 'lumora.executions.service'
assert find_spec('mas') is None, 'Replaced Program namespace is still installed'
for retired in ('unifai', 'unifai_plugins', 'flareward', 'flareward_plugins', 'lumora_plugins'):
    assert find_spec(retired) is None, 'Retired namespace is still installed: ' + retired
assert find_spec('lumora.bootstrap.cli') is None, 'Replaced CLI is still installed'
assert find_spec('lumora.elements.behaviors.workload_capable') is None
assert find_spec('lumora.elements.behaviors.iem_capable') is None
assert find_spec('lumora.elements.messaging.protocol.factory') is None
assert find_spec('lumora.elements.messaging.protocol.messenger') is None
assert find_spec('lumora.elements.messaging.protocol.utils') is None
assert find_spec('lumora.resources.builtin_service') is None
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
        application / "packages/service-support/src/global_utils": "global_utils",
        application / "platform/src/lumora": "lumora",
        application / "platform/src/plugins": "plugins",
    }
    if not arguments.platform:
        mappings[application / "platform/tests/support"] = "/opt/test-fixtures/support"
    expected = {}
    for source, package in mappings.items():
        if not source.is_dir():
            parser.error(f"Missing build source directory: {source}")
        for path in source.rglob("*.py"):
            expected[str(Path(package) / path.relative_to(source))] = hashlib.sha256(
                path.read_bytes()
            ).hexdigest()
    images = arguments.image or [
        "lumora-receiver:rename-20261110",
        "lumora-sandbox:rename-20261110",
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
