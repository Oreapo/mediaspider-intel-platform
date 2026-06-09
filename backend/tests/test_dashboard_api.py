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


def test_dashboard_summary_aggregates_intelligence_flow(tmp_path):
    test_container = AppContainer(tmp_path)
    original_container = current_container
    set_container(test_container)
    try:
        client = TestClient(app)
        dataset_file_dir = tmp_path / "storage" / "dataset_files"
        dataset_file_dir.mkdir(parents=True, exist_ok=True)
        (dataset_file_dir / "dashboard_source.jsonl").write_text(
            "\n".join(
                [
                    json.dumps({"content_id": "note_001", "body": "微信 abc12345 引流"}, ensure_ascii=False),
                    json.dumps({"content_id": "note_002", "body": "普通分享"}, ensure_ascii=False),
                ]
            ),
            encoding="utf-8",
        )
        dataset = client.post(
            "/api/datasets",
            json={
                "dataset_name": "Dashboard Source Dataset",
                "dataset_type": "raw",
                "source_platform": "xhs",
                "scenario_type": "lead_diversion",
                "storage_uri": "dashboard_source.jsonl",
            },
        ).json()["dataset"]
        signal = client.post(
            "/api/signals",
            json={
                "dataset_id": dataset["id"],
                "signal_type": "contact_point_hit",
                "signal_source": "rule:contact_points",
                "risk_level": "high",
                "risk_score": 85,
                "summary": "疑似联系方式或导流点：abc12345",
                "status": "confirmed",
                "payload_json": {
                    "contact_point": "abc12345",
                    "source_ref": {"dataset_id": dataset["id"], "row_index": 0},
                },
            },
        ).json()["signal"]
        pending_signal = client.post(
            "/api/signals",
            json={
                "dataset_id": dataset["id"],
                "signal_type": "risk_term_hit",
                "signal_source": "rule:risk_terms",
                "risk_level": "critical",
                "risk_score": 95,
                "summary": "命中风险词：黑产",
                "status": "new",
                "payload_json": {
                    "term": "黑产",
                    "source_ref": {"dataset_id": dataset["id"], "row_index": 1},
                },
            },
        ).json()["signal"]
        entity = client.post(
            "/api/entities/from-signal",
            json={"signal_id": signal["id"]},
        ).json()["entity"]
        case = client.post(
            "/api/cases",
            json={
                "case_name": "Dashboard Case",
                "case_type": "lead_diversion",
                "priority": "high",
                "status": "investigating",
            },
        ).json()["case"]
        ready_case = client.post(
            "/api/cases",
            json={
                "case_name": "Ready Evidence Case",
                "case_type": "lead_diversion",
                "priority": "critical",
                "status": "ready_for_evidence",
            },
        ).json()["case"]
        for link_type, target_id in [
            ("dataset", dataset["id"]),
            ("signal", signal["id"]),
            ("entity", entity["id"]),
        ]:
            response = client.post(
                f"/api/cases/{case['id']}/links",
                json={"link_type": link_type, "target_id": target_id},
            )
            assert response.status_code == 200
        packet = client.post(
            "/api/evidence/packets",
            json={"case_id": case["id"], "packet_name": "Dashboard Evidence"},
        ).json()["packet"]

        response = client.get("/api/dashboard/summary")

        assert response.status_code == 200
        payload = response.json()
        assert payload["summary"]["dataset_count"] == 1
        assert payload["summary"]["record_count"] == 2
        assert payload["summary"]["signal_count"] == 2
        assert payload["summary"]["high_risk_signal_count"] == 2
        assert payload["summary"]["confirmed_signal_count"] == 1
        assert payload["summary"]["entity_count"] == 1
        assert payload["summary"]["case_count"] == 2
        assert payload["summary"]["open_case_count"] == 2
        assert payload["summary"]["evidence_packet_count"] == 1
        assert payload["breakdowns"]["signal_risk_levels"] == {"high": 1, "critical": 1}
        assert payload["breakdowns"]["case_priorities"] == {"high": 1, "critical": 1}
        assert payload["risk_distribution"]["platforms"][0]["key"] == "xhs"
        assert payload["risk_distribution"]["platforms"][0]["high_risk_signal_count"] == 2
        assert payload["risk_distribution"]["scenarios"][0]["key"] == "lead_diversion"
        assert payload["risk_distribution"]["scenarios"][0]["case_count"] == 2
        assert payload["pending"]["high_risk_signals"][0]["id"] == pending_signal["id"]
        assert payload["pending"]["ready_cases"][0]["id"] == ready_case["id"]
        assert {item["id"] for item in payload["latest"]["signals"]} >= {signal["id"], pending_signal["id"]}
        assert {item["id"] for item in payload["latest"]["cases"]} >= {case["id"], ready_case["id"]}
        assert payload["latest"]["evidence_packets"][0]["id"] == packet["id"]
    finally:
        set_container(original_container)
