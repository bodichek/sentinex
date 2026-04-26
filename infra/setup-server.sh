#!/usr/bin/env bash
# One-shot provisioning for a fresh Hetzner Cloud VM (Debian 12 / Ubuntu 24.04).
# Run as root.

set -euo pipefail

apt-get update
apt-get upgrade -y
apt-get install -y --no-install-recommends \
    ca-certificates curl gnupg lsb-release \
    ufw fail2ban git

# Docker
install -m 0755 -d /etc/apt/keyrings
curl -fsSL https://download.docker.com/linux/debian/gpg \
    | gpg --dearmor -o /etc/apt/keyrings/docker.gpg
echo "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.gpg] https://download.docker.com/linux/debian $(lsb_release -cs) stable" \
    > /etc/apt/sources.list.d/docker.list
apt-get update
apt-get install -y docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin

# Certbot
apt-get install -y certbot

# App user
id -u sentinex >/dev/null 2>&1 || useradd -m -s /bin/bash sentinex
usermod -aG docker sentinex

# Repo layout
install -d -o sentinex -g sentinex /opt/sentinex
if [[ ! -d /opt/sentinex/.git ]]; then
    sudo -u sentinex git clone "${GIT_URL:-https://github.com/REPLACE/sentinex.git}" /opt/sentinex
fi

# Firewall
ufw allow OpenSSH
ufw allow 80/tcp
ufw allow 443/tcp
ufw --force enable

# fail2ban
cat > /etc/fail2ban/jail.d/sshd.local <<'EOF'
[sshd]
enabled = true
maxretry = 5
findtime = 10m
bantime = 1h
EOF
systemctl enable --now fail2ban

# Harden SSH
sed -i 's/^#\?PasswordAuthentication.*/PasswordAuthentication no/' /etc/ssh/sshd_config
systemctl reload ssh || systemctl reload sshd

echo "Done. Next steps:"
echo "  1) Place .env at /opt/sentinex/.env (chmod 600, owner sentinex:sentinex)"
echo "  2) Run certbot for wildcard cert (see infra/ssl-renew.sh for renewal)"
echo "  3) sudo -u sentinex bash /opt/sentinex/infra/deploy.sh"
