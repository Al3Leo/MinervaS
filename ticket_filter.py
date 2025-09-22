#!/usr/bin/env python3
from scapy.all import sniff, sendp
import json, time, hashlib, logging
from datetime import datetime

VETH_IN = "enp0s8"
VETH_OUT = "veth1"
CRL_FILE = "crl.json"
LOG_FILE = "crl_drops.log"
CRL_RELOAD_INTERVAL = 10

#configurazione blacklist comportamentale
VIOLATION_THRESHOLD = 3
BLACKLIST_DURATION = 300
VIOLATION_WINDOW = 60

#posizioni dei byte per messaggi da 356 byte (certificato completo)
CERTIFICATE_START_356 = 23
CERTIFICATE_END_356 = 194

#posizioni dei byte per messaggi da 192 byte (hashedID)
HASHED_ID_START_192 = 22
HASHED_ID_END_192 = 30

revoked_certificate_hashes = set()
revoked_hashed_ids = set()
last_load = 0
stored_certificates = {}

#sistema blacklist 
violation_tracker = {}
blacklisted_identifiers = {}
stats = {
    'total_packets': 0,
    'accepted_packets': 0,
    'crl_drops': 0,
    'blacklist_drops': 0,
    'blacklisted_identifiers': 0
}

def setup_logging():
    #logger per console
    console_logger = logging.getLogger('console')
    console_logger.setLevel(logging.INFO)
    console_handler = logging.StreamHandler()
    console_formatter = logging.Formatter('[%(asctime)s] %(message)s', datefmt='%H:%M:%S')
    console_handler.setFormatter(console_formatter)
    console_logger.addHandler(console_handler)
    
    #logger per file drops
    drop_logger = logging.getLogger('drops')
    drop_logger.setLevel(logging.INFO)
    file_handler = logging.FileHandler(LOG_FILE, mode='a', encoding='utf-8')
    file_formatter = logging.Formatter('%(asctime)s - %(message)s', datefmt='%Y-%m-%d %H:%M:%S')
    file_handler.setFormatter(file_formatter)
    drop_logger.addHandler(file_handler)
    
    return console_logger, drop_logger

console_log, drop_log = setup_logging()

def log_drop(packet_type, identifier, reason, packet_size, blacklisted=False):
    message = f"DROP - {packet_type} - {identifier} - {reason} - Size: {packet_size}b"
    drop_log.info(message)
    
    #stampa a video solo se NON è blacklistato
    if not blacklisted:
        console_log.info(f"[DROP] {packet_type}: {identifier} - {reason}")

def log_blacklist_event(identifier, action, details=""):
    message = f"BLACKLIST - {action} - {identifier} - {details}"
    drop_log.warning(message)
    #eventi blacklist vengono ancora stampati a video per monitoraggio
    console_log.warning(f"[BLACKLIST] {action}: {identifier} - {details}")

def log_accept(packet_type, identifier):
    console_log.info(f"[ACCEPT] {packet_type}: {identifier}")

def log_info(message):
    console_log.info(message)

def clean_expired_data():
    current_time = time.time()
    
    #pulisce violazioni non più utili 
    for identifier in list(violation_tracker.keys()):
        violation_tracker[identifier] = [
            ts for ts in violation_tracker[identifier] 
            if current_time - ts <= VIOLATION_WINDOW
        ]
        if not violation_tracker[identifier]:
            del violation_tracker[identifier]
    
    #rimuove identifier dalla blacklist se scaduti
    expired_blacklisted = [
        identifier for identifier, expiry_time in blacklisted_identifiers.items()
        if current_time >= expiry_time
    ]
    
    for identifier in expired_blacklisted:
        del blacklisted_identifiers[identifier]
        stats['blacklisted_identifiers'] -= 1
        log_blacklist_event(identifier, "UNBLACKLISTED", "Blacklist time expired")

