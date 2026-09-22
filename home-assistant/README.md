# Home Assistant heating demand

The top and bottom entities use matching names:

- `sensor.hot_water_tank_top_pt1000_temperature`
- `sensor.hot_water_tank_bottom_pt1000_temperature`
- `binary_sensor.hot_water_tank_top_measurement_problem`
- `binary_sensor.hot_water_tank_bottom_measurement_problem`

All top diagnostics use `hot_water_tank_top_`, matching the bottom's prefix.
The old top temperature entity was `sensor.pt1000_sensor_pt1000_temperature`.
Existing references must be updated when renaming an installation.

## Behavior

[hot_water.yaml](hot_water.yaml) is a Home Assistant package. With automatic
heating enabled, the top must remain **below 45°C for two minutes** before
`input_boolean.hot_water_heating_request` turns on. It remains on as the
water warms and clears at **60°C**. Both thresholds are adjustable helpers;
the stop threshold must exceed the start threshold.

The request clears when the input is unavailable, faulty, stale, invalid,
or automatic heating is disabled. The template checks reporting age against
three minutes (reevaluated on its normal template schedule, including once per
minute). The automation also reconciles every 30 seconds. On restart, enable
and request helpers reset off. After enabling again, a fresh two-minute period
is required; an interrupted timer is not restored.

This package **does not operate a boiler or immersion**. It exposes demand
for the future actuator integration. The previous immersion automation was
removed from the original installation at the owner's request. Bottom
measurement is available for observation and future control logic, but does
not currently affect the request.

## Installation

1. Configure `homeassistant: packages: !include_dir_named packages` in your main
   configuration, merging it with any existing `homeassistant` section.
2. Copy the package to `config/packages/hot_water.yaml`.
3. Validate the Home Assistant configuration. Reload input booleans, input
   numbers, template entities and automations, or restart if an integration
   is not already loaded.
4. Set `input_number.hot_water_start_temperature` to **45** and
   `input_number.hot_water_stop_temperature` to **60**. These values restore
   across restarts; the YAML deliberately omits `initial` so UI adjustments
   are preserved. On a new installation they start at their minimum values,
   so set both before enabling.
5. Enable `input_boolean.hot_water_automatic_heating_enabled` to monitor demand.

The original installation was configured with 45°C/60°C and demand monitoring
enabled. A separate future
change must connect the request to the appropriate hot-water zone control,
including its runtime limits, actuator feedback and behavior when HA is down.

## Temperature choice

45°C is a provisional reheat trigger to leave more useful hot water than a
40°C trigger while the boiler starts. A top reading of 60°C is only a local
measurement; it does not demonstrate that the entire cylinder has reached
60°C. This automation is not a scheduled whole-cylinder disinfection cycle.
Retain the existing cylinder thermostat and hot-water hygiene arrangements.
[HSE storage-temperature guidance](https://www.hse.gov.uk/legionnaires/hot-and-cold.htm)
recommends storage at least at 60°C.

Home Assistant references: [template delay_on](https://www.home-assistant.io/integrations/template/)
and [input boolean initialization](https://www.home-assistant.io/integrations/input_boolean/).
