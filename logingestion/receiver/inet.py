import socket
import os
from modules.database.mongo_db import HerringboneMongoDatabase


def get_mongo():
    """
    Initialize a MongoDB connection handler using env vars.
    Falls back gracefully if required envs are missing.
    """
    try:
        mongo = HerringboneMongoDatabase(
            user=os.environ.get("MONGO_USER", "admin"),
            password=os.environ.get("MONGO_PASS", "secret"),
            database=os.environ.get("DB_NAME", "herringbone"),
            collection=os.environ.get("COLLECTION_NAME", "logs"),
            host=os.environ.get("MONGO_HOST", "localhost"),
            port=int(os.environ.get("MONGO_PORT", 27017))
        )
        print("[✓] Connected to MongoDB")
        return mongo
    except Exception as e:
        print(f"[✗] Mongo connection failed: {e}")
        return None


def start_udp_receiver():
    """
    Start a UDP socket listener and write received logs to MongoDB.
    """
    mongo = get_mongo()
    if not mongo:
        print("UDP receiver exiting due to database init failure.")
        return

    print("Receiver type set to UDP...")
    udp_receiver = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    udp_receiver.bind(("0.0.0.0", 7002))
    print("UDP receiver started on port 7002")

    while True:
        data, addr = udp_receiver.recvfrom(1024)
        data = data.decode("utf-8")
        print(f"[Source Address: {addr}] {data}")

        try:
            mongo.insert_log(
                {"source_address": addr, "raw_log": data},
                clean_codec=True
            )
        except Exception as e:
            print(f"[✗] Mongo insert operation failed: {e}")


def start_tcp_receiver():
    """
    Start a TCP socket listener and write received logs to MongoDB.
    """
    mongo = get_mongo()
    if not mongo:
        print("TCP receiver exiting due to database init failure.")
        return

    print("Receiver type set to TCP...")
    tcp_receiver = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    tcp_receiver.bind(("0.0.0.0", 7002))
    tcp_receiver.listen(5)  # TCP needs to listen before accept
    print("TCP receiver started on port 7002")

    while True:
        conn, addr = tcp_receiver.accept()
        data = conn.recv(1024).decode("utf-8")
        print(f"[Source Address: {addr}] {data}")

        try:
            mongo.insert_log(
                {"source_address": addr, "raw_log": data},
                clean_codec=True
            )
        except Exception as e:
            print(f"[✗] Mongo insert operation failed: {e}")
        finally:
            conn.close()
