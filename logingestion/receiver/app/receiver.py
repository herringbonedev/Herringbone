import os

TYPE = os.environ.get("RECEIVER_TYPE")
print("Starting herringbone receiver..."+ TYPE)

if TYPE == "UDP":
    import inet
    inet.start_udp_receiver()

elif TYPE == "TCP":
    import inet
    inet.start_tcp_receiver()

elif TYPE == "HTTP":
    import web
    web.start_http_receiver()

elif TYPE == "REMOTE":
    import remote
    remote.start_remote_receiver()

else:
    print(f"Unknown receiver type: {TYPE}")