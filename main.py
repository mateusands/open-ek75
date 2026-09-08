# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 Mateus Andrade
#!/usr/bin/env python3
"""Entry point for running from a source checkout, no install needed."""
import sys

from ek75.cli import main

if __name__ == "__main__":
    sys.exit(main())
