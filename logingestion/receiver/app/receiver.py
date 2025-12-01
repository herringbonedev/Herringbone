import os

TYPE = os.environ.get("RECEIVER_TYPE")
print("Starting herringbone receiver..."+ TYPE)

if TYPE == "UDP":
    import inet
    inet.start_udp_receiver()

if TYPE == "TCP":
    import inet
    inet.start_tcp_receiver()

if TYPE == "HTTP":
    import web
    web.start_http_receiver()

if TYPE == "REMOTE":
    import remote
    remote.start_remote_receiver()

else:
    print(f"Unknown receiver type: {TYPE}")