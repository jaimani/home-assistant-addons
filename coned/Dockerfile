FROM ubuntu:focal
ARG DEBIAN_FRONTEND=noninteractive
ARG TZ=America/New_York

USER root
RUN apt-get update && apt-get upgrade -yq

# === INSTALL Python ===

RUN apt-get update && \
    # Install Python
    apt-get install -y python3 python3-distutils python3-pip curl jq nano tzdata && \
    update-alternatives --install /usr/bin/python python /usr/bin/python3 1 && \ 
    # Feature-parity with node.js base images. 
    apt-get install -y --no-install-recommends git openssh-client gpg && \
    # clean apt cache
    rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip3 install -r requirements.txt
RUN playwright install --with-deps chromium

COPY run.py .
COPY run.sh .
COPY coned.py .

CMD cd / && chmod +x /run.sh && /run.sh
