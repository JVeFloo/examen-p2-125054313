#!/bin/bash
# ------------------------------------------------------------
# Parte C2: resuelve la misma pregunta con un script secuencial,
# mide el tiempo y comprueba que el resultado coincide con el del
# job de MapReduce.
#
#   docker compose exec -u hadoop hadoop bash /opt/scripts/comparar.sh
# ------------------------------------------------------------
set -uo pipefail

: "${MATRICULA:?Falta la variable MATRICULA}"

INPUT="/data/input/ventas_${MATRICULA}.csv"
SALIDA_MR="/data/output/resultado/part-00000"
SALIDA_SEQ="/data/output/secuencial.tsv"

[ -f "$INPUT" ]     || { echo "No existe $INPUT"; exit 1; }
[ -f "$SALIDA_MR" ] || { echo "No existe $SALIDA_MR. Corre primero run_job.sh"; exit 1; }

echo "=== Script secuencial (sin Hadoop) ==="
time python3 /opt/jobs/secuencial.py "$INPUT" > "$SALIDA_SEQ"

echo
echo "=== Comparacion de resultados ==="
if diff <(LC_ALL=C sort "$SALIDA_MR") <(LC_ALL=C sort "$SALIDA_SEQ"); then
    echo "Los dos resultados son IDENTICOS ($(wc -l < "$SALIDA_SEQ") tiendas)."
else
    echo "ATENCION: los resultados NO coinciden."
    exit 1
fi
