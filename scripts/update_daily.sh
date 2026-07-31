#!/bin/bash
# CRM Daily Export & Push for Nigeria
# Based on Pakistan training document approach
# Runs: download → convert → push

set -e
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"
TIMESTAMP=$(date +%Y-%m-%d_%H%M)

echo "[$(date)] Starting CRM Nigeria daily export..."

# Download from CRM
python3 -u "$SCRIPT_DIR/download_crm.py" 2>&1
echo "[$(date)] Download complete."

# Find latest downloaded files (now with clear prefixes after rename fix)
INV_FILE=$(ls -t /tmp/crm_downloads/InventoryOverview_* 2>/dev/null | head -1)
TRANSIT_FILE=$(ls -t /tmp/crm_downloads/In_Transit_* 2>/dev/null | head -1)

if [ -z "$INV_FILE" ] || [ -z "$TRANSIT_FILE" ]; then
    echo "[$(date)] ERROR: Download files not found!"
    exit 1
fi

# Convert to JSON
echo "[$(date)] Converting Inventory Overview..."
python3 "$SCRIPT_DIR/build_inventory_index.py" "$INV_FILE" "$PROJECT_DIR/inventory_index.json"

echo "[$(date)] Converting In Transit Report..."
python3 "$SCRIPT_DIR/build_in_transit_index.py" "$TRANSIT_FILE" "$PROJECT_DIR/in_transit_index.json"

# Push to GitHub
echo "[$(date)] Pushing to GitHub..."
cd "$PROJECT_DIR"
git add inventory_index.json in_transit_index.json
git commit -m "Auto-update inventory data $TIMESTAMP" || echo "No changes to commit"
git push origin main

echo "[$(date)] Done! Files updated and pushed."