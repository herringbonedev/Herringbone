import inet, web
import os

TYPE = os.environ.get("RECEIVER_TYPE")
print("Starting herringbone receiver..."+ TYPE)

if TYPE == "UDP":
    inet.start_udp_receiver()

if TYPE == "TCP":
    inet.start_tcp_receiver()

if TYPE == "HTTP":
    web.start_http_receiver()

else:
    print(f"Unknown receiver type: {TYPE}")