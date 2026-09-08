#!/bin/sh
#
# open-ek75 — system integration installer.
#
# Installs one file and nothing else:
#   /etc/udev/rules.d/60-ek75.rules   device access for the logged-in user
#
# It does NOT install the Python package; use pip for that (see README.md).
#
# Usage:
#   sudo sh packaging/install.sh
#   sudo sh packaging/install.sh --uninstall
#
set -eu

UDEV_RULE_NAME="60-ek75.rules"
UDEV_RULE_DIR="/etc/udev/rules.d"
UDEV_RULE_DEST="$UDEV_RULE_DIR/$UDEV_RULE_NAME"

# Older versions of this project installed the rule as 99-ek75.rules, which
# never worked: udev runs rule files in filename order and systemd applies the
# uaccess ACL from 73-seat-late.rules, so a tag set at 99 arrives too late.
# See the comments in 60-ek75.rules. Clean the stale file up on install.
LEGACY_RULE_DEST="$UDEV_RULE_DIR/99-ek75.rules"

# Directory holding this script, so it works from anywhere.
SRC_DIR=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)

say() { printf '%s\n' "$*"; }
die() { printf 'error: %s\n' "$*" >&2; exit 1; }

usage() {
    cat <<EOF
open-ek75 system integration installer

  sudo sh $0              install the udev rule
  sudo sh $0 --uninstall  remove it
  sh $0 --help            this message

File touched:
  $UDEV_RULE_DEST
EOF
}

require_root() {
    if [ "$(id -u)" -ne 0 ]; then
        die "this needs root to write to /etc — re-run with sudo"
    fi
}

install_file() {
    src=$1
    dest=$2
    [ -f "$src" ] || die "missing source file: $src"
    if [ -f "$dest" ] && cmp -s "$src" "$dest"; then
        say "  unchanged  $dest"
        return 0
    fi
    if [ -f "$dest" ]; then
        say "  updating   $dest"
    else
        say "  installing $dest"
    fi
    install -D -m 0644 "$src" "$dest"
}

remove_file() {
    dest=$1
    if [ -f "$dest" ]; then
        say "  removing   $dest"
        rm -f "$dest"
    else
        say "  absent     $dest"
    fi
}

reload_udev() {
    if ! command -v udevadm >/dev/null 2>&1; then
        say "  udevadm not found — reload udev yourself, or replug the keyboard"
        return 0
    fi
    say "  reloading udev rules"
    udevadm control --reload-rules
    say "  triggering hidraw subsystem"
    udevadm trigger --subsystem-match=hidraw
}

do_install() {
    require_root
    say "open-ek75: installing system integration"
    install_file "$SRC_DIR/$UDEV_RULE_NAME" "$UDEV_RULE_DEST"
    if [ -f "$LEGACY_RULE_DEST" ]; then
        say "  removing   $LEGACY_RULE_DEST (superseded — it ran too late to work)"
        rm -f "$LEGACY_RULE_DEST"
    fi
    reload_udev
    say ""
    say "Done. Replug the keyboard so the new rule applies, then:"
    say "  python3 main.py regions"
}

do_uninstall() {
    require_root
    say "open-ek75: removing system integration"
    remove_file "$UDEV_RULE_DEST"
    remove_file "$LEGACY_RULE_DEST"
    reload_udev
    say ""
    say "Done."
}

case "${1-}" in
    ""|--install)   do_install ;;
    --uninstall)    do_uninstall ;;
    -h|--help)      usage ;;
    *)              usage >&2; die "unknown option: $1" ;;
esac
