# Builds the read-only root filesystem image baked into Firecracker VMs.
# Result: /output/nanobot-rootfs.ext4

FROM python:3.11-slim AS builder

# System deps
RUN apt-get update && apt-get install -y --no-install-recommends \
    e2fsprogs \
    busybox-static \
    iproute2 \
    iptables \
    && rm -rf /var/lib/apt/lists/*

# Install nanobot
RUN pip install --no-cache-dir nanobot-ai

# Copy guest agent
WORKDIR /app
COPY guest-agent/vsock_receiver.py /app/vsock_receiver.py
COPY guest-agent/entrypoint.sh /app/entrypoint.sh
RUN chmod +x /app/entrypoint.sh

# ── Build ext4 rootfs ─────────────────────────────────────────────────────
FROM builder AS rootfs-builder

RUN mkdir -p /rootfs/{bin,sbin,lib,lib64,usr,proc,sys,dev,tmp,app,var/log,home/nanobot/.nanobot/skills}

# Copy Python env
RUN cp -a /usr/local /rootfs/usr/local
RUN cp -a /usr/lib /rootfs/usr/lib
RUN cp -a /lib /rootfs/lib || true
RUN cp -a /lib64 /rootfs/lib64 || true
RUN cp -r /app /rootfs/app

# Busybox
RUN cp /bin/busybox-static /rootfs/bin/busybox && \
    /rootfs/bin/busybox --install /rootfs/bin

# Minimal /etc
RUN echo "root:x:0:0:root:/root:/bin/sh" > /rootfs/etc/passwd && \
    echo "nanobot:x:1000:1000::/home/nanobot:/bin/sh" >> /rootfs/etc/passwd && \
    echo "nameserver 8.8.8.8" > /rootfs/etc/resolv.conf

# Init: PID 1 runs entrypoint
RUN cp /rootfs/bin/busybox /rootfs/sbin/init && \
    printf '#!/bin/sh\nmount -t proc proc /proc\nmount -t sysfs sysfs /sys\nexec /app/entrypoint.sh\n' > /rootfs/init && \
    chmod +x /rootfs/init

FROM scratch AS output
COPY --from=rootfs-builder /rootfs /