def record_violation(identifier, hashed_id8=None):
    current_time = time.time()
    
    if identifier not in violation_tracker:
        violation_tracker[identifier] = []
    
    violation_tracker[identifier].append(current_time)
    recent_violations = len(violation_tracker[identifier])
    
    #se supera la soglia, blacklista l'identificatore
    if recent_violations >= VIOLATION_THRESHOLD and identifier not in blacklisted_identifiers:
        expiry_time = current_time + BLACKLIST_DURATION
        blacklisted_identifiers[identifier] = expiry_time
        stats['blacklisted_identifiers'] += 1
        
        #se è un certificato (356 byte), blacklista anche il relativo hashedID
        if hashed_id8 and hashed_id8 not in blacklisted_identifiers:
            blacklisted_identifiers[hashed_id8] = expiry_time
            stats['blacklisted_identifiers'] += 1
            log_blacklist_event(hashed_id8, "BLACKLISTED", f"Related HashedID to certificate - Until {datetime.fromtimestamp(expiry_time).strftime('%H:%M:%S')}")
        
        expiry_str = datetime.fromtimestamp(expiry_time).strftime('%H:%M:%S')
        log_blacklist_event(identifier, "BLACKLISTED", 
                          f"{recent_violations} violations in {VIOLATION_WINDOW}s - Until {expiry_str}")

def is_blacklisted(identifier):
    return identifier in blacklisted_identifiers

def print_stats():
    log_info(f"[STATS] Total: {stats['total_packets']}, "
            f"Accepted: {stats['accepted_packets']}, "
            f"CRL Drops: {stats['crl_drops']}, "
            f"Blacklist Drops: {stats['blacklist_drops']}, "
            f"Blacklisted: {stats['blacklisted_identifiers']}")

def load_crl():
    global revoked_certificate_hashes, revoked_hashed_ids, last_load
    try:
        with open(CRL_FILE, "r") as f:
            crl = json.load(f)
        
        revoked_certificate_hashes = set()
        revoked_hashed_ids = set()
        
        for entry in crl.get("revoked", []):
            if "certificate_hash" in entry and entry["certificate_hash"]:
                revoked_certificate_hashes.add(entry["certificate_hash"])
            if "hashed_id" in entry and entry["hashed_id"]:
                revoked_hashed_ids.add(entry["hashed_id"])
        
        last_load = time.time()
        log_info(f"[CRL] Loaded {len(revoked_certificate_hashes)} revoked certificate hashes")
        log_info(f"[CRL] Loaded {len(revoked_hashed_ids)} revoked hashed IDs")
        
    except Exception as e:
        log_info(f"[CRL] Warning: cannot load CRL file ({e})")
        revoked_certificate_hashes = set()
        revoked_hashed_ids = set()

def extract_certificate_356(pkt):
    try:
        packet_bytes = bytes(pkt)
        
        if len(packet_bytes) < CERTIFICATE_END_356:
            return None, None
        
        certificate_bytes = packet_bytes[CERTIFICATE_START_356:CERTIFICATE_END_356]
        cert_hash = hashlib.sha256(certificate_bytes).digest()
        cert_hash_hex = cert_hash.hex()
        hashed_id8 = cert_hash[-8:].hex()
        
        return cert_hash_hex, hashed_id8
        
    except Exception as e:
        console_log.error(f"[ERROR] Errore nell'estrazione del certificato: {e}")
        return None, None

def extract_hashed_id_192(pkt):
    try:
        packet_bytes = bytes(pkt)
        
        if len(packet_bytes) < HASHED_ID_END_192:
            return None
        
        hashed_id_bytes = packet_bytes[HASHED_ID_START_192:HASHED_ID_END_192]
        hashed_id_hex = hashed_id_bytes.hex()
        
        return hashed_id_hex
        
    except Exception as e:
        console_log.error(f"[ERROR] Errore nell'estrazione del HashedID: {e}")
        return None

