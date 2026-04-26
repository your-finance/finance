#!/usr/bin/env bash
# Broad Market RVOL scanner wrapper.

set -euo pipefail

source /root/workspace/Finance/.env
cd /root/workspace/Finance
python3 scripts/broad_market_scan.py
