"""Strict, read-only far-field photometry import. No file repair or external TILT IO.

File C0 is retained, not inferred to be the housing's front or long axis.
Supported: LM-63-1995/2002 Type C TILT=NONE; EULUMDAT one lamp set,
Isym 0/1/2/4, uniform C grid, zero measurement tilt. Dc=0 is unsupported
even with Mc=1/Isym=1; no special interpretation is guessed. Dimensions: width,
length, height in metres. Negative IES shape dimensions are not supported.
References (format facts, not a claim of standards certification):
https://help.autodesk.com/cloudhelp/2015/ENU/AutoCAD-Core/files/GUID-45CAAF1C-7C9D-49A7-B18D-00CA5E2ED380.htm
https://docs.agi32.com/PhotometricToolbox/Content/Open_Tool/eulumdat_file_format.htm
https://evo.support-en.dial.de/support/solutions/articles/9000074164-description-of-the-eulumdat-format
https://dialux4.support-en.dial.de/support/solutions/articles/9000073286-absolute-photometric-luminaire-data-in-eulumdat-format
https://www.radiance-online.org/cgi-bin/viewcvs.cgi/ray/src/cv/ies2rad.c?revision=2.38&view=markup
"""
from __future__ import annotations

from bisect import bisect_right
from dataclasses import dataclass, replace
from hashlib import sha256
import math
from pathlib import Path
import re
from types import MappingProxyType
from typing import Mapping

MAX_FILE_BYTES = 4 * 1024 * 1024
MAX_ANGLES = 1441
MAX_SAMPLES = 500_000
MAX_CANDELA = 1e10
_NUM = re.compile(r'[+-]?(?:\d+(?:\.\d*)?|\.\d+)(?:[eE][+-]?\d+)?\Z')


class PhotometryError(ValueError):
    """Malformed or deliberately unsupported photometry."""


@dataclass(frozen=True)
class Photometry:
    format: str
    source_name: str
    source_sha256: str
    luminaire: str
    c_angles_deg: tuple[float, ...]
    gamma_angles_deg: tuple[float, ...]
    candela_cd: tuple[tuple[float, ...], ...]
    luminaire_lumens: float | None
    input_watts: float
    dimensions_m: tuple[float, float, float]
    metadata: Mapping[str, object]


def _num(token: str, name: str, low: float = -1e12, high: float = 1e12) -> float:
    if not _NUM.fullmatch(token.strip()):
        raise PhotometryError(f'{name}: expected a finite decimal number')
    value = float(token)
    if not math.isfinite(value) or not low <= value <= high:
        raise PhotometryError(f'{name}: value outside supported bounds [{low}, {high}]')
    return value


def _integer(value: float, name: str, low: int, high: int) -> int:
    if value != int(value) or not low <= value <= high:
        raise PhotometryError(f'{name}: expected integer in [{low}, {high}]')
    return int(value)


def _near(a: float, b: float) -> bool:
    return abs(a-b) <= 1e-7


def _angles(values: list[float], name: str, high: float) -> None:
    if not values or any(not 0 <= x <= high for x in values):
        raise PhotometryError(f'{name}: invalid angle range')
    if any(b-a <= 1e-7 for a, b in zip(values, values[1:])):
        raise PhotometryError(f'{name}: angles must increase strictly')


def _gamma(values: list[float]) -> None:
    _angles(values, 'Gamma', 180)
    if not any(values[0] == a and values[-1] == b
               for a, b in ((0, 90), (90, 180), (0, 180))):
        raise PhotometryError('Gamma: only complete lower, upper, or full sphere is supported')


def _matrix(c: list[float], g: list[float], rows: list[list[float]]) -> None:
    if len(rows) != len(c) or any(len(row) != len(g) for row in rows):
        raise PhotometryError('Intensity matrix shape mismatch')
    if len(c)*len(g) > MAX_SAMPLES:
        raise PhotometryError('Expanded intensity matrix exceeds sample limit')
    if any(not math.isfinite(v) or not 0 <= v <= MAX_CANDELA for row in rows for v in row):
        raise PhotometryError('Scaled candela outside supported bounds')
    for idx, angle in enumerate(g):
        if _near(angle, 0) or _near(angle, 180):
            pole = [row[idx] for row in rows]
            # Allow published rounding only; do not repair or average the data.
            if max(pole)-min(pole) > max(0.01, max(pole)*1e-4):
                raise PhotometryError('Intensity values disagree at a shared pole')


