"""Synthetic analytic fixtures. No manufacturer file or external IO required."""
import dataclasses
import hashlib
import math
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from facility_studio.photometry import (PhotometryError, parse_photometry,
                                       load_photometry, intensity_cd, MAX_FILE_BYTES)


def ies(c=(0,), g=(0, 90), rows=None, version='2002', **changes):
    rows = rows or [[100 for _ in g] for _ in c]
    header = dict(lamps=1, lumens=-1, mult=1, nv=len(g), nh=len(c), typ=1,
                  units=2, width=.1, length=.2, height=.03, ballast=1, reserved=1, watts=10)
    header.update(changes)
    return '\n'.join(['IESNA:LM-63-'+version, '[TEST]synthetic', '[LUMINAIRE]Test lamp',
                      'TILT=NONE', ' '.join(str(v) for v in header.values()),
                      ' '.join(map(str, g)), ' '.join(map(str, c)),
                      ' '.join(str(v) for row in rows for v in row)])


def ldt(sym=1, lamps=-1, flux=2000, factor=.5, lor=100, tilt=0, sets=1, rows=None):
    mc, ng = 4, 3
    count = {0: 4, 1: 1, 2: 3, 3: 3, 4: 2}[sym]
    rows = rows or [[500, 500, 500] for _ in range(count)]
    lines = ['Test maker', 3, sym, mc, 90, ng, 45, 'report', 'LDT test', 'catalog',
             'test.ldt', '2026', 200, 100, 30, 180, 80, 0, 0, 0, 0,
             100, lor, factor, tilt, sets, lamps, 'LED', flux, '4000K', '80', 10]
    lines += [0]*10 + [0, 90, 180, 270] + [0, 45, 90]
    lines += [value for row in rows for value in row]
    return '\n'.join(map(str, lines))


