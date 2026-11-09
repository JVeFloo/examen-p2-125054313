#!/bin/bash
# ------------------------------------------------------------
# Prepara SSH sin contrasena y arranca sshd.
# La llave se genera UNA sola vez y vive en el volumen /ssh-keys,
# compartido con el contenedor api. Asi no hay ninguna contrasena
# ni llave privada dentro de la imagen ni dentro del repositorio.
# ------------------------------------------------------------
set -euo pipefail

HADOOP_USER=hadoop
HADOOP_HOME_DIR=/home/${HADOOP_USER}
KEYDIR=/ssh-keys

# 1. Llaves de host del servidor SSH (se regeneran si no existen)
ssh-keygen -A >/dev/null

# 2. Par de llaves compartido hadoop <-> api
mkdir -p "${KEYDIR}"
if [ ! -f "${KEYDIR}/id_rsa" ]; then
    echo "[entrypoint] Generando par de llaves RSA en ${KEYDIR}..."
    ssh-keygen -t rsa -b 4096 -N "" -C "datamart" -f "${KEYDIR}/id_rsa" >/dev/null
fi
chmod 600 "${KEYDIR}/id_rsa"
chmod 644 "${KEYDIR}/id_rsa.pub"

# 3. Instalar la llave para el usuario hadoop:
#    - authorized_keys -> permite entrar (desde api y desde localhost)
#    - id_rsa          -> permite que 'ssh localhost' salga sin contrasena
install -d -m 700 -o ${HADOOP_USER} -g ${HADOOP_USER} "${HADOOP_HOME_DIR}/.ssh"
cp "${KEYDIR}/id_rsa"     "${HADOOP_HOME_DIR}/.ssh/id_rsa"
cp "${KEYDIR}/id_rsa.pub" "${HADOOP_HOME_DIR}/.ssh/authorized_keys"
cat > "${HADOOP_HOME_DIR}/.ssh/config" <<'EOF'
Host *
    StrictHostKeyChecking no
    UserKnownHostsFile /dev/null
    LogLevel ERROR
EOF
chown -R ${HADOOP_USER}:${HADOOP_USER} "${HADOOP_HOME_DIR}/.ssh"
chmod 600 "${HADOOP_HOME_DIR}/.ssh/id_rsa" \
          "${HADOOP_HOME_DIR}/.ssh/authorized_keys" \
          "${HADOOP_HOME_DIR}/.ssh/config"

# 4. La carpeta de salida se monta desde el host: hay que asegurar permisos
mkdir -p /data/output
chown -R ${HADOOP_USER}:${HADOOP_USER} /data/output || true

echo "[entrypoint] Listo. Arrancando sshd..."
exec "$@"
