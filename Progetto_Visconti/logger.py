#!/usr/bin/env python3
from scapy.all import sniff, Raw, IP
from datetime import datetime
import os

LOG_FILE = "/var/log/v2x_cam.log"
CAM_SIGNATURE = b"\x3f\xe1\xed\x04\x03\xff\xe3\xff\xf4\x00\x40\x01\x24\x00\x02\x6c\x6c" #pattern da matchare per la detection di pacchetti CAM


os.makedirs(os.path.dirname(LOG_FILE), exist_ok=True)

def log_cam_packet(pkt):
    if Raw in pkt:
        payload = bytes(pkt[Raw])
        if CAM_SIGNATURE in payload:
            timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            src_ip = pkt[IP].src if IP in pkt else "unknown"
            length = len(pkt)
            log_entry = f"[{timestamp}] CAM_MSG from {src_ip} length={length}\n"
            with open(LOG_FILE, "a") as f:
                f.write(log_entry)
            print(log_entry.strip())

def main():
    print("Sniffer CAM avviato. Premere CTRL+C per interrompere.")
    sniff(iface="ens37", prn=log_cam_packet, store=False)

if __name__ == "__main__":
    main()
