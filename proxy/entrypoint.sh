#!/bin/bash
set -e

echo "Starting 3proxy service manager..."

# Function to get config file hash
get_config_hash() {
    md5sum /etc/3proxy/3proxy.cfg 2>/dev/null | cut -d' ' -f1
}

# Function to regenerate config
regenerate_config() {
    python3 /app/config_generator.py 2>&1
    sed -i '/^daemon/d' /etc/3proxy/3proxy.cfg 2>/dev/null || true
}

# Wait for database
echo "Waiting for database..."
for i in {1..30}; do
    if python3 -c "import psycopg2, os; psycopg2.connect(
        host=os.environ['DB_HOST'],
        dbname=os.environ['DB_NAME'],
        user=os.environ['DB_USER'],
        password=os.environ['DB_PASSWORD']
    ).close()" &>/dev/null; then
        echo "Database is ready!"
        break
    fi
    echo "Waiting for database... ($i/30)"
    sleep 2
done

# Generate initial config
echo "Generating initial configuration..."
regenerate_config

# Start 3proxy in background
start_3proxy() {
    pkill -9 3proxy 2>/dev/null || true
    sleep 1
    /usr/local/bin/3proxy /etc/3proxy/3proxy.cfg &
    PROXY_PID=$!
    echo "[$(date)] 3proxy started (PID: $PROXY_PID)"
}

start_3proxy
OLD_HASH=$(get_config_hash)

echo "[$(date)] Config auto-reload enabled (checking every 10 seconds)"

# Monitor loop - restart 3proxy only when config changes
while true; do
    sleep 10
    
    # Regenerate config
    regenerate_config > /tmp/regen.log 2>&1
    NEW_HASH=$(get_config_hash)
    
    # Only restart if config actually changed
    if [ "$OLD_HASH" != "$NEW_HASH" ]; then
        echo "[$(date)] 🔄 Config changed, restarting 3proxy..."
        cat /tmp/regen.log
        start_3proxy
        OLD_HASH=$NEW_HASH
        echo "[$(date)] ✅ 3proxy restarted with new config"
    else
        echo "[$(date)] ℹ️ No config changes"
    fi
    
    # Check if 3proxy is still running
    if ! pgrep -x 3proxy > /dev/null; then
        echo "[$(date)] ❌ 3proxy died unexpectedly, restarting..."
        start_3proxy
    fi
done
