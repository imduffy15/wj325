"""Execute the dump's conversion instructions with a small, restricted interpreter.

Run: uv run --with r2pipe --with pyyaml python tests/check_firmware_instructions.py
Requires radare2 and g++. This is NOT a complete ESP8266 emulator.
ADC reads are supplied test counts. ESP8266 ROM arithmetic calls are modeled
with float32/int32 operations; flash/IRAM conversion code executes instruction
by instruction, including the firmware's float division and comparisons.
No device/network access and no firmware changes.
"""
from pathlib import Path
import ctypes
import hashlib
import json
import math
import random
import re
import struct
import subprocess
import tempfile

import r2pipe
import yaml
from firmware_fixture import load_firmware_fixture

# Conversion checks do not need to resolve Wi-Fi credentials.
class ConfigLoader(yaml.SafeLoader):
    pass

ConfigLoader.add_constructor("!secret", lambda loader, node: loader.construct_scalar(node))

ROOT = Path(__file__).resolve().parents[1]
MASK = 0xFFFFFFFF


def signed(v):
    return v - 0x100000000 if v & 0x80000000 else v


def bits(v):
    return struct.unpack('<I', struct.pack('<f', v))[0]


def floating(v):
    return struct.unpack('<f', struct.pack('<I', v & MASK))[0]


