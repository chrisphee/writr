# writerdeck

A minimal, distraction-free **modal (vim-style) text editor** for a DIY e-ink
writing machine. It runs fullscreen on a Raspberry Pi's Linux console (no
X/Wayland), takes input from a Bluetooth keyboard via `evdev`, and renders to a
**Waveshare 4.26" e-Paper HAT (800×480, SPI)**.

Inspired by [ZeroWriter](https://github.com/zerowriter/zerowriter1) (concept) and
built on [Waveshare's](https://github.com/waveshareteam/e-Paper) `epd4in26`
driver. This is a clean rewrite for the **4.26"** panel — it does **not** use the
4.2"-panel drivers bundled in `e-Paper/`.

## Status

Milestones **M1 (type-and-see loop)**, **M2 (modal editing)**, and **M3 (refresh
tuning)** are implemented and tested: evdev keyboard → modal state machine → text
buffer → refresh decision → renderer → display (PNG mock for development, real
panel on the Pi). Files/autosave (M4) is next.

The editor launches in NORMAL, like vim:

- **NORMAL** — motions `h j k l`, `w b e`, `0 $`, `gg G`; edits `x`, `dd`; enter
  INSERT with `i a A I o O`. Refresh is **per action** (instant feedback), and a
  command that changes nothing (a motion into a wall) skips the refresh so the
  e-paper isn't redrawn for nothing.
- **INSERT** — text entry; `Esc` returns to NORMAL.

The e-paper refresh strategy is the heart of the project: while typing in INSERT
mode there is **no per-keystroke refresh**. A partial refresh fires on a word
boundary (space / Enter) or after a short typing pause (debounce, default
400 ms) — whichever comes first. (Word motions use simplified whitespace-word
semantics; vertical motion clamps the column rather than remembering it.)

**Refresh tuning (M3).** Partial refreshes accumulate ghosting, so every Nth
refresh (`full_refresh_every`, default 30) is promoted to a full,
ghosting-clearing refresh. Timings are configurable in [config.py](config.py)
(`debounce_ms`, `full_refresh_every`). The vendored `epd4in26.display_Partial`
resets the panel window to full-screen and writes the whole framebuffer, so it
does **not** expose arbitrary-region partial updates — the editor therefore uses
full-frame partials, which the panel handles in ~0.7s.

## Architecture

```
editor/    buffer, modal state machine, refresh policy, layout, frame — pure, no deps
input/     keymap + key decoder (pure) · evdev_source (hardware)
display/   Display ABC · mock (PNG + logs) · epd4in26 (real panel)
render.py  Frame → PIL.Image (the only editor module that imports PIL)
app.py     the event loop (Editor): key → ModalEditor → refresh decision
main.py    entry point: picks the backend, runs the loop
config.py  panel size, font, debounce, etc.
waveshare_epd/  vendored upstream epd4in26 + epdconfig (Waveshare, MIT)
```

The editor core speaks plain data (a `Frame`), never pixels, so the whole loop is
unit-tested with no PIL and no hardware. Only `render.py` and the display
backends touch PIL; only `display/epd4in26.py` and `input/evdev_source.py` touch
the Pi.

## Develop (any laptop)

```bash
python3 -m venv .venv
.venv/bin/python -m pip install pytest pillow

.venv/bin/python -m pytest -q          # run the test suite
.venv/bin/python tools/preview.py      # render sample frames to ./mock_frames/
.venv/bin/python tools/preview.py "your sentence here"
```

`tools/preview.py` drives the real editor loop through the PNG mock, so you can
eyeball rendering and see the refresh log without any hardware. The pure-logic
tests (buffer, refresh, keymap, decoder, layout, loop) import nothing beyond the
stdlib and project code, so they run with **pytest alone — Pillow is not
required**; the single renderer test auto-skips when Pillow is absent.

## Deploy on the Raspberry Pi

Target: Raspberry Pi (Zero WH / Zero 2 W) running Raspberry Pi OS Lite
(Bookworm), SPI enabled (`raspi-config` → Interface → SPI, or `dtparam=spi=on`).

Install dependencies via apt (no slow pip source-builds on ARMv6):

```bash
sudo apt install python3-pil python3-evdev python3-spidev python3-gpiozero python3-lgpio
```

> **Dependency note (verified against the driver source):** the current upstream
> `epdconfig.py` drives GPIO through **`gpiozero`** (with the `lgpio` pin factory
> on Bookworm) and SPI through `spidev` — it does **not** import `RPi.GPIO`, so
> `python3-rpi-lgpio` is not required by this driver. `python3-numpy` is not used
> yet (it may help speed up framebuffer packing in a later milestone).

Then pull and run:

```bash
cd ~/writerdeck
git pull
python3 main.py            # auto-detects the Pi and uses the epd4in26 panel
python3 main.py -v         # same, logging each refresh
python3 main.py --backend mock   # force the PNG mock (writes ./mock_frames/)
```

The Bluetooth keyboard is auto-discovered among `/dev/input/event*`. If it sleeps
and its device node disappears, the editor keeps polling and reconnects when it
wakes — it will not crash on a vanished device.

## Credits & licensing

- Concept inspired by **ZeroWriter** (and Penkesu before it).
- `waveshare_epd/` contains **Waveshare's** `epd4in26.py` and `epdconfig.py`,
  copied verbatim from the upstream `waveshareteam/e-Paper` repo with their MIT
  headers intact. All Waveshare code belongs to them — buy their displays.
- This project's own code is under the repository's [LICENSE](LICENSE).
