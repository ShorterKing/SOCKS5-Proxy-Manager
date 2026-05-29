# proxy/config_generator.py
import psycopg2
import os
import time
import sys


def wait_for_db():
    max_retries = 30
    for i in range(1, max_retries + 1):
        try:
            conn = psycopg2.connect(
                host=os.environ['DB_HOST'],
                port=os.environ.get('DB_PORT', '5432'),
                database=os.environ['DB_NAME'],
                user=os.environ['DB_USER'],
                password=os.environ['DB_PASSWORD'],
                connect_timeout=3
            )
            conn.close()
            print("Database is ready!")
            return True
        except psycopg2.OperationalError as e:
            print(f"Waiting for database... ({i}/{max_retries})")
            time.sleep(2)
    print("Database connection failed after retries.")
    return False


def generate_config():
    try:
        conn = psycopg2.connect(
            host=os.environ['DB_HOST'],
            port=os.environ.get('DB_PORT', '5432'),
            database=os.environ['DB_NAME'],
            user=os.environ['DB_USER'],
            password=os.environ['DB_PASSWORD']
        )
        cur = conn.cursor()

        # Fetch active users
        cur.execute("""
            SELECT username, plaintext_password, speed_limit_kbps, 
                   daily_quota_mb, blocked_domains, blocked_ips
            FROM users
            WHERE is_active = true 
              AND plaintext_password IS NOT NULL 
              AND plaintext_password != ''
        """)
        users = cur.fetchall()

        print(f"Found {len(users)} active user(s) in database")

        config = """# 3proxy configuration - Auto-generated
log /var/log/3proxy/3proxy.log D
logformat "- %N.%p %E %U %C:%c %R:%r %O %I %h %T"
maxconn 1000
nscache 65536
timeouts 1 5 30 60 180 1800 15 60

# DNS Resolvers (required for domain blocking)
nserver 8.8.8.8
nserver 8.8.4.4
nscache 65536

# Authentication
auth strong

# Users
"""

        # Add users
        for user in users:
            username, password, speed_limit, quota, blocked_domains, blocked_ips = user
            if password:
                print(f"  → Adding user: {username}")
                config += f"users {username}:CL:{password}\n"

        # Bandwidth limits and ACLs
        config += "\n# Access control and limits\n"
        
        for user in users:
            username, _, speed_limit, _, blocked_domains, blocked_ips = user
            
            # Speed limit (KB/s to Bytes/s)
            if speed_limit and speed_limit > 0:
                bytes_per_sec = speed_limit * 1024
                config += f"bandlimin {bytes_per_sec} {username}\n"
                config += f"bandlimout {bytes_per_sec} {username}\n"
            
            # Blocked domains
            if blocked_domains:
                for domain in [d.strip() for d in blocked_domains.split(',') if d.strip()]:
                    config += f"deny {username} * {domain}\n"
            
            # Blocked IPs
            if blocked_ips:
                for ip in [ip.strip() for ip in blocked_ips.split(',') if ip.strip()]:
                    config += f"deny {username} * {ip}\n"

        config += "allow *\n"

        config += "\n# SOCKS5 Proxy Service\n"
        config += "socks -p3389\n"

        # Write config
        os.makedirs('/etc/3proxy', exist_ok=True)
        with open('/etc/3proxy/3proxy.cfg', 'w') as f:
            f.write(config.strip() + "\n")

        print("Configuration generated successfully")
        cur.close()
        conn.close()
        return True

    except Exception as e:
        print(f"Error generating config: {e}")
        return False


if __name__ == "__main__":
    if wait_for_db():
        if generate_config():
            sys.exit(0)
        else:
            sys.exit(1)
    else:
        sys.exit(1)