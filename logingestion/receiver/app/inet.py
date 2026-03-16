from datetime import datetime, UTC
import socket
import os
import threading
import queue

from modules.database.mongo_db import HerringboneMongoDatabase
from app.forwarder import forward_data


forward_route = os.environ.get("FORWARD_ROUTE")
hostname = socket.gethostname()

UDP_BUFFER = int(os.environ.get("UDP_BUFFER", 8192))
WORKER_THREADS = int(os.environ.get("RECEIVER_WORKERS", 4))
QUEUE_SIZE = int(os.environ.get("RECEIVER_QUEUE", 20000))

event_queue = queue.Queue(maxsize=QUEUE_SIZE)

mongo = None


def get_mongo():
    mongo = HerringboneMongoDatabase(
        user=os.environ.get("MONGO_USER", "admin"),
        password=os.environ.get("MONGO_PASS", "secret"),
        database=os.environ.get("DB_NAME", "herringbone"),
        host=os.environ.get("MONGO_HOST", "localhost"),
        port=int(os.environ.get("MONGO_PORT", 27017)),
        replica_set=os.environ.get("MONGO_REPLICA_SET", None),
    )

    print("[✓] MongoDB client initialized")

    return mongo


def worker():
    """
    Worker thread processing ingestion events.
    """

    while True:

        try:
            data, addr, kind = event_queue.get()

            if forward_route:
                forward_data(forward_route, data, addr)

            else:

                event_id = mongo.insert_event({
                    "context_id": os.environ.get("CONTEXT_ID", "default"),
                    "raw": data,
                    "source": {
                        "address": addr,
                        "kind": kind,
                    },
                    "event_time": datetime.now(UTC),
                    "ingested_at": datetime.now(UTC),
                    "receiver": {
                        "hostname": hostname
                    }
                })

                mongo.upsert_event_state(event_id, {
                    "parsed": False,
                    "enriched": False,
                    "detected": False,
                    "severity": None,
                })

        except Exception as e:
            print(f"[✗] Worker failure: {e}")

        finally:
            event_queue.task_done()


def start_workers():

    print(f"[✓] Starting {WORKER_THREADS} worker threads")

    for _ in range(WORKER_THREADS):

        t = threading.Thread(
            target=worker,
            daemon=True
        )

        t.start()


def start_udp_receiver():

    global mongo

    print("Receiver type set to UDP")

    udp_receiver = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    udp_receiver.setsockopt(socket.SOL_SOCKET, socket.SO_RCVBUF, 16 * 1024 * 1024)
    udp_receiver.bind(("0.0.0.0", 7004))

    print("UDP receiver started on port 7004")

    if forward_route is None:
        mongo = get_mongo()

    start_workers()

    while True:

        try:

            data, addr = udp_receiver.recvfrom(UDP_BUFFER)
            decoded = data.decode("utf-8", errors="ignore")

            try:
                event_queue.put_nowait((decoded, addr[0], "udp"))

            except queue.Full:
                print("[✗] Queue full — dropping UDP packet")

        except Exception as e:
            print(f"[✗] UDP receive error: {e}")


def start_tcp_receiver():

    global mongo

    print("Receiver type set to TCP")

    tcp_receiver = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    tcp_receiver.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    tcp_receiver.bind(("0.0.0.0", 7004))
    tcp_receiver.listen(200)

    print("TCP receiver started on port 7004")

    if forward_route is None:
        mongo = get_mongo()

    start_workers()

    while True:

        try:

            conn, addr = tcp_receiver.accept()
            data = conn.recv(8192)

            if not data:
                conn.close()
                continue

            decoded = data.decode("utf-8", errors="ignore")

            try:
                event_queue.put_nowait((decoded, addr[0], "tcp"))

            except queue.Full:
                print("[✗] Queue full — dropping TCP message")

        except Exception as e:
            print(f"[✗] TCP receive error: {e}")

        finally:
            try:
                conn.close()
            except:
                pass