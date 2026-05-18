import os
import socket
import threading
import time

from modules.database.mongo_db import HerringboneMongoDatabase
from app.batcher import get_batch_writer
from app.forwarder import forward_data, get_forward_batcher

forward_route = os.environ.get("FORWARD_ROUTE")

PORT = int(os.environ.get("PORT", os.environ.get("CONTAINER_PORT", 7004)))
UDP_BUFFER = int(os.environ.get("UDP_BUFFER", 65535))
UDP_SOCKET_RCVBUF = int(os.environ.get("UDP_SOCKET_RCVBUF", 32 * 1024 * 1024))
WORKER_THREADS = int(os.environ.get("RECEIVER_WORKERS", 8))
CONTEXT_ID = os.environ.get("CONTEXT_ID", "default")
DROP_LOG_INTERVAL = float(os.environ.get("RECEIVER_DROP_LOG_INTERVAL", "5.0"))
TCP_BACKLOG = int(os.environ.get("TCP_BACKLOG", "1024"))
TCP_RECV_BUFFER = int(os.environ.get("TCP_RECV_BUFFER", os.environ.get("UDP_BUFFER", "65535")))

mongo = None
batch_writer = None

_drop_lock = threading.Lock()
_last_drop_log = 0.0
_drops_since_log = 0


def get_mongo():
    global mongo

    if mongo is None:
        mongo = HerringboneMongoDatabase(
            user=os.environ.get("MONGO_USER", "admin"),
            password=os.environ.get("MONGO_PASS", "secret"),
            database=os.environ.get("DB_NAME", "herringbone"),
            host=os.environ.get("MONGO_HOST", "localhost"),
            port=int(os.environ.get("MONGO_PORT", 27017)),
            auth_source=os.environ.get("AUTH_DB", "admin"),
            replica_set=os.environ.get("MONGO_REPLICA_SET", None),
        )
        print("[✓] MongoDB client initialized", flush=True)

    return mongo


def _log_drop(kind: str, forwarded: bool = False):
    global _last_drop_log, _drops_since_log

    now = time.monotonic()

    with _drop_lock:
        _drops_since_log += 1
        if now - _last_drop_log < DROP_LOG_INTERVAL:
            return
        dropped = _drops_since_log
        _drops_since_log = 0
        _last_drop_log = now

    label = f"forwarded {kind.upper()}" if forwarded else kind.upper()
    depth = batch_writer.queue.qsize() if batch_writer is not None else -1
    print(
        f"[✗] Queue full — dropped {dropped} {label} messages in last {DROP_LOG_INTERVAL}s "
        f"queue_depth={depth}",
        flush=True,
    )


def enqueue_local(data, addr, kind):
    if not batch_writer.enqueue(data, addr, kind, CONTEXT_ID):
        _log_drop(kind)


def enqueue_forward(data, addr, kind):
    if not forward_data(forward_route, data, addr, kind=kind):
        _log_drop(kind, forwarded=True)


def start_udp_receiver():
    global batch_writer

    print("Receiver type set to UDP", flush=True)

    udp_receiver = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    udp_receiver.setsockopt(socket.SOL_SOCKET, socket.SO_RCVBUF, UDP_SOCKET_RCVBUF)
    udp_receiver.bind(("0.0.0.0", PORT))

    actual_rcvbuf = udp_receiver.getsockopt(socket.SOL_SOCKET, socket.SO_RCVBUF)
    print(
        f"UDP receiver started on port {PORT} "
        f"udp_buffer={UDP_BUFFER} requested_rcvbuf={UDP_SOCKET_RCVBUF} actual_rcvbuf={actual_rcvbuf}",
        flush=True,
    )

    if forward_route:
        get_forward_batcher(forward_route)
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
            print(f"[✗] UDP receive error: {exc}", flush=True)


def handle_tcp_connection(conn, addr):
    buffer = b""
    try:
        while True:
            data = conn.recv(TCP_RECV_BUFFER)
            if not data:
                break

            buffer += data

            # Stream newline-delimited messages immediately. This prevents a
            # long-lived TCP sender from holding all parser work until close.
            while b"\n" in buffer:
                line, buffer = buffer.split(b"\n", 1)
                line = line.strip()
                if not line:
                    continue
                decoded = line.decode("utf-8", errors="ignore")
                if forward_route:
                    enqueue_forward(decoded, addr[0], "tcp")
                else:
                    enqueue_local(decoded, addr[0], "tcp")

        remainder = buffer.strip()
        if remainder:
            decoded = remainder.decode("utf-8", errors="ignore")
            if forward_route:
                enqueue_forward(decoded, addr[0], "tcp")
            else:
                enqueue_local(decoded, addr[0], "tcp")

    except Exception as exc:
        print(f"[✗] TCP connection error: {exc}", flush=True)
    finally:
        try:
            conn.close()
        except Exception:
            pass


def start_tcp_receiver():
    global batch_writer

    print("Receiver type set to TCP", flush=True)

    tcp_receiver = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    tcp_receiver.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    tcp_receiver.bind(("0.0.0.0", PORT))
    tcp_receiver.listen(TCP_BACKLOG)

    print(f"TCP receiver started on port {PORT} backlog={TCP_BACKLOG} recv_buffer={TCP_RECV_BUFFER}", flush=True)

    if forward_route:
        get_forward_batcher(forward_route)
    else:
        batch_writer = get_batch_writer(get_mongo())

    while True:
        try:
            conn, addr = tcp_receiver.accept()
            thread = threading.Thread(
                target=handle_tcp_connection,
                args=(conn, addr),
                name=f"tcp-client-{addr[0]}",
                daemon=True,
            )
            thread.start()
        except Exception as exc:
            print(f"[✗] TCP accept error: {exc}", flush=True)
