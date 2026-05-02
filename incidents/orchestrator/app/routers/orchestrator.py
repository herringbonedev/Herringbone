from fastapi import APIRouter, HTTPException, Depends, Request
from modules.auth.auth import require_internal_scopes, service_auth_headers
from modules.audit.logger import AuditLogger
import requests
import os


orchestrator_run = require_internal_scopes("incidents:orchestrate")

router = APIRouter(
    prefix="/incidents/orchestrator",
    tags=["orchestrator"],
)

audit = AuditLogger()

CORRELATOR_URL = os.environ.get(
    "CORRELATOR_URL",
    "http://127.0.0.1:7012/incidents/correlator/correlate",
)

INCIDENTSET_API = os.environ.get(
    "INCIDENTSET_API",
    "http://127.0.0.1:7011/incidents/incidentset",
)


def service_headers(context_id: str) -> dict:
    return {
        **service_auth_headers(),
        "X-Herringbone-Context": context_id,
    }


def resolve_internal_context(
    payload: dict,
    request: Request,
    identity: dict,
) -> str:
    payload_context_id = payload.get("context_id")

    header_context_id = (
        request.headers.get("X-Herringbone-Context")
        or request.headers.get("X-Herringbone-Org")
    )

    context_id = payload_context_id or header_context_id

    if not context_id:
        audit.log(
            event="orchestrator_missing_context",
            identity=identity,
            request=request,
            result="failure",
            severity="WARNING",
        )
        raise HTTPException(status_code=400, detail="Missing context_id")

    if (
        payload_context_id
        and header_context_id
        and str(payload_context_id) != str(header_context_id)
    ):
        audit.log(
            event="orchestrator_context_mismatch",
            identity=identity,
            request=request,
            result="failure",
            severity="WARNING",
            metadata={
                "payload_context_id": str(payload_context_id),
                "header_context_id": str(header_context_id),
            },
        )
        raise HTTPException(status_code=403, detail="Context mismatch")

    context_id = str(context_id)

    request.state.context_id = context_id
    request.state.identity = identity

    return context_id


@router.post("/process_detection")
async def process_detection(
    payload: dict,
    request: Request,
    identity=Depends(orchestrator_run),
):
    context_id = resolve_internal_context(payload, request, identity)

    if "rule_id" not in payload:
        audit.log(
            event="orchestrator_missing_rule_id",
            identity=identity,
            request=request,
            result="failure",
            severity="WARNING",
            metadata={"context_id": context_id},
        )

        raise HTTPException(status_code=400, detail="Missing rule_id")

    rule_id = payload.get("rule_id")
    rule_name = payload.get("rule_name", rule_id)

    try:
        resp = requests.post(
            CORRELATOR_URL,
            json={**payload, "context_id": context_id},
            headers=service_headers(context_id),
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
            severity="ERROR",
            metadata={
                "context_id": context_id,
                "error": str(e),
            },
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
                severity="ERROR",
                metadata={"context_id": context_id},
            )

            raise HTTPException(status_code=500, detail="Missing incident_id")

        update_payload = {
            "_id": incident_id,
            "events": payload.get("event_ids", []),
            "detections": [payload.get("detection_id")],
        }

        try:
            resp = requests.post(
                f"{INCIDENTSET_API}/internal/update_incident",
                json={**update_payload, "context_id": context_id},
                headers=service_headers(context_id),
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
                severity="ERROR",
                metadata={
                    "context_id": context_id,
                    "error": str(e),
                },
            )

            raise HTTPException(status_code=502, detail=str(e))

        audit.log(
            event="orchestrator_incident_attached",
            identity=identity,
            request=request,
            target=incident_id,
            metadata={"context_id": context_id},
        )

        return {
            "result": "attached",
            "incident_id": incident_id,
        }

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
                f"{INCIDENTSET_API}/internal/insert_incident",
                json={**create_payload, "context_id": context_id},
                headers=service_headers(context_id),
                timeout=5,
            )

            resp.raise_for_status()

        except Exception as e:
            audit.log(
                event="orchestrator_incident_create_failed",
                identity=identity,
                request=request,
                result="failure",
                severity="ERROR",
                metadata={
                    "context_id": context_id,
                    "error": str(e),
                },
            )

            raise HTTPException(status_code=502, detail=str(e))

        audit.log(
            event="orchestrator_incident_created",
            identity=identity,
            request=request,
            metadata={
                "rule_id": rule_id,
                "context_id": context_id,
            },
        )

        return {"result": "created"}

    audit.log(
        event="orchestrator_unknown_action",
        identity=identity,
        request=request,
        result="failure",
        severity="WARNING",
        metadata={
            "action": action,
            "context_id": context_id,
        },
    )

    raise HTTPException(status_code=400, detail=f"Unknown action {action}")