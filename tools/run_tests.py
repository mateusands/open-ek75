# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 Mateus Andrade
#!/usr/bin/env python3
"""Run the byte-match tests without pytest — the core has zero dependencies,
and this is how you prove that without installing any."""
import os
import sys
import traceback

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
import tests.test_protocol as suite  # noqa: E402


def main():
    failures = 0
    tests = [(name, fn) for name, fn in vars(suite).items()
             if name.startswith("test_") and callable(fn)]
    for name, fn in tests:
        try:
            fn()
        except AssertionError:
            failures += 1
            print(f"FAIL {name}")
            traceback.print_exc()
        else:
            print(f"ok   {name}")
    print(f"\n{len(tests) - failures}/{len(tests)} passed")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
