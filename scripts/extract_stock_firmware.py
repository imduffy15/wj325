"""Publish only executable firmware and selected numeric calibration, never saved settings."""
from pathlib import Path
import hashlib,json,struct
ROOT=Path(__file__).resolve().parents[1]
raw=(ROOT/'wj325-backup.bin').read_bytes()
assert hashlib.sha256(raw).hexdigest()=='aae09986cf2059fc167e88394ab6a5796ea1afac0bd7b79bd225d4044d051fd2'
assert raw[0x1000]==0xe9
pos=0x1008
for _ in range(raw[0x1001]):
    _,length=struct.unpack_from('<II',raw,pos)
    pos+=8+length
end=(pos+16)&~15
assert end==435552
out=ROOT/'firmware'
out.mkdir(exist_ok=True)
(out/'wj325-stock.bin').write_bytes(raw[:end])
# Explicit allowlist: no strings, network settings, MQTT settings, or SDK sectors.
fields={'data_rate_index':raw[0xfb014], 'full':struct.unpack_from('<i',raw,0xfb528)[0],
        'zero':struct.unpack_from('<i',raw,0xfb52c)[0], 'upper_temperature':struct.unpack_from('<i',raw,0xfb534)[0],
        'pt1000_mode':raw[0xfb538], 'rzero':struct.unpack_from('<f',raw,0xfb53c)[0],
        'vref':struct.unpack_from('<f',raw,0xfb540)[0]}
(out/'calibration.json').write_text(json.dumps(fields,indent=2)+'\n')
(out/'SHA256SUMS').write_text(hashlib.sha256(raw[:end]).hexdigest()+'  wj325-stock.bin\n')
print('Extracted',end,'bytes; configuration and SDK sectors excluded.')
