# Same-probe comparison, 22 September 2026

The user moved the same top-tank probe between two separate WJ325 boards. No calibration or filtering settings were changed during these captures. Times are UTC.

| Capture | Start | End | Samples | Mean °C | Minimum °C | Maximum °C |
| --- | --- | --- | ---: | ---: | ---: | ---: |
| ESPHome before | 2026-09-22T16:27:01Z | 2026-09-22T16:29:01Z | 21 | 58.3774 | 57.9264 | 58.8682 |
| Manufacturer | 2026-09-22T16:31:50Z | 2026-09-22T16:33:57Z | 21 | 61.5865 | 61.4442 | 61.6593 |
| ESPHome return | 2026-09-22T16:40:28Z | 2026-09-22T16:42:28Z | 21 | 59.0678 | 58.3976 | 59.5340 |

The return ESPHome average is 0.69°C above its first baseline and 2.52°C below the intervening manufacturer baseline. Both ESPHome captures show more fluctuation than the manufacturer capture. These sequential measurements suggest a device-dependent discrepancy but do not establish its magnitude independently of temperature changes between captures. The user subsequently confirmed that the boiler was firing during these captures, with no hot-water use, and has now turned the boiler off. Active heating confounds the earlier sequential comparison; it must not be used to assign a calibration offset.

Do not apply a fixed temperature offset based on these measurements. Potential contributors include board-specific analogue calibration, sampling timing, power supply/noise, terminal contact, and a remaining reverse-engineering mismatch. This test does not distinguish them.

ESPHome return voltage and temperature were queried sequentially, so pairs can straddle an update; they are not guaranteed atomic samples.


## Boiler-off comparison

- ESPHome: 2026-09-22T16:43:13Z to 2026-09-22T16:46:14Z; 31 samples, mean 59.0893°C, range 58.5623–59.6295°C.
- Stock: 2026-09-22T16:47:29Z to 2026-09-22T16:49:42Z; 21 samples, mean 62.0101°C, range 61.8745–62.1855°C.

Stock minus ESPHome average: 2.9208°C. Boiler was off and no hot-water use was reported. The captures remain sequential; residual thermal changes cannot be excluded. No calibration changes were made. A return ESPHome capture would complete a boiler-off A/B/A comparison.

### Completed boiler-off return capture

ESPHome return: 2026-09-22T16:51:10Z to 2026-09-22T16:53:10Z; 21 samples, mean 59.0105°C, range 58.4682–59.6533°C. First ten mean 59.1041°C; last ten mean 58.9050°C.

The ESPHome means before and after differ by -0.0788°C. Stock is 2.9208°C above the first and 2.9996°C above the return. The return to essentially the same baseline strongly supports a reproducible difference between the two complete measurement systems near this operating point. It does not distinguish analogue calibration from firmware or sampling differences, nor establish absolute temperature accuracy. No correction has been applied.

## Native six-conversion burst sampling test

User confirmed installation, boiler off, and no hot-water use. Temperature events were collected directly from the ESPHome web event stream.

Capture 2026-09-22T18:12:19Z to 2026-09-22T18:15:18Z: 181 readings, mean 58.4810°C, range 58.0684–58.7741°C, standard deviation 0.1578°C. Median update interval 1.0 s. First 60 readings mean 58.4717°C; last 60 mean 58.5286°C.

Observed standard deviation is 50.7% lower than the first boiler-off baseline (0.3205°C), though the captures occurred at different times and publication cadences. This supports improved short-term stability with burst acquisition, not proof of absolute accuracy. The earlier stock average cannot be directly compared because more than an hour elapsed and the tank can cool with the boiler off. A fresh stock capture on the same probe is needed to assess the remaining inter-device difference.

### Stock comparison following burst sampling

Capture 2026-09-22T18:18:11Z to 2026-09-22T18:20:28Z: 21 valid readings, mean 61.4476°C, range 61.2768–61.5876°C, standard deviation 0.0910°C.

Compared with the final 60 ESPHome burst readings (58.5286°C), stock is 2.9190°C higher. The inter-device gap persists after changing ESPHome to six back-to-back conversions. This does not establish absolute temperature accuracy or identify the analogue cause. No calibration correction has been applied.

## Existing bottom probe: second comparison point

The user confirmed this is the separate probe already fitted at the bottom, not the top probe moved. The same bottom probe and leads must remain in place for both devices in this pair. This supports comparison of the electronics at a second input resistance, not absolute temperature calibration of either probe.

Stock capture 2026-09-22T20:26:08Z to 2026-09-22T20:28:27Z: 20 readings, mean 20.08571°C, range 19.93721–20.16077°C. First ten mean 20.10916°C; last ten mean 20.06226°C. One request timed out and was excluded. The 0.047°C half-to-half difference supports a stable baseline for the next device swap.

### ESPHome on existing bottom probe

Capture 2026-09-22T20:33:52Z to 2026-09-22T20:36:52Z: 181 temperature readings, mean 17.67345°C, range 17.46289–17.82074°C, standard deviation 0.08111°C. Mean recorded ADC voltage 1.36859998 V. First 60 mean 17.67351°C; last 60 mean 17.66269°C.

Stock bottom baseline 20.08571°C minus ESPHome 17.67345°C gives 2.41226°C, compared with approximately 2.92°C at the top. The two points support investigating a scale-and-offset calibration rather than a constant temperature correction. Both comparisons are sequential, use different probes between locations, and have no independent absolute reference. The paired device measurements at each location use the same probe. No calibration coefficients were changed.

## Live bottom-probe check after board calibration installed

User confirmed wireless installation of zero=13/full=28767.

Capture 2026-09-22T20:42:57Z to 2026-09-22T20:45:56Z: 181 readings, mean 20.09875°C, range 19.87071–20.29538°C, standard deviation 0.09434°C. Earlier stock bottom baseline 20.08571°C; mean difference +0.01304°C. First minute mean 20.14545°C; last minute mean 20.09842°C.

This confirms the installed calibration gives the expected agreement near the lower fitted point on a new capture. It is not an independent absolute calibration or validation at a third temperature; measurements are sequential. Top-probe restoration/check remains to be done.
