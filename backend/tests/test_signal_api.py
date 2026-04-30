from __future__ import annotations

import json
import sys
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
