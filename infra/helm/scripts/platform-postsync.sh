#!/bin/bash
set +e
echo "Starting platform postsync hook..."

# Source common functions
source "$(dirname "$0")/postsync-lib.sh"

# Get service details
PLATFORM_ADDR=$(wait_for_ip flareward-platform-be) || exit 1
PLATFORM_PORT=$(wait_for_port flareward-platform-be) || exit 1
PLATFORM_IP=$(wait_for_service_name flareward-platform-be) || exit 1

# Create configmap
create_or_update_configmap platform-config \
  --from-literal=PLATFORM_ADDR="$PLATFORM_ADDR" \
  --from-literal=PLATFORM_PORT="$PLATFORM_PORT" \
  --from-literal=PLATFORM_IP="$PLATFORM_IP"