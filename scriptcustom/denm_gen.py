#!/usr/bin/env python3
import socket
import time
import json

UDP_IP = "127.0.0.1" #loopback poi quando si avrà un nic 802.11p lo si adatterà
UDP_PORT = 2002

sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)

station_id = 12345
duration = 10      # secondi totali
interval = 1       # invio ogni 1 secondo
end_time = time.time() + duration

# Lista dei messaggi da inviare
messages = [
    {"eventType": "roadHazard", "subType": "icyRoad", "severity": "high"},
    {"eventType": "accident", "subType": "lane1Accident", "severity": "high"},
    {"eventType": "traffic", "subType": "trafficJam", "severity": "medium"},
    {"eventType": "roadClosure", "subType": "roadClosed", "severity": "high"},
    {"eventType": "roadWorks", "subType": "roadWorks", "severity": "medium"}
]

sequence_number = 1

print(f"Invio DENM multipli per {duration} secondi...")

while time.time() < end_time:
    # Seleziona il messaggio da inviare in round-robin
    msg_index = (sequence_number - 1) % len(messages)
    base_msg = messages[msg_index]

    # Aggiungi campi standard
    denm_msg = {
        "eventType": base_msg["eventType"],
        "subType": base_msg["subType"],
        "severity": base_msg["severity"],
        "location": {"lat": 45.1234, "lon": 11.5678},
        "stationID": station_id,
        "sequenceNumber": sequence_number
    }

    payload = json.dumps(denm_msg).encode("utf-8")
    sock.sendto(payload, (UDP_IP, UDP_PORT))
    print(f"Inviato DENM {sequence_number}: {denm_msg}")

    sequence_number += 1
    time.sleep(interval)

print("Script terminato automaticamente ✅")
