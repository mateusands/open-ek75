# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 Mateus Andrade
"""Talking to the keyboard over hidraw (I/O). No external dependencies.

The device does not declare a Report ID in its HID descriptor for the vendor
Feature Report (interface 3 in the descriptor this was reverse-engineered
against — see PROTOCOL.md). Linux's hidraw still requires a report-number
prefix byte on HIDIOCSFEATURE/HIDIOCGFEATURE even when the device has none, so
every buffer here is REPORT_SIZE + 1 bytes, with byte 0 fixed at 0x00.
"""
import fcntl
import glob
import os
import time

from . import protocol
from .protocol import REPORT_SIZE, HDR_STATUS, is_response_ready

VID = 0x260D
PID = 0x0101

# The keyboard exposes 5 HID interfaces; only one carries the vendor Feature
# Report this protocol uses. Identify it by its report descriptor rather than
# a hardcoded interface number, which is not guaranteed stable across firmware
# revisions or even across the sibling PIDs this protocol family covers.
_VENDOR_USAGE_PAGE = b"\x06\x00\xff"   # Usage Page (Vendor-Defined, 0xFF00)


def _ioc(direction, type_char, nr, size):
    return (direction << 30) | (size << 16) | (ord(type_char) << 8) | nr


def _hidiocsfeature(size):
    return _ioc(3, 'H', 0x06, size)   # _IOC_WRITE | _IOC_READ


def _hidiocgfeature(size):
    return _ioc(3, 'H', 0x07, size)


def _report_descriptor_path(hidraw_path):
    """/dev/hidrawN -> its sysfs report_descriptor file, or None."""
    name = os.path.basename(hidraw_path)
    for uevent in glob.glob(f"/sys/class/hidraw/{name}/device/../report_descriptor"):
        return uevent
    return None


def _looks_like_vendor_feature_report(desc_path):
    try:
        with open(desc_path, "rb") as f:
            desc = f.read()
    except OSError:
        return False
    # A Feature item (0xB1) inside a Vendor-Defined (0xFF00) usage page, with
    # Report Count 64 (0x95 0x40) — see PROTOCOL.md for the full decode.
    return _VENDOR_USAGE_PAGE in desc and b"\x95\x40\xb1" in desc


def find_device():
    """The /dev/hidrawN path for this keyboard's vendor Feature Report interface.

    Returns None if the keyboard is not connected or the right interface was
    not found. Raises nothing — callers decide how to report absence.
    """
    # HID_ID in the uevent is "bus:vendor:product", each zero-padded to 8 hex
    # digits (e.g. "0003:0000260D:00000101") — not the 4-digit form lsusb uses.
    needle = f"{VID:08X}:{PID:08X}".upper()
    for path in sorted(glob.glob("/dev/hidraw*")):
        uevent_path = f"/sys/class/hidraw/{os.path.basename(path)}/device/uevent"
        try:
            with open(uevent_path) as f:
                uevent = f.read()
        except OSError:
            continue
        if needle not in uevent.upper():
            continue
        desc_path = f"/sys/class/hidraw/{os.path.basename(path)}/device/report_descriptor"
        if _looks_like_vendor_feature_report(desc_path):
            return path
    return None


def _set_feature(fd, packet64):
    buf = bytearray(1 + REPORT_SIZE)
    buf[1:] = packet64
    fcntl.ioctl(fd, _hidiocsfeature(len(buf)), buf, True)


def _get_feature(fd):
    buf = bytearray(1 + REPORT_SIZE)
    fcntl.ioctl(fd, _hidiocgfeature(len(buf)), buf, True)
    return bytes(buf[1:1 + REPORT_SIZE])


def command_process(fd, packet, retries=20, delay=0.01):
    """Send a Feature Report request, then poll for its reply.

    Port of tgdevice.js `CommandProcess`: the device does not answer
    synchronously, so GET_FEATURE is retried a few times until the status
    nibble signals readiness. Returns the 64-byte reply, or None on timeout.
    """
    _set_feature(fd, packet)
    for _ in range(retries):
        reply = _get_feature(fd)
        if is_response_ready(reply):
            return reply
        time.sleep(delay)
    return None


def open_device():
    """Open the keyboard's vendor interface for read/write, or raise FileNotFoundError."""
    path = find_device()
    if path is None:
        raise FileNotFoundError(
            "Dareu TK51G/EK75 keyboard not found (VID 260D PID 0101). "
            "Is it connected by USB cable? (RGB configuration does not work "
            "over the 2.4G wireless dongle on this model.)"
        )
    return os.open(path, os.O_RDWR)


# How long the link needs to be quiet after a run of commands before a read
# reports the keyboard's real state.
#
# Writes are never lost — three bursts of 24 rapid alternating writes each ended
# in the state last written. What trails is the *reading* side while a burst is
# in flight. Measured after a 24-command burst, counting first reads that
# returned an earlier state: 4/8 wrong at 0 ms, 4/8 at 50 ms, 0/8 at 100, 200
# and 300 ms.
#
# 100 ms is the measurement — 8 trials, one unit, CLASS_LIGHTING. 150 ms is that
# plus a margin, and the margin is a judgement call about variance rather than
# something anyone measured. If another unit needs more, the symptom is a read
# that trails and the number has exactly one home.
SETTLE_AFTER_BURST = 0.15


def settle():
    """Leave the link quiet long enough for the keyboard to catch up.

    Belongs here rather than in the service layer: how long this bus needs is a
    property of the hardware link, which is what this module owns. Callers that
    issue a run of commands call it; callers that issue one do not need to, an
    isolated write followed by an immediate read having been correct 30/30.
    """
    time.sleep(SETTLE_AFTER_BURST)


def get_multipacket(fd, profile_id, cmd_class, command, args=b"", width=1,
                     retries=20, delay=0.01):
    """Read a reply too large for one 64-byte report.

    Port of tgdevice.js `GetMultiPacketCmd`: probe for the total length, then
    pull it back in MULTIPACKET_BLOCK-sized chunks. Read-only — every command
    that uses this (LED_CMD_ID_LIST, PFL_CMD_ID_LIST, macro data) is a GET.

    Confirmed end to end on hardware via LED_CMD_ID_LIST, which is the only
    caller so far; the profile list and macro data use the same mechanism.

    Returns the assembled bytes, or None if any step timed out.
    """
    probe = protocol.build_multipacket_probe(profile_id, cmd_class, command, args)
    resp = command_process(fd, probe, retries=retries, delay=delay)
    if resp is None:
        return None
    total = protocol.parse_multipacket_total(resp, nargs=len(args), width=width)
    if total == 0:
        return b""

    data = bytearray(total)
    data_at = protocol.multipacket_chunk_offset(nargs=len(args), width=width)
    offset = 0
    while offset < total:
        chunk_len = min(protocol.MULTIPACKET_BLOCK, total - offset)
        pkt = protocol.build_multipacket_chunk(
            profile_id, cmd_class, command, total, offset, chunk_len,
            args=args, width=width)
        resp = command_process(fd, pkt, retries=retries, delay=delay)
        if resp is None:
            return None
        data[offset:offset + chunk_len] = resp[data_at:data_at + chunk_len]
        offset += chunk_len
    return bytes(data)
