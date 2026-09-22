"""Check the actual YAML lambda against the dump and an independent math model.

Run: uv run --with pyyaml python tests/check_conversion.py
Requires a host C++ compiler. Does not contact or flash either device.
"""
import bisect
import hashlib
from pathlib import Path
import re
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
dump = load_firmware_fixture()
config = yaml.load((ROOT / "pt1000-sensor.yaml").read_text(), Loader=ConfigLoader)
body = next(s["lambda"] for s in config["sensor"] if s.get("id") == "pt1000_temp")
zero = int(re.search(r"constexpr int32_t zero = (-?\d+);", body)[1])
full = int(re.search(r"constexpr int32_t full = (-?\d+);", body)[1])
assert 0 <= zero < 99 and zero < full <= 32767
table = struct.unpack_from("<801H", dump, 0x6992E)
embedded = tuple(map(int, re.findall(r"\d+", body.split("PROGMEM = {", 1)[1].split("};", 1)[0])))
assert embedded == table, "YAML must contain the exact factory table"
assert all(a < b for a, b in zip(table, table[1:]))
assert struct.unpack_from("<ii", dump, 0xFB528) == (28990, 1)
assert struct.unpack_from("<i", dump, 0xFB534)[0] == 600
assert dump[0xFB538] == 1
assert struct.unpack_from("<ff", dump, 0xFB53C) == (30.0, struct.unpack("<f", struct.pack("<f", 3.4))[0])

source = """
#include <cmath>
#include <cstdint>
#include <cstdio>
#include <cassert>
#define PROGMEM
#define pgm_read_word(p) (*(p))
float convert(float voltage_in) {
""" + body.replace("id(pt1000_voltage).state", "voltage_in") + """
}
int main() {
  assert(std::isnan(convert(NAN)));
  assert(std::isnan(convert(INFINITY)));
  assert(std::isnan(convert(-0.1f)));
  assert(std::isnan(convert(0.0f)));
  assert(std::isnan(convert(3.4f)));
  assert(std::isnan(convert(100.0f)));
  for (int i = 0; i <= 32767; ++i) {
    float v = static_cast<float>(i) * (6.144f / 32768.0f);
    std::printf("%.9g %.9g\\n", v, convert(v));
  }
}
"""


def f32(value):
    return struct.unpack("<f", struct.pack("<f", value))[0]


def reference(voltage):
    # Match the two integer quantizations, then independently invert the
    # divider using a dimensionless ratio (rather than the firmware's steps).
    count = int(f32(f32(min(voltage, f32(3.4)) / f32(3.4)) * 32767))
    if count <= 99 or count > 32667:
        return float("nan")
    normalized = (count - zero) * 32767 // (full - zero)
    low = 3.0 / (106539.0 + 3.0)
    high = 65535.0 / (106539.0 + 65535.0)
    ratio = low + (high - low) * normalized / 32767.0
    coordinate = 106539.0 * ratio / (1.0 - ratio)
    if coordinate < 3869 or coordinate > 65635:
        return float("nan")
    if coordinate > 65535:
        return 600.0
    index = max(0, bisect.bisect_left(table, coordinate) - 1)
    return index - 200 + (coordinate - table[index]) / (table[index + 1] - table[index])


with tempfile.TemporaryDirectory(prefix="wj325-test-") as directory:
    cpp = Path(directory) / "check.cpp"
    binary = Path(directory) / "check"
    cpp.write_text(source)
    subprocess.run(["g++", "-std=c++17", "-O2", "-Wall", "-Wextra", "-Werror", str(cpp), "-o", str(binary)], check=True)
    lines = subprocess.check_output([str(binary)], text=True).splitlines()
    maximum_error = 0.0
    for line in lines:
        voltage, actual = map(float, line.split())
        expected = reference(f32(voltage))
        if expected != expected:
            assert actual != actual, (voltage, actual, expected)
        else:
            assert abs(actual - expected) < 0.002, (voltage, actual, expected)
            maximum_error = max(maximum_error, abs(actual - expected))
    print(f"PASS: exact 801-entry table, recovered calibration fixture, invalid inputs, and {len(lines)} ADC inputs; tested zero={zero}, full={full}")
    print(f"Maximum difference from independent model: {maximum_error:.6f} C")
