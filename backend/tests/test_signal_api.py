from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

from fastapi.testclient import TestClient


BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from app.api.dependencies import container as current_container, set_container
from app.api.dependencies.container import AppContainer
from app.main import app


def test_signal_manual_create_and_status_update(tmp_path):
    test_container = AppContainer(tmp_path)
    original_container = current_container
    set_container(test_container)
    try:
        client = TestClient(app)
        dataset_response = client.post(
            "/api/datasets",
            json={
                "dataset_name": "Manual Signal Dataset",
                "dataset_type": "raw",
                "source_platform": "xhs",
                "scenario_type": "lead_diversion",
            },
        )
        dataset_id = dataset_response.json()["dataset"]["id"]

        create_response = client.post(
            "/api/signals",
            json={
                "dataset_id": dataset_id,
                "signal_type": "manual",
                "signal_source": "manual",
                "risk_level": "medium",
                "risk_score": 60,
                "summary": "人工标记的导流线索",
                "payload_json": {"source_ref": {"dataset_id": dataset_id, "row_index": 0}},
            },
        )
        assert create_response.status_code == 200
        signal = create_response.json()["signal"]
        assert signal["dataset_id"] == dataset_id
        assert signal["status"] == "new"

        update_response = client.patch(
            f"/api/signals/{signal['id']}/status",
            json={"status": "confirmed"},
        )
        assert update_response.status_code == 200
        assert update_response.json()["signal"]["status"] == "confirmed"
    finally:
        set_container(original_container)


def test_signal_detail_returns_trace_preview_and_linked_cases(tmp_path):
    test_container = AppContainer(tmp_path)
    original_container = current_container
    set_container(test_container)
    try:
        dataset_file_dir = tmp_path / "storage" / "dataset_files"
        dataset_file_dir.mkdir(parents=True, exist_ok=True)
        sample_path = dataset_file_dir / "signal_detail.jsonl"
        sample_path.write_text(
            json.dumps(
                {
                    "content_id": "note_detail_001",
                    "title": "导流样本",
                    "body": "微信 abc12345 领取资料",
                },
                ensure_ascii=False,
            ),
            encoding="utf-8",
        )

        client = TestClient(app)
        dataset_response = client.post(
            "/api/datasets",
            json={
                "dataset_name": "Signal Detail Dataset",
                "dataset_type": "raw",
                "source_platform": "xhs",
                "scenario_type": "lead_diversion",
                "storage_uri": "signal_detail.jsonl",
            },
        )
        dataset_id = dataset_response.json()["dataset"]["id"]

        signal_response = client.post(
            "/api/signals",
            json={
                "dataset_id": dataset_id,
                "signal_type": "contact_point_hit",
                "signal_source": "manual",
                "risk_level": "high",
                "risk_score": 88,
                "summary": "疑似联系方式或导流点：abc12345",
                "payload_json": {
                    "contact_point": "abc12345",
                    "source_ref": {
                        "dataset_id": dataset_id,
                        "row_index": 0,
                        "source_entity_id": "note_detail_001",
                    },
                },
            },
        )
        signal_id = signal_response.json()["signal"]["id"]

        case_response = client.post(
            "/api/cases",
            json={
                "case_name": "Signal Detail Case",
                "case_type": "lead_diversion",
                "priority": "high",
                "summary": "围绕 abc12345 的详情页关联案件",
            },
        )
        case_id = case_response.json()["case"]["id"]
        link_response = client.post(
            f"/api/cases/{case_id}/links",
            json={"link_type": "signal", "target_id": signal_id, "label": "详情页信号"},
        )
        assert link_response.status_code == 200

        detail_response = client.get(f"/api/signals/{signal_id}/detail")
        assert detail_response.status_code == 200
        detail = detail_response.json()
        assert detail["signal"]["id"] == signal_id
        assert detail["dataset"]["id"] == dataset_id
        assert detail["preview"]["columns"] == ["content_id", "title", "body"]
        assert detail["preview"]["rows"][0][0] == "note_detail_001"
        assert detail["linked_cases"][0]["id"] == case_id
        assert detail["linked_case_details"][0]["links"][0]["target_id"] == signal_id
    finally:
        set_container(original_container)


def test_signal_extraction_preserves_source_traceability(tmp_path):
    test_container = AppContainer(tmp_path)
    original_container = current_container
    set_container(test_container)
    try:
        dataset_file_dir = tmp_path / "storage" / "dataset_files"
        dataset_file_dir.mkdir(parents=True, exist_ok=True)
        sample_path = dataset_file_dir / "xhs_risk_notes.jsonl"
        sample_path.write_text(
            "\n".join(
                [
                    json.dumps(
                        {
                            "content_id": "note_001",
                            "title": "兼职招募",
                            "body": "高佣兼职，微信 abc12345 详聊",
                            "source_url": "https://example.test/note_001",
                        },
                        ensure_ascii=False,
                    ),
                    json.dumps(
                        {
                            "content_id": "note_002",
                            "title": "普通分享",
                            "body": "今天的读书笔记",
                        },
                        ensure_ascii=False,
                    ),
                ]
            ),
            encoding="utf-8",
        )

        client = TestClient(app)
        dataset_response = client.post(
            "/api/datasets",
            json={
                "dataset_name": "XHS Risk Notes",
                "dataset_type": "raw",
                "source_platform": "xhs",
                "scenario_type": "gray_recruitment",
                "storage_uri": "xhs_risk_notes.jsonl",
            },
        )
        dataset_id = dataset_response.json()["dataset"]["id"]

        extract_response = client.post(
            "/api/signals/extract",
            json={
                "dataset_id": dataset_id,
                "extractors": ["risk_terms", "contact_points"],
                "limit": 20,
            },
        )
        assert extract_response.status_code == 200
        signals = extract_response.json()["signals"]
        assert len(signals) >= 2
        assert {item["signal_type"] for item in signals} >= {"risk_term_hit", "contact_point_hit"}

        contact_signal = next(item for item in signals if item["signal_type"] == "contact_point_hit")
        source_ref = contact_signal["payload_json"]["source_ref"]
        assert source_ref["dataset_id"] == dataset_id
        assert source_ref["row_index"] == 0
        assert source_ref["source_entity_id"] == "note_001"
        assert source_ref["raw_ref"] == "https://example.test/note_001"
    finally:
        set_container(original_container)


