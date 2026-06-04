#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")"

ZIP_NAME="scf-cos-signedurl.zip"

# Clean previous build
rm -rf package "$ZIP_NAME"

# Install deps into package/
pip3 install -t package -r requirements.txt --no-cache-dir

# Strip unnecessary files
find package -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
find package -type d -name "*.dist-info" -exec rm -rf {} + 2>/dev/null || true
find package -type f -name "*.pyc" -delete 2>/dev/null || true
rm -rf package/bin

# Create zip from deps
cd package
zip -r9 "../$ZIP_NAME" . -x "*.pyc"
cd ..

# Add application source
zip -g "$ZIP_NAME" index.py

# Cleanup
rm -rf package

echo "Built $ZIP_NAME ($(du -h "$ZIP_NAME" | cut -f1))"
