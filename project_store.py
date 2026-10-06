"""Project provenance and recovery; no code execution or silent value repair."""

from pathlib import Path
from datetime import datetime, timezone
import json, os, uuid
from .errors import ValidationError
from .utils import atomic_text
from .platform_support import app_data_root

SOURCE_TYPES = [
    "系統預設",
    "使用者輸入",
    "舊專案輸入",
    "計算連動",
    "單位等值換算",
    "原廠資料",
    "來源快照",
]


def provenance_record(source, note, value):
    return {
        "source": source,
        "note": note[:1000],
        "value": str(value),
        "recorded_at": datetime.now(timezone.utc).isoformat(),
    }


def validate_provenance(provenance, fields):
    if not isinstance(provenance, dict) or set(provenance) != set(fields):
        raise ValidationError("參數來源欄位不完整", code="invalid_provenance")
    for key, item in provenance.items():
        if (
            not isinstance(item, dict)
            or not {"source", "note"}.issubset(item)
            or set(item) - {"source", "note", "value", "recorded_at"}
            or item["source"] not in SOURCE_TYPES
            or not isinstance(item["note"], str)
            or len(item["note"]) > 1000
        ):
            raise ValidationError("參數來源格式不合法", key, "invalid_provenance")
        for name in ["value", "recorded_at"]:
            if name in item and (
                not isinstance(item[name], str) or len(item[name]) > 1000
            ):
                raise ValidationError("來源版本資料不合法", key, "invalid_provenance")
        if item["source"] == "原廠資料" and not item["note"].strip():
            raise ValidationError(
                "原廠資料必須註記文件或選型編號", key, "source_required"
            )


def app_data():
    root = app_data_root()
    root.mkdir(parents=True, exist_ok=True)
    return root


def save_project_file(path, project):
    path = Path(path)
    if path.exists():
        atomic_text(
            path.with_suffix(path.suffix + ".bak"), path.read_text(encoding="utf-8-sig")
        )
    atomic_text(
        path, json.dumps(project, ensure_ascii=False, indent=2, allow_nan=False)
    )


def recovery_save(project, token):
    directory = app_data() / "Recovery"
    directory.mkdir(exist_ok=True)
    doc = dict(
        kind="recovery",
        saved_at=datetime.now(timezone.utc).isoformat(),
        project=project,
    )
    path = directory / (token + ".json")
    atomic_text(path, json.dumps(doc, ensure_ascii=False, indent=2))
    return path


def read_recovery(path):
    path = Path(path)
    if path.stat().st_size > 15_000_000:
        raise ValidationError("復原檔案過大")
    doc = json.loads(path.read_text(encoding="utf-8-sig"))
    if (
        not isinstance(doc, dict)
        or doc.get("kind") != "recovery"
        or not isinstance(doc.get("project"), dict)
    ):
        raise ValidationError("不是本工具的復原檔")
    return doc["project"]
