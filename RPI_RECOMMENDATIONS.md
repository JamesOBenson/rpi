# Raspberry Pi Performance Recommendations

General tuning guide for getting the most out of a Raspberry Pi (written
for Pi 5 8GB; notes where Pi 4 differs). Ordered by payoff — the top items
are worth more than everything below them combined.

Verified context (our Pi, Oct 2025): CPU-bound workload using ~5GB RAM,
throttles at ~80°C, idled at 63°C before cooling was addressed, uses
~1.4GB swap, 45W PSU.

---

## 1. Cooling — the single biggest lever

A Pi that hits its ~80°C thermal ceiling loses **~20%+** sustained CPU
performance (measured: LLM decode drops ~20% hot vs. idle-temperature).
Check your board first:

```bash
vcgencmd measure_temp           # current SoC temperature
vcgencmd get_throttled          # 0x0 = healthy; see bit table below
```

`get_throttled` bit reference (hex OR of active conditions):

| Bit | Meaning |
|-----|---------|
| 0x01 | Throttled for temperature (currently) |
| 0x02 | Undervoltage has occurred |
| 0x08 | Throttled for temperature (ever, this boot) |
| 0x10 | Throttled due to SD card read errors |
| 0x20 | Undervoltage (currently) |
| 0x8000 | Throttled for temperature (ever) |

If it idles above ~50°C under light load, the board is running uncooled.

**What to do (in order of value):**
1. **Active fan** — official Active Cooler, or a 40mm fan (e.g., Noctua
   NF-A4x10) on top of the CPU heatsink. This is the part that matters.
2. **Heatsink** on the SoC (and ideally the power rail next to it) —
   passive alone does little on Pi 5, but it's the mount for the fan.
3. **Airflow** — vented or no case; a sealed case acts as an oven.
4. **Orientation** — keep the SoC's top surface clear of anything.

Target: < 65°C sustained under load. Re-benchmark before/after — the
difference is directly measurable.

## 2. Power supply

- **Minimum: official 27W (5V/5A) USB-C** for Pi 5. More is fine (a 45W
  brick is perfectly OK — the Pi draws what it needs).
- Under-powered boards don't just crash — they *silently* cap performance
  (undervoltage bits in `get_throttled`) and can corrupt SD cards.
- Check: `vcgencmd get_throttled` — any undervoltage bits mean the supply
  or cable can't keep up under load.
- **Use the short cable that came with it** — long/thin USB-C cables drop
  volts under load.

## 3. Storage

**SD card speed** affects exactly three things — model/binary reads at
startup, swap latency, and package installs. It does *not* affect
runtime/inference performance once everything is in RAM.

Check your card:

```bash
dd if=/dev/mmcblk0 of=/dev/null bs=1M count=512 iflag=direct
# under ~50 MB/s: upgrade the card
# ~100 MB/s: good A2 class, fine for most use
```

- Cheap no-name cards can read at 15-30 MB/s — a 2.9GB model file takes
  2+ minutes to load. A good A2 card loads it in ~30s.
- **NVMe (the real fix):** Pi 5's PCIe slot + NVMe HAT. Model loads in
  seconds, swap stops hurting, `pip` gets fast. Requires current EEPROM
  firmware (see §7). Pi 4 has no PCIe — on Pi 4, a fast A2 SD card is
  the ceiling.

**Swap:** keep it, but on the fastest storage you have. If the box
regularly uses swap, that's a RAM/footprint problem, not a swap-size
problem — fix the footprint first.

## 4. OS choices

- **64-bit OS, always.** On Pi 5 the 32-bit OS leaves real performance
  on the table (and drops ARMv8.6 features).
- **Headless = no desktop.** A minimal (Lite) install saves ~500MB-1GB
  RAM and a constant slice of CPU vs. the desktop image.
- **Trim services you don't use:**

  ```bash
  systemctl list-units --state=running
  # typical safe disables on a headless box (if unused):
  sudo systemctl disable --now bluetooth
  sudo systemctl disable --now avahi-daemon
  ```

