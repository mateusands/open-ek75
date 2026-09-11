# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 Mateus Andrade
"""High-level lighting operations, shared by the CLI and the GUI.

Layering (CLAUDE.md): this module composes `protocol` (packet construction)
with `device` (hidraw I/O). It is the only place that decides *which* packets a
user-facing action turns into, so `cli.py` and `gui/` never build one
themselves and never repeat this logic.

Nothing here is stateful beyond an open file descriptor: the keyboard itself
holds the configuration in persistent memory (see PROTOCOL.md).
"""
import os

from . import device, protocol

# Fallback when LED_CMD_ID_LIST does not answer: the brute-force sweep this
# repo's regions were originally found with (PROTOCOL.md).
SWEEP_RANGE = range(8)


class Session:
    """An open connection to the keyboard's vendor Feature Report interface."""

    def __init__(self, fd):
        self.fd = fd

    @classmethod
    def open(cls):
        return cls(device.open_device())

    def close(self):
        if self.fd is not None:
            os.close(self.fd)
            self.fd = None

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        self.close()

    # --- reads ---------------------------------------------------------------

    def region_ids(self):
        """Every RegionId this keyboard reports, best source first.

        Tries LED_CMD_ID_LIST (the vendor driver's own discovery, read-only);
        falls back to sweeping 0-7 with a GET if that command does not answer,
        which is how regions 1 and 4 were originally found here. Returns
        (ids, source) so callers can say which path produced the answer instead
        of presenting a sweep as if it were the firmware's own list.
        """
        data = device.get_multipacket(
            self.fd, 0, protocol.CLASS_LIGHTING, protocol.LED_CMD_ID_LIST)
        if data:
            ids = protocol.parse_led_region_id_list(data)
            if ids:
                return ids, "LED_CMD_ID_LIST"
        return [r for r in SWEEP_RANGE if self.read_effect(r) is not None], "sweep"

    def region_attribute(self, region_id):
        """Type/FPS/matrix/effect list for one region, or None if it does not answer."""
        resp = device.command_process(
            self.fd, protocol.build_get_led_region_attribute(region_id))
        if resp is None:
            return None
        return protocol.parse_led_region_attribute_response(resp)

    def read_effect(self, region_id):
        resp = device.command_process(
            self.fd, protocol.build_get_lighting_effect(region_id))
        if resp is None:
            return None
        return protocol.parse_lighting_effect_response(resp)

    def read_brightness(self, region_id):
        resp = device.command_process(
            self.fd, protocol.build_get_lighting_brightness(region_id))
        if resp is None:
            return None
        return protocol.parse_lighting_brightness_response(resp)

    def read_region(self, region_id):
        """Everything readable about one region, or None if it does not exist."""
        info = self.read_effect(region_id)
        if info is None:
            return None
        info["brightness"] = self.read_brightness(region_id)
        return info

    def snapshot(self, region_ids=None):
        """{region_id: state} for every region that answers — what `backup` saves."""
        if region_ids is None:
            region_ids = SWEEP_RANGE
        out = {}
        for region in region_ids:
            info = self.read_region(region)
            if info is not None:
                out[region] = info
        return out

    # --- power (read-only) ---------------------------------------------------
    # On Session rather than in a module of their own: gui/controller.py opens
    # exactly one `lighting.Session` for the worker thread, so a second session
    # class would have no way to reach the GUI. The module name is now narrower
    # than what it holds; renaming it is a separate change.

    def read_battery(self):
        """Charge and charging state, or None if the device does not answer."""
        resp = device.command_process(self.fd, protocol.build_get_battery_status())
        if resp is None:
            return None
        return protocol.parse_battery_status_response(resp)

    def read_sleep(self, profile_id=protocol.DEFAULT_PROFILE_ID):
        """The idle timeout stored for one profile, or None if unanswered."""
        resp = device.command_process(
            self.fd, protocol.build_get_time_to_sleep(profile_id))
        if resp is None:
            return None
        return protocol.parse_time_to_sleep_response(resp)

    # --- writes --------------------------------------------------------------

    def set_effect(self, region_id, effect, colors, flag=0, speed=0):
        return device.command_process(
            self.fd,
            protocol.build_set_lighting_effect(
                region_id, effect, colors, flag=flag, speed=speed),
        ) is not None

    def set_brightness(self, region_id, brightness):
        """UNCONFIRMED on hardware — see build_set_lighting_brightness's docstring."""
        return device.command_process(
            self.fd,
            protocol.build_set_lighting_brightness(region_id, brightness),
        ) is not None

    def restore(self, regions):
        """Re-apply a snapshot: effect, colours, flag, speed AND brightness.

        Brightness is part of the state and has to be part of the way back.
        Leaving it out made `restore` look like it worked while the region came
        back at whatever brightness it happened to be sitting at — which, after
        an `off`, is low enough to read as "the light never came back on".

        Returns [(region_id, ok), ...] where `ok` means every write for that
        region was acknowledged, so a caller cannot report a partial restore as
        a success.
        """
        applied = []
        for region, info in regions.items():
            colors = info["colors"] or [(0, 0, 0)]
            ok = self.set_effect(region, info["effect"], colors,
                                 flag=info.get("flag", 0),
                                 speed=info.get("speed", 0))
            brightness = info.get("brightness")
            if ok and brightness is not None:
                ok = self.set_brightness(region, brightness)
            applied.append((region, ok))
        return applied