class PhotometryFormats(unittest.TestCase):
    def test_ies_absolute_multiplier_and_units(self):
        p = parse_photometry(ies(mult=2, ballast=.5, units=1), 'ies')
        self.assertEqual(intensity_cd(p, 999, 45), 100)
        self.assertEqual(p.dimensions_m, (.030480000000000004, .06096000000000001, .009144))
        self.assertIsNone(p.luminaire_lumens)
        self.assertEqual(p.metadata['photometry'], 'absolute')

    def test_ies_relative_not_multiplied_by_lamp_flux(self):
        p = parse_photometry(ies(lamps=4, lumens=3000), 'IES')
        self.assertEqual(intensity_cd(p, 0, 0), 100)
        self.assertIsNone(p.luminaire_lumens)

    def test_missing_hemisphere_is_zero_not_mirrored(self):
        p = parse_photometry(ies(), 'ies')
        self.assertEqual(intensity_cd(p, 0, 100), 0)
        p = parse_photometry(ies(g=(90, 180)), 'ies')
        self.assertEqual(intensity_cd(p, 0, 45), 0)
        self.assertEqual(intensity_cd(p, 0, 135), 100)

    def test_quadrant_symmetry(self):
        p = parse_photometry(ies(c=(0, 90), rows=[[100, 10], [100, 30]]), 'ies')
        self.assertEqual(p.c_angles_deg, (0, 90, 180, 270, 360))
        for a in (45, 135, 225, 315, -45, 405):
            self.assertEqual(intensity_cd(p, a, 90), 20)
        self.assertEqual(intensity_cd(p, 45, 45), 60)

    def test_bilateral_symmetry(self):
        p = parse_photometry(ies(c=(0, 90, 180), rows=[[100, 10], [100, 30], [100, 70]]), 'ies')
        self.assertEqual(intensity_cd(p, 90, 90), 30)
        self.assertEqual(intensity_cd(p, 270, 90), 30)
        self.assertEqual(intensity_cd(p, 180, 90), 70)

    def test_1995_c90_c270_preserves_file_axes_and_mirrors_only_missing_half(self):
        c = (90, 135, 180, 225, 270)
        rows = [[100, value] for value in (10, 30, 70, 50, 90)]
        p = parse_photometry(ies(c=c, rows=rows, version='1995'), 'ies')
        self.assertEqual(p.c_angles_deg, tuple(range(0, 361, 45)))
        expected = {0: 70, 45: 30, 90: 10, 135: 30, 180: 70,
                    225: 50, 270: 90, 315: 50, 360: 70, -45: 50, 405: 30}
        for angle, value in expected.items():
            with self.subTest(angle=angle):
                self.assertEqual(intensity_cd(p, angle, 90), value)
        self.assertEqual(p.metadata['source_c_angles_deg'], c)
        self.assertEqual(p.metadata['symmetry_plane'], 'C90-C270')
        self.assertEqual(p.metadata['coordinate_axis'], 'file C0')
        self.assertEqual(p.metadata['symmetry'], 3)
        self.assertEqual(intensity_cd(p, 45, 45), 65)
        self.assertEqual(intensity_cd(p, 45, 100), 0)

    def test_1995_c90_c270_nonuniform_grid_without_c180(self):
        c = (90, 120, 200, 270)
        rows = [[100, value] for value in (10, 30, 70, 90)]
        p = parse_photometry(ies(c=c, rows=rows, version='1995'), 'ies')
        self.assertEqual(intensity_cd(p, 0, 90), 60)
        self.assertEqual(intensity_cd(p, 180, 90), 60)
        for angle, row in zip(c, rows):
            self.assertEqual(intensity_cd(p, angle, 90), row[-1])
        # Independent evaluation directly on the original measured half.
        for angle in range(-360, 721):
            mapped = angle % 360
            if mapped < 90:
                mapped = 180-mapped
            elif mapped > 270:
                mapped = 540-mapped
            index = next(i for i in range(len(c)-1) if c[i] <= mapped <= c[i+1])
            t = (mapped-c[index])/(c[index+1]-c[index])
            expected = rows[index][-1]*(1-t)+rows[index+1][-1]*t
            self.assertAlmostEqual(intensity_cd(p, angle, 90), expected)
        # Two endpoint rows are also a complete supported half-plane domain.
        p = parse_photometry(ies(c=(90, 270), rows=[[100, 10], [100, 90]], version='1995'), 'ies')
        self.assertEqual(intensity_cd(p, 0, 90), 50)

    def test_1995_c90_c270_measured_sample_shape_and_scaling(self):
        # Synthetic 37 x 37 input exercises the reported grid shape without
        # redistributing manufacturer data. Values vary across both axes.
        c, g = tuple(range(90, 271, 5)), tuple(i*2.5 for i in range(37))
        rows = [[100 + (angle-90)*math.sin(math.radians(gamma)) for gamma in g] for angle in c]
        p = parse_photometry(ies(c=c, g=g, rows=rows, version='1995', mult=2, ballast=.75), 'ies')
        self.assertEqual(len(p.c_angles_deg), 73)
        self.assertEqual(len(p.gamma_angles_deg), 37)
        for angle, row in zip(c, rows):
            for gamma, value in zip(g, row):
                self.assertAlmostEqual(intensity_cd(p, angle, gamma), value*1.5)
                self.assertAlmostEqual(intensity_cd(p, (180-angle) % 360, gamma), value*1.5)

    def test_1995_c90_c270_does_not_relax_invalid_input_guards(self):
        bad = [ies(c=c, version='1995') for c in ((90,), (90, 180), (91, 270),
               (90, 271), (90, 270-1e-8), (90+1e-8, 270), (90, 90, 270))]
        bad += [ies(c=(90, 270), version='2002'),
                ies(c=(90, 270), rows=[[100, 20], [90, 20]], version='1995'),
                ies(c=(90, 270), rows=[[100, -1], [100, 20]], version='1995'),
                ies(c=(90, 270), nv=3, version='1995'),
                ies(c=(90, 270), version='1995')+' 12']
        for value in bad:
            with self.subTest(value=value), self.assertRaises(PhotometryError):
                parse_photometry(value, 'ies')

    def test_1995_c90_c270_load_preserves_raw_file(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder)/'synthetic-1995.ies'
            raw = ies(c=(90, 180, 270), version='1995').replace('\n', '\r\n').encode()
            path.write_bytes(raw)
            before = path.stat().st_mtime_ns
            p = load_photometry(path)
            self.assertEqual(p.source_sha256, hashlib.sha256(raw).hexdigest())
            self.assertEqual(path.read_bytes(), raw)
            self.assertEqual(path.stat().st_mtime_ns, before)

    def test_1995_c90_c270_expansion_keeps_sample_budget(self):
        text = ies(c=(90, 135, 180, 225, 270), version='1995')
        # Ten input samples fit, but eighteen expanded samples do not.
        with patch('facility_studio.photometry.MAX_SAMPLES', 12), \
                self.assertRaisesRegex(PhotometryError, 'Expanded intensity matrix'):
            parse_photometry(text, 'ies')

    def test_1995_c90_c270_upper_and_full_sphere(self):
        for g in ((90, 180), (0, 90, 180)):
            p = parse_photometry(ies(c=(90, 270), g=g, version='1995'), 'ies')
            self.assertEqual(intensity_cd(p, 0, 135), 100)
            self.assertEqual(intensity_cd(p, 315, 45), 0 if g[0] == 90 else 100)

    def test_full_asymmetric_preserved(self):
        p = parse_photometry(ies(c=(0,90,180,270,360), rows=[[100,x] for x in (10,20,30,40,10)]), 'ies')
        self.assertEqual(intensity_cd(p, 270, 90), 40)
        self.assertEqual(intensity_cd(p, 315, 90), 25)

    def test_ies_rejections(self):
        bad = [ies(typ=2), ies(units=3), ies(width=-1), ies(reserved=.5),
               ies(nv=3), ies(mult=0), ies(ballast=0), ies(lumens=0),
               ies(c=(90,270)), ies(c=(0,120)), ies(g=(0,80)),
               ies(g=(0,0)), ies(rows=[[100,-1]]),
               ies(c=(0,90), rows=[[100,20],[90,20]]),
               ies(c=(0,360), rows=[[100,20],[100,30]]),
               ies().replace('TILT=NONE','TILT=INCLUDE'),
               ies().replace('TILT=NONE','TILT=../secret'),
               ies().replace('2002','2019'), ies()+' 12',
               ies().replace('100 100','NaN 100'), ies().replace('100 100','1e309 100')]
        for value in bad:
            with self.subTest(value=value):
                with self.assertRaises(PhotometryError):
                    parse_photometry(value, 'ies')

    def test_ldt_absolute_cd_per_klm_not_raw_cd(self):
        p = parse_photometry(ldt(), 'ldt')
        self.assertAlmostEqual(intensity_cd(p, 50, 30), 500)
        self.assertEqual(p.luminaire_lumens, 2000)
        self.assertEqual(p.dimensions_m, (.1,.2,.03))

    def test_ldt_relative_total_flux_and_no_double_lor(self):
        p = parse_photometry(ldt(lamps=4, lor=50), 'ldt')
        self.assertEqual(intensity_cd(p, 0, 0), 500)
        self.assertEqual(p.luminaire_lumens, 1000)
        self.assertEqual(p.metadata['photometry'], 'relative')

    def test_ldt_no_symmetry_seam(self):
        p = parse_photometry(ldt(sym=0, rows=[[100, x, x] for x in (10,20,30,40)]), 'ldt')
        self.assertEqual(intensity_cd(p, 315, 90), 25)
        self.assertEqual(intensity_cd(p, 360, 90), 10)

    def test_ldt_symmetry(self):
        for sym in (2,4):
            p = parse_photometry(ldt(sym=sym), 'ldt')
            self.assertEqual(p.c_angles_deg[0], 0)
            self.assertEqual(p.c_angles_deg[-1], 360)
            self.assertEqual(intensity_cd(p, 333, 22), 500)

    def test_ldt_rejections(self):
        bad = [ldt(sym=3), ldt(tilt=1), ldt(sets=2), ldt(lamps=0), ldt(flux=0),
               ldt(factor=0), ldt()+'\n99', ldt()+'\n\n', ldt().rsplit('\n',1)[0]]
        for value in bad:
            with self.subTest(value=value):
                with self.assertRaises(PhotometryError):
                    parse_photometry(value, 'ldt')

    def test_ldt_blank_text_line_retained(self):
        value = ldt().replace('report\n', '\n')
        p = parse_photometry(value, 'ldt')
        self.assertEqual(p.metadata['report'], '')
        self.assertEqual(intensity_cd(p, 0, 0), 500)

    def test_ldt_grid_and_scaling_rejections(self):
        original = ldt().splitlines()
        # Zero-based fields: Mc, Dc, Ng, Dg, intensity conversion factor.
        for index, replacement in ((3, '5'), (4, '0'), (6, '30'),
                                   (23, '1e6'), (42, '1'), (43, '89')):
            lines = original.copy()
            lines[index] = replacement
            if index == 23:
                lines[28] = '1e9'  # combined scale exceeds allowed candela
            with self.subTest(index=index):
                with self.assertRaises(PhotometryError):
                    parse_photometry('\n'.join(lines), 'ldt')

    def test_1995_comma_tokens_and_exact_boundary(self):
        value = ies().replace('2002', '1995')
        lines = value.splitlines()
        lines[4] = lines[4].replace(' ', ',')
        p = parse_photometry('\n'.join(lines), 'ies')
        self.assertEqual(intensity_cd(p, 360, 90), 100)
        self.assertEqual(intensity_cd(p, 0, 90.0001), 0)

    def test_exact_domain_endpoints_no_epsilon_normalization(self):
        bad = [ies(c=(1e-8,)), ies(c=(0, 90-1e-8)),
               ies(c=(0, 180-1e-8)), ies(c=(0, 360-1e-8)),
               ies(g=(1e-8, 90)), ies(g=(0, 90-1e-8)),
               ies(g=(90+1e-8, 180)), ies(g=(0, 180-1e-8))]
        for value in bad:
            with self.subTest(value=value):
                with self.assertRaises(PhotometryError):
                    parse_photometry(value, 'ies')
        for sym, index, value in ((1, 42, '1e-8'), (1, 46, '1e-8'),
                                  (1, 48, '89.99999999'),
                                  (2, 44, '179.99999999'),
                                  (4, 43, '89.99999999')):
            lines = ldt(sym=sym).splitlines()
            lines[index] = value
            with self.subTest(sym=sym, index=index):
                with self.assertRaises(PhotometryError):
                    parse_photometry('\n'.join(lines), 'ldt')

    def test_raw_headers_cannot_override_metadata(self):
        injected = ('[version]FAKE\n[coordinate_axis]front\n'
                    '[tilt]INCLUDE\n[photometry]relative\n[headers]fake\n'
                    '[version]SECOND\n')
        p = parse_photometry(ies().replace('TILT=NONE', injected+'TILT=NONE'), 'ies')
        self.assertEqual(p.metadata['version'], 'IESNA:LM-63-2002')
        self.assertEqual(p.metadata['coordinate_axis'], 'file C0')
        self.assertEqual(p.metadata['tilt'], 'NONE')
        self.assertEqual(p.metadata['photometry'], 'absolute')
        self.assertEqual(p.luminaire, 'Test lamp')
        headers = p.metadata['headers']
        self.assertIsInstance(headers, tuple)
        self.assertEqual(tuple(pair for pair in headers if pair[0] == 'version'),
                         (('version', 'FAKE'), ('version', 'SECOND')))
        with self.assertRaises(TypeError):
            headers[0] = ('TEST', 'changed')
        with self.assertRaises(TypeError):
            headers[0][1] = 'changed'
        self.assertEqual(p.source_sha256,
                         hashlib.sha256(ies().replace('TILT=NONE', injected+'TILT=NONE').encode()).hexdigest())

    def test_immutable_and_hash(self):
        text = ies()
        p = parse_photometry(text, '.ies', 'test.ies')
        self.assertEqual(p.source_sha256, hashlib.sha256(text.encode()).hexdigest())
        with self.assertRaises(dataclasses.FrozenInstanceError):
            p.luminaire = 'changed'
        with self.assertRaises(TypeError):
            p.metadata['a'] = 1

    def test_loading_bom_crlf_byte_hash_and_no_write(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder)/'test.IES'
            raw = b'\xef\xbb\xbf'+ies().replace('\n','\r\n').encode()
            path.write_bytes(raw)
            before = path.stat().st_mtime_ns
            p = load_photometry(path)
            self.assertEqual(p.source_sha256, hashlib.sha256(raw).hexdigest())
            self.assertEqual(path.read_bytes(), raw)
            self.assertEqual(path.stat().st_mtime_ns, before)

    def test_bounds_and_query(self):
        for value in ('\x00', ' '* (MAX_FILE_BYTES+1), ies().replace('100 100','1e20 100')):
            with self.assertRaises(PhotometryError):
                parse_photometry(value, 'ies')
        p = parse_photometry(ies(), 'ies')
        for c, g in ((float('nan'),0),(0,float('inf')),(0,-1),(0,181)):
            with self.assertRaises(PhotometryError):
                intensity_cd(p,c,g)