def test_recruit_pattern_extractor_requires_intent_and_incentive(tmp_path):
    test_container = AppContainer(tmp_path)
    original_container = current_container
    set_container(test_container)
    try:
        dataset_file_dir = tmp_path / "storage" / "dataset_files"
        dataset_file_dir.mkdir(parents=True, exist_ok=True)
        sample_path = dataset_file_dir / "recruit_notes.jsonl"
        sample_path.write_text(
            "\n".join(
                [
                    json.dumps(
                        {"content_id": "r1", "title": "诚招代理", "body": "日结佣金，上不封顶，带做"},
                        ensure_ascii=False,
                    ),
                    json.dumps(
                        {"content_id": "r2", "title": "招募", "body": "招募志愿者参加公益活动"},
                        ensure_ascii=False,
                    ),
                ]
            ),
            encoding="utf-8",
        )

        client = TestClient(app)
        dataset_id = client.post(
            "/api/datasets",
            json={
                "dataset_name": "Recruit Notes",
                "dataset_type": "raw",
                "source_platform": "xhs",
                "scenario_type": "gray_recruitment",
                "storage_uri": "recruit_notes.jsonl",
            },
        ).json()["dataset"]["id"]

        extract_response = client.post(
            "/api/signals/extract",
            json={
                "dataset_id": dataset_id,
                "extractors": ["recruit_pattern"],
                "limit": 20,
            },
        )
        assert extract_response.status_code == 200
        signals = extract_response.json()["signals"]
        recruit_signals = [s for s in signals if s["signal_type"] == "recruit_pattern_hit"]
        # Only the row with both an intent term and an incentive cue should hit.
        assert len(recruit_signals) == 1
        hit = recruit_signals[0]
        assert hit["payload_json"]["source_ref"]["row_index"] == 0
        assert hit["payload_json"]["recruit_intent_terms"]
        assert hit["payload_json"]["recruit_incentive_terms"]
    finally:
        set_container(original_container)


def test_service_offer_extractor_requires_offer_and_trade(tmp_path):
    test_container = AppContainer(tmp_path)
    original_container = current_container
    set_container(test_container)
    try:
        dataset_file_dir = tmp_path / "storage" / "dataset_files"
        dataset_file_dir.mkdir(parents=True, exist_ok=True)
        sample_path = dataset_file_dir / "service_notes.jsonl"
        sample_path.write_text(
            "\n".join(
                [
                    json.dumps(
                        {"content_id": "s1", "title": "协议号出售", "body": "号商一手货源，秒发质保"},
                        ensure_ascii=False,
                    ),
                    json.dumps(
                        {"content_id": "s2", "title": "脚本", "body": "分享一个学习脚本的教程"},
                        ensure_ascii=False,
                    ),
                ]
            ),
            encoding="utf-8",
        )

        client = TestClient(app)
        dataset_id = client.post(
            "/api/datasets",
            json={
                "dataset_name": "Service Notes",
                "dataset_type": "raw",
                "source_platform": "xhs",
                "scenario_type": "gray_recruitment",
                "storage_uri": "service_notes.jsonl",
            },
        ).json()["dataset"]["id"]

        extract_response = client.post(
            "/api/signals/extract",
            json={
                "dataset_id": dataset_id,
                "extractors": ["service_offer"],
                "limit": 20,
            },
        )
        assert extract_response.status_code == 200
        signals = extract_response.json()["signals"]
        offer_signals = [s for s in signals if s["signal_type"] == "service_offer_hit"]
        # Only the row with both an offer noun and a trade cue should hit.
        assert len(offer_signals) == 1
        hit = offer_signals[0]
        assert hit["payload_json"]["source_ref"]["row_index"] == 0
        assert hit["payload_json"]["service_offer_terms"]
        assert hit["payload_json"]["service_trade_terms"]
    finally:
        set_container(original_container)


def test_traffic_route_extractor_requires_action_and_landing(tmp_path):
    test_container = AppContainer(tmp_path)
    original_container = current_container
    set_container(test_container)
    try:
        dataset_file_dir = tmp_path / "storage" / "dataset_files"
        dataset_file_dir.mkdir(parents=True, exist_ok=True)
        sample_path = dataset_file_dir / "traffic_notes.jsonl"
        sample_path.write_text(
            "\n".join(
                [
                    json.dumps(
                        {"content_id": "t1", "title": "扫码进群", "body": "加我微信领福利"},
                        ensure_ascii=False,
                    ),
                    json.dumps(
                        {"content_id": "t2", "title": "日常分享", "body": "今天天气不错"},
                        ensure_ascii=False,
                    ),
                ]
            ),
            encoding="utf-8",
        )

        client = TestClient(app)
        dataset_id = client.post(
            "/api/datasets",
            json={
                "dataset_name": "Traffic Notes",
                "dataset_type": "raw",
                "source_platform": "xhs",
                "scenario_type": "lead_diversion",
                "storage_uri": "traffic_notes.jsonl",
            },
        ).json()["dataset"]["id"]

        extract_response = client.post(
            "/api/signals/extract",
            json={
                "dataset_id": dataset_id,
                "extractors": ["traffic_route"],
                "limit": 20,
            },
        )
        assert extract_response.status_code == 200
        signals = extract_response.json()["signals"]
        route_signals = [s for s in signals if s["signal_type"] == "traffic_route_hit"]
        # Only the row with both a guiding action and an off-platform landing should hit.
        assert len(route_signals) == 1
        hit = route_signals[0]
        assert hit["payload_json"]["source_ref"]["row_index"] == 0
        assert hit["payload_json"]["traffic_action_terms"]
        assert hit["payload_json"]["traffic_landing_terms"]
    finally:
        set_container(original_container)


