"""Versioned whole-project documents, including editable drafts and AHU links.

Calculation documents migrate older schemas without losing drafts. This envelope
owns project identity, AHU instances, saved A/B snapshots and transfer receipts.
"""
import copy
import json
import uuid
from pathlib import Path
from .errors import ValidationError
from .schema import FIELDS, PD_DEFAULTS, PD_KEYS, SCHEMA_VERSION, VERSION
from .ahu_schema import NM_DEFAULTS
from .project_store import validate_provenance
from .json_io import read_json_file
from .contributions import empty_ledger, validate_ledger


def raw_project(project):
    from .engine import migrate_project
    p = migrate_project(copy.deepcopy(project))
    if not isinstance(p, dict) or set(p) != {"schema_version", "inputs", "pressure_drop", "provenance"} or p["schema_version"] != SCHEMA_VERSION:
        raise ValidationError("主案結構或版本不符")
    if not isinstance(p["inputs"], dict) or set(p["inputs"]) != set(FIELDS):
        raise ValidationError("主案欄位不完整")
    bounded_strings(p["inputs"])
    if not isinstance(p["pressure_drop"], dict) or set(p["pressure_drop"]) != set(PD_KEYS):
        raise ValidationError("壓損資料不完整")
    for row in p["pressure_drop"].values():
        if not isinstance(row, dict) or set(row) != set(PD_DEFAULTS):
            raise ValidationError("壓損欄位不完整")
        bounded_strings(row)
    validate_provenance(p["provenance"], FIELDS)
    return p


def bounded_strings(values):
    if any(not isinstance(v, str) or len(v) > 1000 for v in values.values()):
        raise ValidationError("草稿必須為有長度限制的文字，不能包含執行物件")


def new_workspace(project):
    return dict(kind="facility_workspace", workspace_version=2, app_version=VERSION,
                project_id=uuid.uuid4().hex, main=raw_project(project),
                ahus=[], comparisons={}, receipts=[], drafts={}, demand_ledger=empty_ledger())


def validate_workspace(doc):
    if not isinstance(doc, dict):
        raise ValidationError("不是專案物件")
    if doc.get("kind") != "facility_workspace":
        return new_workspace(doc)
    keys = {"kind", "workspace_version", "app_version", "project_id", "main", "ahus", "comparisons", "receipts", "drafts"}
    if doc.get("workspace_version") == 1 and set(doc) == keys:
        doc = copy.deepcopy(doc)
        doc.update(workspace_version=2, demand_ledger=empty_ledger())
    keys.add("demand_ledger")
    if set(doc) != keys or doc["workspace_version"] != 2:
        raise ValidationError("不支援的整案保存格式")
    d = copy.deepcopy(doc)
    d["demand_ledger"] = validate_ledger(d["demand_ledger"])
    if not isinstance(d["project_id"], str) or not 1 <= len(d["project_id"]) <= 100:
        raise ValidationError("專案識別碼不合法")
    if not isinstance(d["app_version"], str) or len(d["app_version"]) > 30:
        raise ValidationError("軟體版本不合法")
    d["main"] = raw_project(d["main"])
    if not isinstance(d["drafts"], dict) or set(d["drafts"]) - set(FIELDS):
        raise ValidationError("保留草稿格式不符")
    for k, v in d["drafts"].items():
        validate_provenance({k: v}, [k])
    if not isinstance(d["ahus"], list) or len(d["ahus"]) > 100:
        raise ValidationError("單機清單過大或格式不符")
    ids = set()
    for entry in d["ahus"]:
        expected = {"id", "inputs", "source_project_id"}
        if not isinstance(entry, dict) or set(entry) != expected:
            raise ValidationError("單機記錄格式不符")
        for name in ["id", "source_project_id"]:
            if not isinstance(entry[name], str) or len(entry[name]) > 100:
                raise ValidationError("單機來源識別不符")
        if not entry["id"] or entry["id"] in ids:
            raise ValidationError("單機識別碼重複或空白")
        ids.add(entry["id"])
        if not isinstance(entry["inputs"], dict) or set(entry["inputs"]) != set(NM_DEFAULTS):
            raise ValidationError("單機草稿欄位不完整")
        bounded_strings(entry["inputs"])
    if not isinstance(d["comparisons"], dict) or set(d["comparisons"]) - {"A", "B"}:
        raise ValidationError("方案比較格式不符")
    for tag, result in list(d["comparisons"].items()):
        if not isinstance(result, dict) or not isinstance(result.get("hash"), str):
            raise ValidationError("方案快照不完整")
        from .utils import project_hash
        original_main = result.get("project")
        if result["hash"] != project_hash(original_main):
            raise ValidationError("方案快照與其輸入雜湊不一致")
        saved_main = raw_project(original_main)
        if any(k not in result for k in ["qs", "moisture", "summer", "winter", "water", "electric", "quality"]):
            raise ValidationError("方案快照缺少計算依據")
        if project_hash(saved_main) != result["hash"]:
            from .engine import calculate
            upgraded = calculate(saved_main)
            for key in ("captured_at", "owner_project_id"):
                if key in result:
                    upgraded[key] = result[key]
            upgraded["migration_note"] = "舊方案依保留輸入重新檢核；原版本 " + str(result.get("version", "?")) + "，原雜湊 " + result["hash"]
            d["comparisons"][tag] = upgraded
    for result in d["comparisons"].values():
        from .design_workflow import compare_results
        import math
        try:
            metrics = compare_results(result, result)["metrics"]
            if any(not isinstance(x["a"], (int, float)) or not math.isfinite(x["a"]) for x in metrics):
                raise ValueError("non-finite comparison")
            if not isinstance(result["quality"]["status"], str):
                raise ValueError("invalid status")
        except (KeyError, TypeError, ValueError, OverflowError):
            raise ValidationError("方案快照的比較數值不完整") from None
    if not isinstance(d["receipts"], list) or len(d["receipts"]) > 500:
        raise ValidationError("來源快照清單過大或不合法")
    for receipt in d["receipts"]:
        if not isinstance(receipt, dict) or set(receipt) != {"source_id", "source_project_id", "source_name", "source_hash", "captured_at", "values", "status"}:
            raise ValidationError("來源快照格式不符")
        if not isinstance(receipt["values"], dict) or set(receipt["values"]) - set(FIELDS):
            raise ValidationError("來源快照目標欄位不符")
        bounded_strings(receipt["values"])
        bounded_strings({k: v for k, v in receipt.items() if k != "values"})
    return d


def read_workspace(path):
    path = Path(path)
    if path.stat().st_size > 15_000_000:
        raise ValidationError("整案檔案不得超過 15 MB")
    return validate_workspace(read_json_file(path))
