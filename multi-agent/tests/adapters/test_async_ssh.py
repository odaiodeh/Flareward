"""Blocking SSH SDK work drains before cleanup and never repeats unknown effects."""

import asyncio
import io
import threading
from unittest.mock import Mock, create_autospec

import paramiko
import pytest
from mas.elements.tools.ssh_exec.ssh_exec import SshExecTool, SshExecutionError


@pytest.fixture
async def ssh_case():
    client = create_autospec(paramiko.SSHClient, instance=True)
    client.get_transport.return_value.is_active.return_value = True
    client.exec_command.return_value = (None, io.BytesIO(b"result"), io.BytesIO())
    factory = Mock(return_value=client)
    tool = SshExecTool(
        host="host.invalid",
        port=22,
        username="user",
        password="private-fixture",
        client_factory=factory,
    )
    try:
        yield tool, client, factory
    finally:
        await tool.aclose()


async def test_ssh_construction_is_pure_and_connection_is_owned(ssh_case):
    tool, client, factory = ssh_case
    factory.assert_not_called()
    assert await tool.run(cmd="printf result") == "result"
    factory.assert_called_once()
    client.connect.assert_called_once()
    await tool.aclose()
    client.close.assert_called_once()


async def test_ssh_does_not_reconnect_and_repeat_a_failed_command(ssh_case):
    tool, client, factory = ssh_case
    client.exec_command.side_effect = OSError("password=private-fixture")
    with pytest.raises(SshExecutionError) as failure:
        await tool.run(cmd="write-once")
    assert "private-fixture" not in str(failure.value)
    client.exec_command.assert_called_once()
    client.connect.assert_called_once()
    factory.assert_called_once()


async def test_ssh_cancellation_drains_sdk_work_before_closing_connection(ssh_case):
    tool, client, _ = ssh_case
    entered, release = threading.Event(), threading.Event()
    caller_thread = threading.get_ident()

    def execute(command, *, timeout):
        assert threading.get_ident() != caller_thread
        entered.set()
        if not release.wait(3):
            raise TimeoutError("The test did not release SSH work")
        return None, io.BytesIO(b"result"), io.BytesIO()

    client.exec_command.side_effect = execute
    async with asyncio.TaskGroup() as work:
        task = work.create_task(tool.run(cmd="write-once"))
        try:
            assert await asyncio.to_thread(entered.wait, 3)
            task.cancel()
            await asyncio.sleep(0)
            closing = work.create_task(tool.aclose())
            await asyncio.sleep(0)
            assert not task.done() and not closing.done()
            client.close.assert_not_called()
            release.set()
            with pytest.raises(asyncio.CancelledError):
                await task
            await closing
            client.close.assert_called_once()
        finally:
            release.set()
