#!/bin/bash
# Copia la llave privada compartida (generada por el contenedor hadoop)
# para poder hacer: ssh hadoop@hadoop  sin contrasena.
set -euo pipefail

mkdir -p /root/.ssh && chmod 700 /root/.ssh

for _ in $(seq 1 30); do
    [ -f /ssh-keys/id_rsa ] && break
    sleep 1
done

if [ -f /ssh-keys/id_rsa ]; then
    cp /ssh-keys/id_rsa /root/.ssh/id_rsa
    chmod 600 /root/.ssh/id_rsa
    cat > /root/.ssh/config <<'EOF'
Host hadoop
    HostName hadoop
    User hadoop
    IdentityFile /root/.ssh/id_rsa
    StrictHostKeyChecking no
    UserKnownHostsFile /dev/null
    LogLevel ERROR
EOF
    chmod 600 /root/.ssh/config
    echo "[entrypoint] Llave SSH instalada."
else
    echo "[entrypoint] AVISO: no se encontro /ssh-keys/id_rsa (el contenedor hadoop no ha arrancado)."
fi

exec "$@"
