# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 Mateus Andrade
"""The keyboard's physical layout and per-region effect list, from Dareu's own
device profile (`ek75/data/<PID>.json`).

Pure data loading — no I/O to the device, no packet construction. The GUI draws
its keyboard from this rather than from a hand-made layout table, so the shape
on screen is the vendor's own description of the hardware.

Everything here is a *fallback* for what the keyboard can be asked directly:
`LED_CMD_ATTRIBUTE` returns the authoritative per-region effect list at runtime
(see core/lighting.py). The profile is what to draw before the device answers,
and what to fall back to if it never does.
"""
import json
import os

DATA_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data")
DEFAULT_PID = "0101"


class Key:
    """One physical key, positioned in the profile's own coordinate space."""

    __slots__ = ("id", "label", "x", "y", "w", "h", "radius",
                 "function_id", "function_data", "fn_function_id", "fn_function_data")

    def __init__(self, entry, origin_x, origin_y):
        self.id = entry["KeyID"]
        self.label = entry["KeyString"]
        self.x = entry["margin-left"] - origin_x
        self.y = entry["margin-top"] - origin_y
        self.w = entry["Width"]
        self.h = entry["Height"]
        self.radius = entry.get("border-radius", 0)
        self.function_id = entry.get("default-function-Id")
        self.function_data = entry.get("default-function-data", [])
        self.fn_function_id = entry.get("default-fn-function-Id")
        self.fn_function_data = entry.get("default-fn-function-data", [])

    def __repr__(self):
        return f"<Key {self.id} {self.label!r} at ({self.x},{self.y})>"


class DeviceProfile:
    """A parsed `<PID>.json`: device metadata, key layout, per-region effects."""

    def __init__(self, raw):
        self.raw = raw
        device = raw.get("Device", {})
        self.pid = device.get("PID")
        self.model = device.get("Model")
        self.product_name = device.get("ProductName")
        self.fw_type = device.get("FwType")
        self.has_battery = device.get("HasBattery", False)
        self.firmware_version = device.get("LatestFwVer")

        entries = raw.get("Keys", [])
        origin_x = min((e["margin-left"] for e in entries), default=0)
        origin_y = min((e["margin-top"] for e in entries), default=0)
        self.keys = [Key(e, origin_x, origin_y) for e in entries]

    @property
    def width(self):
        return max((k.x + k.w for k in self.keys), default=0)

    @property
    def height(self):
        return max((k.y + k.h for k in self.keys), default=0)

    def custom_effect_list(self, index):
        """The profile's suggested effect list for the Nth lighting region.

        Indexed by *position* in the profile's `Lighting.Region` array, not by
        RegionId — the profile does not record ids. On PID 0101 position 0 is
        the key matrix (RegionId 1) and position 1 the side light (RegionId 4),
        which is why callers pass a position, not a region number.
        """
        regions = self.raw.get("Lighting", {}).get("Region", [])
        if 0 <= index < len(regions):
            return list(regions[index].get("CustomEffectList", []))
        return []


def profile_path(pid=DEFAULT_PID):
    return os.path.join(DATA_DIR, f"{pid}.json")


def load(pid=DEFAULT_PID):
    """Load a device profile, or raise FileNotFoundError if this PID has none."""
    with open(profile_path(pid), encoding="utf-8") as f:
        return DeviceProfile(json.load(f))
