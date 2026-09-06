"""Cross-language protocol round-trip tests for Python models.

Verifies that canonical JSON fixtures in packages/protocol/fixtures parse,
serialize back to byte-for-byte identical JSON, and fail loudly on unknown variants.
"""

import json
from pathlib import Path

import pytest
from pydantic import ValidationError

from protocol.models import (
    DiffContent,
    PermissionRequestParams,
    ProtocolMessage,
    SessionUpdateNotification,
)

FIXTURES_DIR = Path(__file__).resolve().parent.parent.parent / "packages" / "protocol" / "fixtures"


def test_initialize_request_roundtrip() -> None:
    path = FIXTURES_DIR / "initialize_request.json"
    raw_data = json.loads(path.read_text(encoding="utf-8"))

    msg = ProtocolMessage.model_validate(raw_data)
    serialized = msg.model_dump(by_alias=True, exclude_none=True)

    assert serialized == raw_data


def test_session_update_tool_call_roundtrip() -> None:
    path = FIXTURES_DIR / "session_update_tool_call.json"
    raw_data = json.loads(path.read_text(encoding="utf-8"))

    update = SessionUpdateNotification.model_validate(raw_data)
    serialized = update.model_dump(by_alias=True, exclude_none=True)

    assert serialized == raw_data


def test_permission_request_roundtrip() -> None:
    path = FIXTURES_DIR / "permission_request.json"
    raw_data = json.loads(path.read_text(encoding="utf-8"))

    req = PermissionRequestParams.model_validate(raw_data)
    serialized = req.model_dump(by_alias=True, exclude_none=True)

    assert serialized == raw_data


def test_diff_content_absent_optional_roundtrip() -> None:
    path = FIXTURES_DIR / "diff_content_absent_optional.json"
    raw_data = json.loads(path.read_text(encoding="utf-8"))

    diff = DiffContent.model_validate(raw_data)
    assert diff.old_text is None

    serialized = diff.model_dump(by_alias=True, exclude_none=True)
    assert "oldText" not in serialized
    assert serialized == raw_data


def test_swaraj_meta_provenance_roundtrip() -> None:
    path = FIXTURES_DIR / "swaraj_meta_provenance.json"
    raw_data = json.loads(path.read_text(encoding="utf-8"))

    notification = SessionUpdateNotification.model_validate(raw_data)
    serialized = notification.model_dump(by_alias=True, exclude_none=True)

    assert serialized == raw_data
    assert notification.meta is not None
    assert notification.meta.provenance is not None
    assert notification.meta.provenance.confidence == 0.98


def test_unknown_variant_fails_loudly() -> None:
    invalid_data = {
        "sessionId": "sess-unknown",
        "update": {
            "type": "non_existent_update_variant",
            "foo": "bar",
        },
    }

    with pytest.raises(ValidationError) as exc_info:
        SessionUpdateNotification.model_validate(invalid_data)

    assert "discriminator" in str(exc_info.value).lower() or "type" in str(exc_info.value).lower()