def test_extractors_defeat_obfuscated_black_grey_content(tmp_path):
    """Full-width, spacing, zero-width and emoji insertion must not evade rules."""
    test_container = AppContainer(tmp_path)
    original_container = current_container
    set_container(test_container)
    try:
        dataset_file_dir = tmp_path / "storage" / "dataset_files"
        dataset_file_dir.mkdir(parents=True, exist_ok=True)
        sample_path = dataset_file_dir / "obfuscated_notes.jsonl"
        sample_path.write_text(
            "\n".join(
                [
                    # 诚 招 (spaced), 日❤结 (emoji), 引​流 (zero-width),
                    # 加ＶＸ (full-width) — every term is broken up on purpose.
                    json.dumps(
                        {
                            "content_id": "o1",
                            "title": "诚 招 代 理",
                            "body": "日❤结佣金，引​流稳定，加ＶＸ：daili_8888",
                        },
                        ensure_ascii=False,
                    ),
                    json.dumps(
                        {"content_id": "o2", "title": "今天天气", "body": "分享生活日常"},
                        ensure_ascii=False,
                    ),
                ]
            ),
            encoding="utf-8",
        )

        client = TestClient(app)
        dataset_id = client.post(
            "/api/datasets",
            json={
                "dataset_name": "Obfuscated Notes",
                "dataset_type": "raw",
                "source_platform": "xhs",
                "scenario_type": "gray_recruitment",
                "storage_uri": "obfuscated_notes.jsonl",
            },
        ).json()["dataset"]["id"]

        extract_response = client.post(
            "/api/signals/extract",
            json={
                "dataset_id": dataset_id,
                "extractors": ["risk_terms", "recruit_pattern", "contact_points"],
                "limit": 20,
            },
        )
        assert extract_response.status_code == 200
        signals = extract_response.json()["signals"]
        by_type = {s["signal_type"]: s for s in signals}

        # Zero-width-split 引流 is still caught and flagged as evasive.
        assert "risk_term_hit" in by_type
        risk_hit = by_type["risk_term_hit"]
        assert risk_hit["payload_json"]["term"] == "引流"
        assert risk_hit["payload_json"]["deobfuscated"] is True

        # Spaced 诚招 + emoji-split 日结 co-occurrence survives collapsing.
        assert "recruit_pattern_hit" in by_type
        assert by_type["recruit_pattern_hit"]["payload_json"]["deobfuscated"] is True

        # Full-width ＶＸ folds to vx and the id keeps its underscore.
        assert "contact_point_hit" in by_type
        assert by_type["contact_point_hit"]["payload_json"]["contact_point"] == "daili_8888"

        # The innocent row must not produce any signal.
        row_indexes = {s["payload_json"]["source_ref"]["row_index"] for s in signals}
        assert row_indexes == {0}
    finally:
        set_container(original_container)


def test_extractors_resolve_homophone_variants(tmp_path):
    """Look-alike spellings (薇信/扣扣/引留) must resolve to their canonical rule."""
    test_container = AppContainer(tmp_path)
    original_container = current_container
    set_container(test_container)
    try:
        dataset_file_dir = tmp_path / "storage" / "dataset_files"
        dataset_file_dir.mkdir(parents=True, exist_ok=True)
        sample_path = dataset_file_dir / "variant_notes.jsonl"
        sample_path.write_text(
            "\n".join(
                [
                    # 薇信 -> 微信 (contact trigger), 引留 -> 引流 (risk term)
                    json.dumps(
                        {"content_id": "v1", "title": "引留推广", "body": "加薇信：daili_8888"},
                        ensure_ascii=False,
                    ),
                    # 扣扣 -> qq (contact trigger)
                    json.dumps(
                        {"content_id": "v2", "title": "低价", "body": "扣扣 998877665"},
                        ensure_ascii=False,
                    ),
                ]
            ),
            encoding="utf-8",
        )

        client = TestClient(app)
        dataset_id = client.post(
            "/api/datasets",
            json={
                "dataset_name": "Variant Notes",
                "dataset_type": "raw",
                "source_platform": "xhs",
                "scenario_type": "lead_diversion",
                "storage_uri": "variant_notes.jsonl",
            },
        ).json()["dataset"]["id"]

        extract_response = client.post(
            "/api/signals/extract",
            json={
                "dataset_id": dataset_id,
                "extractors": ["risk_terms", "contact_points"],
                "limit": 20,
            },
        )
        assert extract_response.status_code == 200
        signals = extract_response.json()["signals"]

        # 引留 resolves to the 引流 risk term.
        risk = [s for s in signals if s["signal_type"] == "risk_term_hit"]
        assert any(s["payload_json"]["term"] == "引流" for s in risk)

        # 薇信 and 扣扣 both resolve to contact triggers and capture the id.
        contacts = {
            s["payload_json"]["contact_point"]
            for s in signals
            if s["signal_type"] == "contact_point_hit"
        }
        assert "daili_8888" in contacts
        assert "998877665" in contacts
    finally:
        set_container(original_container)


