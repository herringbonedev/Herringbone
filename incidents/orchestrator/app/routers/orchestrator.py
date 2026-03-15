from fastapi import APIRouter, HTTPException, Depends, Request
from modules.auth.auth import require_scopes
from modules.audit.logger import AuditLogger
import requests
import os


orchestrator_run = require_scopes("incidents:orchestrate")

router = APIRouter(
    prefix="/incidents/orchestrator",
    tags=["orchestrator"],
)

audit = AuditLogger()

SERVICE_TOKEN_PATH = "/run/secrets/service_token"

CORRELATOR_URL = os.environ.get(
    "CORRELATOR_URL",
    "http://127.0.0.1:7012/incidents/correlator/correlate",
)

INCIDENTSET_API = os.environ.get(
    "INCIDENTSET_API",
    "http://127.0.0.1:7011/incidents/incidentset",
)

_service_token_cache: str | None = None


def service_auth_headers():
    global _service_token_cache

    if _service_token_cache is None:
        try:
            with open(SERVICE_TOKEN_PATH, "r") as f:
                _service_token_cache = f.read().strip()
        except Exception as e:
            raise RuntimeError(f"Failed to read service token: {e}")

        if not _service_token_cache:
            raise RuntimeError("Service token is empty")

    return {"Authorization": f"Bearer {_service_token_cache}"}


@router.post("/process_detection")
async def process_detection(
    payload: dict,
    request: Request,
    identity=Depends(orchestrator_run),
):

    if "rule_id" not in payload:

        audit.log(
            event="orchestrator_missing_rule_id",
            identity=identity,
            request=request,
            result="failure",
        )

        raise HTTPException(status_code=400, detail="Missing rule_id")

    rule_id = payload.get("rule_id")
    rule_name = payload.get("rule_name", rule_id)


    try:

        resp = requests.post(
            CORRELATOR_URL,
            json=payload,
            headers=service_auth_headers(),
            timeout=5,
        )

        resp.raise_for_status()
        decision = resp.json()

    except Exception as e:

        audit.log(
            event="orchestrator_correlator_failed",
            identity=identity,
            request=request,
            result="failure",
            metadata={"error": str(e)},
            severity="ERROR",
        )

        raise HTTPException(status_code=502, detail=str(e))

    action = decision.get("action")


    if action == "attach":

        incident_id = decision.get("incident_id")

        if not incident_id:

            audit.log(
                event="orchestrator_missing_incident_id",
                identity=identity,
                request=request,
                result="failure",
            )

            raise HTTPException(status_code=500, detail="Missing incident_id")

        update_payload = {
            "_id": incident_id,
            "events": payload.get("event_ids", []),
            "detections": [payload.get("detection_id")],
        }

        try:

            resp = requests.post(
                f"{INCIDENTSET_API}/update_incident",
                json=update_payload,
                headers=service_auth_headers(),
                timeout=5,
            )

            resp.raise_for_status()

        except Exception as e:

            audit.log(
                event="orchestrator_incident_attach_failed",
                identity=identity,
                request=request,
                target=incident_id,
                result="failure",
                metadata={"error": str(e)},
                severity="ERROR",
            )

            raise HTTPException(status_code=502, detail=str(e))

        audit.log(
            event="orchestrator_incident_attached",
            identity=identity,
            request=request,
            target=incident_id,
        )

        return {"result": "attached", "incident_id": incident_id}


    if action == "create":

        create_payload = {
            "title": payload.get("title", "Incident from " + rule_name),
            "description": payload.get(
                "description",
                "Incident created automatically from detection " + rule_name,
            ),
            "status": "open",
            "priority": payload.get("priority", "medium"),
            "owner": None,
            "events": payload.get("event_ids", []),
            "detections": [payload.get("detection_id")],
            "rule_id": rule_id,
            "rule_name": rule_name,
            "correlation_identity": decision.get("correlation_identity", {}),
        }

        try:

            resp = requests.post(
                f"{INCIDENTSET_API}/insert_incident",
                json=create_payload,
                headers=service_auth_headers(),
                timeout=5,
            )

            resp.raise_for_status()

        except Exception as e:

            audit.log(
                event="orchestrator_incident_create_failed",
                identity=identity,
                request=request,
                result="failure",
                metadata={"error": str(e)},
                severity="ERROR",
            )

            raise HTTPException(status_code=502, detail=str(e))

        audit.log(
            event="orchestrator_incident_created",
            identity=identity,
            request=request,
            metadata={"rule_id": rule_id},
        )

        return {"result": "created"}
    

    audit.log(
        event="orchestrator_unknown_action",
        identity=identity,
        request=request,
        result="failure",
        metadata={"action": action},
    )

    raise HTTPException(status_code=400, detail=f"Unknown action {action}")