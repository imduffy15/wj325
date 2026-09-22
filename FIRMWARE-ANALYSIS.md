# WJ325 manufacturer conversion in ESPHome

`pt1000-sensor.yaml` now uses native ESPHome ADS1115 acquisition and filters,
with the recovered temperature calculation and exact lookup table in a YAML
lambda. No external C++ files or custom components are required. The original
configuration is saved as `analysis/pt1000-sensor.before-manufacturer.yaml`.
The current revision uses **six consecutive conversions once per second** and
board-specific calibration fitted to the paired measurements below. The earlier
six-seconds-per-average version is saved as
`analysis/pt1000-sensor.before-burst-sampling.yaml`.

The calculation is reconstructed from the firmware. The first version copied
the original **bottom** unit's calibration, which gave a repeatable discrepancy
when both boards were connected to the same probe in turn. The current version
fits the ESPHome board's calibration to those paired readings at approximately
20°C and 61°C. This is relative calibration against the stock unit; independent
absolute accuracy and accuracy outside that range have not been established.

## Evidence

Source: `wj325-backup.bin`, 2,097,152 bytes.
SHA-256: `aae09986cf2059fc167e88394ab6a5796ea1afac0bd7b79bd225d4044d051fd2`.

The application image begins at file offset `0x1000`. Its executable flash
segment maps file offset `0x1010` to address `0x40201010`. Its constant-data
segment maps file offset `0x68cec` to RAM address `0x3ffe8510`.

| Finding | Firmware evidence |
| --- | --- |
| SDA GPIO12, SCL GPIO14, ADS address 0x48 | Initialization at `0x40201c90` |
| ADS1115, gain bits zero: 6.144 V full scale | Constructor at `0x4021c6e4`, called at `0x4020a7c9` |
| Single-ended channel 0, six conversions averaged | `0x40201ce0`, called by `0x40201d7c` |
| 64 SPS | Saved rate index 3 at `0xfb014`; dispatcher `0x40202164` maps to configuration bits `0x0060` |
| Reference-scaled count, then integer zero/full calibration | `0x40201d7c` and `0x40202020` |
| Nonlinear PT1000 correction | `0x40201ef0` |
| Linear interpolation of an 801-entry table | `0x40201e04`; table at `0x3ffe9152`, file `0x6992e` |

