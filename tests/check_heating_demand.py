"""Exercise the real HA package in an isolated Home Assistant instance.

Run with the same Home Assistant Python environment as the deployed server:
  python tests/check_heating_demand.py
No connection to live HA, devices or boiler. Takes about two minutes.
"""
import asyncio
from pathlib import Path
import tempfile
import yaml
from homeassistant.core import HomeAssistant
from homeassistant import loader, bootstrap, config_entries
from homeassistant.setup import async_setup_component

ROOT=Path(__file__).resolve().parents[1]
TEMP='sensor.hot_water_tank_top_pt1000_temperature'
FAULT='binary_sensor.hot_water_tank_top_measurement_problem'
ENABLE='input_boolean.hot_water_automatic_heating_enabled'
REQUEST='input_boolean.hot_water_heating_request'
START='input_number.hot_water_start_temperature'
STOP='input_number.hot_water_stop_temperature'
BELOW='binary_sensor.hot_water_top_below_start_temperature'
VALID='binary_sensor.hot_water_heating_input_valid'

async def main():
 with tempfile.TemporaryDirectory() as directory:
  hass=HomeAssistant(directory)
  loader.async_setup(hass)
  config=yaml.safe_load((ROOT/'home-assistant/hot_water.yaml').read_text())
  hass.config_entries=config_entries.ConfigEntries(hass,config)
  assert await bootstrap.async_load_base_functionality(hass)
  hass.states.async_set(TEMP,'50')
  hass.states.async_set(FAULT,'off')
  for domain in ('input_boolean','input_number','template','automation'):
   assert await async_setup_component(hass,domain,config),domain
  await hass.async_start()
  async def settle():
   await hass.async_block_till_done()
   await asyncio.sleep(.05)
   await hass.async_block_till_done()
  async def service(domain,action,entity,value=None):
   data={'entity_id':entity}
   if value is not None:data['value']=value
   await hass.services.async_call(domain,action,data,blocking=True)
   await settle()
  async def temp(value):
   hass.states.async_set(TEMP,str(value));await settle()
  def state(entity,value):
   actual=hass.states.get(entity)
   assert actual is not None and actual.state==value,(entity,actual,value)
  await service('input_number','set_value',START,45)
  await service('input_number','set_value',STOP,60)
  await settle();state(VALID,'on');state(REQUEST,'off')
  await service('input_boolean','turn_on',ENABLE)
  await temp(44)
  state(BELOW,'off');state(REQUEST,'off')
  await temp(46) # Brief dip must not latch a request.
  state(BELOW,'off');state(REQUEST,'off')
  await temp(44)
  print('Checking actual two-minute qualification timer...',flush=True)
  await asyncio.sleep(118)
  state(REQUEST,'off')
  await asyncio.sleep(3)
  await settle();state(BELOW,'on');state(REQUEST,'on')
  await temp(50);state(REQUEST,'on') # Hold request through the deadband.
  await temp(60);state(REQUEST,'off')
  await temp(50);state(REQUEST,'off') # No restart within the deadband.
  await service('input_boolean','turn_on',REQUEST)
  await temp('unavailable');state(VALID,'off');state(REQUEST,'off')
  await temp(50);state(VALID,'on');state(REQUEST,'off')
  await service('input_boolean','turn_on',REQUEST)
  hass.states.async_set(FAULT,'on');await settle();state(REQUEST,'off')
  hass.states.async_set(FAULT,'off');await settle()
  await service('input_boolean','turn_on',REQUEST)
  await service('input_number','set_value',START,60)
  state(VALID,'off');state(REQUEST,'off')
  await service('input_number','set_value',START,45)
  await service('input_boolean','turn_on',REQUEST)
  await service('input_boolean','turn_off',ENABLE);state(REQUEST,'off')
  assert 'switch' not in config and 'climate' not in config
  print('PASS: 2-minute start, cancelled brief dip, hysteresis, cutoff, unavailable/fault input, invalid thresholds, disable.',flush=True)
  await hass.async_stop()
asyncio.run(main())