- **Keep it current:** Pi 5 firmware/OS fixes (thermal, PCIe, USB power)
  landed throughout 2025. Periodically:

  ```bash
  sudo apt update && sudo apt full-upgrade
  ```

## 5. CPU tuning

**Governor** — for latency-sensitive workloads (voice assistants, servers),
pin the cores to max frequency so first-response time is predictable
instead of waiting for boost:

```bash
# one-shot
sudo cpufreq-set -g performance
# persist across reboots (raspi-config route):
sudo raspi-config   # Advanced Options > Performance Options > CPU Scheduling
```

Only do this *after* cooling is sorted — a performance governor on an
uncooled Pi just hits the throttle ceiling sooner and runs hotter.

**Mild overclock** — Pi 5 ships at 2.4 GHz. In
`/boot/firmware/config.txt`:

```
arm_freq=2600
over_voltage=4
```

+8% is commonly stable *with good cooling*. Measure it (before/after
benchmark) and back it out if temps or stability suffer. Skip
aggressive values — the thermal ceiling usually eats the gain.

**`temp_limit`** — the throttle ceiling itself is tunable. Leaving it at
the default is the right call: raising it trades longevity for peak
speed with no sustained gain.

## 6. config.txt (GPU memory)

Headless boxes don't need the firmware's default video RAM allocation:

```
# /boot/firmware/config.txt — headless only
gpu_mem=16
```

Frees hundreds of MB for the actual workload. **Do not do this if the
box uses the GPU** (desktop, video output, KMS) — 16MB will break it.

## 7. EEPROM firmware update (Pi 4B Rev 2 / Pi 5)

The board's firmware lives in EEPROM, separate from the SD card.
Older boards may run months-old firmware missing thermal, PCIe (NVMe),
and USB power fixes:

```bash
sudo rpi-eeprom-update          # show current vs. recommended
sudo rpi-eeprom-update -d       # install the stable recommended
sudo reboot
```

- **Never kill power mid-update** (it's a ~10s write) — with a healthy
  PSU this is a non-issue, but don't do it on a flaky supply.
- Required-before for NVMe HATs and some newer peripherals.
- Optional hygiene: `sudo rpi-eeprom-config -a` stores your config.txt
  in the EEPROM as a fallback bank (useful if the SD card dies).

## 8. RAM (bigger picture)

- Pi 5: 4/8/16GB variants. If a workload consistently lives in swap,
  the fix is the 16GB board (or shrinking the workload), not more swap.
- Watch it: `free -h` under real load; if `available` regularly drops
  below ~500MB you're one model-size away from swap thrash.

## 9. Offload, don't just optimize

Tuning a CPU gets you ~20%. Moving work *off* the CPU gets you 10x+:
- **Hailo-8L** for NPU inference (Whisper-class STT: 0.8s vs ~1.8s on CPU)
- **GPU (Pi 5 KMS + CANN, or a small external GPU)** for heavier inference
- Smaller/quantized models (Q4_K_M, int8) before any hardware spend

## 10. Suggested order of operations

Each step independently measurable — benchmark before/after each one:

1. `sudo rpi-eeprom-update -d && sudo reboot` (free, fixes foundations)
2. Baseline: `get_throttled` + a workload benchmark
3. Add cooling (fan + heatsink) → re-benchmark — **expect the biggest jump here**
4. `gpu_mem=16` if headless → re-check `free -h`
5. Governor `performance` → re-benchmark
6. Optional: mild overclock → re-benchmark, revert if not a clear win
7. Storage: check card speed → upgrade card or move to NVMe
8. Trim unused services

## Quick health check (copy-paste)

```bash
echo "--- temp ---";       vcgencmd measure_temp
echo "--- throttled ---";  vcgencmd get_throttled
echo "--- freq ---";       vcgencmd get_arm
echo "--- eeprom ---";     rpi-eeprom-update --show 2>/dev/null | grep -m1 CURRENT || sudo rpi-eeprom-update | head -2
echo "--- mem ---";        free -h | head -2
echo "--- card speed ---"; dd if=/dev/mmcblk0 of=/dev/null bs=1M count=512 iflag=direct 2>&1 | tail -1
```