#!/bin/bash
set -e

# Fix permissions for all volume mounts (must be done as root before switching to gameuser)
echo "🔧 Fixing permissions for volume mounts..."
# Fix permissions for all volumes used by the server
chown -R gameuser:gameuser /app/__server_patches 2>/dev/null || true
chown -R gameuser:gameuser /app/__game_backups 2>/dev/null || true
chown -R gameuser:gameuser /app/__patches 2>/dev/null || true
chown -R gameuser:gameuser /app/__config 2>/dev/null || true
chmod -R 755 /app/__server_patches 2>/dev/null || true
chmod -R 755 /app/__game_backups 2>/dev/null || true
chmod -R 755 /app/__patches 2>/dev/null || true
chmod -R 755 /app/__config 2>/dev/null || true

# Also ensure directories exist (in case volumes are empty)
mkdir -p /app/__server_patches /app/__game_backups /app/__patches /app/__config
chown -R gameuser:gameuser /app/__server_patches /app/__game_backups /app/__patches /app/__config
chmod -R 755 /app/__server_patches /app/__game_backups /app/__patches /app/__config

# Start the server as the non-root user
echo "🎮 Starting GenGame Server..."
exec su -s /bin/bash -c "$*" gameuser
