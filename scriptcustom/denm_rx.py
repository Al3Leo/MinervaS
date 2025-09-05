#!/usr/bin/env python3
import socket

# Configurazione socket UDP
UDP_IP = "127.0.0.1"   # loopback, cambiare quando si avrà un nic  che supporti 802.11p
UDP_PORT = 2002         # porta dove arrivano i DENM

sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
sock.bind((UDP_IP, UDP_PORT))

print(f"In ascolto su {UDP_IP}:{UDP_PORT} per pacchetti DENM...")

while True:
    data, addr = sock.recvfrom(1024)  # buffer fino a 1024 byte
    payload_str = data.decode("utf-8", errors="ignore")
    
    # Stampa informazioni base del DENM
    print("----")
    print(f"Da: {addr}")
    print(f"Lunghezza payload: {len(data)} byte")
    print(f"Contenuto payload: {payload_str}")

#Alessio Leo
