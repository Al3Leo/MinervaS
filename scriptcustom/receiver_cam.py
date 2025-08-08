#!/usr/bin/env python3

import subprocess
import sys

def main():
    socktap_command = [
        "../vanetza/build/bin/socktap",
        "--interface=lo",
        "--applications=ca",
        "--mac-address=00:11:22:33:44:56",
        "--print-rx-cam"
    ]
    
    print("Avvio del modulo ricevente. Premi Ctrl+C per uscire.\n")

    try:
        process = subprocess.Popen(socktap_command, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, bufsize=1)
        
        for line in process.stdout:
            # Se la riga contiene "received packet from", è l'inizio di un nuovo pacchetto
            if "received packet from" in line:
                print("=" * 60)  # Stampa una linea di separazione più evidente
            
            print(line.strip())

    except FileNotFoundError:
        print("Errore: Eseguibile socktap non trovato. Assicurati che il tuo script sia nella stessa cartella di socktap.")
    except KeyboardInterrupt:
        print("\nUscita. Processo socktap terminato.")
    except Exception as e:
        print(f"Si è verificato un errore: {e}")
    finally:
        if 'process' in locals() and process.poll() is None:
            process.kill()

if __name__ == "__main__":
    main()
