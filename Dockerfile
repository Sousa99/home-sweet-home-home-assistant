FROM ghcr.io/home-assistant/home-assistant:stable

COPY config/ /config-seed/
COPY scripts/restore-state.sh /usr/local/bin/restore-state.sh
COPY scripts/fix-zha-serial.py /usr/local/bin/fix-zha-serial.py
COPY scripts/fix-http-proxy.py /usr/local/bin/fix-http-proxy.py

RUN chmod 0755 /usr/local/bin/restore-state.sh /usr/local/bin/fix-zha-serial.py /usr/local/bin/fix-http-proxy.py