def test_cluster_by_contact_groups_signals_sharing_contact_point(tmp_path):
    test_container = AppContainer(tmp_path)
    original_container = current_container
    set_container(test_container)
    try:
        dataset_file_dir = tmp_path / "storage" / "dataset_files"
        dataset_file_dir.mkdir(parents=True, exist_ok=True)
        (dataset_file_dir / "cluster_source.jsonl").write_text(
            json.dumps({"content_id": "c1", "body": "seed"}, ensure_ascii=False),
            encoding="utf-8",
        )

        client = TestClient(app)
        dataset_id = client.post(
            "/api/datasets",
            json={
                "dataset_name": "Cluster Dataset",
                "dataset_type": "raw",
                "source_platform": "xhs",
                "scenario_type": "gray_recruitment",
                "storage_uri": "cluster_source.jsonl",
            },
        ).json()["dataset"]["id"]

        def make_signal(contact, risk_level, risk_score):
            return client.post(
                "/api/signals",
                json={
                    "dataset_id": dataset_id,
                    "signal_type": "contact_point_hit" if contact else "risk_term_hit",
                    "signal_source": "rule:test",
                    "risk_level": risk_level,
                    "risk_score": risk_score,
                    "summary": f"test {contact or 'none'}",
                    "status": "new",
                    "payload_json": {"contact_point": contact} if contact else {},
                },
            )

        make_signal("wxid_gang01", "high", 85)
        make_signal("wxid_gang01", "critical", 95)
        make_signal("qq_88888", "medium", 60)
        make_signal(None, "low", 20)  # no contact point -> excluded from clusters

        clusters = test_container.signal_service.cluster_by_contact(dataset_id)
        assert len(clusters) == 2
        # Largest cluster (shared contact) surfaces first.
        assert clusters[0]["contact_point"] == "wxid_gang01"
        assert clusters[0]["signal_count"] == 2
        assert clusters[0]["risk_levels"] == {"high": 1, "critical": 1}
        assert clusters[0]["max_risk_score"] == 95
        assert clusters[1]["contact_point"] == "qq_88888"
        assert clusters[1]["signal_count"] == 1
    finally:
        set_container(original_container)


def test_pii_masking_masks_contacts_when_enabled(tmp_path, monkeypatch):
    monkeypatch.setenv("MEDIASPIDER_PII_MASKING", "true")
    test_container = AppContainer(tmp_path)
    original_container = current_container
    set_container(test_container)
    try:
        dataset_file_dir = tmp_path / "storage" / "dataset_files"
        dataset_file_dir.mkdir(parents=True, exist_ok=True)
        (dataset_file_dir / "pii_source.jsonl").write_text(
            json.dumps({"content_id": "p1", "body": "seed"}, ensure_ascii=False),
            encoding="utf-8",
        )

        client = TestClient(app)
        dataset_id = client.post(
            "/api/datasets",
            json={
                "dataset_name": "PII Dataset",
                "dataset_type": "raw",
                "source_platform": "xhs",
                "scenario_type": "lead_diversion",
                "storage_uri": "pii_source.jsonl",
            },
        ).json()["dataset"]["id"]

        client.post(
            "/api/signals",
            json={
                "dataset_id": dataset_id,
                "signal_type": "contact_point_hit",
                "signal_source": "rule:test",
                "risk_level": "high",
                "risk_score": 85,
                "summary": "疑似联系方式：daili_8888",
                "status": "new",
                "payload_json": {
                    "contact_point": "daili_8888",
                    "record_excerpt": "加微信 daili_8888 或电话 13812345678",
                },
            },
        )

        listed = client.get(f"/api/signals?dataset_id={dataset_id}").json()["signals"]
        assert len(listed) == 1
        masked = listed[0]
        # Structured contact and free-text occurrences are masked; raw is gone.
        assert masked["payload_json"]["contact_point"] == "da******88"
        assert "daili_8888" not in json.dumps(masked, ensure_ascii=False)
        # Phone number keeps prefix + last four only.
        assert "138****5678" in masked["payload_json"]["record_excerpt"]
        assert "13812345678" not in masked["payload_json"]["record_excerpt"]
    finally:
        set_container(original_container)


def test_pii_masking_masks_dataset_preview_and_gangs(tmp_path, monkeypatch):
    monkeypatch.setenv("MEDIASPIDER_PII_MASKING", "true")
    test_container = AppContainer(tmp_path)
    original_container = current_container
    set_container(test_container)
    try:
        dataset_file_dir = tmp_path / "storage" / "dataset_files"
        dataset_file_dir.mkdir(parents=True, exist_ok=True)
        (dataset_file_dir / "pii_preview.jsonl").write_text(
            "\n".join(
                [
                    json.dumps(
                        {"content_id": "p1", "wechat": "daili_8888", "body": "电话 13812345678"},
                        ensure_ascii=False,
                    ),
                ]
            ),
            encoding="utf-8",
        )

        client = TestClient(app)
        dataset_id = client.post(
            "/api/datasets",
            json={
                "dataset_name": "PII Preview Dataset",
                "dataset_type": "raw",
                "source_platform": "xhs",
                "scenario_type": "lead_diversion",
                "storage_uri": "pii_preview.jsonl",
            },
        ).json()["dataset"]["id"]

        # Dataset preview: contact column masked, phone masked in free text.
        preview = client.get(f"/api/datasets/{dataset_id}/preview").json()
        flat = json.dumps(preview, ensure_ascii=False)
        assert "daili_8888" not in flat
        assert "da******88" in flat
        assert "13812345678" not in flat
        assert "138****5678" in flat

        # Gang clusters: shared-contact label and contact_point masked.
        client.post(
            "/api/signals",
            json={
                "dataset_id": dataset_id,
                "signal_type": "contact_point_hit",
                "signal_source": "rule:test",
                "risk_level": "high",
                "risk_score": 85,
                "summary": "test",
                "status": "new",
                "payload_json": {"contact_point": "daili_8888"},
            },
        )
        client.post(
            "/api/signals",
            json={
                "dataset_id": dataset_id,
                "signal_type": "contact_point_hit",
                "signal_source": "rule:test",
                "risk_level": "critical",
                "risk_score": 95,
                "summary": "test",
                "status": "new",
                "payload_json": {"contact_point": "daili_8888"},
            },
        )
        gangs = client.get(f"/api/signals/gangs?dataset_id={dataset_id}").json()["clusters"]
        assert len(gangs) == 1
        assert gangs[0]["contact_point"] == "da******88"
        assert "daili_8888" not in json.dumps(gangs, ensure_ascii=False)
    finally:
        set_container(original_container)


