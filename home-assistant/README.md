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
minute). The automation also reconciles every 30 seconds. On restart, the enable helper restores its previous setting and the request
resets off. If enabled and still below the start threshold, a fresh two-minute
period is required before requesting heat; an interrupted timer is not restored.

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

## Hot Water dashboard and tank widget

The installed **Hot Water** sidebar dashboard is at `/hot-water/tank`.
[hot-water-dashboard.yaml](hot-water-dashboard.yaml) contains its complete
Lovelace configuration. [tank-card.yaml](tank-card.yaml) is the standalone
widget for reuse on another dashboard.

The widget uses [Slate Heating Card](https://github.com/jouwdan/slate-heating-card)
installed as a HACS custom Dashboard repository, plus the existing
[card-mod](https://github.com/thomasloven/lovelace-card-mod) installation.
Slate version 0.1.0, upstream commit
`28c749bcf7bab47e6ac95371a2c75d308121a3f2`, was inspected and tested.
The installed module SHA256 is
`48b294dd15a51c62790654326e47fd032225b904c07e0ffcb4d3b9f0b62f7ddb`.
HACS manages the unmodified upstream module at
`/hacsfiles/slate-heating-card/slate-heating-card.js` and registers the resource.
No upstream JavaScript is copied into this repository.

Slate supplies the tank layout, temperature labels and tap-to-history actions.
The card-mod styling turns its separate layers into a continuous vertical
gradient, using Slate's blue-at-20°C to orange-at-60°C colour scale. These are
colour limits, not sensor limits or heating thresholds. Between the two probes,
the colour is an illustration of interpolation, not a measured temperature
profile or an estimate of usable hot-water volume. Slate's percentage estimate
is disabled. Missing readings or either probe's fault flag make the tank grey;
a separate dashboard warning reports fault/unavailable probe entities.

The dashboard also includes a native 24-hour history graph and the request
helpers. Top history is orange and bottom is blue. The graph display is bounded
to 0–80°C so old commissioning spikes do not flatten normal readings. Raw
history is not modified; values outside those bounds remain available through
the entity's history dialog. Request state is displayed without a toggle, and
is explicitly separate from actual boiler operation.

To reproduce the dashboard:

1. Add `https://github.com/jouwdan/slate-heating-card` to HACS custom repositories,
   category **Dashboard**, and install it. Install card-mod if needed.
2. Refresh the frontend so both custom modules are loaded.
3. Create a new dashboard and paste `hot-water-dashboard.yaml` into its raw
   configuration editor, or add `tank-card.yaml` as a manual card elsewhere.
4. Map the two temperatures and fault entities if your IDs differ. The full
   dashboard additionally uses the helpers from `hot_water.yaml`.

The CSS targets Slate 0.1.0's `.tank-vessel`, `.tank-layer` and `.tank-profile`
classes. Recheck the appearance after upstream layout changes. Both desktop
(1280 px) and phone (390 px) layouts were checked in a real browser, including
resource loading, gradient rendering, absence of frontend errors and opening
Home Assistant's native more-info dialog. `tests/check_tank_card.py` checks
normal, equal-temperature, missing-reading, fault and recovery cases in an
isolated Home Assistant template environment.
