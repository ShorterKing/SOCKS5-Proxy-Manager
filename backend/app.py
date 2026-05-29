# backend/app.py
from flask import Flask, request, jsonify, session
from flask_cors import CORS
import psycopg2
import bcrypt
import os
import time
import secrets
import threading
import psutil
from datetime import datetime, timedelta
from functools import wraps

app = Flask(__name__)
app.secret_key = os.environ.get('SECRET_KEY', secrets.token_hex(32))
CORS(app, supports_credentials=True, origins=['http://localhost', 'https://localhost'])

DB_CONFIG = {
    'host': os.environ.get('DB_HOST', 'postgres'),
    'port': os.environ.get('DB_PORT', 5432),
    'database': os.environ.get('DB_NAME', 'proxydb'),
    'user': os.environ.get('DB_USER', 'proxyuser'),
    'password': os.environ.get('DB_PASSWORD', 'changeme123')
}

def get_db_connection():
    return psycopg2.connect(**DB_CONFIG)

# Authentication decorator
def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'admin_id' not in session:
            return jsonify({'error': 'Unauthorized'}), 401
        return f(*args, **kwargs)
    return decorated_function

def init_db():
    max_retries = 30
    for i in range(max_retries):
        try:
            conn = get_db_connection()
            cur = conn.cursor()

            # Create admin_users table
            cur.execute("""
                CREATE TABLE IF NOT EXISTS admin_users (
                    id SERIAL PRIMARY KEY,
                    username VARCHAR(50) UNIQUE NOT NULL,
                    password VARCHAR(255) NOT NULL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)

            # Create proxy users table
            cur.execute("""
                CREATE TABLE IF NOT EXISTS users (
                    id SERIAL PRIMARY KEY,
                    username VARCHAR(50) UNIQUE NOT NULL,
                    password VARCHAR(255) NOT NULL,
                    plaintext_password VARCHAR(255),
                    is_active BOOLEAN DEFAULT true,
                    speed_limit_kbps INTEGER DEFAULT 0,
                    daily_quota_mb INTEGER DEFAULT 0,
                    blocked_domains TEXT DEFAULT '',
                    blocked_ips TEXT DEFAULT '',
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)

            # Create proxy_settings table
            cur.execute("""
                CREATE TABLE IF NOT EXISTS proxy_settings (
                    id SERIAL PRIMARY KEY,
                    is_running BOOLEAN DEFAULT true,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)

            # Initialize proxy settings
            cur.execute("SELECT COUNT(*) FROM proxy_settings")
            if cur.fetchone()[0] == 0:
                cur.execute("INSERT INTO proxy_settings (is_running) VALUES (true)")

            # Create traffic logs table
            cur.execute("""
                CREATE TABLE IF NOT EXISTS traffic_logs (
                    id SERIAL PRIMARY KEY,
                    username VARCHAR(50) NOT NULL,
                    source_ip VARCHAR(45),
                    destination_ip VARCHAR(45),
                    destination_domain VARCHAR(255),
                    bytes_sent BIGINT DEFAULT 0,
                    bytes_received BIGINT DEFAULT 0,
                    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)

            # Create daily usage table
            cur.execute("""
                CREATE TABLE IF NOT EXISTS daily_usage (
                    id SERIAL PRIMARY KEY,
                    username VARCHAR(50) NOT NULL,
                    date DATE NOT NULL,
                    total_mb FLOAT DEFAULT 0,
                    UNIQUE(username, date)
                )
            """)

            # Create default admin if not exists
            cur.execute("SELECT * FROM admin_users WHERE username = 'admin'")
            if not cur.fetchone():
                hashed = bcrypt.hashpw('admin123'.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')
                cur.execute("""
                    INSERT INTO admin_users (username, password)
                    VALUES ('admin', %s)
                """, (hashed,))

            conn.commit()
            cur.close()
            conn.close()
            print("Database initialized successfully")
            return
        except Exception as e:
            print(f"Waiting for database... ({i+1}/{max_retries}): {e}")
            time.sleep(2)

    raise Exception("Could not initialize database")

# Log Parsing and Quota Enforcement Logic
def log_parser_task():
    print("Background log parser task started")
    log_path = '/var/log/3proxy/3proxy.log'
    last_pos = 0
    
    if os.path.exists(log_path):
        last_pos = os.path.getsize(log_path)

    while True:
        try:
            if os.path.exists(log_path):
                current_size = os.path.getsize(log_path)
                if current_size < last_pos:
                    last_pos = 0
                
                if current_size > last_pos:
                    with open(log_path, 'r') as f:
                        f.seek(last_pos)
                        lines = f.readlines()
                        last_pos = f.tell()
                        
                        if lines:
                            process_log_lines(lines)
            
            enforce_quotas()
            
        except Exception as e:
            print(f"Log parser error: {e}")
            
        time.sleep(10)

def process_log_lines(lines):
    try:
        conn = get_db_connection()
        cur = conn.cursor()
        
        for line in lines:
            try:
                parts = line.split()
                if len(parts) < 10 or parts[0] != '-': continue
                
                username = parts[3]
                if username == '-': continue
                
                source_ip = parts[4].split(':')[0]
                destination_ip = parts[5].split(':')[0]
                bytes_sent = int(parts[6])
                bytes_received = int(parts[7])
                destination_domain = parts[8]
                
                cur.execute("""
                    INSERT INTO traffic_logs (username, source_ip, destination_ip, destination_domain, bytes_sent, bytes_received)
                    VALUES (%s, %s, %s, %s, %s, %s)
                """, (username, source_ip, destination_ip, destination_domain, bytes_sent, bytes_received))
                
                today = datetime.now().date()
                total_mb = (bytes_sent + bytes_received) / (1024 * 1024)
                
                cur.execute("""
                    INSERT INTO daily_usage (username, date, total_mb)
                    VALUES (%s, %s, %s)
                    ON CONFLICT (username, date)
                    DO UPDATE SET total_mb = daily_usage.total_mb + EXCLUDED.total_mb
                """, (username, today, total_mb))
                
            except (IndexError, ValueError):
                continue
                
        conn.commit()
        cur.close()
        conn.close()
    except Exception as e:
        print(f"Database error in process_log_lines: {e}")

def enforce_quotas():
    try:
        conn = get_db_connection()
        cur = conn.cursor()
        today = datetime.now().date()
        
        cur.execute("""
            SELECT u.id, u.username, u.daily_quota_mb, COALESCE(du.total_mb, 0)
            FROM users u
            JOIN daily_usage du ON u.username = du.username
            WHERE du.date = %s 
              AND u.daily_quota_mb > 0 
              AND du.total_mb >= u.daily_quota_mb 
              AND u.is_active = true
        """, (today,))
        
        exceeded_users = cur.fetchall()
        for user_id, username, quota, used in exceeded_users:
            print(f"User {username} exceeded quota ({used:.2f}/{quota} MB). Disabling.")
            cur.execute("UPDATE users SET is_active = false WHERE id = %s", (user_id,))
            
        if exceeded_users:
            conn.commit()
            
        cur.close()
        conn.close()
    except Exception as e:
        print(f"Database error in enforce_quotas: {e}")

init_db()
threading.Thread(target=log_parser_task, daemon=True).start()

@app.route('/api/health', methods=['GET'])
def health():
    return jsonify({'status': 'ok'}), 200

@app.route('/api/system/info', methods=['GET'])
@login_required
def get_system_info():
    try:
        info = {
            'cpu_usage': psutil.cpu_percent(interval=1),
            'memory': psutil.virtual_memory()._asdict(),
            'disk': psutil.disk_usage('/')._asdict(),
            'uptime': time.time() - psutil.boot_time(),
            'load_avg': os.getloadavg()
        }
        return jsonify(info), 200
    except Exception as e:
        return jsonify({'error': str(e)}), 500

# Authentication endpoints
@app.route('/api/auth/login', methods=['POST'])
def login():
    try:
        data = request.json
        username = data.get('username')
        password = data.get('password')

        if not username or not password:
            return jsonify({'error': 'Username and password required'}), 400

        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute("SELECT id, password FROM admin_users WHERE username = %s", (username,))
        admin = cur.fetchone()
        cur.close()
        conn.close()

        if not admin:
            return jsonify({'error': 'Invalid credentials'}), 401

        if bcrypt.checkpw(password.encode('utf-8'), admin[1].encode('utf-8')):
            session['admin_id'] = admin[0]
            session['admin_username'] = username
            return jsonify({'message': 'Login successful', 'username': username}), 200
        else:
            return jsonify({'error': 'Invalid credentials'}), 401

    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/auth/logout', methods=['POST'])
@login_required
def logout():
    session.clear()
    return jsonify({'message': 'Logged out successfully'}), 200

@app.route('/api/auth/check', methods=['GET'])
def check_auth():
    if 'admin_id' in session:
        return jsonify({'authenticated': True, 'username': session.get('admin_username')}), 200
    return jsonify({'authenticated': False}), 200

@app.route('/api/auth/change-password', methods=['POST'])
@login_required
def change_admin_password():
    try:
        data = request.json
        current_password = data.get('current_password')
        new_password = data.get('new_password')

        if not current_password or not new_password:
            return jsonify({'error': 'Current and new password required'}), 400

        if len(new_password) < 6:
            return jsonify({'error': 'Password must be at least 6 characters'}), 400

        admin_id = session['admin_id']
        
        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute("SELECT password FROM admin_users WHERE id = %s", (admin_id,))
        admin = cur.fetchone()

        if not admin:
            return jsonify({'error': 'Admin not found'}), 404

        if not bcrypt.checkpw(current_password.encode('utf-8'), admin[0].encode('utf-8')):
            return jsonify({'error': 'Current password is incorrect'}), 401

        hashed = bcrypt.hashpw(new_password.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')
        cur.execute("UPDATE admin_users SET password = %s WHERE id = %s", (hashed, admin_id))
        conn.commit()
        cur.close()
        conn.close()

        return jsonify({'message': 'Password changed successfully'}), 200
    except Exception as e:
        return jsonify({'error': str(e)}), 500

# Proxy control endpoints
@app.route('/api/proxy/status', methods=['GET'])
@login_required
def get_proxy_status():
    try:
        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute("SELECT is_running FROM proxy_settings LIMIT 1")
        result = cur.fetchone()
        cur.close()
        conn.close()
        return jsonify({'is_running': result[0] if result else False}), 200
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/proxy/toggle', methods=['POST'])
@login_required
def toggle_proxy():
    try:
        data = request.json
        is_running = data.get('is_running', True)

        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute("UPDATE proxy_settings SET is_running = %s, updated_at = CURRENT_TIMESTAMP", (is_running,))
        conn.commit()
        cur.close()
        conn.close()

        return jsonify({'message': 'Proxy status updated', 'is_running': is_running}), 200
    except Exception as e:
        return jsonify({'error': str(e)}), 500

# User management endpoints
@app.route('/api/users', methods=['GET'])
@login_required
def get_users():
    try:
        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute("""
            SELECT id, username, is_active, speed_limit_kbps, daily_quota_mb,
                   blocked_domains, blocked_ips, created_at, plaintext_password
            FROM users
            ORDER BY created_at DESC
        """)
        users = cur.fetchall()

        result = []
        for user in users:
            result.append({
                'id': user[0],
                'username': user[1],
                'is_active': user[2],
                'speed_limit_kbps': user[3],
                'daily_quota_mb': user[4],
                'blocked_domains': user[5],
                'blocked_ips': user[6],
                'created_at': user[7].isoformat() if user[7] else None,
                'has_password': bool(user[8])
            })

        cur.close()
        conn.close()
        return jsonify(result), 200
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/users', methods=['POST'])
@login_required
def create_user():
    try:
        data = request.json
        username = data.get('username')
        password = data.get('password')
        speed_limit = data.get('speed_limit_kbps', 0)
        daily_quota = data.get('daily_quota_mb', 0)
        blocked_domains = data.get('blocked_domains', '')
        blocked_ips = data.get('blocked_ips', '')

        if not username or not password:
            return jsonify({'error': 'Username and password required'}), 400

        hashed = bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')

        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute("""
            INSERT INTO users (username, password, plaintext_password, speed_limit_kbps, daily_quota_mb, blocked_domains, blocked_ips)
            VALUES (%s, %s, %s, %s, %s, %s, %s)
            RETURNING id
        """, (username, hashed, password, speed_limit, daily_quota, blocked_domains, blocked_ips))

        user_id = cur.fetchone()[0]
        conn.commit()
        cur.close()
        conn.close()

        return jsonify({'id': user_id, 'message': 'User created successfully'}), 201
    except psycopg2.IntegrityError:
        return jsonify({'error': 'Username already exists'}), 409
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/users/<int:user_id>', methods=['PUT'])
@login_required
def update_user(user_id):
    try:
        data = request.json
        conn = get_db_connection()
        cur = conn.cursor()

        updates = []
        params = []

        if 'password' in data and data['password']:
            hashed = bcrypt.hashpw(data['password'].encode('utf-8'), bcrypt.gensalt()).decode('utf-8')
            updates.append('password = %s')
            params.append(hashed)
            updates.append('plaintext_password = %s')
            params.append(data['password'])

        if 'is_active' in data:
            updates.append('is_active = %s')
            params.append(data['is_active'])

        if 'speed_limit_kbps' in data:
            updates.append('speed_limit_kbps = %s')
            params.append(data['speed_limit_kbps'])

        if 'daily_quota_mb' in data:
            updates.append('daily_quota_mb = %s')
            params.append(data['daily_quota_mb'])

        if 'blocked_domains' in data:
            updates.append('blocked_domains = %s')
            params.append(data['blocked_domains'])

        if 'blocked_ips' in data:
            updates.append('blocked_ips = %s')
            params.append(data['blocked_ips'])

        if not updates:
            return jsonify({'error': 'No fields to update'}), 400

        params.append(user_id)
        query = f"UPDATE users SET {', '.join(updates)} WHERE id = %s"
        cur.execute(query, params)

        conn.commit()
        cur.close()
        conn.close()

        return jsonify({'message': 'User updated successfully'}), 200
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/users/<int:user_id>', methods=['DELETE'])
@login_required
def delete_user(user_id):
    try:
        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute("DELETE FROM users WHERE id = %s", (user_id,))
        conn.commit()
        cur.close()
        conn.close()

        return jsonify({'message': 'User deleted successfully'}), 200
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/stats/usage', methods=['GET'])
@login_required
def get_usage_stats():
    try:
        conn = get_db_connection()
        cur = conn.cursor()

        today = datetime.now().date()
        cur.execute("""
            SELECT u.username, COALESCE(du.total_mb, 0) as total_mb
            FROM users u
            LEFT JOIN daily_usage du ON u.username = du.username AND du.date = %s
            WHERE u.is_active = true
            ORDER BY total_mb DESC
        """, (today,))

        usage = cur.fetchall()
        result = []
        for row in usage:
            result.append({
                'username': row[0],
                'used_mb': round(row[1], 2)
            })

        cur.close()
        conn.close()
        return jsonify(result), 200
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/logs', methods=['GET'])
@login_required
def get_logs():
    try:
        username = request.args.get('username')
        limit = int(request.args.get('limit', 100))

        conn = get_db_connection()
        cur = conn.cursor()

        if username:
            cur.execute("""
                SELECT username, source_ip, destination_ip, destination_domain,
                       bytes_sent, bytes_received, timestamp
                FROM traffic_logs
                WHERE username = %s
                ORDER BY timestamp DESC
                LIMIT %s
            """, (username, limit))
        else:
            cur.execute("""
                SELECT username, source_ip, destination_ip, destination_domain,
                       bytes_sent, bytes_received, timestamp
                FROM traffic_logs
                ORDER BY timestamp DESC
                LIMIT %s
            """, (limit,))

        logs = cur.fetchall()
        result = []
        for log in logs:
            result.append({
                'username': log[0],
                'source_ip': log[1],
                'destination_ip': log[2],
                'destination_domain': log[3],
                'bytes_sent': log[4],
                'bytes_received': log[5],
                'timestamp': log[6].isoformat() if log[6] else None
            })

        cur.close()
        conn.close()
        return jsonify(result), 200
    except Exception as e:
        return jsonify({'error': str(e)}), 500

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=8000, debug=False)