def test_pii_masking_off_by_default_keeps_raw_contact(tmp_path):
    test_container = AppContainer(tmp_path)
    original_container = current_container
    set_container(test_container)
    try:
        dataset_file_dir = tmp_path / "storage" / "dataset_files"
        dataset_file_dir.mkdir(parents=True, exist_ok=True)
        (dataset_file_dir / "pii_raw.jsonl").write_text(
            json.dumps({"content_id": "p1", "body": "seed"}, ensure_ascii=False),
            encoding="utf-8",
        )

        client = TestClient(app)
        dataset_id = client.post(
            "/api/datasets",
            json={
                "dataset_name": "PII Raw Dataset",
                "dataset_type": "raw",
                "source_platform": "xhs",
                "scenario_type": "lead_diversion",
                "storage_uri": "pii_raw.jsonl",
            },
        ).json()["dataset"]["id"]

        client.post(
            "/api/signals",
            json={
                "dataset_id": dataset_id,
                "signal_type": "contact_point_hit",
                "signal_source": "rule:test",
                "risk_level": "high",
                "risk_score": 85,
                "summary": "test",
                "status": "new",
                "payload_json": {"contact_point": "daili_8888"},
            },
        )

        listed = client.get(f"/api/signals?dataset_id={dataset_id}").json()["signals"]
        assert listed[0]["payload_json"]["contact_point"] == "daili_8888"
    finally:
        set_container(original_container)


def test_detect_activity_bursts_flags_spike_day(tmp_path):
    """A quiet baseline with one heavy day must flag that day as a burst."""
    test_container = AppContainer(tmp_path)
    original_container = current_container
    set_container(test_container)
    try:
        dataset_file_dir = tmp_path / "storage" / "dataset_files"
        dataset_file_dir.mkdir(parents=True, exist_ok=True)

        rows = []
        # Baseline: one post per day for six days (ISO strings).
        for day in range(1, 7):
            rows.append({"content_id": f"b{day}", "publish_time": f"2026-03-0{day} 09:00:00"})
        # Burst: eight posts on a single later day (epoch milliseconds).
        burst_ms = int(datetime(2026, 3, 10, 12, 0, tzinfo=timezone.utc).timestamp() * 1000)
        for i in range(8):
            rows.append({"content_id": f"s{i}", "publish_time": burst_ms + i * 1000})

        (dataset_file_dir / "burst_source.jsonl").write_text(
            "\n".join(json.dumps(row, ensure_ascii=False) for row in rows),
            encoding="utf-8",
        )

        client = TestClient(app)
        dataset_id = client.post(
            "/api/datasets",
            json={
                "dataset_name": "Burst Dataset",
                "dataset_type": "raw",
                "source_platform": "xhs",
                "scenario_type": "topic_watch",
                "storage_uri": "burst_source.jsonl",
            },
        ).json()["dataset"]["id"]

        response = client.get(f"/api/signals/activity?dataset_id={dataset_id}")
        assert response.status_code == 200
        result = response.json()

        assert result["total_records"] == 14
        assert result["day_count"] == 7
        bursts = result["bursts"]
        assert len(bursts) == 1
        assert bursts[0]["date"] == "2026-03-10"
        assert bursts[0]["count"] == 8
        # The quiet days must not be flagged.
        flagged = {b["date"] for b in result["buckets"] if b["is_burst"]}
        assert flagged == {"2026-03-10"}
    finally:
        set_container(original_container)


def test_cluster_gangs_links_signals_transitively_across_attributes(tmp_path):
    """A—contact—B and B—template—C must collapse into one gang."""
    test_container = AppContainer(tmp_path)
    original_container = current_container
    set_container(test_container)
    try:
        dataset_file_dir = tmp_path / "storage" / "dataset_files"
        dataset_file_dir.mkdir(parents=True, exist_ok=True)
        (dataset_file_dir / "gang_source.jsonl").write_text(
            json.dumps({"content_id": "g1", "body": "seed"}, ensure_ascii=False),
            encoding="utf-8",
        )

        client = TestClient(app)
        dataset_id = client.post(
            "/api/datasets",
            json={
                "dataset_name": "Gang Dataset",
                "dataset_type": "raw",
                "source_platform": "xhs",
                "scenario_type": "gray_recruitment",
                "storage_uri": "gang_source.jsonl",
            },
        ).json()["dataset"]["id"]

        def make_signal(payload, risk_level="high", risk_score=85):
            client.post(
                "/api/signals",
                json={
                    "dataset_id": dataset_id,
                    "signal_type": "contact_point_hit",
                    "signal_source": "rule:test",
                    "risk_level": risk_level,
                    "risk_score": risk_score,
                    "summary": "test",
                    "status": "new",
                    "payload_json": payload,
                },
            )

        # A shares a contact with B; B shares a template with C; A and C share
        # nothing directly, yet all three are one gang.
        make_signal({"contact_point": "wx_a", "source_ref": {"source_platform": "xhs"}})
        make_signal({"contact_point": "wx_a", "template_key": "tpl-1"}, "critical", 96)
        make_signal({"template_key": "tpl-1", "source_ref": {"source_platform": "dy"}})
        # An unrelated signal stays out of the gang.
        make_signal({"contact_point": "lonely_1"})

        gangs = test_container.signal_service.cluster_gangs(dataset_id)
        assert len(gangs) == 1
        gang = gangs[0]
        assert gang["signal_count"] == 3
        assert set(gang["link_types"]) == {"contact", "template"}
        assert gang["contact_points"] == ["wx_a"]
        assert set(gang["platforms"]) == {"xhs", "dy"}
        assert gang["max_risk_score"] == 96

        response = client.get(f"/api/signals/gangs?dataset_id={dataset_id}")
        assert response.status_code == 200
        assert response.json()["total"] == 1
    finally:
        set_container(original_container)