def _expand(c: list[float], rows: list[list[float]], symmetry: int):
    result: dict[float, list[float]] = {}
    for angle, row in zip(c, rows):
        images = [angle]
        if symmetry == 1:
            images = [0.0, 360.0]
        elif symmetry == 2:
            images += [360-angle]
        elif symmetry == 4:
            images += [180-angle, 180+angle, 360-angle]
        for image in images:
            result[round(image, 10)] = row
    result[360.0] = result[0.0]
    angles = sorted(result)
    return angles, [result[a] for a in angles]


def _ies(text: str):
    lines = text.splitlines()
    if not lines or lines[0].strip() not in ('IESNA:LM-63-1995', 'IESNA:LM-63-2002'):
        raise PhotometryError('Only IESNA:LM-63-1995 and IESNA:LM-63-2002 are supported')
    tilt = [i for i, line in enumerate(lines) if line.strip().startswith('TILT=')]
    if len(tilt) != 1 or lines[tilt[0]].strip() != 'TILT=NONE':
        raise PhotometryError('Exactly one TILT=NONE is required; embedded/external tilt is unsupported')
    meta = {'version': lines[0].strip(), 'coordinate_axis': 'file C0', 'tilt': 'NONE'}
    headers = []
    luminaire = ''
    for line in lines[1:tilt[0]]:
        match = re.fullmatch(r'\[([^\]]+)\](.*)', line.strip())
        if match:
            tag, value = match[1], match[2].strip()
            headers.append((tag, value))
            if tag == 'LUMINAIRE':
                luminaire = value
        elif line.strip():
            raise PhotometryError('Unexpected unlabelled IES header line')
    meta['headers'] = tuple(headers)
    tokens = re.split(r'[\s,]+', '\n'.join(lines[tilt[0]+1:]).strip())
    if len(tokens) < 13:
        raise PhotometryError('Truncated IES numeric header')
    header = [_num(s, 'IES header') for s in tokens[:13]]
    lamps, lumens, mult, nv, nh, typ, units, width, length, height, bf, reserved, watts = header
    _integer(lamps, 'Lamp count', 1, 100000)
    nv, nh = _integer(nv, 'Nv', 2, MAX_ANGLES), _integer(nh, 'Nh', 1, MAX_ANGLES)
    if nv*nh > MAX_SAMPLES or len(tokens) != 13+nv+nh+nv*nh:
        raise PhotometryError('IES numeric count mismatch or sample limit exceeded')
    if typ != 1 or units not in (1, 2):
        raise PhotometryError('Only Type C with feet or metre dimension units is supported')
    if reserved != 1 or mult <= 0 or bf <= 0:
        raise PhotometryError('Positive candela/ballast factors and reserved factor 1 are required')
    if lumens != -1 and lumens <= 0:
        raise PhotometryError('Lumens per lamp must be positive or -1 (absolute)')
    if min(width, length, height, watts) < 0:
        raise PhotometryError('Negative shape dimensions or input watts are unsupported')
    scale = 0.3048 if units == 1 else 1.0
    dimensions = tuple(x*scale for x in (width, length, height))
    if max(dimensions) > 100 or watts > 1e7:
        raise PhotometryError('Luminaire dimensions or input watts exceed supported bounds')
    g = [_num(t, 'Gamma', 0, 180) for t in tokens[13:13+nv]]
    c = [_num(t, 'C', 0, 360) for t in tokens[13+nv:13+nv+nh]]
    _gamma(g)
    _angles(c, 'C', 360)
    if c[0] != 0:
        raise PhotometryError('IES C angles must start at 0; 90-270 orientation is unsupported')
    if nh == 1:
        sym = 1
    elif c[-1] == 90:
        sym = 4
    elif c[-1] == 180:
        sym = 2
    elif c[-1] == 360:
        sym = 0
    else:
        raise PhotometryError('IES horizontal domain must be 0, 0-90, 0-180, or 0-360')
    values = [_num(t, 'Candela', 0, MAX_CANDELA)*mult*bf for t in tokens[13+nv+nh:]]
    rows = [values[i*nv:(i+1)*nv] for i in range(nh)]
    _matrix(c, g, rows)
    if sym == 0 and any(not math.isclose(a, b, rel_tol=1e-4, abs_tol=.01) for a, b in zip(rows[0], rows[-1])):
        raise PhotometryError('C0 and C360 intensities disagree')
    c, rows = _expand(c, rows, sym)
    _matrix(c, g, rows)
    meta.update(photometry='absolute' if lumens == -1 else 'relative', lamp_count=int(lamps),
                lamp_lumens=None if lumens == -1 else lumens, candela_multiplier=mult,
                ballast_factor=bf, symmetry=sym, missing_hemisphere='zero')
    # Lamp lumens are not luminaire lumens; integration is deliberately not guessed.
    return luminaire, c, g, rows, None, watts, dimensions, meta


