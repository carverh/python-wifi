import subprocess
import re
import textwrap

from wifi.models import Cell

cells_re = re.compile(r'Cell \d+ - ')
quality_re = re.compile(r'Quality=(\d+/\d+).*Signal level=(-\d+) dBm')
frequency_re = re.compile(r'([\d\.]+ .Hz).*')


scalars = (
    'address',
    'channel',
    'mode',
)

identity = lambda x: x

key_translations = {
    'encryption key': 'encrypted',
    'essid': 'ssid',
}


def normalize_key(key):
    key = key.strip().lower()

    key = key_translations.get(key, key)

    return key.replace(' ', '')

normalize_value = {
    'ssid': lambda v: v.strip('"'),
    'frequency': lambda v: frequency_re.search(v).group(1),
    'encrypted': lambda v: v == 'on',
    'channel': int,
    'address': identity,
    'mode': identity,
}


def split_on_colon(string):
    key, _, value = map(lambda s: s.strip(), string.partition(':'))

    return key, value


def normalize(cell_block):
    """
    The cell blocks come in with the every line except the first
    indented 20 spaces.  This will remove all of that extra stuff.
    """
    lines = textwrap.dedent(' ' * 20 + cell_block).splitlines()
    cell = Cell()

    while lines:
        line = lines.pop(0)

        if line.startswith('Quality'):
            cell.quality, cell.signal = quality_re.search(line).groups()
        elif line.startswith('Bit Rates'):
            values = split_on_colon(line)[1].split('; ')

            # consume next line of bit rates, because they are split on
            # different lines, sometimes...
            while lines[0].startswith(' ' * 10):
                values += lines.pop(0).strip().split('; ')

            cell.bitrates.extend(values)
        elif ':' in line:
            key, value = split_on_colon(line)
            key = normalize_key(key)

            if key == 'ie':
                if 'Unknown' in value:
                    continue

                # consume remaining block
                values = [value]
                while lines[0].startswith(' ' * 4):
                    values.append(lines.pop(0).strip())

                if 'WPA2' in value:
                    cell.encryption_type = 'wpa2'
            elif key in normalize_value:
                setattr(cell, key, normalize_value[key](value))
    return cell


def scan():
    iwlist_scan = subprocess.check_output(['/sbin/iwlist', 'wlan0', 'scan'])

    cells = map(normalize, cells_re.split(iwlist_scan)[1:])

    return cells