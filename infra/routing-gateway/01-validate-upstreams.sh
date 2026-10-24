#!/bin/sh
# Fail closed before NGINX starts. All legitimate upstreams must be explicitly
# deployed/approved dedicated services. Never disclose configured hostnames.
set -eu
for name in ROUTING_UPSTREAM GEOCODING_UPSTREAM; do
  eval 'value=${'"$name"'-}'
  if [ -z "$value" ]; then
    echo "ERROR: Dedicated provider environment variable is missing" >&2
    exit 1
  fi
  case "$value" in
    http://*|https://*) ;;
    *) echo "ERROR: Invalid provider URL scheme" >&2; exit 1 ;;
  esac
  host="${value#*://}"
  case "$host" in
    ""|*/*|*\?*|*\#*|*@*|*%*)
      echo "ERROR: Provider must be a bare credential-free origin" >&2
      exit 1
      ;;
  esac
  case "$host" in
    photon.komoot.io|photon.komoot.io:*|router.project-osrm.org|router.project-osrm.org:*)
      echo "ERROR: Public routing demos cannot be dedicated upstreams" >&2
      exit 1
      ;;
  esac
  case "$host" in
    localhost|localhost:*|127.*|127.*:*|\[::1\]|\[::1\]:*)
      if [ "${KATOPTRON_TEST_LOOPBACK:-}" != "1" ]; then
        echo "ERROR: Loopback provider requires explicit local test mode" >&2
        exit 1
      fi
      ;;
  esac
done
