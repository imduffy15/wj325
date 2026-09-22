"""Fit zero/full counts to the saved same-probe comparisons (no device writes).
Run: uv run --with pyyaml python tests/fit_board_calibration.py
Uses the actual YAML lambda compiled on the host, including float32 and integer
quantization. Calibration is relative to the stock device, not an absolute RTD
calibration. Writes an evidence report only; never modifies the YAML.
"""
import ctypes
import json
import math
from pathlib import Path
import re
import statistics
import struct
import subprocess
import tempfile

import yaml
from firmware_fixture import load_firmware_fixture

# Conversion checks do not need to resolve Wi-Fi credentials.
class ConfigLoader(yaml.SafeLoader):
    pass

ConfigLoader.add_constructor("!secret", lambda loader, node: loader.construct_scalar(node))

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / 'analysis'
config = yaml.load((ROOT/'pt1000-sensor.yaml').read_text(), Loader=ConfigLoader)
body = next(s['lambda'] for s in config['sensor'] if s.get('id') == 'pt1000_temp')
body = re.sub(r'constexpr int32_t (zero|full) = -?\d+;', '', body)
source = '''#include <cmath>\n#include <cstdint>\n#define PROGMEM\n#define pgm_read_word(p) (*(p))\nextern "C" float convert(float voltage_in, int32_t zero, int32_t full) {\n''' + body.replace('id(pt1000_voltage).state','voltage_in') + '\n}\n'


def f32(v):
    return struct.unpack('<f', struct.pack('<f',v))[0]


def read(name):
    return json.loads((DATA/name).read_text())


points = []
for name, espfile, stockfile, tail in [
    ('bottom', 'esphome-bottom-baseline.json', 'stock-bottom-baseline.json', None),
    ('top', 'esphome-burst-sampling-baseline.json', 'stock-after-burst-baseline.json', 60),
]:
    esp = read(espfile)
    if tail: esp = esp[-tail:]
    # SSE initial enumeration can lack a corresponding voltage for one row.
    paired = [r for r in esp if isinstance(r.get('voltage'),(int,float))]
    stock = read(stockfile)
    points.append({'location':name, 'volts':[r['voltage'] for r in paired],
                   'source_esphome':espfile, 'source_stock':stockfile,
                   'esphome_samples':len(paired), 'stock_samples':len(stock),
                   'stock_target_C':statistics.mean(r['temperature'] for r in stock),
                   'previous_esphome_C':statistics.mean(r['temperature'] for r in paired)})

table = struct.unpack_from('<801H',load_firmware_fixture(),0x6992E)
# Invert the factory divider and RTD interpolation to seed the integer search.
for p in points:
    pos = p['stock_target_C']+200; i = math.floor(pos)
    coordinate = table[i]+(pos-i)*(table[i+1]-table[i])
    low = 3/(106539+3); high = 65535/(106539+65535)
    p['target_normalized_count'] = 32767*(coordinate/(106539+coordinate)-low)/(high-low)
    p['mean_reference_count'] = statistics.mean(int(f32(f32(f32(v)/f32(3.4))*32767)) for v in p['volts'])
a,b = points
slope = (b['mean_reference_count']-a['mean_reference_count'])/(b['target_normalized_count']-a['target_normalized_count'])
zero0 = a['mean_reference_count']-slope*a['target_normalized_count']
full0 = zero0+32767*slope

with tempfile.TemporaryDirectory(prefix='wj325-fit-') as directory:
    cpp=Path(directory)/'fit.cpp';lib=Path(directory)/'fit.so';cpp.write_text(source)
    subprocess.run(['g++','-O2','-std=c++17','-shared','-fPIC',str(cpp),'-o',str(lib)],check=True)
    library=ctypes.CDLL(str(lib));fn=library.convert
    fn.argtypes=[ctypes.c_float,ctypes.c_int32,ctypes.c_int32];fn.restype=ctypes.c_float
    best=None
    for zero in range(round(zero0)-12,round(zero0)+13):
        for full in range(round(full0)-12,round(full0)+13):
            means=[statistics.mean(fn(v,zero,full) for v in p['volts']) for p in points]
            score=sum((mean-p['stock_target_C'])**2 for mean,p in zip(means,points))
            if best is None or score<best[0]:best=(score,zero,full,means)
    score,zero,full,means=best
    for p,mean in zip(points,means):
        p['predicted_calibrated_C']=mean
        p['fit_residual_C']=mean-p['stock_target_C']
        assert abs(p['fit_residual_C'])<0.02
        p['mean_voltage_V']=statistics.mean(p.pop('volts'))
    report={'reference':'Stock WJ325, same probe per paired comparison; no independent absolute reference',
            'method':'Fit factory zero/full count parameters; retain ADC settings, Vref, Rzero and nonlinear RTD conversion',
            'original_zero':1,'original_full':28990,'fitted_zero':zero,'fitted_full':full,
            'continuous_seed':{'zero':zero0,'full':full0},'fit_sum_squared_error':score,'points':points,
            'limits':'Sequential observations, two different probes across locations. Provisional near 20–61 C; not validated outside that range. Fit residual is not an accuracy claim.'}
    (DATA/'board-calibration-fit.json').write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps(report,indent=2))