def test_signal_clusters_endpoint_returns_grouped_contacts(tmp_path):
    test_container = AppContainer(tmp_path)
    original_container = current_container
    set_container(test_container)
    try:
        dataset_file_dir = tmp_path / "storage" / "dataset_files"
        dataset_file_dir.mkdir(parents=True, exist_ok=True)
        (dataset_file_dir / "cluster_api.jsonl").write_text(
            json.dumps({"content_id": "c1", "body": "seed"}, ensure_ascii=False),
            encoding="utf-8",
        )

        client = TestClient(app)
        dataset_id = client.post(
            "/api/datasets",
            json={
                "dataset_name": "Cluster API Dataset",
                "dataset_type": "raw",
                "source_platform": "xhs",
                "scenario_type": "gray_recruitment",
                "storage_uri": "cluster_api.jsonl",
            },
        ).json()["dataset"]["id"]

        for contact, risk in [("wxid_gang01", "high"), ("wxid_gang01", "critical"), ("qq_88888", "medium")]:
            client.post(
                "/api/signals",
                json={
                    "dataset_id": dataset_id,
                    "signal_type": "contact_point_hit",
                    "signal_source": "rule:test",
                    "risk_level": risk,
                    "risk_score": 80,
                    "summary": f"test {contact}",
                    "status": "new",
                    "payload_json": {"contact_point": contact},
                },
            )

        response = client.get("/api/signals/clusters", params={"dataset_id": dataset_id})
        assert response.status_code == 200
        data = response.json()
        assert data["total"] == 2
        assert data["clusters"][0]["contact_point"] == "wxid_gang01"
        assert data["clusters"][0]["signal_count"] == 2
    finally:
        set_container(original_container)


def test_signal_clusters_endpoint_edge_cases(tmp_path):
    test_container = AppContainer(tmp_path)
    original_container = current_container
    set_container(test_container)
    try:
        client = TestClient(app)

        # Unknown dataset -> valid empty result, not an error.
        response = client.get("/api/signals/clusters", params={"dataset_id": "ds_missing"})
        assert response.status_code == 200
        assert response.json() == {"clusters": [], "total": 0}

        # Missing dataset_id -> validation error (query param is required).
        assert client.get("/api/signals/clusters").status_code == 422

        # Blank dataset_id -> validation error (min_length=1).
        assert client.get("/api/signals/clusters", params={"dataset_id": ""}).status_code == 422
    finally:
        set_container(original_container)


def test_signal_extraction_is_idempotent_for_same_dataset(tmp_path):
    test_container = AppContainer(tmp_path)
    original_container = current_container
    set_container(test_container)
    try:
        dataset_file_dir = tmp_path / "storage" / "dataset_files"
        dataset_file_dir.mkdir(parents=True, exist_ok=True)
        sample_path = dataset_file_dir / "repeat_extract.jsonl"
        sample_path.write_text(
            json.dumps(
                {
                    "content_id": "note_repeat_001",
                    "title": "兼职招募",
                    "body": "微信 abc12345 领取资料",
                    "source_url": "https://example.test/note_repeat_001",
                },
                ensure_ascii=False,
            ),
            encoding="utf-8",
        )

        client = TestClient(app)
        dataset_response = client.post(
            "/api/datasets",
            json={
                "dataset_name": "Repeat Extract Dataset",
                "dataset_type": "raw",
                "source_platform": "xhs",
                "scenario_type": "lead_diversion",
                "storage_uri": "repeat_extract.jsonl",
            },
        )
        dataset_id = dataset_response.json()["dataset"]["id"]
        payload = {
            "dataset_id": dataset_id,
            "extractors": ["risk_terms", "contact_points"],
            "limit": 20,
        }

        first_response = client.post("/api/signals/extract", json=payload)
        assert first_response.status_code == 200
        first_signals = first_response.json()["signals"]
        assert len(first_signals) >= 2
        assert all(item["payload_json"].get("dedupe_key") for item in first_signals)

        second_response = client.post("/api/signals/extract", json=payload)
        assert second_response.status_code == 200
        assert second_response.json()["signals"] == []

        list_response = client.get("/api/signals", params={"dataset_id": dataset_id})
        assert list_response.status_code == 200
        assert list_response.json()["total"] == len(first_signals)
    finally:
        set_container(original_container)


def test_signal_list_supports_filters_search_and_pagination(tmp_path):
    test_container = AppContainer(tmp_path)
    original_container = current_container
    set_container(test_container)
    try:
        client = TestClient(app)
        dataset_response = client.post(
            "/api/datasets",
            json={
                "dataset_name": "Signal Filter Dataset",
                "dataset_type": "raw",
                "source_platform": "xhs",
                "scenario_type": "lead_diversion",
            },
        )
        dataset_id = dataset_response.json()["dataset"]["id"]
        samples = [
            {
                "summary": "疑似联系方式或导流点：abc12345",
                "signal_type": "contact_point_hit",
                "risk_level": "high",
                "status": "confirmed",
                "payload_json": {
                    "source_ref": {
                        "dataset_id": dataset_id,
                        "row_index": 0,
                        "source_entity_id": "note_contact",
                    }
                },
            },
            {
                "summary": "命中风险词：兼职",
                "signal_type": "risk_term_hit",
                "risk_level": "medium",
                "status": "new",
                "payload_json": {"source_ref": {"dataset_id": dataset_id, "row_index": 1}},
            },
            {
                "summary": "疑似模板复用：2 条内容高度相似",
                "signal_type": "template_similarity_hit",
                "risk_level": "high",
                "status": "reviewing",
                "payload_json": {"source_ref": {"dataset_id": dataset_id, "row_index": 2}},
            },
        ]
        for item in samples:
            response = client.post(
                "/api/signals",
                json={
                    "dataset_id": dataset_id,
                    "signal_source": "test",
                    "risk_score": 80,
                    **item,
                },
            )
            assert response.status_code == 200

        high_response = client.get("/api/signals", params={"risk_level": "high"})
        assert high_response.status_code == 200
        assert len(high_response.json()["signals"]) == 2

        confirmed_response = client.get("/api/signals", params={"status": "confirmed"})
        assert confirmed_response.status_code == 200
        assert [item["summary"] for item in confirmed_response.json()["signals"]] == [
            "疑似联系方式或导流点：abc12345"
        ]

        query_response = client.get("/api/signals", params={"q": "note_contact"})
        assert query_response.status_code == 200
        assert query_response.json()["signals"][0]["signal_type"] == "contact_point_hit"

        page_response = client.get("/api/signals", params={"limit": 1, "offset": 1})
        assert page_response.status_code == 200
        assert len(page_response.json()["signals"]) == 1
        assert page_response.json()["total"] == 3
    finally:
        set_container(original_container)


