#!/usr/bin/env python3
"""
Adaptive Sender con KNN
---------------------------
Questo script invia pacchetti UDP (CAM) a un receiver e regola
dinamicamente l'intervallo di invio usando un classificatore KNN
(addestrato su metriche di rete: RTT medio e PDR).

Funzioni principali:
- Invio batch di pacchetti con sequenza crescente
- Ricezione ACK corrispondenti e calcolo RTT/PDR
- Media robusta RTT (con filtro outlier IQR)
- Adattamento intervallo basato su classe predetta dal KNN
- Logging su CSV delle statistiche di ogni batch

Autore: <tuo nome>
Data: settembre 2025
"""

import socket
import time
import select
import joblib
import numpy as np
import pandas as pd
import csv
import os

# ------------------ CONFIG ------------------
RECEIVER_IP = "100.74.67.233"   # indirizzo receiver
RECEIVER_PORT = 5005            # porta di ricezione CAM
ACK_PORT = 5001                 # porta locale per ricevere ACK

PACKETS_PER_BATCH = 10          # pacchetti inviati per batch
START_INTERVAL = 0.2            # secondi (200 ms)
ACK_TIMEOUT = 1.0               # ignora RTT > 1.0 s come outlier
FINAL_WAIT = 0.8                # attesa finale ACK tardivi
INTERVAL_STEP = 0.03            # variazione 30 ms
MIN_INTERVAL = 0.01             # limite minimo 10 ms
MAX_INTERVAL = 2.0              # limite massimo 2 s

CSV_FILE = "batch_metrics.csv"  # file per logging batch
# --------------------------------------------

# Carica modello e scaler
knn = joblib.load("knn_model.pkl")
scaler = joblib.load("scaler.pkl")

def process_acks(sock, sent_times, batch_seqs, received_rtts, processed_seqs, wait=0.05):
    """
    Legge gli ACK dal socket (non bloccante con select).
    Calcola RTT (ms) se ACK appartiene al batch corrente.
    Aggiorna received_rtts e processed_seqs.
    """
    processed = 0
    try:
        ready, _, _ = select.select([sock], [], [], wait)
        if not ready:
            return processed
        while True:
            data, _ = sock.recvfrom(1024)
            try:
                seq = int(data.decode().strip())
            except:
                continue
            now = time.time()
            if seq in batch_seqs and seq not in processed_seqs and seq in sent_times:
                # Calcolo RTT in ms
                rtt = (now - sent_times[seq]) * 1000.0
                if rtt <= ACK_TIMEOUT * 1000.0:
                    received_rtts.append(rtt)
                processed_seqs.add(seq)
                del sent_times[seq]
                processed += 1
                print(f"[{now:.3f}] ✓ ACK seq={seq} RTT={rtt:.1f} ms")
            # continua a leggere finché ci sono pacchetti pronti
            ready, _, _ = select.select([sock], [], [], 0)
            if not ready:
                break
    except Exception as e:
        print(f"Errore in process_acks: {e}")
    return processed

def robust_avg(values):
    """Calcola la media robusta RTT filtrando outlier con IQR."""
    if not values:
        return 1000.0
    if len(values) == 1:
        return values[0]
    q1, q3 = np.percentile(values, [25, 75])
    iqr = q3 - q1
    if iqr == 0:
        return float(np.mean(values))
    lower, upper = q1 - 1.5*iqr, q3 + 1.5*iqr
    filtered = [v for v in values if lower <= v <= upper]
    return float(np.mean(filtered)) if filtered else float(np.mean(values))

def flush_old_acks(sock):
    """Svuota eventuali ACK residui nel buffer prima di un nuovo batch."""
    flushed = 0
    try:
        while True:
            ready, _, _ = select.select([sock], [], [], 0)
            if not ready:
                break
            sock.recvfrom(1024)
            flushed += 1
    except:
        pass
    if flushed:
        print(f"Svuotati {flushed} ACK vecchi dal buffer")

