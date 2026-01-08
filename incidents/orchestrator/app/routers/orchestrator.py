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
    print(payload)

    if "rule_id" not in payload:
        print("[✗] Missing rule_id in detection payload")
        raise HTTPException(status_code=400, detail="Missing rule_id")

    rule_id = payload.get("rule_id")
    rule_name = payload.get("rule_name", rule_id)

    print(f"[*] rule_id: {rule_id}")
    print(f"[*] rule_name: {rule_name}")

    print(f"[*] Calling correlator at {CORRELATOR_URL}")
    try:
        resp = requests.post(CORRELATOR_URL, json=payload, timeout=5)
        resp.raise_for_status()
        decision = resp.json()
        print("[✓] Correlator response:")
        print(decision)
    except Exception as e:
        print("[✗] Correlator failed")
        print(str(e))
        raise HTTPException(status_code=502, detail=str(e))

    action = decision.get("action")
    print(f"[*] Correlator action: {action}")

    if action == "attach":
        incident_id = decision.get("incident_id")
        if not incident_id:
            print("[✗] Missing incident_id on attach")
            raise HTTPException(status_code=500, detail="Missing incident_id")

        update_payload = {
            "_id": incident_id,
            "events": payload.get("event_ids", []),
            "detections": [payload.get("detection_id")],
        }

        print("[*] Attaching detection")
        print(update_payload)

        try:
            resp = requests.post(
                f"{INCIDENTSET_API}/update_incident",
                json=update_payload,
                timeout=5,
            )
            resp.raise_for_status()
            print("[✓] Incident updated")
        except Exception as e:
            print("[✗] Incident update failed")
            print(str(e))
            raise HTTPException(status_code=502, detail=str(e))

        return {"result": "attached", "incident_id": incident_id}

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

        print("[*] Creating incident")
        print(create_payload)

        try:
            resp = requests.post(
                f"{INCIDENTSET_API}/insert_incident",
                json=create_payload,
                timeout=5,
            )
            resp.raise_for_status()
            print("[✓] Incident created")
        except Exception as e:
            print("[✗] Incident create failed")
            print(str(e))
            raise HTTPException(status_code=502, detail=str(e))

        return {"result": "created"}

    print("[✗] Unknown action")
    raise HTTPException(status_code=400, detail=f"Unknown action {action}")
