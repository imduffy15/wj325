# WJ325 PT1000 sensors with ESPHome

Reverse-engineering notes, firmware evidence and native ESPHome configurations
for two WJ325 boards measuring a hot-water tank with two-wire PT1000 probes.
Tested with ESPHome **2026.9.0** and Home Assistant **2026.9.3**.

Both boards now run ESPHome. Acquisition uses the native ADS1115 component,
six consecutive conversions once per second, and ESPHome filters. The recovered
manufacturer conversion and exact 801-entry lookup table live in a YAML lambda;
there are no external C++ components.

## Configurations

| File | Device | Calibration zero / full |
| --- | --- | --- |
| [pt1000-sensor.yaml](pt1000-sensor.yaml) | Hot Water Tank Top | 13 / 28767, fitted against the other board |
| [pt1000-sensor-bottom.yaml](pt1000-sensor-bottom.yaml) | Hot Water Tank Bottom | 1 / 28990, recovered from this board's stock configuration |

These coefficients belong to the individual boards, not the probe locations.
Do not copy them blindly to another WJ325. Agreement with the stock unit is a
relative calibration; it does not establish absolute accuracy. The original
paired measurements were around 20°C and 61°C.

Copy `secrets.example.yaml` to `secrets.yaml` and supply your Wi-Fi credentials.
Keep the secret file alongside the active configurations in ESPHome. Validate
and compile the configuration for the intended board before flashing it.
Historical YAML files in `analysis/` are evidence, not deployment targets.

The stock board was successfully migrated wirelessly through its manufacturer
updater. See [firmware/README.md](firmware/README.md) for the endpoint credentials,
DNS-redirection procedure and image compatibility checks.

## Notes and evidence

- [Firmware analysis](FIRMWARE-ANALYSIS.md): addresses, conversion, sampling,
  per-board calibration, validation and successful migration.
- [PCB notes](PCB-NOTES.md): inspection of the twelve included PCB photographs.
- [Probe comparisons](analysis/probe-comparison-2026-09-22.md): chronology of the
  controlled comparisons, including early measurements confounded by heating.
- [Manufacturer English manual](WJ325-EN.pdf) and [Chinese manual](WJ325.pdf).
- `analysis/`: recorded measurements, extracted executable/data segments,
  disassembly, fitting results and historical configurations.
- [Stock firmware](firmware/README.md): executable image and numeric calibration
  with personal saved settings excluded.
- [Home Assistant package and dashboard](home-assistant/README.md): consistent
  entity IDs, heating-request automation, and a Slate tank widget with a live
  top-to-bottom colour gradient.

The detailed notes are chronological. Later findings supersede early hypotheses
and statements that a flash or calibration had not yet been performed.

## Validation

Requires Python, `uv`, a host C++ compiler, and radare2 for the instruction check:

```sh
uv run --with pyyaml python tests/check_conversion.py
uv run --with r2pipe --with pyyaml python tests/check_firmware_instructions.py
uv run --with pyyaml python tests/fit_board_calibration.py
```

The numerical check covers 32,768 ADC inputs. The restricted instruction
interpreter executes the original conversion instructions for 693 sequences,
including invalid inputs. It is not a complete ESP8266 emulator.
Tests reconstruct only the required calibration bytes from the public numeric
fixture; the private full-flash backup is not required.

`tests/check_heating_demand.py` exercises the actual Home Assistant package in
an isolated instance using an installed Home Assistant Python environment.
It does not communicate with the live devices or operate heating.

## Privacy and provenance

The original `wj325-backup.bin` remains local and is ignored by Git because it
contains saved settings. The published stock image preserves the bootloader
and application bytes exactly; it excludes everything after the application,
including the EEPROM-emulation and SDK configuration sectors. Numeric
calibration is published separately through an explicit allowlist.

The stock updater's hardcoded authentication credentials are intentionally
documented. Personal Wi-Fi credentials are not included. Do not add full device
backups or `secrets.yaml` to the repository.

Manufacturer firmware and manuals are third-party material, retained here as
technical reference. No new license is asserted over that material.
