#!/usr/bin/env python3

import subprocess
import time
import sys

# Lista dei tipi di messaggio supportati
supported_apps = ["ca", "denm", "cpm"]

def send_message(app_type):
    """Invia un singolo tipo di messaggio CAM."""
    command = [
        "home/ubuntu/vanetza/build/bin/socktap",
        "--interface=lo",
        f"--applications={app_type}",
        f"--{app_type}-interval=1000", # Invia un pacchetto ogni secondo
        "--mac-address=00:11:22:33:44:55",
    ]
    
    print(f"Invio di messaggi {app_type.upper()} avviato. Premi Ctrl+C per tornare al menu.")
    
    try:
        process = subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
        # Il processo rimane attivo per 5 secondi, inviando 5 messaggi
        time.sleep(5)
    except KeyboardInterrupt:
        print("\nTerminazione dell'invio...")
    finally:
        if 'process' in locals() and process.poll() is None:
            process.kill()

def main():
    while True:
        print("\n--- Test mittente Vanetza ---")
        print("Quale tipo di messaggio vuoi inviare?")
        print("Tipi disponibili: ca, denm, cpm")
        print("Premi 0 per uscire.")
        
        user_input = input("Inserisci un tipo di messaggio (es. ca): ").lower().strip()
        
        if user_input == "0":
            print("Uscita dal programma.")
            break
        elif user_input in supported_apps:
            send_message(user_input)
        else:
            print(f"Errore: tipo di messaggio '{user_input}' non supportato. Riprova.")

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\nProgramma terminato.")
