"""Standalone IPC regression; outside the canonical native test collection."""

import ast
import asyncio
import importlib.util
import json
import os
import queue
import subprocess
import sys
import time
import types
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BROWSER = ROOT / "tools/p5a_visual_browser.py"
NATIVE = ROOT / "tools/p5a_visual_native.py"
RESPONSE = {"options": {"flow_plan": [], "control": {"allowed_weekdays": ["mon"]}}, "pid": 123}


def browser_module():
    spec = importlib.util.spec_from_file_location("owned_p5a_browser", BROWSER)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    assert Path(module.__file__).resolve() == BROWSER
    return module


def native_boundary():
    """Execute the actual dispatch try node, not a rewritten transport function."""
    tree = ast.parse(NATIVE.read_bytes())
    nodes = [
        node
        for node in ast.walk(tree)
        if isinstance(node, ast.Try)
        and any(
            isinstance(item, ast.Call)
            and isinstance(item.func, ast.Name)
            and item.func.id == "action"
            for item in ast.walk(node)
        )
        and any(
            isinstance(item.type, ast.Name) and item.type.id == "Exception"
            for item in node.handlers
        )
    ]
    assert len(nodes) == 1
    function = ast.parse("async def boundary():\n    pass\n").body[0]
    function.body = [nodes[0], ast.parse("return result").body[0]]
    extracted = ast.fix_missing_locations(ast.Module(body=[function], type_ignores=[]))
    return compile(extracted, str(NATIVE), "exec")


class TransportRegression(unittest.TestCase):
    def test_delayed_fresh_sdk_real_pipe(self):
        child = subprocess.Popen(
            [sys.executable, "-B", str(Path(__file__).resolve()), "--rpc-child"],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            env=os.environ.copy(),
        )
        started = time.monotonic()
        killed = False
        stdout = stderr = ""
        try:
            request = json.loads(child.stdout.readline())
            self.assertEqual(request, {"id": 1, "kind": "fresh_sdk", "payload": None})
            time.sleep(16)
            if child.poll() is None:
                child.stdin.write(json.dumps(RESPONSE) + "\n")
                child.stdin.flush()
            stdout, stderr = child.communicate(timeout=65)
            self.assertEqual(child.returncode, 0, stderr)
            self.assertEqual(json.loads(stdout), RESPONSE)
            self.assertGreaterEqual(time.monotonic() - started, 16)
        finally:
            if child.poll() is None:
                killed = True
                child.kill()
                stdout, stderr = child.communicate(timeout=10)
            print(
                json.dumps(
                    {
                        "probe": "real_pipe",
                        "elapsed": time.monotonic() - started,
                        "child_exit": child.returncode,
                        "owned_kill": killed,
                        "pipes_drained": True,
                        "helper": str(BROWSER),
                        "stderr": stderr,
                    }
                ),
                file=sys.stderr,
                flush=True,
            )
            child.stdin.close()
            child.stdout.close()
            child.stderr.close()
            self.assertIsNotNone(child.returncode)

    def test_client_budgets_error_eof_and_no_retry(self):
        module = browser_module()
        for kind, budget in (("fresh_sdk", 65), ("snapshot", 15), ("ws", 15)):
            calls = []

            class Inbox:
                def get(self, *, timeout):
                    calls.append(timeout)
                    return json.dumps(RESPONSE)

            module.INBOX = Inbox()
            self.assertEqual(module.rpc(kind), RESPONSE)
            self.assertEqual(calls, [budget])
        for reply, error in (
            (None, "native parent EOF"),
            (json.dumps({"harness_error": "owned failure"}), "owned failure"),
        ):
            module.INBOX = queue.Queue()
            module.INBOX.put(reply)
            before = module.COUNTER
            with self.assertRaisesRegex(RuntimeError, error):
                module.rpc("fresh_sdk")
            self.assertEqual(module.COUNTER, before + 1)

    def test_server_budget_selection_and_error_propagation(self):
        import traceback

        async def run():
            for kind, expected in (("fresh_sdk", [60]), ("snapshot", []), ("ws", [])):
                deadlines, calls = [], []

                def timeout(seconds):
                    deadlines.append(seconds)
                    return asyncio.timeout(seconds)

                async def action(actual, payload):
                    calls.append((actual, payload))
                    raise ValueError("owned action failure")

                namespace = {
                    "asyncio": types.SimpleNamespace(timeout=timeout),
                    "traceback": traceback,
                    "sys": sys,
                    "action": action,
                    "message": {"kind": kind, "payload": {"unchanged": True}},
                }
                exec(native_boundary(), namespace)
                result = await namespace["boundary"]()
                self.assertEqual(result, {"harness_error": "ValueError: owned action failure"})
                self.assertEqual(deadlines, expected)
                self.assertEqual(calls, [(kind, {"unchanged": True})])

        asyncio.run(run())

    def test_server_cancellation_awaits_owned_child_cleanup(self):
        import traceback

        async def run():
            entered = asyncio.Event()
            observed = {}

            async def action(kind, payload):
                child = await asyncio.create_subprocess_exec(
                    sys.executable,
                    "-B",
                    "-c",
                    "import time; time.sleep(90)",
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE,
                )
                try:
                    entered.set()
                    await asyncio.wait_for(child.communicate(), 45)
                finally:
                    if child.returncode is None:
                        child.kill()
                        await asyncio.wait_for(child.communicate(), 10)
                    observed["returncode"] = child.returncode

            namespace = {
                "asyncio": asyncio,
                "traceback": traceback,
                "sys": sys,
                "action": action,
                "message": {"kind": "fresh_sdk"},
            }
            exec(native_boundary(), namespace)
            task = asyncio.create_task(namespace["boundary"]())
            await asyncio.wait_for(entered.wait(), 10)
            task.cancel()
            with self.assertRaises(asyncio.CancelledError):
                await task
            self.assertIsNotNone(observed["returncode"])
            print(json.dumps({"probe": "cancel_cleanup", **observed}), file=sys.stderr)

        asyncio.run(run())

    def test_preserved_readback_and_global_deadlines(self):
        text = NATIVE.read_text()
        self.assertIn("asyncio.wait_for(fresh.communicate(), 45)", text)
        self.assertIn("async with asyncio.timeout(300):", text)
        self.assertIn("stdout, stderr = await asyncio.wait_for(fresh.communicate(), 10)", text)
        self.assertIn("fresh.kill()", text)
        self.assertNotIn("shield(", text)


if __name__ == "__main__":
    if sys.argv[1:] == ["--rpc-child"]:
        started = time.monotonic()
        try:
            print(json.dumps(browser_module().rpc("fresh_sdk")), flush=True)
        finally:
            print(
                json.dumps({"rpc_child_elapsed": time.monotonic() - started}),
                file=sys.stderr,
                flush=True,
            )
    else:
        suite = unittest.defaultTestLoader.loadTestsFromTestCase(TransportRegression)
        assert suite.countTestCases() == 5
        print("Registered transport cases: 5", flush=True)
        outcome = unittest.TextTestRunner(verbosity=2).run(suite)
        sys.exit(not outcome.wasSuccessful())
