# WJ325 PCB photo inspection

Inspected all 12 supplied images on 2026-09-21. No firmware or configuration
changes were made as part of this inspection.

## Identified parts

| Part | Finding | Evidence / confidence |
| --- | --- | --- |
| ESP module | Espressif ESP-WROOM-02U | Shield marking is clearly legible in `2025-02-23_15-01-44_875.jpeg`. Consistent with the existing ESP8266 `esp_wroom_02` board selection. |
| U1 | TI TLV376 single precision op-amp, SOIC-8 | `TLV / 15M` marking is legible in the same photo and `2025-02-23_15-02-20_078.jpeg`. TI's package marking table assigns this marking to TLV376IDR. |
| U3 | Candidate ADS1115 / related ADC | Underside 10-pin package, surrounding traces, and working ADS1115 firmware support this hypothesis. Marking is too faint to confidently transcribe; exact part remains unconfirmed. Best views: `2025-02-23_15-02-44_711.jpeg` and `2025-02-23_15-03-02_508.jpeg`. |
| LED1 and S1 | LED and switch locations visible | GPIO connections and LED polarity have not been established. |
| PCB label | Visible suffix `321`, revision `V1.0` | Do not equate a shared PCB identifier with the complete WJ325 product model or its PT100/PT1000 input variant. |

The input-side photo shows resistors marked `512`, `5101`, `682`, and `000`.
These markings alone do not establish the circuit's resistance-to-voltage
relationship. Full connectivity and supply/reference information are still needed.

## Implications

- The ESP module identification supports the existing ESP8266 platform choice.
- The precision op-amp establishes that there is an active analog circuit near
  the probe terminals. Its exact role (excitation, amplification, buffering, etc.)
  needs trace/continuity verification.
- These photos do not validate the calibration ratio `1.365 / 1078.19`, zero
  offset assumption, ADC channel selection, or full resistance-to-voltage model.
- Existing plausible readings are supporting evidence for communication, not
  proof of the ADC's exact identity or of temperature accuracy.
- No separate EEPROM is positively identified. The manual's mention of EEPROM
  does not establish that it is a separate physical chip; flash-backed emulation
  remains possible. A full ESP flash dump is still the first backup to obtain.
- The visible headers are not labeled clearly enough to assign an FTDI pinout
  from these photos alone. Identify them by continuity against the module pinout
  before connecting an adapter.

## Next evidence to collect

With the board unpowered, verify suspected ADC connections against the ADS1115
10-pin pinout: pin 9 SDA to ESP GPIO12, pin 10 SCL to ESP GPIO14, and pin 1 ADDR
to ground for address 0x48. These are checks of the current hypothesis, not
confirmed PCB connections. Trace pin 4 AIN0 back to the analog circuit as well.

For firmware extraction, locate module UART TX/RX, ground, GPIO0, and reset using
the ESP-WROOM-02U datasheet. Verify any header mapping with continuity. Use
3.3 V UART logic and read the entire flash twice for matching backups.

The original firmware can then be examined for ADC register setup, calibration
storage, and resistance/temperature conversion. Any recovered per-unit
calibration should not automatically be transferred to the other unit.

## Manufacturer references

- [Espressif ESP-WROOM-02D/02U datasheet](https://documentation.espressif.com/esp-wroom-02u_esp-wroom-02d_datasheet_en.html)
- [TI TLVx376 datasheet and package markings](https://www.ti.com/lit/gpn/tlv2376)
- [TI ADS1115 datasheet](https://www.ti.com/lit/ds/symlink/ads1115.pdf): DGS pinout on page 3; ADS1115 DGS marking `BOGI` in the package addendum. Similar family members have different markings, so package shape alone is insufficient.
