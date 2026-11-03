"""Local FEED document register. Records human review, never certifies a design.

No network or automatic directory scan. Evidence is copied only on an explicit
attachment action. Review fingerprints cover the entire design basis and register.
"""
from copy import deepcopy
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import re
from uuid import uuid4

FIELDS = {
    "project": "專案名稱", "revision": "設計版次", "site": "廠址／適用地區",
    "owner": "業主／委託單位", "scope": "系統範圍與界面",
    "conditions": "設計工況／最不利條件", "units": "單位與基準狀態",
    "criteria": "驗收準則與允許誤差", "preparer": "編製者",
}
DELIVERABLES = {
    "basis": "設計依據與適用規範",
    "balance": "熱質平衡與公用需求",
    "process": "流程圖／管儀圖與系統界面",
    "equipment": "設備表與規格書",
    "piping": "管路／風管／保溫與材料選用",
    "electrical": "用電負載／單線圖與保護",
    "control": "控制理念／連鎖／I/O 點表",
    "layout": "配置與維修／施工空間",
    "risk": "安全風險與適用危害分析",
    "quantity": "工程數量／成本與估算依據",
    "verification": "工程核對與軟體測試證據",
    "acceptance": "業主驗收清單與簽核要求",
}
MAX_BYTES = 50 * 1024 * 1024
LIMITATION = "本表只檢查文件完整性與人工覆核紀錄；不驗證內容正確性、簽章身分或工程認證。"


def now():
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def digest(value):
    return hashlib.sha256(json.dumps(value, ensure_ascii=False, sort_keys=True,
                                    separators=(",", ":"), allow_nan=False).encode()).hexdigest()


def new_dossier():
    return dict(kind="facility_design_dossier", schema=1, id=uuid4().hex,
                basis={k: "" for k in FIELDS}, standards=[],
                documents={k: dict(evidence=[], exclusion="") for k in DELIVERABLES},
                reviews={})


def _text(value, name, required=True):
    if not isinstance(value, str) or len(value) > 20000 or "\x00" in value:
        raise ValueError(f"{name}必須為有效文字")
    if required and not value.strip():
        raise ValueError(f"請填寫{name}")
    return value.strip()


def _keys(value, keys, label):
    if not isinstance(value, dict) or set(value) != set(keys):
        raise ValueError(f"{label}欄位不完整或含未知欄位")


def validate(data):
    _keys(data, ("kind", "schema", "id", "basis", "standards", "documents", "reviews"), "設計資料")
    if data["kind"] != "facility_design_dossier" or type(data["schema"]) is not int or data["schema"] != 1:
        raise ValueError("不支援的設計資料版本")
    if not isinstance(data["id"], str) or not re.fullmatch(r"[a-f0-9]{32}", data["id"]):
        raise ValueError("無效的專案識別碼")
    _keys(data["basis"], FIELDS, "設計依據")
    for key, label in FIELDS.items():
        _text(data["basis"][key], label, False)
    if not isinstance(data["standards"], list) or len(data["standards"]) > 1000:
        raise ValueError("規範清單格式錯誤")
    for standard in data["standards"]:
        _keys(standard, ("name", "edition", "clause", "scope", "source"), "規範")
        for key in standard:
            _text(standard[key], "規範" + key)
    _keys(data["documents"], DELIVERABLES, "交付清單")
    paths = set()
    for key, doc in data["documents"].items():
        _keys(doc, ("evidence", "exclusion"), "交付項目")
        _text(doc["exclusion"], "不適用原因", False)
        if not isinstance(doc["evidence"], list) or len(doc["evidence"]) > 1000:
            raise ValueError("證據清單格式錯誤")
        for record in doc["evidence"]:
            _keys(record, ("name", "path", "sha256", "bytes"), "證據")
            _text(record["name"], "證據名稱")
            if not isinstance(record["path"], str) or not re.fullmatch(r"evidence/[a-f0-9]{32}\.bin", record["path"]):
                raise ValueError("證據路徑必須在專案 evidence 資料夾內")
            if record["path"] in paths:
                raise ValueError("證據路徑重複")
            paths.add(record["path"])
            if not isinstance(record["sha256"], str) or not re.fullmatch(r"[a-f0-9]{64}", record["sha256"]):
                raise ValueError("證據雜湊格式錯誤")
            if type(record["bytes"]) is not int or not 0 < record["bytes"] <= MAX_BYTES:
                raise ValueError("證據檔案大小無效")
    if not isinstance(data["reviews"], dict) or set(data["reviews"]) - set(DELIVERABLES):
        raise ValueError("覆核項目無效")
    for review in data["reviews"].values():
        _keys(review, ("reviewer", "decision", "comment", "time", "snapshot"), "覆核")
        for key in review:
            _text(review[key], "覆核" + key)
        if review["decision"] not in ("accepted", "rejected"):
            raise ValueError("覆核決定無效")
        if not re.fullmatch(r"[a-f0-9]{64}", review["snapshot"]):
            raise ValueError("覆核快照無效")
        try:
            timestamp = datetime.fromisoformat(review["time"])
            if timestamp.tzinfo is None:
                raise ValueError()
        except ValueError:
            raise ValueError("覆核時間必須含時區") from None
    return data