class Machine:
    def __init__(self):
        dump = load_firmware_fixture()
        self.regions = [(0x3FFE8000, bytearray(0x18000)), (0x40100000, bytearray(0x10000)),
                        (0x40201010, bytearray(0x605F4))]
        offset = 0x1008
        for _ in range(dump[0x1001]):
            address, length = struct.unpack_from('<II', dump, offset)
            offset += 8
            memory, index = self.locate(address, length)
            memory[index:index+length] = dump[offset:offset+length]
            offset += length
        memory, index = self.locate(0x3FFF1490, 0x544)
        memory[index:index+0x544] = dump[0xFB000:0xFB544]
        self.decoders = {}
        for base, filename in [(0x40201010, 'segment-40201010.bin'), (0x401001B8, 'segment-401001b8.bin')]:
            extracted = (ROOT/'analysis'/filename).read_bytes()
            memory, index = self.locate(base, len(extracted))
            assert extracted == memory[index:index+len(extracted)], 'decoder input differs from dump'
            self.decoders[base] = r2pipe.open(str(ROOT/'analysis'/filename), flags=['-2','-a','xtensa','-b','32','-m',hex(base)])
        self.cache = {}
        self.coverage = set()
        self.r = [0]*16
        self.reset()
        self.r[2] = 0x3FFF19DC
        self.run(0x4021C6E4)
        assert self.read(0x3FFF19DC+8, 4) == 0  # factory full-scale gain
        assert self.read(0x3FFF19DC+4, 1) == 0  # ADS1115 shift

    def locate(self, address, length):
        for base, memory in self.regions:
            if base <= address and address+length <= base+len(memory):
                return memory, address-base
        raise AssertionError(f'unmapped memory {address:#x}+{length}')

    def read(self, address, length):
        memory, i = self.locate(address, length)
        return int.from_bytes(memory[i:i+length], 'little')

    def write(self, address, length, value):
        memory, i = self.locate(address, length)
        memory[i:i+length] = (value & ((1 << (8*length))-1)).to_bytes(length, 'little')

    def reset(self):
        self.r = [0]*16
        self.r[0] = MASK
        self.r[1] = 0x3FFFF000
        self.shift = 0
        self.adc = iter(())
        self.reads = 0
        self.register_writes = []

    def instruction(self, pc):
        if pc not in self.cache:
            decoder = self.decoders[0x40201010 if pc >= 0x40200000 else 0x401001B8]
            instruction = decoder.cmdj(f'aoj 1 @ {pc}')[0]
            text = instruction['opcode']
            op, _, args = text.partition(' ')
            args = [x.strip() for x in args.split(',')] if args else []
            self.cache[pc] = (op.removesuffix('.n'), args, instruction['size'])
        self.coverage.add(pc)
        return self.cache[pc]

    def hook(self, address):
        # ROM symbols verified against ESP8266 eagle.rom.addr.v6.ld.
        a, b = self.r[2], self.r[3]
        if address == 0x40213DFC:  # capture writeRegister without an I2C device
            assert self.r[2] == 0x3FFF19DC
            self.register_writes.append((self.r[3], self.r[4] & 0xFFFF))
            value = 0
        elif address == 0x40213F30:  # readADC_SingleEnded: emulate hardware only
            assert self.r[2] == 0x3FFF19DC and self.r[3] == 0
            value = next(self.adc)
            self.reads += 1
        elif address == 0x4000C180: value = bits(floating(a)+floating(b))
        elif address == 0x4000C268: value = bits(floating(a)-floating(b))
        elif address == 0x4000C3DC: value = bits(floating(a)*floating(b))
        elif address == 0x4000E2AC: value = bits(signed(a))
        elif address == 0x4000E2A4: value = bits(a)
        elif address == 0x4000C4C4: value = int(floating(a))
        elif address == 0x4000DC88:
            aa, bb = signed(a), signed(b)
            value = (abs(aa)//abs(bb)) * (-1 if (aa<0) != (bb<0) else 1)
        else: return False
        self.r[2] = value & MASK
        return True

    def run(self, pc, stop=MASK):
        r = self.r
        def val(arg): return r[int(arg[1:])] if arg.startswith('a') else int(arg, 0)
        for step in range(200000):
            if pc == stop: return
            op, args, size = self.instruction(pc)
            nxt = pc+size
            v = [val(x) for x in args]
            dest = int(args[0][1:]) if args and args[0].startswith('a') else None
            result = None
            if op in ('movi','mov'): result = v[1]
            elif op in ('addi','addi.n','addmi','add'): result = v[1]+v[2]
            elif op == 'sub': result = v[1]-v[2]
            elif op == 'neg': result = -v[1]
            elif op in ('addx2','addx4','addx8'): result = v[1]*int(op[-1])+v[2]
            elif op == 'or': result = v[1]|v[2]
            elif op == 'and': result = v[1]&v[2]
            elif op == 'xor': result = v[1]^v[2]
            elif op == 'slli': result = v[1]<<v[2]
            elif op == 'srli': result = v[1]>>v[2]
            elif op == 'srai': result = signed(v[1])>>v[2]
            elif op == 'ssr': self.shift = v[0]&31
            elif op == 'sra': result = signed(v[1])>>self.shift
            elif op == 'srl': result = v[1]>>self.shift
            elif op == 'sll': result = v[1]<<(32-self.shift)
            elif op == 'extui': result = (v[1]>>v[2])&((1<<v[3])-1)
            elif op == 'l32r': result = self.read(v[1],4)
            elif op in ('l32i','l16ui','l16si','l8ui'):
                length = {'l32i':4,'l16ui':2,'l16si':2,'l8ui':1}[op]
                result = self.read((v[1]+v[2])&MASK,length)
                if op == 'l16si' and result&0x8000: result -= 65536
            elif op in ('s32i','s16i','s8i'):
                self.write((v[1]+v[2])&MASK,{'s32i':4,'s16i':2,'s8i':1}[op],v[0])
            elif op in ('movnez','moveqz'):
                if (v[2]!=0) == (op=='movnez'): result=v[1]
            elif op in ('call0','callx0'):
                target=v[0]
                r[0]=nxt
                if not self.hook(target): nxt=target
            elif op == 'ret': nxt=r[0]
            elif op in ('j','jx'): nxt=v[0]
            elif op.startswith('b'):
                if op in ('beqz','bnez','bltz','bgez'):
                    condition={'beqz':v[0]==0,'bnez':v[0]!=0,'bltz':signed(v[0])<0,'bgez':signed(v[0])>=0}[op]
                elif op in ('beq','beqi'): condition=v[0]==(v[1]&MASK)
                elif op in ('bne','bnei'): condition=v[0]!=(v[1]&MASK)
                elif op in ('blt','blti'): condition=signed(v[0])<signed(v[1]&MASK)
                elif op in ('bge','bgei'): condition=signed(v[0])>=signed(v[1]&MASK)
                elif op in ('bltu','bltui'): condition=v[0]<v[1]
                elif op in ('bgeu','bgeui'): condition=v[0]>=v[1]
                elif op == 'ball': condition=(v[0]&v[1])==v[1]
                elif op == 'bnall': condition=(v[0]&v[1])!=v[1]
                else: raise AssertionError((hex(pc),op,args))
                if condition: nxt=v[-1]
            elif op == 'nop': pass
            else: raise AssertionError((hex(pc),op,args))
            if result is not None: r[dest]=result&MASK
            pc=nxt
        raise AssertionError('instruction limit')

    def measure(self, samples):
        self.reset()
        self.adc=iter(samples)
        self.run(0x40202020, stop=0x4020208B)  # result stored, before Modbus serialization
        assert self.reads==6
        return floating(self.read(0x3FFF19D4,4)), floating(self.read(0x3FFF19F0,4))

    def close(self):
        for decoder in self.decoders.values(): decoder.quit()


def main():
    config=yaml.load((ROOT/'pt1000-sensor.yaml').read_text(), Loader=ConfigLoader)
    body=next(s['lambda'] for s in config['sensor'] if s.get('id')=='pt1000_temp')
    zero=int(re.search(r'constexpr int32_t zero = (-?\d+);',body)[1])
    full=int(re.search(r'constexpr int32_t full = (-?\d+);',body)[1])
    source='''#include <cmath>\n#include <cstdint>\n#define PROGMEM\n#define pgm_read_word(p) (*(p))\nextern "C" float convert(float voltage_in) {\n'''+body.replace('id(pt1000_voltage).state','voltage_in')+'\n}\n'
    machine=Machine()
    # Run the factory instructions with the calibration configured in the YAML.
    # Only emulated RAM changes; the firmware dump and devices are untouched.
    machine.write(0x3FFF1490+0x528,4,full)
    machine.write(0x3FFF1490+0x52C,4,zero)
    try:
        # Execute the actual saved-rate dispatcher and conversion-register setup.
        machine.reset();machine.r[2]=machine.read(0x3FFF1490+0x14,2)
        machine.run(0x40202164)
        assert machine.read(0x3FFF19DC+12,2)==0x60
        machine.reset();machine.r[2]=0x3FFF19DC
        machine.r[3]=machine.read(0x3FFE97FE,2);machine.r[4]=0
        machine.run(0x40213E30)
        assert machine.register_writes==[(1,0xC160),(3,0x8000),(2,0)]
        print('Factory ADC register writes:',machine.register_writes,flush=True)
        # Check the interpreter's actual IRAM float routines against host float32.
        for x,y in [(3.4,6.144),(32767.,28989.),(0.,3.4),(-2.,4.),(1.,1.),(65535.,172074.)]:
            for address,expected in [(0x40106240,bits(floating(bits(x))/floating(bits(y)))),
                                     (0x401062FC,int(x!=y)),
                                     (0x40106324,int(x>y)),
                                     (0x401063B0,(-1 if x<y else 0)&MASK)]:
                machine.reset();machine.r[2]=bits(x);machine.r[3]=bits(y);machine.run(address)
                assert machine.r[2]==expected,(hex(address),x,y,hex(machine.r[2]),hex(expected))
        with tempfile.TemporaryDirectory(prefix='wj325-machine-') as directory:
            cpp=Path(directory)/'lambda.cpp';lib=Path(directory)/'lambda.so';cpp.write_text(source)
            subprocess.run(['g++','-std=c++17','-O2','-shared','-fPIC',str(cpp),'-o',str(lib)],check=True)
            library=ctypes.CDLL(str(lib));library.convert.argtypes=[ctypes.c_float];library.convert.restype=ctypes.c_float
            rng=random.Random(325)
            counts=sorted(set([0,1,50,100,200,1000,4000,7000,8000,8154,8178,8300,10000,16000,18000,18133,20000,32767]+list(range(0,32768,64))))
            vectors=[[n]*6 for n in counts]
            vectors += [[rng.randint(7000,9000) for _ in range(6)] for _ in range(100)]
            vectors += [[max(0,min(32767,n+rng.randint(-20,20))) for _ in range(6)] for n in counts[::8]]
            max_error=0.;max_native_error=0.;faults=0
            for i,samples in enumerate(vectors):
                voltage,stock=machine.measure(samples)
                actual=library.convert(voltage)
                if not -200<=stock<=600:
                    assert math.isnan(actual),(samples,voltage,stock,actual);faults+=1
                else:
                    error=abs(stock-actual);max_error=max(max_error,error)
                    assert error<0.0001,(samples,voltage,stock,actual,error)
                    # ESPHome's native driver scales in mV then divides by 1000.
                    # Quantify that arithmetic-order difference independently.
                    native_sum=0.0
                    for sample in samples:
                        native_v=floating(bits(floating(bits(sample*6144/32768))/1000))
                        native_sum=floating(bits(native_sum+native_v))
                    native_mean=floating(bits(native_sum/6))
                    native_result=library.convert(native_mean)
                    assert math.isfinite(native_result),(samples,stock,native_result)
                    max_native_error=max(max_native_error,abs(stock-native_result))
                if i%100==0: print(f'Checked {i+1}/{len(vectors)} ADC sequences',flush=True)
            result={'calibration_zero':zero,'calibration_full':full,
                    'adc_sequences':len(vectors),'fault_sequences':faults,'max_temperature_difference_C':max_error,
                    'max_native_driver_scaling_difference_C':max_native_error,
                    'unique_instructions_executed':len(machine.coverage),'decoded_instructions':len(machine.cache)}
            (ROOT/'analysis/instruction-validation.json').write_text(json.dumps(result,indent=2)+'\n')
            print('PASS',json.dumps(result),flush=True)
    finally: machine.close()


if __name__=='__main__':main()
