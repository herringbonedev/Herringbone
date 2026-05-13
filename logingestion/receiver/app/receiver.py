import os
import sys

TYPE = os.environ.get("RECEIVER_TYPE")

if not TYPE:
    print("[✗] RECEIVER_TYPE is required. Valid values: UDP, TCP, HTTP, REMOTE")
    sys.exit(1)

TYPE = TYPE.upper()
print(f"Starting herringbone receiver...{TYPE}")

if TYPE == "UDP":
    import logingestion.receiver.app.inet
    logingestion.receiver.app.inet.start_udp_receiver()

elif TYPE == "TCP":
    import logingestion.receiver.app.inet
    logingestion.receiver.app.inet.start_tcp_receiver()

elif TYPE == "HTTP":
    import logingestion.receiver.app.web
    logingestion.receiver.app.web.start_http_receiver()

elif TYPE == "REMOTE":
    import logingestion.receiver.app.remote
    logingestion.receiver.app.remote.start_remote_receiver()

else:
    print(f"[✗] Unknown receiver type: {TYPE}. Valid values: UDP, TCP, HTTP, REMOTE")
    sys.exit(1)
