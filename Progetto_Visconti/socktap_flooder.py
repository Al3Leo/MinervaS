#!/usr/bin/env python3
import subprocess
import random
import time

SOCKTAP_BIN = "./bin/socktap"  # percorso binario socktap
INTERFACE = "ens37"

# Range possibili per i parametri
LAT_RANGE = (48.700, 48.800)     # Latitudine
LON_RANGE = (11.400, 11.500)     # Longitudine
DURATION_SEC = 10                 # durata di ogni sessione socktap

def random_param():
    lat = round(random.uniform(*LAT_RANGE), 6)
    lon = round(random.uniform(*LON_RANGE), 6)
    return lat, lon

def main():
    while True:
        lat, lon = random_param()
        cmd = [
            SOCKTAP_BIN,
            "--interface", INTERFACE,
            "--positioning", "static",
            "--latitude", str(lat),
            "--longitude", str(lon),
            "--cam-interval", str(500)
        ]
        print(f"[INFO] Avvio socktap: lat={lat}, lon={lon}, interval= 500 ms")
        proc = subprocess.Popen(cmd)

        # lascio girare per N secondi
        time.sleep(DURATION_SEC)

        # interrompo il processo
        proc.terminate()
        proc.wait()
        print("[INFO] Socktap terminato.\n")

        # piccola pausa prima del prossimo
        time.sleep(1)

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n[INFO] Interrotto dall'utente.")