def _ldt(text: str):
    lines = text.splitlines()
    if len(lines) < 42:
        raise PhotometryError('Truncated EULUMDAT file')
    at = 0
    def string():
        nonlocal at
        if at >= len(lines):
            raise PhotometryError('Truncated EULUMDAT file')
        val = lines[at].strip()
        at += 1
        return val
    def number(name, low=-1e12, high=1e12):
        return _num(string(), name, low, high)
    maker = string()
    typ = _integer(number('Ityp'), 'Ityp', 0, 3)
    sym = _integer(number('Isym'), 'Isym', 0, 4)
    if sym == 3:
        raise PhotometryError('EULUMDAT Isym3 is not supported')
    mc = _integer(number('Mc'), 'Mc', 1, MAX_ANGLES)
    dc = number('Dc', 0, 360)
    ng = _integer(number('Ng'), 'Ng', 2, MAX_ANGLES)
    dg = number('Dg', 0, 180)
    report, luminaire, lum_number, file_name, date = [string() for _ in range(5)]
    dims = [number('Dimension mm', 0, 100000) for _ in range(9)]
    dff, lor = number('DFF', 0, 100), number('LOR', 0, 100)
    factor = number('Intensity conversion factor', 1e-12, 1e6)
    if number('Measurement tilt') != 0:
        raise PhotometryError('Only zero EULUMDAT measurement tilt is supported')
    if number('Lamp sets') != 1:
        raise PhotometryError('Exactly one EULUMDAT lamp set is supported')
    lamps = _integer(number('Lamp count'), 'Lamp count', -100000, 100000)
    if lamps == 0:
        raise PhotometryError('Lamp count must be nonzero')
    lamp_type = string()
    flux = number('Total flux lm', 1e-9, 1e9)
    colour, cri = string(), string()
    watts = number('Input watts', 0, 1e7)
    for _ in range(10):
        number('Direct ratio', 0, 1)
    if sym in (2, 4) and mc % sym:
        raise PhotometryError('Mc must be divisible by symmetry sector count')
    count = {0: mc, 1: 1, 2: mc//2+1, 4: mc//4+1}[sym]
    if mc*ng > MAX_SAMPLES or len(lines)-at != mc+ng+count*ng:
        raise PhotometryError('EULUMDAT numeric count mismatch or sample limit exceeded')
    c = [number('C', 0, 360) for _ in range(mc)]
    g = [number('Gamma', 0, 180) for _ in range(ng)]
    _angles(c, 'C', 360)
    _gamma(g)
    if g[0] != 0:
        raise PhotometryError('EULUMDAT gamma must start at zero')
    if c[0] != 0 or not _near(dc, 360/mc) or any(not _near(a, i*dc) for i, a in enumerate(c)):
        raise PhotometryError('Only uniform EULUMDAT C grids covering [0,360) are supported')
    if dg and any(not _near(a, i*dg) for i, a in enumerate(g)):
        raise PhotometryError('EULUMDAT gamma angles disagree with Dg')
    rows = [[number('Intensity cd/klm', 0, MAX_CANDELA)*factor*flux/1000 for _ in range(ng)] for _ in range(count)]
    c = c[:count]
    if sym in (2, 4) and c[-1] != 360/sym:
        raise PhotometryError('EULUMDAT symmetry domain endpoint must be exactly 180 or 90 degrees')
    _matrix(c, g, rows)
    c, rows = _expand(c, rows, sym)
    _matrix(c, g, rows)
    meta = dict(manufacturer=maker, report=report, luminaire_number=lum_number,
                source_file_name=file_name, date=date, lamp_type=lamp_type,
                colour=colour, cri=cri, type=typ, symmetry=sym, lamp_count=lamps,
                photometry='absolute' if lamps < 0 else 'relative', total_reference_lumens=flux,
                conversion_factor=factor, downward_fraction_percent=dff, light_output_ratio_percent=lor,
                coordinate_axis='file C0', measurement_tilt=0, missing_hemisphere='zero')
    return luminaire, c, g, rows, flux if lamps < 0 else flux*lor/100, watts, (dims[1]/1000, dims[0]/1000, dims[2]/1000), meta


def parse_photometry(text: str, format: str, source_name: str = '') -> Photometry:
    """Parse supplied text only; reject unsupported data without modifying it."""
    if not isinstance(text, str) or len(text) > MAX_FILE_BYTES:
        raise PhotometryError('Photometry must be bounded text')
    raw = text.encode('utf-8')
    if len(raw) > MAX_FILE_BYTES or '\x00' in text:
        raise PhotometryError('Photometry exceeds size limit or contains NUL')
    if any(len(line) > 65536 for line in text.splitlines()):
        raise PhotometryError('Photometry line exceeds size limit')
    fmt = str(format).lower().lstrip('.')
    if fmt not in ('ies', 'ldt'):
        raise PhotometryError('Only .ies and .ldt formats are supported')
    lum, c, g, rows, flux, watts, dims, meta = (_ies if fmt == 'ies' else _ldt)(text.lstrip('\ufeff'))
    return Photometry(fmt, str(source_name), sha256(raw).hexdigest(), lum,
                      tuple(c), tuple(g), tuple(tuple(row) for row in rows),
                      flux, watts, dims, MappingProxyType(meta))


def load_photometry(path) -> Photometry:
    """Read one local UTF-8/ASCII file, bounded before and during reading."""
    path = Path(path)
    if path.suffix.lower() not in ('.ies', '.ldt'):
        raise PhotometryError('Only .ies and .ldt files are supported')
    if not path.is_file() or path.stat().st_size > MAX_FILE_BYTES:
        raise PhotometryError('Photometry is not a bounded regular file')
    with path.open('rb') as handle:
        raw = handle.read(MAX_FILE_BYTES+1)
    if len(raw) > MAX_FILE_BYTES:
        raise PhotometryError('Photometry exceeds size limit')
    try:
        text = raw.decode('utf-8-sig')
    except UnicodeError as exc:
        raise PhotometryError('Only UTF-8/ASCII photometry is supported') from exc
    return replace(parse_photometry(text, path.suffix, path.name), source_sha256=sha256(raw).hexdigest())


def intensity_cd(photometry: Photometry, c_deg: float, gamma_deg: float) -> float:
    """Bilinear interpolation; C wraps, absent hemisphere is zero, not mirrored."""
    if not math.isfinite(c_deg) or not math.isfinite(gamma_deg):
        raise PhotometryError('Query angles must be finite')
    if not 0 <= gamma_deg <= 180:
        raise PhotometryError('Query gamma must lie in [0,180]')
    c, g, rows = photometry.c_angles_deg, photometry.gamma_angles_deg, photometry.candela_cd
    if gamma_deg < g[0] or gamma_deg > g[-1]:
        return 0.0
    angle = c_deg % 360
    ci = min(len(c)-2, max(0, bisect_right(c, angle)-1))
    gi = min(len(g)-2, max(0, bisect_right(g, gamma_deg)-1))
    ct = (angle-c[ci])/(c[ci+1]-c[ci])
    gt = (gamma_deg-g[gi])/(g[gi+1]-g[gi])
    low = rows[ci][gi]*(1-gt)+rows[ci][gi+1]*gt
    high = rows[ci+1][gi]*(1-gt)+rows[ci+1][gi+1]*gt
    return low*(1-ct)+high*ct