def init_csv(file):
    """Crea file CSV con header se non esiste già."""
    if not os.path.exists(file):
        with open(file, "w", newline="") as f:
            writer = csv.writer(f)
            writer.writerow(["batch_id", "interval_ms", "avg_rtt_ms", "pdr_percent", "class", "action"])

def log_csv(file, batch_id, interval_ms, avg_rtt, pdr, level, action):
    """Scrive una riga nel CSV con i risultati del batch."""
    with open(file, "a", newline="") as f:
        writer = csv.writer(f)
        writer.writerow([batch_id, interval_ms, avg_rtt, pdr, level, action])

def main():
    send_sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    ack_sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    ack_sock.bind(("0.0.0.0", ACK_PORT))
    ack_sock.setblocking(False)

    interval = START_INTERVAL
    seq = 0
    batch_id = 0

    init_csv(CSV_FILE)

    print(f"== Avvio sender KNN (interval iniziale {interval*1000:.1f} ms) ==")

    try:
        while True:
            batch_id += 1
            print(f"\n--- Batch #{batch_id} (interval {interval*1000:.1f} ms) ---")

            flush_old_acks(ack_sock)

            sent_times = {}
            batch_seqs = []
            received_rtts = []
            processed_seqs = set()

            # Invio pacchetti del batch
            for i in range(PACKETS_PER_BATCH):
                seq += 1
                send_t = time.time()
                sent_times[seq] = send_t
                send_sock.sendto(f"CAM {seq}".encode(), (RECEIVER_IP, RECEIVER_PORT))
                batch_seqs.append(seq)
                print(f"[{send_t:.3f}] → Inviato seq={seq}")
                process_acks(ack_sock, sent_times, batch_seqs, received_rtts, processed_seqs, wait=0.02)
                if i < PACKETS_PER_BATCH - 1:
                    time.sleep(interval)

            # Attesa finale per ACK tardivi
            final_deadline = time.time() + FINAL_WAIT
            while time.time() < final_deadline:
                process_acks(ack_sock, sent_times, batch_seqs, received_rtts, processed_seqs, wait=0.05)
                if len(processed_seqs) >= len(batch_seqs):
                    print("Tutti gli ACK del batch sono arrivati.")
                    break

            # Calcolo statistiche
            sent_count = len(batch_seqs)
            received_count = len(received_rtts)
            pdr = (received_count / sent_count) * 100.0 if sent_count else 0.0
            avg_rtt = robust_avg(received_rtts)

            print(f"\n>>> Batch #{batch_id} completato <<<")
            print(f"Sent={sent_count}, Received={received_count}, PDR={pdr:.2f}%, RTT_medio={avg_rtt:.1f} ms")

            # Predizione con KNN
            features_df = pd.DataFrame([[avg_rtt, pdr]], columns=['rtt_medio','pdr_percent'])
            scaled = scaler.transform(features_df)
            level = knn.predict(scaled)[0]

            # Adattamento intervallo
            old_interval = interval
            if level == 0:
                interval = interval + INTERVAL_STEP
                action = "aumentato"
            elif level == 2:
                interval = interval - INTERVAL_STEP
                action = "diminuito"
            else:
                action = "stabile"

            interval = max(MIN_INTERVAL, min(interval, MAX_INTERVAL))

            print(f"Classe predetta: {level} → Azione: {action}")
            print(f"Intervallo nuovo: {old_interval:.3f}s -> {interval:.3f}s")

            # Log su CSV
            log_csv(CSV_FILE, batch_id, old_interval*1000, avg_rtt, pdr, level, action)

            # Pausa tra batch
            time.sleep(2.0)

    except KeyboardInterrupt:
        print("\nInterrotto dall'utente.")
    finally:
        send_sock.close()
        ack_sock.close()
        print("Socket chiusi, uscita.")

if __name__ == "__main__":
    main()
