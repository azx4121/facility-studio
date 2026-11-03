"""Direct-only point-source illuminance on a horizontal receiving plane.

World coordinates are metres, +z up. All luminaires point down. At yaw=0,
the imported file's C0 axis is +x and C90 is +y; positive yaw rotates both when
viewed from above. This is an explicit file-coordinate convention, not a
claim about the luminaire housing's front. No tilt, occlusion or reflection.

E = I(C, gamma) * cos(gamma) / distance**2. Maintenance is applied once,
after adding initial direct contributions. No utilization factor is used.
Reference: IALA International Dictionary, illumination / inverse square law:
https://www.iala.int/wiki/dictionary/images/8/88/20120520_Dictionary_Alphabetical_F-O.pdf
"""

from copy import deepcopy
import math

from .photometry import intensity_cd


METHOD = "direct_point_source_horizontal_plane_v1"
MAX_FIXTURES = 200
MAX_GRID_SIDE = 80
MAX_CONTRIBUTIONS = 2_000_000
MAX_TOTAL_PHOTOMETRIC_SAMPLES = 2_000_000
LIMITATIONS = (
    "Direct-only point-source estimate; not a DIALux-equivalent calculation.",
    "No reflected light, daylight, obstruction shadows, UGR or compliance assessment.",
    "All fixtures face vertically downward; only file-C0 yaw rotation is supported.",
    "Statistics describe the selected cell-centre samples, not continuous extrema or a certified area average.",
    "A coarse grid can miss narrow-beam peaks or dark zones; refine the grid and check convergence.",
    "Isolux lines are piecewise-linear interpolations of calculated grid values.",
    "Far-field validity and minimum installation distance require manufacturer confirmation; numerical clearance is not an accuracy guarantee.",
)


def _number(value, name, low, high):
    if isinstance(value, bool):
        raise ValueError(name + " must be a finite number")
    try:
        number = float(value)
    except (ValueError, TypeError, OverflowError):
        raise ValueError(name + " must be a finite number") from None
    if not math.isfinite(number) or not low <= number <= high:
        raise ValueError(f"{name} must be within [{low:g}, {high:g}]")
    return number


def _integer(value, name, low, high):
    number = _number(value, name, low, high)
    if number != int(number):
        raise ValueError(name + " must be an integer")
    return int(number)


def validate_scene(scene, photometries):
    if not isinstance(scene, dict):
        raise ValueError("Scene must be an object")
    expected = {"length_m", "width_m", "workplane_m", "edge_m", "nx", "ny", "maintenance", "fixtures"}
    if set(scene) != expected:
        raise ValueError("Scene fields must be exactly: " + ", ".join(sorted(expected)))
    if not isinstance(photometries, dict) or not 1 <= len(photometries) <= 32:
        raise ValueError("Import between 1 and 32 photometric sources")
    if any(not isinstance(key, str) or not key or len(key) > 80 for key in photometries):
        raise ValueError("Photometric source IDs must be nonempty text of at most 80 characters")
    if sum(len(source.c_angles_deg) * len(source.gamma_angles_deg) for source in photometries.values()) > MAX_TOTAL_PHOTOMETRIC_SAMPLES:
        raise ValueError("Combined imported photometry exceeds the sample budget")
    length = _number(scene["length_m"], "length_m", .1, 1000)
    width = _number(scene["width_m"], "width_m", .1, 1000)
    plane = _number(scene["workplane_m"], "workplane_m", 0, 100)
    edge = _number(scene["edge_m"], "edge_m", 0, min(length, width) / 2)
    if 2 * edge >= min(length, width):
        raise ValueError("Boundary inset leaves no calculation area")
    nx = _integer(scene["nx"], "nx", 2, MAX_GRID_SIDE)
    ny = _integer(scene["ny"], "ny", 2, MAX_GRID_SIDE)
    maintenance = _number(scene["maintenance"], "maintenance", 0, 1)
    raw_fixtures = scene["fixtures"]
    if not isinstance(raw_fixtures, list) or not 1 <= len(raw_fixtures) <= MAX_FIXTURES:
        raise ValueError(f"Provide between 1 and {MAX_FIXTURES} luminaires")
    if nx * ny * len(raw_fixtures) > MAX_CONTRIBUTIONS:
        raise ValueError("Calculation exceeds the bounded point/luminaire workload")
    fixtures = []
    keys = {"photometry", "x_m", "y_m", "z_m", "yaw_deg", "multiplier"}
    for index, row in enumerate(raw_fixtures, 1):
        if not isinstance(row, dict) or set(row) != keys:
            raise ValueError(f"Luminaire {index}: unsupported or missing fields; tilt is not supported")
        source = row["photometry"]
        if not isinstance(source, str) or source not in photometries:
            raise ValueError(f"Luminaire {index}: unknown photometric source")
        z = _number(row["z_m"], f"luminaire {index} z_m", 0, 200)
        if z - plane < .01:
            raise ValueError(f"Luminaire {index}: must be at least 0.01 m above the workplane")
        fixtures.append(dict(photometry=source,
                             x_m=_number(row["x_m"], f"luminaire {index} x_m", 0, length),
                             y_m=_number(row["y_m"], f"luminaire {index} y_m", 0, width),
                             z_m=z,
                             yaw_deg=_number(row["yaw_deg"], f"luminaire {index} yaw_deg", -36000, 36000) % 360,
                             multiplier=_number(row["multiplier"], f"luminaire {index} multiplier", 0, 1)))
    return dict(length_m=length, width_m=width, workplane_m=plane, edge_m=edge,
                nx=nx, ny=ny, maintenance=maintenance, fixtures=fixtures)


