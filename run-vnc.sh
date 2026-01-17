#!/bin/bash
set -e

# 1. Fix permissions for all volume mounts (must be done as root before switching to gameuser)
echo "🔧 Fixing permissions for volume mounts..."
# Fix permissions for all volumes used by the client
chown -R gameuser:gameuser /app/__game_backups 2>/dev/null || true
chown -R gameuser:gameuser /app/__patches 2>/dev/null || true
chown -R gameuser:gameuser /app/__config 2>/dev/null || true
chmod -R 755 /app/__game_backups 2>/dev/null || true
chmod -R 755 /app/__patches 2>/dev/null || true
chmod -R 755 /app/__config 2>/dev/null || true

# Also ensure directories exist (in case volumes are empty)
mkdir -p /app/__game_backups /app/__patches /app/__config
chown -R gameuser:gameuser /app/__game_backups /app/__patches /app/__config
chmod -R 755 /app/__game_backups /app/__patches /app/__config

# --- Clean up stale X11 lock files ---
echo "🧹 Cleaning up stale X11 lock files..."
rm -f /tmp/.X0-lock
rm -rf /tmp/.X11-unix
# -----------------------------------------------

# Suppress ALSA audio errors
export SDL_AUDIODRIVER=dummy

# 2. Start Xvfb (Virtual Screen)
echo "📺 Starting Virtual X Server (Xvfb)..."
Xvfb :0 -screen 0 1400x900x24 &
sleep 2

# 3. Start Window Manager (Fluxbox)
echo "🪟 Starting Window Manager..."
fluxbox &
sleep 1

# 3.5. Start clipboard synchronizer
echo "📋 Starting Clipboard Synchronizer..."
autocutsel -fork -selection PRIMARY &
autocutsel -fork -selection CLIPBOARD &
sleep 1

# 4. Start x11vnc (clipboard support is enabled by default)
echo "🔌 Starting VNC Server..."
x11vnc -display :0 -forever -shared -rfbport 5900 -nopw -bg

# 5. Start noVNC Web Server
echo "🌐 Starting noVNC Web Server (Port 6080)..."
/usr/bin/novnc_proxy --vnc localhost:5900 --listen 6080 &

# 6. Start the Game as the non-root user
echo "🎮 Starting GenGame Client..."
export DISPLAY=:0
export SDL_VIDEODRIVER=x11

exec su -s /bin/bash -c "$*" gameuser