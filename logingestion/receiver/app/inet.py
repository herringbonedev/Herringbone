from datetime import datetime
import socket
import os
from modules.database.mongo_db_2 import HerringboneMongoDatabase
from forwarder import forward_data

forward_route = os.environ.get("FORWARD_ROUTE", None)

def get_mongo():
    try:
        mongo = HerringboneMongoDatabase(
            user=os.environ.get("MONGO_USER", "admin"),
            password=os.environ.get("MONGO_PASS", "secret"),
            database=os.environ.get("DB_NAME", "herringbone"),
            host=os.environ.get("MONGO_HOST", "localhost"),
            port=int(os.environ.get("MONGO_PORT", 27017)),
            replica_set=os.environ.get("MONGO_REPLICA_SET", None),
        )
        print("[✓] Connected to MongoDB")
        return mongo
    except Exception as e:
        print(f"[✗] Mongo connection failed: {e}")
        return None


def start_udp_receiver():
    print("Receiver type set to UDP...")
    udp_receiver = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    udp_receiver.bind(("0.0.0.0", 7004))
    print("UDP receiver started on port 7004")

    while True:
        data, addr = udp_receiver.recvfrom(1024)
        data = data.decode("utf-8")
        print(f"[Source Address: {addr}] {data}")

        if forward_route is None:
            mongo = get_mongo()
            if not mongo:
                print("UDP receiver exiting due to database init failure.")
                return

            try:
                event_id = mongo.insert_event({
                    "raw": data,
                    "source": {
                        "address": addr[0],
                        "kind": "udp",
                    },
                    "event_time": datetime.utcnow(),
                    "ingested_at": datetime.utcnow(),
                })

                mongo.upsert_event_state(event_id, {
                    "parsed": False,
                    "enriched": False,
                    "detected": False,
                    "severity": None,
                })

                print("[✓] Data received and inserted into MongoDB 200")
            except Exception as e:
                print(f"[✗] Mongo insert operation failed: {e}")
                return (f"Insert failed: {e}", 500)
        else:
            result = forward_data(forward_route, data, addr[0])
            if result:
                print("[✓] Forward succeed 200")
            else:
                print("[✗] Forward failed 500")


def start_tcp_receiver():
    print("Receiver type set to TCP...")
    tcp_receiver = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    tcp_receiver.bind(("0.0.0.0", 7004))
    tcp_receiver.listen(5)
    print("TCP receiver started on port 7004")

    while True:
        conn, addr = tcp_receiver.accept()
        data = conn.recv(1024).decode("utf-8")
        print(f"[Source Address: {addr}] {data}")

        if forward_route is None:
            mongo = get_mongo()
            if not mongo:
                print("TCP receiver exiting due to database init failure.")
                return

            try:
                event_id = mongo.insert_event({
                    "raw": data,
                    "source": {
                        "address": addr[0],
                        "kind": "tcp",
                    },
                    "event_time": datetime.utcnow(),
                    "ingested_at": datetime.utcnow(),
                })

                mongo.upsert_event_state(event_id, {
                    "parsed": False,
                    "enriched": False,
                    "detected": False,
                    "severity": None,
                })
            except Exception as e:
                print(f"[✗] Mongo insert operation failed: {e}")
        else:
            result = forward_data(forward_route, data, addr[0])
            if result:
                return (f"Forward succeed", 200)
            else:
                return (f"Forward failed", 500)

        conn.close()
