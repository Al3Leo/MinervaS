#!/usr/bin/env bash
# Uso: cam_dos_blocker <MAC> [--timeout SEC]

IFACE="ens37"
TABLE="camdrop"
CHAIN="ingress"
LOG="/var/log/cam_dos_blocker.log"

MAC="$1"
if [[ "$2" == "--timeout" && -n "$3" ]]; then
  TIMEOUT="$3"
else
  TIMEOUT=""
fi

nft list table netdev "$TABLE" >/dev/null 2>&1 || nft add table netdev "$TABLE"
nft list chain netdev "$TABLE" "$CHAIN" >/dev/null 2>&1 || \
  nft add chain netdev "$TABLE" "$CHAIN" "{ type filter hook ingress device $IFACE priority 0; }"

nft add rule netdev "$TABLE" "$CHAIN" ether saddr "$MAC" drop
nft list ruleset > /etc/nftables.conf
echo "$(date '+%F %T') drop MAC=$MAC su $IFACE (nft)" >> "$LOG"

# Auto-unban opzionale
if [[ -n "$TIMEOUT" ]]; then
  (
    sleep "$TIMEOUT"
    SNAP=$(mktemp)
    nft list chain netdev "$TABLE" "$CHAIN" > "$SNAP"
    nft flush chain netdev "$TABLE" "$CHAIN"
    nft list ruleset > /etc/nftables.conf
    echo "$(date '+%F %T') unban MAC=$MAC (nft flush semplice)" >> "$LOG"
    rm -f "$SNAP"
  ) >/dev/null 2>&1 &
fi

exit 0
