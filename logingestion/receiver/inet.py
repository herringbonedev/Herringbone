import socket
import os
from database import MongoDatabaseHandler

def start_udp_receiver():
    print("Connecting to database...")
    mongo = MongoDatabaseHandler()

    print("Receiver type set to UDP...")
    udp_receiver = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    udp_receiver.bind(('0.0.0.0', 7002))
    print("Started on container port 7002")

    while( True):
        data, addr = udp_receiver.recvfrom(1024)
        data = data.decode('utf-8')
        print(f"[Source Address: {addr}] {data}")
        mongo.insert_log({"source_address": addr, "log": data})

def start_tcp_receiver():
    print("Receiver type set to TCP...")
    tcp_receiver = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    tcp_receiver.bind(('0.0.0.0', 7002))
    print("Started on container port 7002")

    while(True):
        data, addr = tcp_receiver.accept()
        data = data.recv(1024).decode('utf-8')
        print(f"[Source Address: {addr}] {data}")