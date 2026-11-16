# shellcheck shell=bash
# Action: preflight (read-only)
# Shows what the owner must check by eye in L2: versions, host key and CA fingerprints,
# the root login method and which keys may log in as root. Changes nothing.
# A read that fails is reported as a failure (exit 4) or as an explicit WARNING line; it is
# never shown as "nothing there". The one exception is a root authorized_keys file that
# ssh-keygen cannot fully read: that prints a WARNING, because the owner must look anyway.

export LC_ALL=C
cl_log "preflight on $(hostname -s)"
pveversion || cl_die 4 "pveversion failed"
echo "--- host key fingerprints"
shopt -s nullglob
host_keys=(/etc/ssh/ssh_host_*_key.pub)
shopt -u nullglob
[ "${#host_keys[@]}" -gt 0 ] || cl_die 4 "no ssh host public keys found under /etc/ssh"
for f in "${host_keys[@]}"; do ssh-keygen -lf "$f" || cl_die 4 "cannot read $f"; done
echo "--- cluster CA fingerprint"
openssl x509 -in /etc/pve/pve-root-ca.pem -noout -fingerprint -sha256 -subject -enddate \
  || cl_die 4 "cannot read the cluster CA certificate"
echo "--- sshd root login settings"
sshd_conf=$(sshd -T 2>/dev/null) || cl_die 4 "sshd -T failed"
printf '%s\n' "$sshd_conf" | grep -Ei '^(permitrootlogin|passwordauthentication|pubkeyauthentication|kbdinteractiveauthentication) ' \
  || cl_die 4 "sshd -T printed none of the expected settings"
echo "--- keys allowed to log in as root (fingerprints only)"
if [ -e /root/.ssh/authorized_keys ]; then
  if ! ssh-keygen -lf /root/.ssh/authorized_keys; then
    cl_log "WARNING: ssh-keygen could not read every entry of /root/.ssh/authorized_keys; check it by hand"
  fi
else
  echo "no /root/.ssh/authorized_keys"
fi
echo "--- perl JSON::PP (needed by the host scripts)"
perl -MJSON::PP -e 'print "JSON::PP $JSON::PP::VERSION\n"' || cl_die 4 "perl JSON::PP is missing"
cl_log "preflight done"