def test_signal_list_contract_is_preserved_in_sqlite_mode(tmp_path, monkeypatch):
    sqlite_path = tmp_path / "storage" / "platform.sqlite3"
    monkeypatch.setenv("MEDIASPIDER_REPOSITORY_MODE", "sqlite")
    monkeypatch.setenv("MEDIASPIDER_SQLITE_PATH", str(sqlite_path))
    test_container = AppContainer(tmp_path)
    original_container = current_container
    set_container(test_container)
    try:
        client = TestClient(app)
        dataset = client.post(
            "/api/datasets",
            json={
                "dataset_name": "SQLite Signal Dataset",
                "dataset_type": "raw",
                "source_platform": "xhs",
                "scenario_type": "lead_diversion",
            },
        ).json()["dataset"]
        for index in range(3):
            response = client.post(
                "/api/signals",
                json={
                    "dataset_id": dataset["id"],
                    "signal_type": "contact_point_hit",
                    "signal_source": "sqlite-test",
                    "risk_level": "high",
                    "risk_score": 85,
                    "summary": f"SQLite contact signal {index}",
                    "status": "confirmed",
                    "payload_json": {
                        "source_ref": {
                            "dataset_id": dataset["id"],
                            "source_entity_id": f"sqlite_note_{index}",
                        }
                    },
                },
            )
            assert response.status_code == 200

        response = client.get(
            "/api/signals",
            params={
                "dataset_id": dataset["id"],
                "status": "confirmed",
                "risk_level": "high",
                "q": "sqlite_note",
                "limit": 1,
                "offset": 1,
            },
        )

        assert response.status_code == 200
        assert set(response.json()) == {"signals", "total"}
        assert len(response.json()["signals"]) == 1
        assert response.json()["total"] == 3
    finally:
        set_container(original_container)


def test_signal_extraction_missing_dataset_returns_404(tmp_path):
    test_container = AppContainer(tmp_path)
    original_container = current_container
    set_container(test_container)
    try:
        client = TestClient(app)
        response = client.post(
            "/api/signals/extract",
            json={"dataset_id": "ds_missing", "extractors": ["risk_terms"]},
        )
        assert response.status_code == 404
    finally:
        set_container(original_container)


def test_signal_invalid_status_returns_422(tmp_path):
    test_container = AppContainer(tmp_path)
    original_container = current_container
    set_container(test_container)
    try:
        client = TestClient(app)
        response = client.patch(
            "/api/signals/sig_missing/status",
            json={"status": "invalid"},
        )
        assert response.status_code == 422
    finally:
        set_container(original_container)


def test_platform_specific_social_extractors(tmp_path):
    test_container = AppContainer(tmp_path)
    original_container = current_container
    set_container(test_container)
    try:
        dataset_file_dir = tmp_path / "storage" / "dataset_files"
        dataset_file_dir.mkdir(parents=True, exist_ok=True)
        sample_path = dataset_file_dir / "dy_sync_posts.jsonl"
        rows = [
            {
                "aweme_id": "dy_001",
                "caption": "同城副业项目，私信了解完整流程",
                "publish_time": "2026-04-30 10:15:01",
                "share_count": "320",
                "comment_count": "260",
                "liked_count": "2",
            },
            {
                "aweme_id": "dy_002",
                "caption": "同城副业项目，私信了解完整流程",
                "publish_time": "2026-04-30 10:15:35",
                "share_count": "10",
                "comment_count": "11",
                "liked_count": "3",
            },
        ]
        sample_path.write_text("\n".join(json.dumps(row, ensure_ascii=False) for row in rows), encoding="utf-8")

        client = TestClient(app)
        dataset_response = client.post(
            "/api/datasets",
            json={
                "dataset_name": "DY Sync Posts",
                "dataset_type": "raw",
                "source_platform": "dy",
                "scenario_type": "topic_watch",
                "storage_uri": "dy_sync_posts.jsonl",
            },
        )
        dataset_id = dataset_response.json()["dataset"]["id"]

        extract_response = client.post(
            "/api/signals/extract",
            json={
                "dataset_id": dataset_id,
                "extractors": ["template_similarity", "abnormal_activity"],
                "limit": 20,
            },
        )
        assert extract_response.status_code == 200
        signals = extract_response.json()["signals"]
        assert {item["signal_type"] for item in signals} >= {
            "template_similarity_hit",
            "abnormal_activity_hit",
        }
        assert any(item["payload_json"]["source_ref"]["source_platform"] == "dy" for item in signals)
    finally:
        set_container(original_container)


def test_xianyu_seller_template_and_price_extractors(tmp_path):
    test_container = AppContainer(tmp_path)
    original_container = current_container
    set_container(test_container)
    try:
        dataset_file_dir = tmp_path / "storage" / "dataset_files"
        dataset_file_dir.mkdir(parents=True, exist_ok=True)
        sample_path = dataset_file_dir / "xianyu_products.jsonl"
        rows = [
            {
                "product_id": "prd_001",
                "seller_id": "seller_1",
                "product_title": "全新手机低价出，走平台，支持验机",
                "product_desc": "急出回血，私信秒回",
                "price": "3.9",
                "original_price": "899",
            },
            {
                "product_id": "prd_002",
                "seller_id": "seller_1",
                "product_title": "全新手机低价出，走平台，支持验机",
                "product_desc": "急出回血，私信秒回",
                "price": "4.5",
                "original_price": "799",
            },
        ]
        sample_path.write_text("\n".join(json.dumps(row, ensure_ascii=False) for row in rows), encoding="utf-8")

        client = TestClient(app)
        dataset_response = client.post(
            "/api/datasets",
            json={
                "dataset_name": "Xianyu Products",
                "dataset_type": "raw",
                "source_platform": "xianyu",
                "scenario_type": "product_risk",
                "storage_uri": "xianyu_products.jsonl",
            },
        )
        dataset_id = dataset_response.json()["dataset"]["id"]

        extract_response = client.post(
            "/api/signals/extract",
            json={
                "dataset_id": dataset_id,
                "extractors": ["seller_template_reuse", "abnormal_price_band"],
                "limit": 20,
            },
        )
        assert extract_response.status_code == 200
        signals = extract_response.json()["signals"]
        sources = {item["signal_source"] for item in signals}
        assert "platform:xianyu:seller_template_reuse" in sources
        assert "platform:xianyu:abnormal_price_band" in sources
        assert all(item["payload_json"]["source_ref"]["source_platform"] == "xianyu" for item in signals)
    finally:
        set_container(original_container)


