#!/bin/bash
set -e

passwd -u git || true

chown -R git:git /home/git

if [[ ! -f /etc/ssh/ssh_host_rsa_key ]]
then
  echo "[INFO] Generating SSH host keys..."
  ssh-keygen -A
fi


# check for first-time setup, if already set up skip
if [[ ! -d "/home/git/repo/.git" ]]
then
  echo "[INFO] First-time setup: initializing Git repo."

  su git -c "git init /home/git/repo"
  su git -c "git config --global user.name 'Git Access Control'"
  su git -c "git config --global user.email 'Git Access Control'"
  su git -c "git config --global --add safe.directory /home/git/repo"
  echo "ssh-ed25519 $1" > /home/git/.ssh/authorized_keys

  su git -c "/home/git/repo/gac.sh $1"
else
  echo "[INFO] Git repo already exists, skipping initialization."
fi

# configure SSH correctly and start daemon 
chmod 700 /home/git/.ssh
chmod 600 /home/git/.ssh/authorized_keys
chown -R git:git /home/git/.ssh

sed -i 's/^#\?PasswordAuthentication.*/PasswordAuthentication no/' /etc/ssh/sshd_config
sed -i 's/^#\?PubkeyAuthentication.*/PubkeyAuthentication yes/' /etc/ssh/sshd_config
sed -i 's|^#\?AuthorizedKeysFile.*|AuthorizedKeysFile .ssh/authorized_keys|' /etc/ssh/sshd_config

/usr/sbin/sshd -D
