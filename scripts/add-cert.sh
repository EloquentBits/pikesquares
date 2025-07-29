#!/bin/bash
set -e

CERT_NAME="Caddy Local Authority Pikesquares"
CERT_PATH="/var/lib/pikesquares/caddy/pki/authorities/local/root.crt"
LEVEL="CT,,"
USER_HOME="$(eval echo ~${SUDO_USER:-$USER})"


certutil=$(command -v certutil)
if [[ -z "$certutil" ]]; then
    echo "certutil not found. Install libnss3-tools"
    exit 1
fi

nss_bases=()

# Chrome/Chromium
if [[ -d "$USER_HOME/.pki/nssdb" ]]; then
  if [[ -f "$USER_HOME/.pki/nssdb/cert9.db" ]]; then
    nss_bases+=("$USER_HOME/.pki/nssdb")
  fi
fi

for browser in chromium google-chrome; do
  snap_dir="$USER_HOME/snap/$browser"
  if [[ -d "$snap_dir" ]]; then
    for version_dir in "$snap_dir"/*; do
      nss_dir="$version_dir/.pki/nssdb"
      if [[ -f "$nss_dir/cert9.db" ]]; then
        nss_bases+=("$nss_dir")
      fi
    done
  fi
done

# Firefox
for firefox_dir in "$USER_HOME/.mozilla/firefox" "$USER_HOME/snap/firefox/common/.mozilla/firefox"; do
  if [[ -d "$firefox_dir" ]]; then
    for profile_dir in "$firefox_dir"/*; do
      if [[ -f "$profile_dir/cert9.db" ]]; then
        nss_bases+=("$profile_dir")
      fi
    done
  fi
done

added=false
for nss_dir in "${nss_bases[@]}"; do
  if ! certutil -L -d "sql:$nss_dir" | grep -q "$CERT_NAME"; then
    certutil -A -n "$CERT_NAME" -t "$LEVEL" -i "$CERT_PATH" -d "sql:$nss_dir"
    echo "$nss_dir":
    certutil -L -d "sql:$nss_dir"
    added=true
  fi
done

if $added; then
  echo "Pikesquares Root Certificate installed"
fi
