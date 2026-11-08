"""Restore the owner's exact compiled candidate. Do not execute the application."""
import hashlib
import json
from pathlib import Path
import zipfile

ROOT = Path(".delivery/facs-v22-r3")
EXPECTED_SHA256 = "26dcbac483b5c039486af1d88b750ba7dda5f11dbb9965e88fabc08d0236643a"
EXPECTED_SIZE = 78519839
PARTS = [{"index":0,"size":5242878,"git_blob_sha":"a4be8a9d171e68c5c0d1afaa3449eabb2f4fbd83","sha256":"8a6db6e0a7d00b5eaded48a893696d7af808fdc4aa84c9226982f4253cde5a2e"},{"index":1,"size":5242878,"git_blob_sha":"4c9ccd89614070a7f2fd2d239661974427f925b5","sha256":"f034f838f3273d9a624f6fb79b099b808145f63bfe9dcbe89ae1a2267d6e379b"},{"index":2,"size":5242878,"git_blob_sha":"dbb134b555a2ff603a747c78c54e1b4da0e3366a","sha256":"bcc753a9f023914036bb5183d2ef25186a53cb17d823479b233fea248268e807"},{"index":3,"size":5242878,"git_blob_sha":"2294db574b7fe5419b96b76578eb6c9fe5e122d4","sha256":"d06b3f418913d2a1f45f4b9378bed1bcb42ba3f17a7c81c7c578351bbc34af0c"},{"index":4,"size":5242878,"git_blob_sha":"1554f49f7f9ae6b30b440c78107e381e3d3b9042","sha256":"c07ada5db7fa4b8b1d0c0eedf23b83f4513777d6a572534491c0ab75c66c8777"},{"index":5,"size":5242878,"git_blob_sha":"e7e8a2f8ab5d58b269967c44d96dea2a29e6548c","sha256":"f6e437c76dfdd37c35fac3336cba317d85bcfb217ade18e8ec53e338f2408e20"},{"index":6,"size":5242878,"git_blob_sha":"f5014179d18fd9e4b712910b4823ae65b3487608","sha256":"5fb3a5e349c3a65a4580ccfb8b253922e574efab99c14a0bc044f1644dcff6b2"},{"index":7,"size":5242878,"git_blob_sha":"70e093f230735f05fba78e86bed3235e0428a473","sha256":"00a856e3b6a7c6d5038e2d75ff5d98bf6cb4fa99042cb30d179451f31e35b16f"},{"index":8,"size":5242878,"git_blob_sha":"34fddd5b64394f55683408fb1061672ee7d25ebf","sha256":"0581c2e91d55846756e5c6c4c882d4714af63242066eb217da9c83f713bd5b8e"},{"index":9,"size":5242878,"git_blob_sha":"5aa06a22bdcc7e7e460d52eb1e0997a427e37eed","sha256":"7b0b4a078c1de1be4f94d2c16608d0481a152583ca16c8f7cadcfbc4d440ef0d"},{"index":10,"size":5242878,"git_blob_sha":"3186020331990d2000de2e39e8472d86bde7488f","sha256":"3d4939901e6a8767ea4f1e5dc36dac233c6b8b2926ae85385540ed742cc2bf70"},{"index":11,"size":5242878,"git_blob_sha":"52dc5428b5bde226d8a85ea9a88ff54c86a8ddf5","sha256":"3e4f8a75be6f999b8014159f6e5375f9a164d5c188b06ba2a1b868f28e3d1d35"},{"index":12,"size":5242878,"git_blob_sha":"2616872e108d8a89c5cf5bfddd3df7c4c6eb4c53","sha256":"77da98bcb15d2798d705439e0f0ea5751bd7f4688d12ff166d64e581c65fd4f2"},{"index":13,"size":5242878,"git_blob_sha":"76335ace03d1c437bd8705da251ed19ebd920921","sha256":"3d6e10dd0dbe14492b8dcd494717c49482c5f9f833b4c8d7bbcd25dbc2b758c6"},{"index":14,"size":5119547,"git_blob_sha":"f9860546812c69f63b2f11944468db4923263def","sha256":"4acd7f4edc37cf2c51a73f14b99374eac304e96276ed84496d4151952c8a8e84"}]
output = Path("FACS-v22-r3-UNVALIDATED-COMPILE-ONLY-macOS-arm64.zip")
with output.open("xb") as target:
    for part in PARTS:
        data = (ROOT / "payload" / ("part%03d.bin" % part["index"])).read_bytes()
        if len(data) != part["size"] or hashlib.sha256(data).hexdigest() != part["sha256"]:
            raise SystemExit("Transport part did not match the original bytes")
        target.write(data)
data = output.read_bytes()
if len(data) != EXPECTED_SIZE or hashlib.sha256(data).hexdigest() != EXPECTED_SHA256:
    raise SystemExit("Complete ZIP identity mismatch; publication is forbidden")
with zipfile.ZipFile(output) as archive:
    if archive.testzip() is not None:
        raise SystemExit("ZIP integrity failure")
    identity = json.loads(archive.read("CANDIDATE_IDENTITY.json"))
    if identity["classification"] != "UNVALIDATED_PRIVATE_COMPILE_ONLY":
        raise SystemExit("Unexpected candidate classification")
    if identity["source_version"] != "v22" or identity["workflow_revision"] != "r3":
        raise SystemExit("Unexpected candidate version")
    if any(identity["acceptance"].values()) or identity["product_executed"] or identity["gui_or_frozen_run"]:
        raise SystemExit("Unexpected acceptance claims")
    if not any(name.startswith("FACS-v22-UNVALIDATED-COMPILE-ONLY.app/Contents/") for name in archive.namelist()):
        raise SystemExit("Complete macOS app is missing")
print("RESTORED_ORIGINAL_ZIP", EXPECTED_SIZE, EXPECTED_SHA256)
