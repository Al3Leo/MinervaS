# Rilevamento e Mitigazione CAM Flooding tramite HIDS

## 📋 Obiettivo
Rilevare un attacco **CAM flooding** nel contesto V2X su una macchina *car2* e attivare automaticamente una mitigazione tramite **OSSEC**.

---

## 🖥 Architettura
- **car1 (Ubuntu 22.04)** – *Macchina Attaccante*  
  - Esegue lo script [`socktap_flooder.py`](https://github.com/Al3Leo/MinervaS/blob/main/Progetto_Visconti/socktap_flooder.py) per inviare pacchetti CAM con parametri variabili.
  - Simula un attacco DoS tramite **CAM flooding** verso *car2*.

- **car2 (Ubuntu 22.04)** – *Macchina Vittima*  
  - Riceve traffico CAM (anche malevolo) su interfaccia di rete.
  - [`logger.py`](https://github.com/Al3Leo/MinervaS/blob/main/Progetto_Visconti/logger.py) cattura pacchetti CAM (usando firma binaria custom) e scrive in `/var/log/v2x_cam.log`.
  - OSSEC Agent legge il file di log e lo invia al server OSSEC.

- **OSSEC Server (Ubuntu 20.04)** – *Sistema di Monitoraggio e Mitigazione*  
  - Riceve log dall’agente su *car2*.
  - Applica regola personalizzata per rilevare CAM flooding.
  - Esegue **active response** per bloccare l’IP sorgente (*car1*).

---

## 🚦 Fasi del Progetto
5 fasi: 
1. **Generazione del traffico CAM (car1)**  
   - Utilizzo di **socktap** di Vanetza per trasmettere pacchetti CAM.  
   - Wrapper Python per randomizzare parametri come posizione, intervallo e altre opzioni, simulando comportamento anomalo tipico di un attacco DoS.

2. **Cattura e logging dei pacchetti CAM (car2)**  
   - Sniffing di rete sull’interfaccia dedicata ai messaggi V2X.  
   - Filtraggio in base a una firma binaria identificativa dei pacchetti CAM.  
   - Registrazione di ogni evento rilevato in un file di log locale con timestamp e metadati.

3. **Trasmissione dei log al server di analisi**  
   - Agente di monitoraggio su *car2* che legge i log in tempo reale.  
   - Invio al **server OSSEC** attraverso un canale sicuro (**log ingestion**).

4. **Analisi e rilevamento dell’anomalia (OSSEC Server)**  
   - Decodifica e applicazione di regole personalizzate.  
   - Rilevamento di pattern di flooding tramite soglie di frequenza.

5. **Mitigazione dell’attacco**  
   - Attivazione di una **active response** (es. blocco IP via firewall).  
   - Riduzione o interruzione del traffico malevolo.

---

## 📊 Timeline Visuale del Flusso

```mermaid
sequenceDiagram
    participant Car1 as car1 (Attaccante)
    participant Car2 as car2 (Target / Logger)
    participant Server as OSSEC Server

    Car1->>Car2: Pacchetti CAM flooding (socktap con parametri randomizzati)
    Car2->>Car2: Sniffing rete e filtraggio pacchetti CAM
    Car2->>Car2: Logging pacchetti rilevati
    Car2->>Server: Invio log (log ingestion)
    Server->>Server: Analisi e rilevamento anomalia
    Server->>Car2: Active response (blocco IP o altre mitigazioni)