# Separate, non-cancelling scale and nonuniform anisotropic fixtures.
def ies_payload(mult=3, ballast=.8, relative=False):
    return '\n'.join([
        'IESNA:LM-63-2002', '[TEST] Independent synthetic fixture',
        '[TESTLAB] Software regression, not a physical laboratory', '[ISSUEDATE]2026-11-03',
        '[MANUFAC] No real manufacturer', 'TILT=NONE',
        f'4 {3000 if relative else -1} {mult} 4 5 1 2 0.1 0.2 0.03',
        f'{ballast} 1 40', '0 30 90 180', '0 90 180 270 360',
        '100 110 10 0', '100 210 20 0', '100 310 30 0',
        '100 410 40 0', '100 110 10 0'])

def ldt_payload(sym, negative=False):
    mc, dc, ng = 8, 45, 4
    counts = {0: 8, 1: 1, 2: 5, 4: 3}
    body = [
        'Independent synthetic fixture', 3, sym, mc, dc, ng, 0,
        'Software regression only', 'Synthetic anisotropic source', 'NONE', 'synthetic.ldt', '2026-11-03',
        200, 100, 30, 200, 100, 0, 0, 0, 0,
        100, 50, 2, 0, 1, -4 if negative else 4, 'Synthetic', 3000, 'N/A', 'N/A', 40,
    ]
    body += [0]*10 + list(range(0, 360, 45)) + [0, 30, 90, 180]
    for index in range(counts[sym]):
        body += [100, 110+100*index, 10+10*index, 0]
    return '\n'.join(map(str, body))

