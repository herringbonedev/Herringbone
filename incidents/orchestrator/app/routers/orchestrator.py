from fastapi import APIRouter, HTTPException
import requests
import os

router = APIRouter(
    prefix="/incidents/orchestrator",
    tags=["orchestrator"],
)

CORRELATOR_URL = os.environ.get(
    "CORRELATOR_URL",
    "http://127.0.0.1:7012/incidents/correlator/correlate",
)

INCIDENTSET_API = os.environ.get(
    "INCIDENTSET_API",
    "http://127.0.0.1:7011/incidents/incidentset",
)


@router.post("/process_detection")
async def process_detection(payload: dict):
    print("[*] Received detection payload")
    print(f"[*] Payload: {payload}")

    if "rule_id" not in payload:
        print("[✗] Missing rule_id in detection payload")
        raise HTTPException(status_code=400, detail="Missing rule_id")

    rule_id = payload.get("rule_id")
    rule_name = payload.get("rule_name", rule_id)

    print(f"[*] rule_id: {rule_id}")
    print(f"[*] rule_name: {rule_name}")

    print(f"[*] Calling correlator at {CORRELATOR_URL}")
    try:
        corr_resp = requests.post(CORRELATOR_URL, json=payload, timeout=5)
        corr_resp.raise_for_status()
        decision = corr_resp.json()
        print("[✓] Correlator responded successfully")
        print(f"[*] Correlation decision payload: {decision}")
    except Exception as e:
        print(f"[✗] Correlator request failed: {e}")
        raise HTTPException(status_code=502, detail=f"Correlator error: {e}")

    action = decision.get("action")
    print(f"[*] Correlation decision resolved to: {action}")

    if action == "attach":
        incident_id = decision.get("incident_id")
        if not incident_id:
            print("[✗] Correlator returned attach without incident_id")
            raise HTTPException(status_code=500, detail="Missing incident_id from correlator")

        update_payload = {
            "_id": incident_id,
        }

        print(f"[*] Attaching detection to incident {incident_id}")
        print(f"[*] Update payload: {update_payload}")

        try:
            resp = requests.post(
                f"{INCIDENTSET_API}/update_incident",
                json=update_payload,
                timeout=5,
            )
            resp.raise_for_status()
            print("[✓] Incident updated successfully")
        except Exception as e:
            print(f"[✗] Incident update failed: {e}")
            raise HTTPException(status_code=502, detail=f"Incident update failed: {e}")

        return {
            "result": "attached",
            "incident_id": incident_id,
        }

    if action == "create":
        create_payload = {
            "title": payload.get("title", "New incident from detection"),
            "description": payload.get(
                "description",
                "Incident created automatically from detection",
            ),
            "status": "open",
            "priority": payload.get("priority", "medium"),
            "owner": None,
            "events": payload.get("event_ids", []),
            "detections": [payload.get("detection_id")],
            "rule_id": rule_id,
            "rule_name": rule_name,
        }

        print("[*] Creating new incident")
        print(f"[*] Create payload: {create_payload}")

        try:
            resp = requests.post(
                f"{INCIDENTSET_API}/insert_incident",
                json=create_payload,
                timeout=5,
            )
            resp.raise_for_status()
            print("[✓] Incident created successfully")
        except Exception as e:
            print(f"[✗] Incident creation failed: {e}")
            raise HTTPException(status_code=502, detail="Incident create failed")

        return {
            "result": "created",
        }

    print(f"[✗] Unknown correlation action received: {action}")
    raise HTTPException(status_code=400, detail=f"Unknown action: {action}")
