#!/usr/bin/env bash
set -u
DIR=/opt/bot-metrics
SLICE=/sys/fs/cgroup/system.slice
FILE="$DIR/metrics.csv"
mkdir -p "$DIR"
if [ ! -f "$FILE" ]; then
  printf 'ts,service,memory_current_bytes,memory_peak_bytes,cpu_usec\n' > "$FILE"
fi
collect() {
  local unit="$1" cg="$2" memc=0 memp=0 cpu=0
  if [ -r "$cg/memory.current" ]; then
    memc=$(cat "$cg/memory.current" 2>/dev/null || echo 0)
  fi
  if [ -r "$cg/memory.peak" ]; then
    memp=$(cat "$cg/memory.peak" 2>/dev/null || echo 0)
  fi
  if [ -r "$cg/cpu.stat" ]; then
    cpu=$(awk '$1=="usage_usec"{print $2}' "$cg/cpu.stat" 2>/dev/null || echo 0)
  fi
  printf '%s,%s,%s,%s,%s\n' "$(date -u +%FT%TZ)" "$unit" "$memc" "$memp" "$cpu" >> "$FILE"
}
collect voice-budget-bot.service "$SLICE/voice-budget-bot.service"
collect second-memory-bot.service "$SLICE/second-memory-bot.service"
collect second-memory-worker.service "$SLICE/second-memory-worker.service"
collect 'postgresql@16-main.service' "$SLICE/system-postgresql.slice/postgresql@16-main.service"
collect tonometer-bot.service "$SLICE/tonometer-bot.service"