def test_xhs_comment_lead_diversion_extractor(tmp_path):
    test_container = AppContainer(tmp_path)
    original_container = current_container
    set_container(test_container)
    try:
        dataset_file_dir = tmp_path / "storage" / "dataset_files"
        dataset_file_dir.mkdir(parents=True, exist_ok=True)
        sample_path = dataset_file_dir / "xhs_comments.jsonl"
        sample_path.write_text(
            json.dumps(
                {
                    "note_id": "note_001",
                    "comment_id": "cmt_001",
                    "comment_text": "资料在群里，微信 abc12345 私信发完整流程",
                    "source_url": "https://example.test/note_001#cmt_001",
                },
                ensure_ascii=False,
            ),
            encoding="utf-8",
        )

        client = TestClient(app)
        dataset_response = client.post(
            "/api/datasets",
            json={
                "dataset_name": "XHS Comments",
                "dataset_type": "raw",
                "source_platform": "xhs",
                "scenario_type": "lead_diversion",
                "storage_uri": "xhs_comments.jsonl",
            },
        )
        dataset_id = dataset_response.json()["dataset"]["id"]

        extract_response = client.post(
            "/api/signals/extract",
            json={
                "dataset_id": dataset_id,
                "extractors": ["xhs_comment_lead_diversion"],
                "limit": 20,
            },
        )
        assert extract_response.status_code == 200
        signal = extract_response.json()["signals"][0]
        assert signal["signal_source"] == "platform:xhs:comment_lead_diversion"
        assert signal["payload_json"]["source_ref"]["source_entity_id"] == "cmt_001"
        assert "abc12345" in signal["payload_json"]["contact_points"]
    finally:
        set_container(original_container)


def test_dy_script_diversion_extractor(tmp_path):
    test_container = AppContainer(tmp_path)
    original_container = current_container
    set_container(test_container)
    try:
        dataset_file_dir = tmp_path / "storage" / "dataset_files"
        dataset_file_dir.mkdir(parents=True, exist_ok=True)
        sample_path = dataset_file_dir / "dy_scripts.jsonl"
        sample_path.write_text(
            json.dumps(
                {
                    "aweme_id": "aweme_001",
                    "caption": "评论区置顶领取资料",
                    "ocr_text": "加微信 dyabc12345 获取教程",
                    "source_url": "https://example.test/video/aweme_001",
                },
                ensure_ascii=False,
            ),
            encoding="utf-8",
        )

        client = TestClient(app)
        dataset_response = client.post(
            "/api/datasets",
            json={
                "dataset_name": "DY Scripts",
                "dataset_type": "raw",
                "source_platform": "dy",
                "scenario_type": "lead_diversion",
                "storage_uri": "dy_scripts.jsonl",
            },
        )
        dataset_id = dataset_response.json()["dataset"]["id"]

        extract_response = client.post(
            "/api/signals/extract",
            json={
                "dataset_id": dataset_id,
                "extractors": ["dy_script_diversion"],
                "limit": 20,
            },
        )
        assert extract_response.status_code == 200
        signal = extract_response.json()["signals"][0]
        assert signal["signal_source"] == "platform:dy:script_diversion"
        assert signal["payload_json"]["source_ref"]["source_entity_id"] == "aweme_001"
        assert "dyabc12345" in signal["payload_json"]["contact_points"]
    finally:
        set_container(original_container)


def test_wb_topic_propagation_extractor(tmp_path):
    test_container = AppContainer(tmp_path)
    original_container = current_container
    set_container(test_container)
    try:
        dataset_file_dir = tmp_path / "storage" / "dataset_files"
        dataset_file_dir.mkdir(parents=True, exist_ok=True)
        sample_path = dataset_file_dir / "wb_topic.jsonl"
        rows = [
            {
                "weibo_id": "wb_001",
                "user_id": "u1",
                "topic": "副业项目",
                "content": "#副业项目# 限时开放名额，私信领取完整流程",
                "created_time": "2026-04-30 11:20:01",
            },
            {
                "weibo_id": "wb_002",
                "user_id": "u2",
                "topic": "副业项目",
                "content": "#副业项目# 限时开放名额，私信领取完整流程",
                "created_time": "2026-04-30 11:20:42",
            },
        ]
        sample_path.write_text("\n".join(json.dumps(row, ensure_ascii=False) for row in rows), encoding="utf-8")

        client = TestClient(app)
        dataset_response = client.post(
            "/api/datasets",
            json={
                "dataset_name": "WB Topic",
                "dataset_type": "raw",
                "source_platform": "wb",
                "scenario_type": "topic_watch",
                "storage_uri": "wb_topic.jsonl",
            },
        )
        dataset_id = dataset_response.json()["dataset"]["id"]

        extract_response = client.post(
            "/api/signals/extract",
            json={
                "dataset_id": dataset_id,
                "extractors": ["wb_topic_propagation"],
                "limit": 20,
            },
        )
        assert extract_response.status_code == 200
        signal = extract_response.json()["signals"][0]
        assert signal["signal_source"] == "platform:wb:topic_propagation"
        assert signal["risk_level"] == "high"
        assert signal["payload_json"]["user_ids"] == ["u1", "u2"]
    finally:
        set_container(original_container)