def snapshot(data):
    validate(data)
    return digest({k: v for k, v in data.items() if k != "reviews"})


def _safe_file(root, relative):
    root = Path(root).resolve(strict=True)
    path = root / relative
    if path.is_symlink() or path.parent.is_symlink() or not path.is_file():
        raise ValueError("證據遺失或使用符號連結")
    if not path.resolve().is_relative_to(root):
        raise ValueError("證據超出專案範圍")
    if not 0 < path.stat().st_size <= MAX_BYTES:
        raise ValueError("證據不可空白或超過 50 MiB")
    return path


def _hash_file(path):
    h = hashlib.sha256()
    total = 0
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            total += len(chunk)
            if total > MAX_BYTES:
                raise ValueError("證據超過 50 MiB")
            h.update(chunk)
    return h.hexdigest(), total


def attach(data, root, key, source):
    validate(data)
    if key not in DELIVERABLES:
        raise ValueError("交付項目無效")
    source = Path(source)
    if source.is_symlink() or not source.is_file() or not 0 < source.stat().st_size <= MAX_BYTES:
        raise ValueError("只能附加非空白的一般檔案，限 50 MiB，不接受符號連結")
    root = Path(root).resolve(strict=True)
    folder = root / "evidence"
    if folder.is_symlink():
        raise ValueError("證據資料夾不得為符號連結")
    folder.mkdir(exist_ok=True)
    relative = f"evidence/{uuid4().hex}.bin"
    target = root / relative
    h, total = hashlib.sha256(), 0
    try:
        with source.open("rb") as src, target.open("xb") as dst:
            for chunk in iter(lambda: src.read(1024 * 1024), b""):
                total += len(chunk)
                if total > MAX_BYTES:
                    raise ValueError("證據超過 50 MiB")
                h.update(chunk)
                dst.write(chunk)
        if total == 0:
            raise ValueError("證據不可空白")
    except Exception:
        target.unlink(missing_ok=True)  # Only our own failed new copy.
        raise
    record = dict(name=source.name, path=relative, sha256=h.hexdigest(), bytes=total)
    data["documents"][key]["evidence"].append(record)
    return record


def evaluate(data, root):
    validate(data)
    missing = [label for key, label in FIELDS.items() if not data["basis"][key].strip()]
    if not data["standards"]:
        missing.append("適用規範（名稱、版次、條號、適用範圍、來源）")
    current = snapshot(data)
    rows = []
    for key, label in DELIVERABLES.items():
        doc = data["documents"][key]
        issues = []
        if not doc["evidence"] and not doc["exclusion"].strip():
            issues.append("待附文件或不適用理由")
        for record in doc["evidence"]:
            try:
                h, size = _hash_file(_safe_file(root, record["path"]))
                if h != record["sha256"] or size != record["bytes"]:
                    issues.append("證據內容已變更：" + record["name"])
            except (OSError, ValueError):
                issues.append("證據無法核對：" + record["name"])
        review = data["reviews"].get(key)
        if not review:
            issues.append("待人工覆核")
        elif review["snapshot"] != current:
            issues.append("設計依據或交付清單已變更，舊覆核失效")
        elif review["reviewer"].strip() == data["basis"]["preparer"].strip():
            issues.append("覆核者不可與編製者相同")
        elif review["decision"] == "rejected":
            issues.append("人工覆核要求修正：" + review["comment"])
        rows.append(dict(key=key, label=label, issues=issues,
                         status="待處理" if issues else "已記錄覆核（不適用）" if doc["exclusion"].strip() else "已記錄覆核"))
    ready = not missing and all(not row["issues"] for row in rows)
    return dict(status="文件齊備，可送工程審查" if ready else "文件／覆核尚未齊備",
                can_submit=ready, missing_basis=missing, rows=rows, snapshot=current,
                limitation=LIMITATION)


