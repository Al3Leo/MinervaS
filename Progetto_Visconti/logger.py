#!/usr/bin/env python3
from scapy.all import sniff, Raw, IP
from datetime import datetime
from collections import deque
import time
import os

# --- Config ---
IFACE = "ens37"
RAW_LOG_FILE = "/var/log/v2x_cam_raw.log"   # log CAM singoli
DOS_LOG_FILE = "/var/log/v2x_cam_dos.log"   # log eventi DoS
CAM_SIGNATURE = b"\x3f\xe1\xed\x04\x03\xff\xe3\xff\xf4\x00\x40\x01\x24\x00\x02\x6c"

# Soglie DoS globali
WINDOW_SEC = 5
THRESHOLD_GLOBAL = 80
COOLDOWN_SEC = 20

# -------------

for path in (RAW_LOG_FILE, DOS_LOG_FILE):
    os.makedirs(os.path.dirname(path), exist_ok=True)

global_window = deque()
last_alert_global = 0.0


def now_ts() -> float:
    return time.time()


def ts_str(ts=None) -> str:
    if ts is None:
        ts = time.time()
    return datetime.fromtimestamp(ts).strftime("%Y-%m-%d %H:%M:%S")


def prune(dq: deque, cutoff: float):
    while dq and dq[0] < cutoff:
        dq.popleft()


def write_log(path: str, line: str):
    with open(path, "a") as f:
        f.write(line)
    print(line.strip())


def handle_cam(src_ip: str, length: int):
    global last_alert_global
    t = now_ts()
    cutoff = t - WINDOW_SEC

    # log raw CAM
    write_log(RAW_LOG_FILE, f"[{ts_str(t)}] CAM_MSG from {src_ip} length={length}\n")

    # aggiorna finestra globale
    global_window.append(t)
    prune(global_window, cutoff)

    # detection globale
    if len(global_window) >= THRESHOLD_GLOBAL:
        if (t - last_alert_global) >= COOLDOWN_SEC:
            last_alert_global = t
            write_log(
                DOS_LOG_FILE,
                f"[{ts_str(t)}] DOS_CAM_DETECTED count={len(global_window)} "
                f"window={WINDOW_SEC}s mode=global\n"
            )


def log_cam_packet(pkt):
    try:
        if Raw in pkt:
            payload = bytes(pkt[Raw])
            if CAM_SIGNATURE in payload:
                src_ip = pkt[IP].src if IP in pkt else "unknown"
                length = len(pkt)
                handle_cam(src_ip, length)
    except Exception as e:
        write_log(DOS_LOG_FILE, f"[{ts_str()}] LOGGER_ERROR {e}\n")


def main():
    print(f"Sniffer CAM avviato su {IFACE}. CTRL+C per interrompere.")
    sniff(iface=IFACE, prn=log_cam_packet, store=False)


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\nInterrotto dall'utente.")
