"""Controlled candidate evaluation proves bounded values, private errors and cleanup."""

import asyncio

import pytest
from support.python_checks import ADDITION, SUBTRACTION, evaluation_input

from flareward.elements.operation import OperationContext
from flareward.executions.domain.context import ExecutionContext
from flareward.services.identity.domain import Identity
from plugins.testing.contracts import PythonFunctionConfig
from plugins.testing.python_functions import PythonFunctionEvaluation
from plugins.testing.specification import PythonFunctionFactory


@pytest.fixture
def context():
    return OperationContext(
        execution=ExecutionContext(identity=Identity.user("verifier")), key="check"
    )


@pytest.mark.parametrize(
    "source,values,failure",
    [
        (ADDITION, (3, -2, 0), None),
        (SUBTRACTION, (-1, -4, 0), None),
        (b"raise RuntimeError('private source diagnostic')\n", None, "execution_failed"),
        (b"print('debug output')\n" + ADDITION, (3, -2, 0), None),
        (b"print('x' * 100_000)\n" + ADDITION, None, "invalid_or_excessive_output"),
    ],
)
async def test_controlled_python_checks_are_independent_and_clean(
    tmp_path, context, source, values, failure, monkeypatch
):
    monkeypatch.setenv("FLAREWARD_PRIVATE_TEST_CREDENTIAL", "synthetic-private-value")
    config = PythonFunctionConfig(function="add")
    source = b"import os\nassert 'FLAREWARD_PRIVATE_TEST_CREDENTIAL' not in os.environ\n" + source
    operation = PythonFunctionEvaluation(config, tmp_path)
    request = evaluation_input(source)
    result = await operation.execute(request, context)
    assert result.values == values and result.failure == failure
    assert "private source diagnostic" not in result.model_dump_json()
    assert "synthetic-private-value" not in result.model_dump_json()
    assert not list(tmp_path.iterdir())


async def test_child_preserves_sandbox_transport_without_provider_or_invocation_data(
    tmp_path, context, monkeypatch
):
    monkeypatch.setenv("HTTP_PROXY", "http://127.0.0.1:3128")
    monkeypatch.setenv("SSL_CERT_FILE", "/tmp/sandbox-proxy-ca.pem")
    monkeypatch.setenv("OPENAI_API_KEY", "synthetic-provider-secret")
    monkeypatch.setenv("RUNENGINE_PARAMS", "synthetic-invocation-payload")
    source = (
        b"import os\n"
        b"assert os.environ['HTTP_PROXY'] == 'http://127.0.0.1:3128'\n"
        b"assert os.environ['SSL_CERT_FILE'] == '/tmp/sandbox-proxy-ca.pem'\n"
        b"assert 'OPENAI_API_KEY' not in os.environ\n"
        b"assert 'RUNENGINE_PARAMS' not in os.environ\n"
    ) + ADDITION
    result = await PythonFunctionEvaluation(PythonFunctionConfig(function="add"), tmp_path).execute(
        evaluation_input(source), context
    )
    assert result.values == (3, -2, 0) and result.failure is None
    assert not list(tmp_path.iterdir())


@pytest.mark.parametrize("cancel", [False, True])
async def test_deadline_or_cancellation_reaps_the_owned_process(
    tmp_path, context, monkeypatch, cancel
):
    processes = []
    original = asyncio.create_subprocess_exec

    async def acquire(*args, **kwargs):
        process = await original(*args, **kwargs)
        processes.append(process)
        return process

    monkeypatch.setattr(asyncio, "create_subprocess_exec", acquire)
    config = PythonFunctionConfig(function="add", timeout_seconds=10 if cancel else 0.2)
    task = asyncio.create_task(
        PythonFunctionEvaluation(config, tmp_path).execute(
            evaluation_input(b"while True:\n    pass\n"), context
        )
    )
    if cancel:
        async with asyncio.timeout(5):
            while not processes:
                await asyncio.sleep(0.01)
        task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await task
    else:
        result = await task
        assert result.values is None and result.failure == "deadline_exceeded"
    assert len(processes) == 1 and processes[0].returncode is not None
    assert not list(tmp_path.iterdir())


def test_normal_factory_requires_receiver_authorization(monkeypatch):
    monkeypatch.setenv("FLAREWARD_PYTHON_CHECK_EXECUTION_ENABLED", "false")
    with pytest.raises(ValueError, match="not enabled"):
        PythonFunctionFactory().create(PythonFunctionConfig(function="add"))
