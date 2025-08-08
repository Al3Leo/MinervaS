#!/usr/bin/env python3

import subprocess
import time
import sys

def send_cam_messages():
    """Invia messaggi CAM per un periodo di tempo fisso."""
    command = [
        # Assicurati che il percorso a socktap sia corretto.
        # Usa il percorso assoluto per evitare errori.
        "../vanetza/build/bin/socktap",
        "--interface=lo",
        "--applications=ca",
        "--cam-interval=1000", # Invia un pacchetto ogni secondo
        "--mac-address=00:11:22:33:44:55",
    ]
    
    print("Avvio dell'invio di messaggi CAM. I messaggi verranno inviati per 10 secondi.")
    print("Premi Ctrl+C in qualsiasi momento per terminare l'invio.")
    
    try:
        # Avvia il processo in background
        process = subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
        
        # Aspetta 10 secondi mentre i messaggi vengono inviati
        time.sleep(10)
        
        print("\nInvio di messaggi completato.")
    except FileNotFoundError:
        print("Errore: Eseguibile socktap non trovato. Assicurati che il percorso sia corretto.")
    except KeyboardInterrupt:
        print("\nTerminazione dell'invio manuale...")
    except Exception as e:
        print(f"Si è verificato un errore: {e}")
    finally:
        # Assicura che il processo venga terminato
        if 'process' in locals() and process.poll() is None:
            process.kill()

if __name__ == "__main__":
    send_cam_messages()