def packet_filter(pkt):
    global revoked_certificate_hashes, revoked_hashed_ids, last_load, stored_certificates, stats
    
    #reload periodico della CRL
    if time.time() - last_load > CRL_RELOAD_INTERVAL:
        load_crl()
    
    clean_expired_data()
    stats['total_packets'] += 1
    packet_size = len(pkt)
    
    #stampa statistiche ogni 100 pacchetti
    if stats['total_packets'] % 100 == 0:
        print_stats()
    
    if packet_size == 356:
        cert_hash, hashed_id8 = extract_certificate_356(pkt)
        if cert_hash is None:
            log_info(f"[WARN] Impossibile estrarre certificato, pacchetto scartato")
            return
        
        identifier = cert_hash
        short_id = cert_hash[:16] + "..."
        
        #memorizza associazioni ticket-hashedID8 per semplificare le operazioni di confronto future
        if hashed_id8:
            stored_certificates[hashed_id8] = {
                "certificate_hash": cert_hash,
                "timestamp": time.time()
            }
        
        #quando arriva un pacchetto da 356B, prima vedi se è nella blacklist
        if is_blacklisted(identifier):
            log_drop("Certificate SHA", short_id, "BLACKLISTED - Repeated violations", packet_size, blacklisted=True)
            stats['blacklist_drops'] += 1
            return
        
        #se non c'è, controlla la CRL
        if identifier in revoked_certificate_hashes:
            record_violation(identifier, hashed_id8)
            log_drop("Certificate SHA", short_id, "Certificate revoked in CRL", packet_size)
            stats['crl_drops'] += 1
            return
        else:
            log_accept("Certificate SHA", short_id)
            stats['accepted_packets'] += 1
    
    elif packet_size == 192:
        hashed_id = extract_hashed_id_192(pkt)
        if hashed_id is None:
            log_info(f"[WARN] Impossibile estrarre HashedID, pacchetto scartato")
            return
        
        identifier = hashed_id
        
        #quando arriva un pacchetto da 192B, prima vedi se è nella blacklist
        if is_blacklisted(identifier):
            log_drop("HashedID", identifier, "BLACKLISTED - Repeated violations", packet_size, blacklisted=True)
            stats['blacklist_drops'] += 1
            return
        
        #se non c'è, controlla la CRL
        if identifier in revoked_hashed_ids:
            record_violation(identifier)
            log_drop("HashedID", identifier, "HashedID revoked in CRL", packet_size)
            stats['crl_drops'] += 1
            return
        else:
            log_accept("HashedID", identifier)
            stats['accepted_packets'] += 1
    
    else:
        log_info(f"[WARN] Dimensione pacchetto non supportata: {packet_size} byte")
        return
    
    #se il pkt non è in blacklist e CRL, invialo sull'interfaccia virtuale dove socktap è in ascolto
    try:
        sendp(pkt, iface=VETH_OUT, verbose=False)
    except Exception as e:
        console_log.error(f"[ERROR] Errore nell'invio del pacchetto: {e}")

if __name__ == "__main__":
    print(f"[Filtro CRL Enhanced] Ascolto su {VETH_IN}, inoltro su {VETH_OUT}")
    print(f"[Filtro CRL Enhanced] Supporto messaggi da 356 byte (certificato SHA) e 192 byte (hashedID)")
    print(f"[Filtro CRL Enhanced] Certificato: byte {CERTIFICATE_START_356}-{CERTIFICATE_END_356-1}")
    print(f"[Filtro CRL Enhanced] HashedID: byte {HASHED_ID_START_192}-{HASHED_ID_END_192-1}")
    print(f"[Filtro CRL Enhanced] Log drops salvato in: {LOG_FILE}")
    print(f"[Filtro CRL Enhanced] Blacklist: {VIOLATION_THRESHOLD} violazioni in {VIOLATION_WINDOW}s = ban per {BLACKLIST_DURATION}s")
    print(f"[Filtro CRL Enhanced] Certificati blacklistati (356b) bloccano anche i relativi HashedID (192b)")
    print(f"[Filtro CRL Enhanced] NOTA: Pacchetti blacklistati vengono loggati solo su file, non a video")
    
    load_crl()
    
    #log di avvio nel file dei drop
    drop_log.info("=" * 60)
    drop_log.info("CRL FILTER WITH BLACKLIST STARTED")
    drop_log.info(f"Interface IN: {VETH_IN}, Interface OUT: {VETH_OUT}")
    drop_log.info(f"CRL File: {CRL_FILE}")
    drop_log.info(f"Blacklist Config: {VIOLATION_THRESHOLD} violations in {VIOLATION_WINDOW}s = {BLACKLIST_DURATION}s ban")
    drop_log.info("=" * 60)
    
    log_info("[Filtro CRL Enhanced] Inizio filtraggio con sistema blacklist...")
    try:
        sniff(iface=VETH_IN, prn=packet_filter, store=False)
    except KeyboardInterrupt:
        log_info("\n[Filtro CRL Enhanced] Filtraggio interrotto dall'utente")
        print_stats()
        drop_log.info(f"CRL FILTER STOPPED - Final Stats: {stats}")
    except Exception as e:
        console_log.error(f"[ERROR] Errore durante il filtraggio: {e}")
        drop_log.error(f"CRL FILTER ERROR: {e}")
