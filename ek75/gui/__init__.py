# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 Mateus Andrade
"""Tkinter GUI for open-ek75.

Zero dependencies, like the rest of the project: tkinter ships with Python.

Layering, same rule as `cli.py` (CLAUDE.md): nothing under `gui/` builds a
packet or touches hidraw. Every device operation goes through
`core.lighting.Session`, driven off the UI thread by `gui.controller`.
"""
