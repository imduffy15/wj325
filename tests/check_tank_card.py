"""Check tank-card gradient templates in an isolated Home Assistant instance.
Run with the installed Home Assistant Python environment; never contacts devices.
"""
import asyncio
from pathlib import Path
import tempfile
import yaml
from homeassistant.core import HomeAssistant
from homeassistant.helpers.template import Template

ROOT=Path(__file__).resolve().parents[1]
TOP='sensor.hot_water_tank_top_pt1000_temperature'
BOTTOM='sensor.hot_water_tank_bottom_pt1000_temperature'
TF='binary_sensor.hot_water_tank_top_measurement_problem'
BF='binary_sensor.hot_water_tank_bottom_measurement_problem'

async def main():
 with tempfile.TemporaryDirectory() as directory:
  hass=HomeAssistant(directory)
  card=yaml.safe_load((ROOT/'home-assistant/tank-card.yaml').read_text())
  assert card['tank_entities']==[TOP,BOTTOM]
  assert card['show_tank_estimate'] is False
  assert not card.get('hot_water_entity')
  style=Template(card['card_mod']['style'],hass)
  def render(top,bottom,tf='off',bf='off'):
   for entity,value in ((TOP,top),(BOTTOM,bottom),(TF,tf),(BF,bf)):
    hass.states.async_set(entity,str(value))
   return style.async_render()
  hot=render(60,20)
  assert 'linear-gradient(180deg,' in hot
  assert 'rgb(251,' in hot and 'rgb(96,' in hot
  equal=render(40,40)
  assert 'linear-gradient(180deg,' in equal
  assert 'rgb(174,' in equal
  for args in [('unavailable',20),(60,'unknown'),('nan',20),(60,20,'on'),(60,20,'off','unavailable')]:
   fault=render(*args)
   assert 'linear-gradient(180deg,' not in fault,args
   assert 'background: var(--disabled-text-color, #777)' in fault,args
  assert 'linear-gradient(180deg,' in render(55,25)
  print('PASS: probe order, gradient colours, equal-temperature tank, missing/invalid readings, fault flags and recovery; no controller mapped.')
  await hass.async_stop()
asyncio.run(main())
