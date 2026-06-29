FROM ubuntu:22.04

# TigerGraph 4.1 bare-metal install prerequisites + tools for fault-injection tests
ENV DEBIAN_FRONTEND=noninteractive
RUN apt-get update && apt-get install -y --no-install-recommends \
        openssh-server sudo curl wget vim less jq \
        net-tools iputils-ping iproute2 dnsutils lsof \
        cron tar gzip coreutils util-linux procps python3 sshpass ca-certificates \
    && rm -rf /var/lib/apt/lists/*

# tigergraph user with passwordless sudo (installer's sudo user)
RUN useradd -m -s /bin/bash tigergraph \
    && echo 'tigergraph:tigergraph' | chpasswd \
    && echo 'tigergraph ALL=(ALL) NOPASSWD:ALL' > /etc/sudoers.d/tigergraph \
    && chmod 0440 /etc/sudoers.d/tigergraph \
    && echo 'root:root' | chpasswd

# Shared SSH keypair baked into the image -> every container from this image
# trusts every other one (mutual passwordless SSH for the cluster installer)
RUN mkdir -p /home/tigergraph/.ssh \
    && ssh-keygen -t rsa -b 2048 -f /home/tigergraph/.ssh/id_rsa -N "" -q \
    && cp /home/tigergraph/.ssh/id_rsa.pub /home/tigergraph/.ssh/authorized_keys \
    && printf 'Host *\n  StrictHostKeyChecking no\n  UserKnownHostsFile /dev/null\n  LogLevel ERROR\n' \
        > /home/tigergraph/.ssh/config \
    && chmod 700 /home/tigergraph/.ssh \
    && chmod 600 /home/tigergraph/.ssh/id_rsa /home/tigergraph/.ssh/authorized_keys /home/tigergraph/.ssh/config \
    && chown -R tigergraph:tigergraph /home/tigergraph/.ssh

# sshd runtime dir + host keys
RUN mkdir -p /run/sshd && ssh-keygen -A

EXPOSE 22 9000 14240 14241
CMD ["/usr/sbin/sshd", "-D"]
