#!/usr/bin/env python3
"""
Receiver UDP con simulatore di rete dinamico
--------------------------------------------
- Riceve pacchetti CAM da un sender e simula un canale con congestione dinamica.
- Calcola automaticamente gli intervalli tra pacchetti per rilevare congestione.
- Decide se scartare pacchetti (loss) o aggiungere ritardo (delay) in base alla velocità.
- Accoda e invia ACK con ritardi simulati.
- Registra ogni evento in un file CSV dettagliato.
"""

import socket
import time
import random
import threading
import queue
import csv
import os

# === CONFIGURAZIONE DI RETE E CANALE ===
RECEIVER_IP = "100.74.67.233"   # IP su cui ascolta il receiver
RECEIVER_PORT = 5005            # Porta su cui riceve i CAM
SENDER_IP = "100.82.203.80"     # IP del sender per inviare ACK
ACK_PORT = 5001                 # Porta del sender per ACK

BASE_INTERVAL = 0.750           # Intervallo base per stimare congestione (s)
CONGESTION_THRESHOLD = 0.8      # Percentuale soglia congestione (80%)
LOSS_PROB_FAST = 0.15           # Probabilità di perdita se congesto
BASE_DELAY = 0.005              # Ritardo base per ogni pacchetto (s)
EXTRA_DELAY = 0.050             # Ritardo extra in congestione (s)
JITTER_MAX = 0.010              # Jitter massimo casuale (s)

RECEIVER_LOG = "receiver_detailed.csv"  # File di log dettagliato

# === CLASSE PRINCIPALE DEL SIMULATORE ===
class NetworkSimulator:
    """
    Simula un canale di rete con congestione dinamica e ritardi adattivi.
    Tiene traccia delle statistiche, gestisce la coda ACK e registra i log.
    """
    def __init__(self):
        self.last_recv_time = 0.0
        self.ack_queue = queue.Queue()
        self.stats = {'received': 0, 'dropped': 0, 'congested': 0, 'acks_sent': 0, 'ack_errors': 0}
        self.running = True

        # Crea il file CSV se non esiste
        if not os.path.exists(RECEIVER_LOG):
            with open(RECEIVER_LOG, "w", newline="") as f:
                csv.writer(f).writerow([
                    "timestamp", "seq", "interval_detected_ms", "delta_ms",
                    "action", "delay_applied_ms", "congestion_factor", "notes"
                ])

    def detect_current_interval(self, delta):
        """
        Stima l'intervallo corrente in ms basandosi su delta (s).
        Restituisce una categoria indicativa (10, 50, 100 ms, ecc.)
        """
        if delta < 0.015: return 10
        elif delta < 0.075: return 50
        elif delta < 0.150: return 100
        elif delta < 0.250: return 200
        elif delta < 0.350: return 300
        elif delta < 0.450: return 400
        elif delta < 0.550: return 500
        elif delta < 0.750: return 600
        elif delta < 0.950: return 800
        elif delta < 1.250: return 1000
        elif delta < 1.750: return 1500
        else: return 2000

    def should_drop_packet(self, current_time):
        """
        Decide se scartare il pacchetto in base alla congestione:
        - Calcola delta = tempo tra pacchetti.
        - Se delta < soglia → aumenta probabilità di scarto.
        """
        delta = current_time - self.last_recv_time
        congestion_threshold = BASE_INTERVAL * CONGESTION_THRESHOLD

        if delta < congestion_threshold and self.last_recv_time > 0:
            self.stats['congested'] += 1
            speed_factor = congestion_threshold / max(delta, 0.001)
            adjusted_loss_prob = min(LOSS_PROB_FAST * speed_factor, 0.9)
            if random.random() < adjusted_loss_prob:
                self.stats['dropped'] += 1
                return True, delta, speed_factor

        return False, delta, 1.0

    def calculate_delay(self, delta):
        """
        Calcola ritardo adattivo in base alla congestione:
        - Ritardo extra se i pacchetti arrivano troppo veloci.
        - Aggiunge jitter casuale.
        """
        base_delay = BASE_DELAY
        congestion_factor = 1.0
        congestion_threshold = BASE_INTERVAL * CONGESTION_THRESHOLD

        if delta < congestion_threshold and self.last_recv_time > 0:
            congestion_factor = congestion_threshold / max(delta, 0.001)
            base_delay += EXTRA_DELAY * min(congestion_factor * 0.5, 2.0)

        jitter = random.uniform(-JITTER_MAX * 0.5, JITTER_MAX * 0.5)
        total_delay = max(0.001, base_delay + jitter)
        return total_delay, congestion_factor

    def queue_ack(self, seq_num, delay):
        """Accoda un ACK per l'invio ritardato."""
        if self.running:
            send_time = time.time() + delay
            self.ack_queue.put((seq_num, send_time, delay))

    def log_packet_event(self, seq_num, delta, action, delay=0, congestion_factor=1.0, notes=""):
        """Scrive evento nel log dettagliato CSV."""
        try:
            with open(RECEIVER_LOG, "a", newline="") as f:
                csv.writer(f).writerow([
                    time.time(),
                    seq_num,
                    self.detect_current_interval(delta),
                    delta * 1000,
                    action,
                    delay * 1000,
                    f"{congestion_factor:.2f}",
                    notes
                ])
        except Exception as e:
            print(f"Errore logging: {e}")

    def stop(self):
        """Ferma il simulatore."""
        self.running = False