def record_review(data, root, key, reviewer, decision, comment):
    validate(data)
    if key not in DELIVERABLES or decision not in ("accepted", "rejected"):
        raise ValueError("覆核項目或決定無效")
    reviewer = _text(reviewer, "覆核者")
    comment = _text(comment, "覆核意見／依據")
    if reviewer == data["basis"]["preparer"].strip():
        raise ValueError("覆核者不可與編製者相同")
    state = evaluate(data, root)
    doc = data["documents"][key]
    integrity = [s for s in next(r for r in state["rows"] if r["key"] == key)["issues"]
                 if s.startswith(("證據", "待附"))]
    if decision == "accepted" and (state["missing_basis"] or integrity):
        raise ValueError("設計依據／規範及此項證據須先齊備並通過完整性檢查")
    if decision == "accepted" and doc["exclusion"].strip() and len(comment) < 8:
        raise ValueError("不適用項目須填具體覆核理由（至少八字）")
    data["reviews"][key] = dict(reviewer=reviewer, decision=decision,
                                comment=comment, time=now(), snapshot=state["snapshot"])


def save_revision(data, root):
    validate(data)
    destination = Path(root) / ("設計審查_" + uuid4().hex + ".json")
    with destination.open("x", encoding="utf-8") as stream:
        json.dump(data, stream, ensure_ascii=False, indent=2, allow_nan=False)
    return destination


def load_revision(path):
    path = Path(path)
    if path.is_symlink() or path.stat().st_size > 4 * 1024 * 1024:
        raise ValueError("設計資料不得為符號連結或超過 4 MiB")
    def unique_pairs(pairs):
        result = {}
        for key, value in pairs:
            if key in result:
                raise ValueError("設計資料含重複欄位")
            result[key] = value
        return result
    return validate(json.loads(path.read_text(encoding="utf-8"), object_pairs_hook=unique_pairs))


def export_review(data, root):
    state = evaluate(data, root)
    revision = save_revision(data, root)
    lines = ["Facility Studio｜設計依據與交付審查", state["status"], LIMITATION,
             "對應設計資料：" + revision.name, ""]
    lines += [f"{label}：{data['basis'][key]}" for key, label in FIELDS.items()]
    lines += ["", "適用規範（使用者填報）："]
    for s in data["standards"]:
        lines.append("｜".join(s[k] for k in ("name", "edition", "clause", "scope", "source")))
    lines += ["", "待補設計依據：" + "、".join(state["missing_basis"])]
    for row in state["rows"]:
        key = row["key"]
        lines.append(f"\n{row['label']}：{row['status']}")
        lines += ["  " + issue for issue in row["issues"]]
        doc = data["documents"][key]
        if doc["exclusion"]:
            lines.append("  不適用理由：" + doc["exclusion"])
        for evidence in doc["evidence"]:
            lines.append(f"  證據：{evidence['name']}｜SHA256 {evidence['sha256']}")
        review = data["reviews"].get(key)
        if review:
            lines.append(f"  填報覆核者：{review['reviewer']}｜{review['time']}｜{review['comment']}")
    lines += ["", "資料快照 SHA256：" + state["snapshot"]]
    destination = Path(root) / ("交付審查報告_" + uuid4().hex + ".txt")
    with destination.open("x", encoding="utf-8") as stream:
        stream.write("\n".join(lines) + "\n")
    return destination, deepcopy(state)
