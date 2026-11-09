#!/bin/bash
# ------------------------------------------------------------
# Lanza el job de Hadoop Streaming.
# Se ejecuta DENTRO del contenedor hadoop, como usuario 'hadoop':
#   docker compose exec -u hadoop hadoop bash /opt/scripts/run_job.sh
# ------------------------------------------------------------
set -euo pipefail

: "${MATRICULA:?Falta la variable MATRICULA}"

INPUT="/data/input/ventas_${MATRICULA}.csv"
OUTDIR="/data/output/resultado"

[ -f "$INPUT" ] || { echo "No existe $INPUT. Deja el CSV en la carpeta ./data del host."; exit 1; }

# Hadoop se niega a escribir sobre un directorio de salida que ya existe
rm -rf "$OUTDIR"

# /opt/jobs esta montado de solo lectura: trabajamos sobre una copia
WORK=$(mktemp -d)
cp /opt/jobs/mapper.py /opt/jobs/reducer.py "$WORK/"
chmod +x "$WORK"/mapper.py "$WORK"/reducer.py
cd "$WORK"

echo "=== Lanzando MapReduce sobre $INPUT ==="
time hadoop jar "$HADOOP_HOME"/share/hadoop/tools/lib/hadoop-streaming-*.jar \
    -input  "$INPUT" \
    -output "$OUTDIR" \
    -mapper mapper.py \
    -reducer reducer.py \
    -file mapper.py \
    -file reducer.py

echo
echo "=== Resultado en $OUTDIR/part-00000 ==="
cat "$OUTDIR/part-00000"
