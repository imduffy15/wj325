"""Reconstruct only the flash bytes needed by conversion tests, without private settings."""
from pathlib import Path
import hashlib,json,struct

def load_firmware_fixture():
    root=Path(__file__).resolve().parents[1]
    app=(root/'firmware/wj325-stock.bin').read_bytes()
    expected=(root/'firmware/SHA256SUMS').read_text().split()[0]
    assert hashlib.sha256(app).hexdigest()==expected
    assert len(app)==435552
    data=bytearray(b'\xff'*2097152)
    data[:len(app)]=app
    data[0xfb000:0xfb544]=bytes(0x544)
    c=json.loads((root/'firmware/calibration.json').read_text())
    data[0xfb014]=c['data_rate_index']
    struct.pack_into('<ii',data,0xfb528,c['full'],c['zero'])
    struct.pack_into('<i',data,0xfb534,c['upper_temperature'])
    data[0xfb538]=c['pt1000_mode']
    struct.pack_into('<ff',data,0xfb53c,c['rzero'],c['vref'])
    return bytes(data)
