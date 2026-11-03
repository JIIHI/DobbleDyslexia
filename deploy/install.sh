#!/bin/bash
# Sets up Word Spot online on a fresh Ubuntu 24.04 server.
#   DOMAIN=play.example.com FAMILY_CODE=secret bash install.sh
# Safe to run again (it just updates things).
set -euo pipefail

DOMAIN="${DOMAIN:?set DOMAIN, e.g. play.silautron.com}"
FAMILY_CODE="${FAMILY_CODE:-}"
REPO="${REPO:-https://github.com/JIIHI/DobbleDyslexia.git}"
BRANCH="${BRANCH:-word-spot-app}"
BASE=/opt/wordspot
APP=$BASE/app

export DEBIAN_FRONTEND=noninteractive
apt-get update -q
apt-get install -y -q docker.io docker-compose-v2 git ufw unattended-upgrades

# Security updates install themselves; reboot at 04:30 if one needs it.
cat > /etc/apt/apt.conf.d/52wordspot-auto-reboot <<'CONF'
Unattended-Upgrade::Automatic-Reboot "true";
Unattended-Upgrade::Automatic-Reboot-Time "04:30";
CONF
cat > /etc/apt/apt.conf.d/20auto-upgrades <<'CONF'
APT::Periodic::Update-Package-Lists "1";
APT::Periodic::Unattended-Upgrade "1";
CONF

# Firewall: only SSH and the website.
ufw allow OpenSSH
ufw allow 80/tcp
ufw allow 443/tcp
ufw allow 443/udp
ufw --force enable

systemctl enable --now docker

mkdir -p $BASE
if [ -d $APP/.git ]; then
  git -C $APP fetch -q origin $BRANCH
  git -C $APP reset -q --hard origin/$BRANCH
else
  git clone -q --branch $BRANCH $REPO $APP
fi

cat > $BASE/.env <<CONF
DOMAIN=$DOMAIN
WORDSPOT_ACCESS_CODE=$FAMILY_CODE
CONF
chmod 600 $BASE/.env
echo "BRANCH=$BRANCH" > $BASE/branch

docker compose -f $APP/deploy/compose.yaml --env-file $BASE/.env up -d --build

# Pick up new versions from GitHub every night at 03:30.
cat > /etc/cron.d/wordspot-update <<CONF
30 3 * * * root bash $APP/deploy/update.sh >> /var/log/wordspot-update.log 2>&1
CONF

# Handy commands for later.
cat > /usr/local/bin/wordspot-status <<CONF
#!/bin/bash
docker compose -f $APP/deploy/compose.yaml --env-file $BASE/.env ps
echo; echo "Recent game server log:"; docker compose -f $APP/deploy/compose.yaml --env-file $BASE/.env logs --tail 20 wordspot
CONF
cat > /usr/local/bin/wordspot-update <<CONF
#!/bin/bash
bash $APP/deploy/update.sh "\$@"
CONF
chmod +x /usr/local/bin/wordspot-status /usr/local/bin/wordspot-update

echo "Word Spot is installed. It will be at https://$DOMAIN once the domain points here."
