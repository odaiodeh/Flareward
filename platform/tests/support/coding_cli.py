"""Shared local Codex protocol executable; no model or network calls."""

import sys
from pathlib import Path

import pytest


@pytest.fixture
def codex_cli(tmp_path):
    return write_codex_cli(tmp_path)


def write_codex_cli(directory: Path, *, git_repository: Path | None = None) -> Path:
    executable = directory / "codex"
    executable.write_text(
        f"#!{sys.executable}\n"
        + """
import json
import os
import subprocess
import sys
import time
from pathlib import Path

git_repository = GIT_REPOSITORY_BINDING
prompt = sys.stdin.read()
workspace = Path(sys.argv[sys.argv.index('--cd') + 1])
(workspace / 'sandbox').write_text(sys.argv[sys.argv.index('--sandbox') + 1])
(workspace / 'home').write_text(os.environ['CODEX_HOME'])
assert 'OPENAI_API_KEY' not in os.environ
assert os.environ['CODEX_API_KEY'] == 'private-test-token'
assert '--json' in sys.argv and '--ephemeral' in sys.argv
assert 'shell_environment_policy.inherit="none"' in sys.argv
if prompt == 'hang':
    child = subprocess.Popen([sys.executable, '-c', 'import time; time.sleep(120)'])
    (workspace / 'child').write_text(str(child.pid))
# Publish readiness atomically, after setup and any descendant acquisition.
(workspace / 'starting').write_text(str(os.getpid()))
(workspace / 'starting').replace(workspace / 'started')
if prompt == 'parallel':
    deadline = time.monotonic() + 10
    while len(list(workspace.parent.parent.glob('*/work/started'))) < 2:
        if time.monotonic() > deadline:
            raise RuntimeError('Concurrent invocation did not start')
        time.sleep(0.01)
if prompt == 'hang':
    time.sleep(120)
if prompt == 'failure':
    print('private-test-token', file=sys.stderr)
    print(json.dumps({'type':'turn.failed', 'error':{'message':'private-test-token'}}))
    sys.exit(1)
if prompt == 'commands':
    for _ in range(3):
        print(json.dumps({'type':'item.started','item':{'type':'command_execution'}}), flush=True)
    time.sleep(120)
if prompt == 'overflow':
    print('x' * 2048)
    sys.exit(0)
if prompt == 'malformed':
    print('private-test-token')
    sys.exit(1)
if prompt == 'incomplete':
    sys.exit(0)
answer_text = 'done'
if sys.argv[sys.argv.index('--model') + 1] == 'designer-fixture':
    request, _ = json.JSONDecoder().raw_decode(
        prompt.split('Feature design request:' + chr(10), 1)[1]
    )
    plan = 'Implement and independently test: ' + request['acceptance_criteria'][0]
    if request['feedback'] is not None:
        plan += ' Address reviewer feedback: ' + json.dumps(request['feedback']['review']['data'])
    answer_text = json.dumps({'plan': plan, 'references': []})
    (workspace / 'design-request.json').write_text(json.dumps(request))
elif sys.argv[sys.argv.index('--model') + 1] == 'engineering-fixture':
    bad = 'def add(a, b):' + chr(10) + '    return a - b' + chr(10)
    good = bad.replace('a - b', 'a + b')
    answer = workspace / 'answer.py'
    reports = list((workspace / '.flareward/reports').glob('*'))
    if reports:
        assert answer.read_text() == bad, 'Repair did not restore the exact previous candidate'
        report = json.loads(reports[0].read_text())
        assert report['details']['failures'], 'Repair did not receive the failed trusted checks'
        answer.write_text(good)
    else:
        assert not answer.exists(), 'Fresh isolated coding unexpectedly inherited work'
        answer.write_text(bad)
elif sys.argv[sys.argv.index('--model') + 1] == 'git-fixture':
    assert git_repository is not None
    def git(*arguments):
        return subprocess.run(
            ['git', '-c', 'user.name=Platform Test', '-c', 'user.email=test@example.test',
             '-c', 'core.hooksPath=' + os.devnull, *arguments],
            cwd=workspace, check=True, capture_output=True, text=True,
            env={'PATH': os.environ.get('PATH', ''),
                 'GIT_CONFIG_NOSYSTEM':'1', 'GIT_CONFIG_GLOBAL':os.devnull},
        ).stdout.strip()
    git('init', '--quiet', '--initial-branch=work')
    reports = list((workspace / '.flareward/reports').glob('*'))
    if reports:
        raw_feedback = prompt.split('Previous attempt feedback:' + chr(10), 1)[1]
        feedback, _ = json.JSONDecoder().raw_decode(raw_feedback)
        assert feedback['candidate']['identity']['repository'] == 'product'
        git('fetch', '--quiet', git_repository, feedback['candidate']['identity']['commit'])
        git('checkout', '--quiet', '--detach', feedback['candidate']['identity']['commit'])
        assert 'a - b' in (workspace / 'answer.py').read_text()
        assert json.loads(reports[0].read_text())['details']['failures']
    body = '    return a + b' if reports else '    return a - b'
    (workspace / 'answer.py').write_text('def add(a, b):' + chr(10) + body + chr(10))
    git('add', 'answer.py')
    git('commit', '--quiet', '-m', 'Implement candidate')
    commit = git('rev-parse', 'HEAD')
    git('push', '--quiet', git_repository, commit + ':refs/heads/flareward/candidates/' + commit)
    answer_text = json.dumps({'repository':'product', 'commit':commit})
else:
    (workspace / 'answer.txt').write_text(prompt)
print(json.dumps({'type':'item.started','item':{'type':'command_execution'}}))
print(json.dumps({'type':'item.completed','item':{'type':'agent_message','text':answer_text}}))
print(json.dumps({'type':'turn.completed','usage':{'input_tokens':12,'output_tokens':2}}))
""".replace("GIT_REPOSITORY_BINDING", repr(str(git_repository) if git_repository else None))
    )
    executable.chmod(0o700)
    return executable
