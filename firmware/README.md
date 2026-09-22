# Stock WJ325 firmware and wireless migration

`wj325-stock.bin` is the **435,552-byte bootloader/application image** extracted
from the original 2 MiB flash dump. It preserves offsets 0x00000–0x6a55f exactly.
It is not the complete backup: the device's saved configuration and SDK sectors
are excluded. No restoration test of this extracted image has been performed.
Retain a private full-flash backup for recovery; do not assume this image restores
network settings or per-board calibration.

`calibration.json` contains only seven explicitly selected numeric fields from
the original unit. `SHA256SUMS` identifies the published image.
`scripts/extract_stock_firmware.py` reproducibly extracts these artifacts from
the known original dump; that private input is deliberately absent from Git.

## Manufacturer update authentication

The inspected stock firmware uses HTTP Digest authentication:

- Username: `wifi8`
- Password: `12345678`
- Realm: `Custom Auth Realm`
- Update page: `http://DEVICE_IP/update`

These are hardcoded vendor credentials recovered from the executable, not the
owner's Wi-Fi password. They are documented intentionally. Their applicability
to other WJ325 firmware versions is unverified.

The UI does not upload a file. The latest-version action is:

```text
GET /startUpdate?id=update&value=1&ver=0
```

It downloads `http://www.wayjun.cn/wayjunUpdate/WJ325.bin`. Other versions add
a suffix to the filename. `value=0` polls update status; `value=1` starts an
actual flash operation.

## Successful stock-to-ESPHome migration

The original board was migrated to `pt1000-sensor-bottom.yaml` with ESPHome
2026.9.0. The top board's fitted calibration was not copied to it.

1. Compile the correct board's ESPHome OTA binary and verify its ESP8266 image
   header, actual flash capacity and file size. This installation used
   `firmware.ota.bin`, 425,616 bytes, DOUT, 40 MHz, 2 MiB flash.
2. Serve **that ESPHome binary**, not this stock reference image, at
   `/wayjunUpdate/WJ325.bin` on a controlled HTTP server, TCP port 80. Supply
   Content-Length and an `x-MD5` matching the image; do not use chunked encoding.
3. Override DNS for `www.wayjun.cn` to that server and verify the override works
   for the device. Restrict the server to the intended image and device.
4. Authenticate to `/update`, then start the latest-version update. The
   downloader reports its MAC, physical flash size and free sketch space in
   `x-ESP8266-*` headers. Check these before serving the image. Our board
   reported 2,097,152 bytes physical flash and 524,288 bytes free sketch space.
5. Monitor transfer completion, then verify the board returns with the intended
   ESPHome identity, native API, web interface and working ADC acquisition.
6. Stop the temporary HTTP server and remove the DNS override. Future updates
   use native ESPHome OTA.

The first request in this installation was rejected because inter-VLAN NAT
changed its source address. The second allowed that route and verified the
board's MAC, update mode and capacity before delivering the image. The device
rebooted into ESPHome successfully. The connected bottom probe subsequently
read about 19.8°C with its fault flag cleared.

The updater closes its original HTTP connection during flashing, so a dropped
`/startUpdate` response alone is not proof of either success or failure. Verify
the downloaded image and the device after reboot.

Reference implementation: [ESP8266 HTTP updater](https://github.com/esp8266/Arduino/blob/2.7.4/libraries/ESP8266httpUpdate/src/ESP8266httpUpdate.cpp).
