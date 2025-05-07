import socket
import os

def start_udp_receiver():
    print("Receiver type set to UDP...")
    udp_receiver = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    udp_receiver.bind(('0.0.0.0', 7002))
    print("Started on container port 7002")

    while( True):
        print("Receiving...")
        data, addr = udp_receiver.recvfrom(1024)
        data = data.decode('utf-8')
        print(f"[{addr}] {data}")

def start_tcp_receiver():
    print("Receiver type set to TCP...")
    tcp_receiver = socker.socket(socket.AF_INET, socket.SOCK_STREAM)
    tcp_receiver.bind(('0.0.0.0', 7002))
    print("Started on container port 7002")

    while(True):
        print("Receiving...")
        data, addr = tcp_receiver.accept()
        data = data.recv(1024).decode('utf-8')
        print(f"[{addr}] {data}")