# Runtime data

`0101.json` is a copy of `docs/vendor-reference/0101.json` — Dareu's own device
profile for PID `0101`, fetched from
`https://dr.dareu.com/products/0101/0101.json`.

It lives here as well as under `docs/` because the GUI needs it **at runtime**,
not just as reference: it supplies the physical key layout (83 keys with pixel
geometry, which is how `gui/keyboard_view.py` draws the keyboard) and the
per-region `CustomEffectList` used as a fallback when the keyboard's own
`LED_CMD_ATTRIBUTE` reply is unavailable.

Keep the two copies in sync. `docs/vendor-reference/README.md` explains how to
re-fetch it, and adding a new PID means dropping its `<PID>.json` in here too.