def point_illuminance(photometry, fixture, x_m, y_m, workplane_m):
    """Initial direct lux from one validated down-facing luminaire."""
    dx, dy = x_m - fixture["x_m"], y_m - fixture["y_m"]
    height = fixture["z_m"] - workplane_m
    if height <= 0:
        raise ValueError("Receiving plane must be below the luminaire")
    distance_sq = dx * dx + dy * dy + height * height
    gamma = math.degrees(math.atan2(math.hypot(dx, dy), height))
    c_angle = (math.degrees(math.atan2(dy, dx)) - fixture["yaw_deg"]) % 360
    candela = intensity_cd(photometry, c_angle, gamma)
    return candela * height / distance_sq ** 1.5 * fixture["multiplier"]


def calculate_direct(photometries, scene):
    adopted = validate_scene(scene, photometries)
    length, width, edge = (adopted[key] for key in ("length_m", "width_m", "edge_m"))
    xs = [edge + (i + .5) * (length - 2 * edge) / adopted["nx"] for i in range(adopted["nx"])]
    ys = [edge + (j + .5) * (width - 2 * edge) / adopted["ny"] for j in range(adopted["ny"])]
    initial = [[math.fsum(point_illuminance(photometries[row["photometry"]], row, x, y, adopted["workplane_m"])
                         for row in adopted["fixtures"]) for x in xs] for y in ys]
    maintained = [[value * adopted["maintenance"] for value in row] for row in initial]
    values = [value for row in maintained for value in row]
    if not all(math.isfinite(value) and value >= 0 for value in values):
        raise ValueError("Calculated illuminance is outside the finite nonnegative range")
    average = math.fsum(values) / len(values)
    minimum, maximum = min(values), max(values)
    sources = {}
    warnings = []
    for key in sorted({row["photometry"] for row in adopted["fixtures"]}):
        source = photometries[key]
        sources[key] = dict(format=source.format, source_name=source.source_name,
                            source_sha256=source.source_sha256, luminaire=source.luminaire,
                            luminaire_lumens=source.luminaire_lumens, input_watts=source.input_watts,
                            dimensions_m=list(source.dimensions_m), metadata=deepcopy(dict(source.metadata)))
        size = max(abs(value) for value in source.dimensions_m)
        if size == 0:
            warnings.append(f"{key}: the file reports zero luminaire dimensions (point-source convention). "
                            "Physical luminaire size and far-field distance validity are not established; "
                            "obtain the manufacturer's dimensions and distance limits.")
        elif any(row["photometry"] == key and row["z_m"] - adopted["workplane_m"] < 5 * size
                            for row in adopted["fixtures"]):
            warnings.append(f"{key}: mounting clearance is less than five times the reported luminaire size. "
                            "Far-field point-source accuracy is not established; obtain the manufacturer's distance limits.")
    return dict(method=METHOD, method_version=1, scene=adopted, sources=sources,
                coordinate_system=dict(world_units="m", z_up=True, luminaire_axis="-z",
                                       file_C0_at_yaw0="+x", file_C90_at_yaw0="+y",
                                       positive_yaw="counterclockwise from above"),
                grid=dict(x_m=xs, y_m=ys, initial_lux=initial, lux=maintained,
                          sampling="uniform_cell_centres", unit="lx"),
                summary=dict(average_lux=average, minimum_lux=minimum, maximum_lux=maximum,
                             initial_average_lux=math.fsum(value for row in initial for value in row) / len(values),
                             uniformity_min_avg=minimum / average if average > 0 else None,
                             uniformity_min_max=minimum / maximum if maximum > 0 else None),
                reflected_lux=None, ugr=None, warnings=warnings, limitations=list(LIMITATIONS))


def contour_segments(result, levels):
    """March fixed triangles over actual samples; no invented optical data.

The SW-to-NE cell diagonal is fixed. Contours end at the sample hull, not at
the room boundary. These are rendering interpolations, not additional rays.
"""
    grid = result["grid"]
    xs, ys, values = grid["x_m"], grid["y_m"], grid["lux"]
    if len(levels) > 20:
        raise ValueError("Use at most 20 isolux levels")
    output = {}
    for level in levels:
        level = _number(level, "isolux level", 0, 1e300)
        segments = []
        for j in range(len(ys) - 1):
            for i in range(len(xs) - 1):
                p = [(xs[i], ys[j], values[j][i]), (xs[i + 1], ys[j], values[j][i + 1]),
                     (xs[i + 1], ys[j + 1], values[j + 1][i + 1]), (xs[i], ys[j + 1], values[j + 1][i])]
                for triangle in ((p[0], p[1], p[2]), (p[0], p[2], p[3])):
                    hits = []
                    for a, b in zip(triangle, (triangle[1], triangle[2], triangle[0])):
                        if (a[2] <= level < b[2]) or (b[2] <= level < a[2]):
                            fraction = (level - a[2]) / (b[2] - a[2])
                            point = (a[0] + fraction * (b[0] - a[0]), a[1] + fraction * (b[1] - a[1]))
                            if point not in hits:
                                hits.append(point)
                    if len(hits) == 2 and hits[0] != hits[1]:
                        segments.append((hits[0], hits[1]))
        output[level] = segments
    return output
