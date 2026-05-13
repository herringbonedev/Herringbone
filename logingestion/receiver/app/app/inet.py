import os
import queue
import socket
import threading

from modules.database.mongo_db import HerringboneMongoDatabase
from app.batcher import get_batch_writer
from app.forwarder import forward_data

forward_route = os.environ.get("FORWARD_ROUTE")

UDP_BUFFER = int(os.environ.get("UDP_BUFFER", 8192))
UDP_SOCKET_RCVBUF = int(os.environ.get("UDP_SOCKET_RCVBUF", 16 * 1024 * 1024))
WORKER_THREADS = int(os.environ.get("RECEIVER_WORKERS", 4))
QUEUE_SIZE = int(os.environ.get("RECEIVER_QUEUE", 20000))
CONTEXT_ID = os.environ.get("CONTEXT_ID", "default")

forward_queue = queue.Queue(maxsize=QUEUE_SIZE)
mongo = None
batch_writer = None


def get_mongo():
    global mongo

    if mongo is None:
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


def forward_worker():
    while True:
        try:
            data, addr = forward_queue.get()
            forward_data(forward_route, data, addr)
        except Exception as exc:
            print(f"[✗] Forward worker failure: {exc}")
        finally:
            forward_queue.task_done()


def start_forward_workers():
    print(f"[✓] Starting {WORKER_THREADS} forward worker threads")

    for index in range(WORKER_THREADS):
        thread = threading.Thread(target=forward_worker, name=f"forward-worker-{index}", daemon=True)
        thread.start()


def enqueue_local(data, addr, kind):
    if not batch_writer.enqueue(data, addr, kind, CONTEXT_ID):
        print(f"[✗] Queue full — dropping {kind.upper()} message")


def enqueue_forward(data, addr, kind):
    try:
        forward_queue.put_nowait((data, addr))
    except queue.Full:
        print(f"[✗] Queue full — dropping forwarded {kind.upper()} message")


def start_udp_receiver():
    global batch_writer

    print("Receiver type set to UDP")

    udp_receiver = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    udp_receiver.setsockopt(socket.SOL_SOCKET, socket.SO_RCVBUF, UDP_SOCKET_RCVBUF)
    udp_receiver.bind(("0.0.0.0", 7004))

    print("UDP receiver started on port 7004")

    if forward_route:
        start_forward_workers()
    else:
        batch_writer = get_batch_writer(get_mongo())

    while True:
        try:
            data, addr = udp_receiver.recvfrom(UDP_BUFFER)
            decoded = data.decode("utf-8", errors="ignore")

            if forward_route:
                enqueue_forward(decoded, addr[0], "udp")
            else:
                enqueue_local(decoded, addr[0], "udp")

        except Exception as exc:
            print(f"[✗] UDP receive error: {exc}")


def start_tcp_receiver():
    global batch_writer

    print("Receiver type set to TCP")

    tcp_receiver = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    tcp_receiver.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    tcp_receiver.bind(("0.0.0.0", 7004))
    tcp_receiver.listen(200)

    print("TCP receiver started on port 7004")

    if forward_route:
        start_forward_workers()
    else:
        batch_writer = get_batch_writer(get_mongo())

    while True:
        conn = None

        try:
            conn, addr = tcp_receiver.accept()
            data = conn.recv(UDP_BUFFER)

            if not data:
                continue

            decoded = data.decode("utf-8", errors="ignore")

            if forward_route:
                enqueue_forward(decoded, addr[0], "tcp")
            else:
                enqueue_local(decoded, addr[0], "tcp")

        except Exception as exc:
            print(f"[✗] TCP receive error: {exc}")

        finally:
            try:
                if conn is not None:
                    conn.close()
            except Exception:
                pass
