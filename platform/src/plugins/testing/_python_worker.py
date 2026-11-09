"""Candidate worker receives arguments only; its entire receiver is untrusted."""

import contextlib
import json
import runpy
import sys


def main() -> None:
    cases = json.load(sys.stdin)
    with contextlib.redirect_stdout(sys.stderr):
        function = runpy.run_path(sys.argv[1])[sys.argv[2]]
        results = [function(*case["args"], **case["kwargs"]) for case in cases]
    print(json.dumps(results, allow_nan=False))


if __name__ == "__main__":
    main()