The ADS driver matches the structure of the
[Adafruit ADS1X15 implementation](https://github.com/adafruit/Adafruit_ADS1X15/blob/master/Adafruit_ADS1X15.cpp).
The [ESP8266 ROM symbol definitions](https://github.com/esp8266/Arduino/blob/master/tools/sdk/ld/eagle.rom.addr.v6.ld)
identify float arithmetic and integer conversion calls used by the firmware.
ADC configuration options were checked against the installed ESPHome 2026.9.0
source and the [ESPHome ADS1115 documentation](https://esphome.io/components/sensor/ads1115/).

## Recovered calibration

The EEPROM-emulation configuration starts at flash offset `0xfb000`, with
validity marker `0xaa`. The configuration loader at `0x402021d8` reads `0x544`
bytes into RAM at `0x3fff1490`. These are saved values, not guesses from PCB
resistor markings or generic factory defaults.

| Field | File offset | Value |
| --- | --- | --- |
| Gain_Data[0] / full-scale count | `0xfb528` | 28990 |
| Offset_Data[0] / zero count | `0xfb52c` | 1 |
| Lower range | `0xfb530` | -200°C |
| Upper range, used to select full-scale table entry | `0xfb534` | 600°C |
| PT100orPT1000 | `0xfb538` | 1, PT1000 branch |
| Rzero | `0xfb53c` | 30.0 |
| MyVref | `0xfb540` | 3.4 V, stored as float32 |

The configuration command handler independently identifies the last two names
and fields near `0x40206adc` and `0x40206b11`. No configuration commands were sent
to either device. Rzero is used in scaled table coordinates; it must not be
interpreted as a measured 30-ohm lead resistance.

## Calculation

With the averaged ADC voltage `V`, first clamp to `Vref`, then calculate:

```text
count = truncate((V / Vref) * 32767)
normalized = integer_divide((count - zero) * 32767, full - zero)

C = 106539                     # PT1000 branch constant
z = Rzero / 10
v0 = Vref * z / (C + z)
vfull = Vref * 65535 / (C + 65535)
scale = 32767 / (vfull - v0)
v = normalized / scale + v0
coordinate = v * C / (Vref - v)
```

Temperature is interpolated between the surrounding table entries, with index
zero representing -200°C and index 800 representing 600°C. Table anchors include
20890 at 0°C, 24943 at 50°C, and 65535 at 600°C. Table values are not ohms.
The YAML preserves the float operation order and integer truncation.

For illustration, an input of 1.545 V gives approximately 62.02°C with this
profile; the previous formula gave 57.24°C. Neither is a live observation or a
validation against a thermometer.

The stock normalized-zero branch changes Rzero. It is unreachable with the
recovered zero=1 calibration after the ADC lower-limit check, and is omitted.
The lambda specifically implements this dump's PT1000 / 600°C profile, not
arbitrary PT100 modes or configurable upper ranges.

## Deliberate ESPHome adaptations

- Use the native ADS1115 driver, 16-bit resolution, 6.144 V range, 64 SPS and
  single-shot mode. Retain the existing confirmed I²C pins and address.
- Average six samples using the native moving-average filter. An ESPHome
  interval and repeat action now trigger six consecutive conversions once per
  second. Stock takes six consecutive conversions in its main loop; the
  per-batch scheduling and driver overhead still differ. The first deployed
  version spaced samples one second apart; the diagnostic removes that spacing.
- Use ESPHome's native voltage scaling. Its float arithmetic order differs
  slightly from the stock ADC driver; a quantization-boundary difference is
  possible. This is not a bit-for-bit firmware emulator.
- Report ADC counts <=99 or >32667 and table-range faults as NaN/unavailable.
  Stock instead returns approximately +/-888.889 or +/-666.66. Preserve its
  narrow high-end plateau: coordinates above 65535 through 65635 return 600°C.
- Retain availability monitoring, Wi-Fi/API/OTA, web access and diagnostics.
  Measurement continues without a Home Assistant connection.
- Store the lookup table in program flash with PROGMEM.

The 6.144 V setting is the ADC's gain/full-scale selection, not permission to
apply 6.144 V to a board powered at a lower voltage.

## Validation and next check

Run `uv run --with pyyaml python tests/check_conversion.py`. The test extracts
the actual lambda from the YAML and compiles it with a host C++ compiler. It
checks all 801 table entries and the calibration bytes against the dump,
nonfinite/invalid inputs, and 32,768 positive ADC codes against an independently
rearranged divider equation and table interpolation. Maximum observed difference
was 0.000214°C. This validates the transcription/math, not hardware calibration.

The YAML is compiled with ESPHome 2026.9.0 in the existing Kubernetes instance.
The updated calibration is staged in the dashboard at `/config/pt1000-sensor.yaml`
for the user to install. No firmware is installed automatically. The prior
dashboard YAML is backed up at
`/config/backups/pt1000-sensor.before-board-calibration-20260922.yaml.bak`.

Physical verification should use the same known resistance or the same probe
in stable conditions on each unit in turn. The two-wire arrangement also includes
lead resistance in the measured circuit. Keep the manufacturer's required
two-wire terminal bridge; firmware cannot supply the missing electrical link.

Neither device was initially reachable. Subsequent live same-probe comparisons
are recorded in `analysis/probe-comparison-2026-09-22.md`; those established
approximately a 3°C difference near 60°C between the two devices.


## Stock serial diagnostics discovered after comparison

Disassembly of `0x40207924` shows that JSON generation also prints a diagnostic line to the serial object at `0x3fff2170`: `adc0:<integer>,volts0:<two decimals>,temp:<two decimals>`. The strings are at `0x3ffe8a70`, `0x3ffe8a76`, and `0x3ffe8a7f`. The integer is read from `0x3fff19f4`, the reference-scaled count produced by `0x40201d7c`, before zero/full-scale correction; it is not the original ADS1115 count. Voltage comes from `0x3fff19d4`, temperature from `0x3fff19f0`. Setup at `0x402039b4` initializes the same serial object at 115200 baud (`0x1c200`).

Capturing this line while the stock unit measures the probe allows direct testing of the recovered count-to-temperature calculation against a stock measurement on the same hardware. Use the integer `adc0` rather than the voltage rounded to two decimals. This removes cross-board analogue differences from that particular software comparison. The serial output has been identified statically but has not yet been captured on hardware.

## Instruction-level validation without serial access

Run `uv run --with r2pipe --with pyyaml python tests/check_firmware_instructions.py`.
Requires radare2 and a host C++ compiler. Results are saved in
`analysis/instruction-validation.json`.

This restricted interpreter decodes the actual Xtensa instructions from the
verified dump. It executes the ADC constructor, saved-rate dispatcher,
conversion register setup, six-reading voltage averaging, reference scaling,
integer calibration, nonlinear conversion and table interpolation. The IRAM
float division and comparison routines also execute their original instructions.
Only hardware ADC reads and known ESP8266 ROM arithmetic functions are substituted.
The ROM functions are modeled using float32/int32 arithmetic; this is not a full
ESP8266 emulator or a validation of analogue hardware, Wi-Fi or ADC bus timing.

693 ADC sequences were tested, including a broad positive-code sweep, explicit
values near the operating point, varying six-sample inputs and fault conditions.
There were 331 fault sequences; the YAML correctly maps the stock fault numbers
to unavailable. All valid outputs matched the compiled YAML lambda exactly in
these cases. Native ESPHome voltage-scaling order also produced no temperature
difference in these cases. A separate test covers 32,768 ADC inputs against the
algebraic model. These results strongly support the conversion reconstruction;
they do not prove that calibration copied between boards is valid.

The stock driver writes ADS1115 config `0xc160`, high threshold `0x8000`, low
threshold `0x0000`. This confirms AIN0/GND, gain 6.144 V, single-shot and 64 SPS.
ESPHome's equivalent measurement config is `0xc163`: the low two bits disable
comparator output. Stock configures conversion-ready signaling. Both inspected
drivers poll conversion completion over I²C. That output-pin difference is not
changed by this test, and its board-level wiring has not been established.

### Next hardware experiment: acquisition cadence only

`analysis/pt1000-sampling-test.yaml` is a standalone copy of the staged diagnostic.
Its temperature lambda is unchanged. `update_interval: never` stops periodic
ADC acquisition; an `interval: 1s` automation repeats `component.update` six
times. The existing six-sample filter then publishes once per burst, with no
additional smoothing stage. The generated C++ was checked to contain only one
six-sample averaging filter and the timeout filter.

A native 64 SPS conversion waits 17 ms plus bus overhead, so six calls occupy
roughly 0.1–0.15 seconds. A long-operation log warning may occur for the interval
handler. The test uses native ESPHome YAML components/actions and requires no
additional C++ file. It is not claimed to fix the offset: different sampling
could change noise pickup, and the test determines whether it also changes the
mean. Compare the mean and fluctuation after installation with the saved
boiler-off baseline, keeping heating and water use unchanged. Do not apply a
fixed temperature offset from this single operating point.

## Board-specific two-point calibration

The user requested applying the next calibration step after the bottom-probe
comparison. The fit uses the same physical probe and leads for each paired
stock/ESPHome comparison, with separate probes at the two tank positions:

| Point | ESPHome mean voltage | Stock reference | Previous ESPHome | Predicted with new calibration |
| --- | ---: | ---: | ---: | ---: |
| Bottom | 1.36859998 V | 20.09°C | 17.67°C | 20.09°C |
| Top | 1.53155682 V | 61.45°C | 58.53°C | 61.45°C |

The top input uses the final 60 paired voltage readings before the stock swap;
the bottom uses all 180 paired readings from its stable capture. The exact
sources, sample counts and fit results are in `analysis/board-calibration-fit.json`.
Run `uv run --with pyyaml python tests/fit_board_calibration.py` to reproduce it.
That script does not update the device or YAML.

The method inverts the stock RTD interpolation and nonlinear divider to estimate
two calibration count parameters. It then searches nearby integer values using
the actual compiled YAML lambda over the saved voltage samples, retaining the
firmware's integer quantization and float operation order. Both temperature
points receive equal weight. The selected parameters are:

- `zero = 13` (previously 1, copied from stock)
- `full = 28767` (previously 28990, copied from stock)
- Vref remains 3.4; Rzero remains 30; the RTD table and nonlinear conversion are unchanged.

Only these two coefficients and explanatory comments change in the staged
configuration. Six-conversion burst acquisition stays enabled. The previous
version is saved in `analysis/pt1000-sensor.before-board-calibration.yaml` and in
the dashboard backup named above. The separate `pt1000-sampling-test.yaml` is a
historical diagnostic with the old calibration, not the current install target.

Validation: 32,768 input codes against the independent mathematical model, and
693 sequences against the original firmware instructions with only the emulated
RAM zero/full fields changed to 13/28767. All valid instruction-model outputs
match the YAML exactly in those test cases; 332 fault sequences correctly map to
unavailable. Original-coefficient instruction results are preserved in
`analysis/instruction-validation-factory-calibration.json`.

The small numerical fit residual is not a statement of measurement accuracy.
These are sequential comparisons against another unverified instrument, with a
limited temperature span. After installation, keep the bottom probe connected
and heating off to confirm the new live reading is near the stock baseline.
A later same-probe check at an intermediate stable temperature would be a useful
independent validation; the two fit points themselves cannot establish linearity
or accuracy beyond the observed range. No firmware is flashed automatically.

## Original stock board ESPHome configuration

`pt1000-sensor-bottom.yaml` is prepared and compiled with ESPHome 2026.9.0, and
staged as a separate dashboard entry **Hot Water Tank Bottom**. It uses the
original board's recovered zero=1/full=28990 calibration, not the top board's
fitted values. Its temperature lambda matches the pre-fit stock-mirror lambda.
The hostname is `hot-water-tank-bottom`; sensor IDs are scoped to this firmware.
No flash operation has been performed on the stock device.

The dump contains `/update` (authenticated update UI) and `/startUpdate`
(update action). The extracted UI is saved in `analysis/stock-update-page.html`.
It invokes `startUpdate?id=update&value=...&ver=...`; this is not evidence of an
ESPHome-compatible OTA upload endpoint. No update action was called. First
installation using the existing FTDI/serial method is the established route;
wireless migration through the factory updater needs separate verification.

For eventual boiler-demand automation, the observed calibrated fluctuation
(standard deviation about 0.09°C at the bottom) is compatible with using
separate demand-on/demand-off thresholds and a sustained below-threshold timer.
No boiler automation or temperature setpoint has been configured. Thresholds,
minimum cycling times, missing-data handling and restart/recovery behavior
should be designed around the existing boiler controls; a sensor graph need
not be perfectly flat to make reliable demand decisions.

### Live factory update endpoint inspection

At the user's request, GET `/update` was tested. It returned HTTP 401 with
Digest authentication; using the credentials referenced by the firmware's own
handler returned HTTP 200. Credentials are deliberately omitted from this report.
The live page exactly matches the extracted `analysis/stock-update-page.html`.

The page offers manufacturer versions (latest, V1.20, V1.10, V1.00), with no file
upload or arbitrary firmware URL field. It calls `/startUpdate` with `id=update`,
`value=1`, and the version. The handler at `0x40209d0c` uses the URL pointer at
`0x3ffe84e0`, which resolves to `0x3ffe9116`:
`http://www.wayjun.cn/wayjunUpdate/WJ325.bin`. A nonzero version inserts a version
suffix before `.bin`. The URL is passed through `0x40208100` to the updater.

No `/startUpdate` action was called and no firmware was flashed. Using the page
normally fetches manufacturer firmware, not the prepared ESPHome image. A local
redirect of the download would be a separate migration approach requiring
validation of the updater and a narrowly scoped network change; no DNS or
routing settings have been changed.


### Successful wireless migration (2026-09-22)

After the user redirected `www.wayjun.cn` to this host, `192.168.20.235`,
we served the compiled bottom-board ESPHome 2026.9.0 OTA image at
`/wayjunUpdate/WJ325.bin` and invoked the authenticated stock
`/startUpdate?id=update&value=1&ver=0` endpoint.
The first request was rejected before image delivery because inter-VLAN NAT
made its source address appear as `192.168.20.254`. The retry allowed that route
and checked the device MAC, sketch update mode, free space and physical flash
capacity before returning the image with Content-Length and x-MD5.

The stock updater reported 524288 bytes free sketch space, 435552 bytes current
sketch size, and 2097152 bytes physical flash. The delivered image is 425616 bytes,
SHA256 `2b2ca9d0ff78ad30b10509e4cc9fa0d5d2eafcc497241d19557d58409f5a95af`.
The complete transfer is recorded in `analysis/stock-wireless-migration-server.log`.

After reboot, mDNS advertised ESPHome 2026.9.0, board esp_wroom_02, MAC
D8:BC:38:82:31:6C, hostname hot-water-tank-bottom, friendly name Hot Water Tank
Bottom, API port 6053 and IP 10.0.30.122. The ESPHome web event stream confirmed
working ADS1115 acquisition. With the probe apparently still disconnected,
voltage was approximately 3.3806 V, temperature unavailable and Measurement
Problem ON, consistent with the stock unit's pre-flash fault value of 666.66.
A connected-probe temperature check remains to be done.

The dashboard `/config/pt1000-sensor-bottom.yaml` matches the local YAML
(SHA256 ff540bb819f5b3a6ad8614fe934c4edea9655926c4bb016baa98c7131e156f7f).
The temporary HTTP firmware server has been stopped. The user's DNS override
can now be removed; future updates use native ESPHome OTA. The original flash
backup remains unchanged. Earlier statements above that no flash occurred
refer to the preparation and inspection stages, before this successful migration.

After the user connected the bottom probe, a 20-second live web-event check
confirmed Measurement Problem OFF and valid temperature: 21 samples, mean
19.799°C, range 19.583–19.893°C, last displayed 19.87°C; last voltage
1.377625 V. This confirms connected-probe acquisition after migration, not
an independent absolute-temperature calibration.

## Public repository and Home Assistant deployment

The public repository includes `firmware/wj325-stock.bin`: the exact first
435552 bytes of the private backup (bootloader and application). Saved device
settings and SDK sectors are excluded. Only the documented numeric calibration
fields are included separately in `firmware/calibration.json`. The original
`wj325-backup.bin` is retained locally and ignored by Git. Tests now reconstruct
the required calibration fixture without loading personal settings. See
`firmware/README.md` for the intentionally documented hardcoded updater login.

Current and historical YAML configurations reference `!secret wifi_ssid` and
`!secret wifi_password`. No conversion or acquisition behavior was changed by
that substitution. Both current configurations pass ESPHome 2026.9.0 validation.
The 32768-input numerical comparison and 693-sequence instruction comparison
also pass using the public firmware and calibration fixture.

Home Assistant entity IDs now consistently use `hot_water_tank_top_` and
`hot_water_tank_bottom_`. The former top temperature ID
`sensor.pt1000_sensor_pt1000_temperature` was renamed to
`sensor.hot_water_tank_top_pt1000_temperature` through the entity-registry API.
The old immersion-maintenance automation was replaced at the owner's request.
The deployed `home-assistant/hot_water.yaml` package requests heat after two
minutes continuously below 45°C and clears demand at 60°C, with adjustable
thresholds and invalid-input handling. It currently drives only a request
helper; no boiler actuator is connected. Enable and request reset off after a
Home Assistant restart. This is not a whole-cylinder hygiene cycle.

An isolated instance using the installed Home Assistant runtime tested the
actual two-minute delay, cancelled short dips, hysteresis, the stop threshold,
unavailable/fault inputs, invalid thresholds and disabling. No live device
states were simulated and no heating outputs were operated during testing.
Live readings after deployment were approximately 61.9°C top and 20.0°C bottom,
with both measurement fault flags off and heating request off.
