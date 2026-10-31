"""Public headless API. Desktop modules are imported only by the launcher."""

from .engine import (
    calculate,
    read_project,
    validate_project,
    migrate_project,
    wetbulb,
    blend,
    condition_air,
    coil_record,
)
from .schema import (
    default_project,
    DEFAULTS,
    FIELDS,
    SCHEMA_VERSION,
    VERSION,
    PD_DEFAULTS,
)
from .ahu_engine import nm_calculate, nm_read_project, nm_validate
from .ahu_schema import NM_DEFAULTS, NM_FIELDS
from .reports import report, nm_report
from .services import independent_domains, converted_units, UNIT_VALUES
from .utils import (
    state_trh,
    state_tw,
    dewpoint,
    enthalpy,
    project_hash,
    atomic_text,
    US_RT_KW,
    G,
)
from .data import VOLTAGE_MAP, WIRE_DB, NFB_SIZES
from .errors import ValidationError, InputError