class IndependentPhotometryChecks(unittest.TestCase):
    def test_non_cancelling_ies_absolute_and_relative_factors(self):
        for relative in (False, True):
            p = parse_photometry(ies_payload(relative=relative), 'ies')
            self.assertAlmostEqual(intensity_cd(p, 90, 30), 504)
            self.assertAlmostEqual(intensity_cd(p, 45, 15), 312)
            self.assertEqual(p.input_watts, 40)

    def test_non_cancelling_ldt_reference_flux_and_conversion(self):
        for negative in (False, True):
            p = parse_photometry(ldt_payload(0, negative), 'ldt')
            self.assertAlmostEqual(intensity_cd(p, 90, 30), 1860)
            self.assertEqual(p.luminaire_lumens, 3000 if negative else 1500)

    def test_ldt_asymmetric_wrap_and_nonuniform_gamma(self):
        p = parse_photometry(ldt_payload(0), 'ldt')
        self.assertAlmostEqual(intensity_cd(p, 315, 30), 4860)
        self.assertAlmostEqual(intensity_cd(p, 337.5, 30), 2760)
        self.assertAlmostEqual(intensity_cd(p, 337.5, 60), 1515)
        self.assertAlmostEqual(intensity_cd(p, -22.5, 60), 1515)

    def test_anisotropic_ldt_bilateral(self):
        p = parse_photometry(ldt_payload(2), 'ldt')
        expected_rows = [110, 210, 310, 410, 510, 410, 310, 210]
        for c, expected in zip(range(0,360,45), expected_rows):
            self.assertAlmostEqual(intensity_cd(p, c, 30), expected*6)

    def test_anisotropic_ldt_quadrant(self):
        p = parse_photometry(ldt_payload(4), 'ldt')
        expected_rows = [110, 210, 310, 210, 110, 210, 310, 210]
        for c, expected in zip(range(0,360,45), expected_rows):
            self.assertAlmostEqual(intensity_cd(p, c, 30), expected*6)

    def test_ldt_axial(self):
        p = parse_photometry(ldt_payload(1), 'ldt')
        for c in range(-720, 721, 7):
            self.assertAlmostEqual(intensity_cd(p, c, 30), 660)

    def test_ldt_negative_or_nonfinite_rejected(self):
        original = ldt_payload(0).splitlines()
        for value in ('-1', 'NaN', 'inf', '1e309'):
            payload = original[:]
            payload[-2] = value
            with self.assertRaises(PhotometryError):
                parse_photometry('\n'.join(payload), 'ldt')


if __name__ == '__main__':
    unittest.main(verbosity=2)
