#!/usr/bin/env bash
ALERTS_LOG="/var/ossec/logs/alerts/alerts.log"

TO="address@domain.tld"                 # <-- cambia con l'indirizzo di destinazione a cui far arrivare le mail delle allerte
FROM="OSSEC ALERTING <address@domain.tld>" 
SUBJECT="OSSEC ALERT - CAM Flooding Detected"
MSMTP="/usr/bin/msmtp"                        

REQUIRE_TEXT=0
RULE_PATTERN='Rule: 100210'
TEXT_PATTERN='CAM flooding detected by edge logger'

DBG="/var/log/ossec_dos_mailer.log"
mkdir -p "$(dirname "$DBG")"

buf=""
alert_id=""

flush_buf() {
  if [[ -n "$buf" ]]; then
    if echo "$buf" | grep -q "$RULE_PATTERN"; then
      if [[ "$REQUIRE_TEXT" -eq 0 ]] || echo "$buf" | grep -q "$TEXT_PATTERN"; then #viene effettuato matching con la nuova riga e viene greppato con l'id della regola e il pattern testuale, in caso ok allora invia mail con i dettagli
        {
          printf 'From: %s\n' "$FROM"
          printf 'To: %s\n' "$TO"
          printf 'Subject: %s%s\n' "$SUBJECT" "${alert_id:+ [$alert_id]}"
          printf '\n'
          printf '%s\n' "$buf"
        } | "$MSMTP" -a default "$TO"
        echo "$(date '+%F %T') SENT id=${alert_id:-N/A}" >> "$DBG"
      else
        echo "$(date '+%F %T') SKIP id=${alert_id:-N/A} (text pattern not found)" >> "$DBG"
      fi
    else
      echo "$(date '+%F %T') SKIP id=${alert_id:-N/A} (rule 100210 not found)" >> "$DBG"
    fi
  fi
  buf=""
  alert_id=""
}


# logrotate check, parte dalle nuove righe
tail -n0 -F "$ALERTS_LOG" | while IFS= read -r line; do
  # Inizio di un nuovo alert
  if [[ "$line" =~ ^\*\*\ Alert\ ([0-9.]+): ]]; then
    flush_buf
    alert_id="${BASH_REMATCH[1]}"
    buf="$line"$'\n'
    echo "$(date '+%F %T') NEW id=$alert_id" >> "$DBG"
    continue
  fi

  # se riga vuota allora flusha
  if [[ -z "$line" ]]; then
    flush_buf
    continue
  fi
  buf+="$line"$'\n'
done
