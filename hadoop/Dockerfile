# ============================================================
#  Imagen de Hadoop en modo standalone (local) sobre Debian
#  Examen Segundo Parcial - Manejo Masivo de Datos
# ============================================================
FROM debian:bookworm-slim

# Hadoop 3.5.0 es la primera version con soporte completo de Java 17,
# que es justamente el JDK que trae Debian bookworm en sus repos.
ARG HADOOP_VERSION=3.5.0
ARG HADOOP_USER=hadoop

ENV DEBIAN_FRONTEND=noninteractive

# ---------- 1. Paquetes base: Java, Python y servidor SSH ----------
RUN apt-get update && apt-get install -y --no-install-recommends \
        openjdk-17-jdk-headless \
        python3 \
        openssh-server \
        openssh-client \
        curl \
        ca-certificates \
        procps \
        less \
        nano \
        tini \
    && rm -rf /var/lib/apt/lists/*

# ---------- 2. Variables de entorno exigidas por Hadoop ----------
ENV JAVA_HOME=/usr/lib/jvm/java-17-openjdk-amd64
ENV HADOOP_HOME=/opt/hadoop
ENV HADOOP_CONF_DIR=${HADOOP_HOME}/etc/hadoop
ENV HADOOP_STREAMING_JAR=${HADOOP_HOME}/share/hadoop/tools/lib/hadoop-streaming-${HADOOP_VERSION}.jar
ENV PATH=${PATH}:${JAVA_HOME}/bin:${HADOOP_HOME}/bin:${HADOOP_HOME}/sbin

# Si la ruta de JAVA_HOME no existiera, la imagen falla aqui y no mas adelante.
RUN test -x "${JAVA_HOME}/bin/java" \
    || { echo "ERROR: JAVA_HOME mal definido. Contenido de /usr/lib/jvm:"; ls -1 /usr/lib/jvm; exit 1; }

# ---------- 3. Descarga e instalacion de Hadoop ----------
RUN set -eux; \
    cd /tmp; \
    cdn="https://dlcdn.apache.org/hadoop/common/hadoop-${HADOOP_VERSION}/hadoop-${HADOOP_VERSION}.tar.gz"; \
    arc="https://archive.apache.org/dist/hadoop/common/hadoop-${HADOOP_VERSION}/hadoop-${HADOOP_VERSION}.tar.gz"; \
    curl -fsSL -o hadoop.tar.gz "$cdn" || curl -fsSL -o hadoop.tar.gz "$arc"; \
    mkdir -p "${HADOOP_HOME}"; \
    tar -xzf hadoop.tar.gz -C "${HADOOP_HOME}" --strip-components=1; \
    rm -f hadoop.tar.gz; \
    rm -rf "${HADOOP_HOME}/share/doc"
# El tar se borra en el MISMO RUN que la descarga: si se borrara en una
# instruccion aparte seguiria ocupando espacio en la capa anterior.
# share/doc es solo la documentacion HTML y no hace falta en el contenedor.

# hadoop-env.sh tambien necesita JAVA_HOME: los scripts de Hadoop se lanzan
# en sesiones no interactivas (por ejemplo via ssh) donde el ENV no viaja.
RUN echo "export JAVA_HOME=${JAVA_HOME}" >> "${HADOOP_CONF_DIR}/hadoop-env.sh" \
 && printf 'export JAVA_HOME=%s\nexport HADOOP_HOME=%s\nexport PATH=$PATH:$JAVA_HOME/bin:$HADOOP_HOME/bin:$HADOOP_HOME/sbin\n' \
        "${JAVA_HOME}" "${HADOOP_HOME}" > /etc/profile.d/hadoop.sh \
 && chmod 644 /etc/profile.d/hadoop.sh

# Verificacion pedida en el examen: si 'hadoop version' falla, la build se cae.
RUN hadoop version

# ---------- 4. Usuario sin contrasena y servidor SSH ----------
# -p '*'  => la cuenta NO queda bloqueada pero tampoco tiene contrasena valida:
#            solo se puede entrar con llave publica. No hay secretos en la imagen.
RUN useradd -m -s /bin/bash -u 1000 -p '*' ${HADOOP_USER} \
 && mkdir -p /var/run/sshd \
 && sed -i 's/^#\?PermitRootLogin.*/PermitRootLogin no/'              /etc/ssh/sshd_config \
 && sed -i 's/^#\?PasswordAuthentication.*/PasswordAuthentication no/' /etc/ssh/sshd_config \
 && sed -i 's/^#\?PubkeyAuthentication.*/PubkeyAuthentication yes/'    /etc/ssh/sshd_config \
 && sed -i 's/^#\?PermitEmptyPasswords.*/PermitEmptyPasswords no/'     /etc/ssh/sshd_config

# ---------- 5. Carpetas de trabajo ----------
RUN mkdir -p /data/input /data/output /opt/jobs \
 && chown -R ${HADOOP_USER}:${HADOOP_USER} /data/output /opt/jobs

COPY entrypoint.sh /usr/local/bin/entrypoint.sh
RUN chmod +x /usr/local/bin/entrypoint.sh

EXPOSE 22
ENTRYPOINT ["/usr/bin/tini", "--", "/usr/local/bin/entrypoint.sh"]
CMD ["/usr/sbin/sshd", "-D", "-e"]