# === THREAD DEDICATO AGLI ACK ===
def ack_sender_thread(ack_sock, sender_ip, ack_port, simulator):
    """
    Thread che gestisce la coda ACK:
    - Preleva ACK dalla coda e li invia quando scade il ritardo.
    """
    pending_acks = []
    while simulator.running:
        try:
            # Preleva ACK pronti
            while not simulator.ack_queue.empty():
                pending_acks.append(simulator.ack_queue.get_nowait())

            current_time = time.time()
            ready_acks = [(seq, sched, delay) for seq, sched, delay in pending_acks if sched <= current_time]

            for seq_num, scheduled_time, original_delay in ready_acks:
                try:
                    ack_sock.sendto(str(seq_num).encode(), (sender_ip, ack_port))
                    simulator.stats['acks_sent'] += 1
                    print(f"[{current_time:.3f}] ✓ ACK seq={seq_num} inviato (ritardo={original_delay*1000:.1f}ms)")
                except Exception as e:
                    print(f"✗ Errore invio ACK seq={seq_num}: {e}")
                    simulator.stats['ack_errors'] += 1
                pending_acks.remove((seq_num, scheduled_time, original_delay))

            time.sleep(0.001)
        except Exception as e:
            print(f"Errore thread ACK: {e}")
            time.sleep(0.01)

# === FUNZIONE PRINCIPALE RECEIVER ===
def main():
    simulator = NetworkSimulator()

    # Socket per ricevere CAM
    recv_sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    recv_sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    recv_sock.bind((RECEIVER_IP, RECEIVER_PORT))

    # Socket per inviare ACK
    ack_sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)

    print(f"{'='*70}\nRECEIVER DEFINITIVO - Simulatore dinamico\n{'='*70}")
    print(f"Ascolto su {RECEIVER_IP}:{RECEIVER_PORT}, log: {RECEIVER_LOG}\n")

    # Avvio thread ACK
    threading.Thread(target=ack_sender_thread, args=(ack_sock, SENDER_IP, ACK_PORT, simulator), daemon=True).start()

    last_stats_time = time.time()
    stats_interval = 10.0

    try:
        while True:
            if time.time() - last_stats_time >= stats_interval:
                print_periodic_stats(simulator.stats)
                last_stats_time = time.time()

            data, addr = recv_sock.recvfrom(1024)
            now = time.time()
            msg = data.decode(errors="ignore").strip()

            simulator.stats['received'] += 1
            print(f"[{now:.3f}] ← Ricevuto: {msg}")

            should_drop, delta, factor = simulator.should_drop_packet(now)
            simulator.last_recv_time = now

            if should_drop:
                print(f"✗ SCARTATO (Δ={delta*1000:.1f}ms, fattore={factor:.1f})")
                if msg.startswith("CAM"):
                    try:
                        seq_num = int(msg.split()[1])
                        simulator.log_packet_event(seq_num, delta, "DROPPED", 0, factor, "Congestione")
                    except: pass
                continue

            if msg.startswith("CAM"):
                parts = msg.split()
                if len(parts) >= 2:
                    seq = int(parts[1])
                    delay, factor = simulator.calculate_delay(delta)
                    simulator.queue_ack(seq, delay)

                    detected = simulator.detect_current_interval(delta)
                    status = "🐌 CONGESTO" if delta < BASE_INTERVAL * CONGESTION_THRESHOLD else "✓ OK"
                    print(f"[{now:.3f}] {status} CAM seq={seq}, Δ={delta*1000:.1f}ms (~{detected}ms), ritardo={delay*1000:.1f}ms")

                    action = "QUEUED_CONGESTED" if delta < BASE_INTERVAL * CONGESTION_THRESHOLD else "QUEUED_NORMAL"
                    simulator.log_packet_event(seq, delta, action, delay, factor, f"Interval ~{detected}ms")
                else:
                    print(f"Formato CAM non valido: {msg}")

    except KeyboardInterrupt:
        print("\nReceiver interrotto.")
    finally:
        simulator.stop()
        time.sleep(0.2)
        print_final_stats(simulator.stats)
        recv_sock.close()
        ack_sock.close()

# === FUNZIONI STATISTICHE ===
def print_periodic_stats(stats):
    print("\n--- Statistiche Intermedie ---")
    print(f"Ricevuti: {stats['received']} | Scartati: {stats['dropped']} | ACK inviati: {stats['acks_sent']}")
    if stats['received'] > 0:
        loss_rate = stats['dropped'] / (stats['received'] + stats['dropped']) * 100
        print(f"Tasso perdita: {loss_rate:.1f}%")
    print("-" * 30)

def print_final_stats(stats):
    total = stats['received'] + stats['dropped']
    print(f"\n{'='*70}\nSTATISTICHE FINALI\n{'='*70}")
    print(f"Pacchetti processati: {total}")
    print(f"Ricevuti: {stats['received']} | Scartati: {stats['dropped']}")
    print(f"Congestione rilevata: {stats['congested']}")
    print(f"ACK inviati: {stats['acks_sent']} | Errori ACK: {stats['ack_errors']}")
    if total > 0:
        print(f"Tasso perdita simulato: {stats['dropped']/total*100:.1f}%")
    if stats['received'] > 0:
        print(f"Tasso successo ACK: {stats['acks_sent']/stats['received']*100:.1f}%")
    print(f"Log dettagliato in: {RECEIVER_LOG}\n{'='*70}")

if __name__ == "__main__":
    main()
