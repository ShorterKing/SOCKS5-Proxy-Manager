// frontend/app.js
const API_BASE = '/api';

let currentUsers = [];
let proxyStatus = true;

// Check if user is authenticated
async function checkAuth() {
    try {
        const response = await fetch(`${API_BASE}/auth/check`, {
            credentials: 'include'
        });
        const data = await response.json();
        
        if (data.authenticated) {
            document.getElementById('login-page').style.display = 'none';
            document.getElementById('app-container').style.display = 'block';
            document.getElementById('admin-username-display').textContent = data.username;
            loadUsers();
            loadProxyStatus();
            checkServerStatus();
        } else {
            document.getElementById('login-page').style.display = 'flex';
            document.getElementById('app-container').style.display = 'none';
        }
    } catch (error) {
        document.getElementById('login-page').style.display = 'flex';
        document.getElementById('app-container').style.display = 'none';
    }
}

// Login function
async function login(event) {
    event.preventDefault();
    const username = document.getElementById('login-username').value;
    const password = document.getElementById('login-password').value;
    const errorDiv = document.getElementById('login-error');
    const submitBtn = event.target.querySelector('button[type="submit"]');

    submitBtn.disabled = true;
    submitBtn.textContent = 'Logging in...';

    try {
        const response = await fetch(`${API_BASE}/auth/login`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            credentials: 'include',
            body: JSON.stringify({ username, password })
        });

        const data = await response.json();

        if (response.ok) {
            checkAuth();
        } else {
            errorDiv.textContent = data.error || 'Invalid credentials';
            errorDiv.style.display = 'block';
            document.getElementById('login-password').value = '';
        }
    } catch (error) {
        errorDiv.textContent = 'Failed to connect to server';
        errorDiv.style.display = 'block';
    } finally {
        submitBtn.disabled = false;
        submitBtn.textContent = 'Login';
    }
}

// Logout function
async function logout() {
    if (confirm('Are you sure you want to logout?')) {
        try {
            await fetch(`${API_BASE}/auth/logout`, {
                method: 'POST',
                credentials: 'include'
            });
        } catch (error) {
            console.error('Logout error:', error);
        }
        checkAuth();
    }
}

// Check server status
function checkServerStatus() {
    fetch(`${API_BASE}/health`)
        .then(response => response.json())
        .then(data => {
            document.getElementById('server-status').textContent = '● Connected';
            document.getElementById('server-status').style.background = 'rgba(255,255,255,0.2)';
        })
        .catch(error => {
            document.getElementById('server-status').textContent = '● Disconnected';
            document.getElementById('server-status').style.background = 'rgba(220, 53, 69, 0.3)';
        });
}

// Load proxy status
async function loadProxyStatus() {
    try {
        const response = await fetch(`${API_BASE}/proxy/status`, {
            credentials: 'include'
        });
        const data = await response.json();
        proxyStatus = data.is_running;
        updateProxyStatusUI();
    } catch (error) {
        console.error('Failed to load proxy status:', error);
    }
}

function updateProxyStatusUI() {
    const statusElement = document.getElementById('proxy-status');
    const toggleBtn = document.getElementById('toggle-proxy-btn');
    
    if (proxyStatus) {
        statusElement.textContent = '● Running';
        statusElement.style.background = 'rgba(40, 167, 69, 0.3)';
        statusElement.style.color = '#28a745';
        toggleBtn.textContent = '⏸️ Stop Proxy';
        toggleBtn.className = 'btn btn-danger btn-sm';
    } else {
        statusElement.textContent = '● Stopped';
        statusElement.style.background = 'rgba(220, 53, 69, 0.3)';
        statusElement.style.color = '#dc3545';
        toggleBtn.textContent = '▶️ Start Proxy';
        toggleBtn.className = 'btn btn-success btn-sm';
    }
}

async function toggleProxy() {
    const newStatus = !proxyStatus;
    const confirmMsg = newStatus ? 
        'Are you sure you want to START the proxy service?' : 
        'Are you sure you want to STOP the proxy service? All users will be disconnected.';
    
    if (!confirm(confirmMsg)) {
        return;
    }

    try {
        const response = await fetch(`${API_BASE}/proxy/toggle`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            credentials: 'include',
            body: JSON.stringify({ is_running: newStatus })
        });

        if (response.ok) {
            proxyStatus = newStatus;
            updateProxyStatusUI();
            alert(`Proxy ${newStatus ? 'started' : 'stopped'} successfully!`);
        } else {
            alert('Failed to toggle proxy status');
        }
    } catch (error) {
        alert('Error: ' + error.message);
    }
}

// Tab switching
function showTab(tabName) {
    document.querySelectorAll('.tab-content').forEach(tab => {
        tab.classList.remove('active');
    });
    document.querySelectorAll('.tab-btn').forEach(btn => {
        btn.classList.remove('active');
    });

    document.getElementById(tabName + '-tab').classList.add('active');
    event.target.classList.add('active');

    if (tabName === 'users') loadUsers();
    if (tabName === 'stats') loadStats();
    if (tabName === 'logs') loadLogs();
    if (tabName === 'settings') loadSystemInfo();
}

// Change admin password
async function changePassword(event) {
    event.preventDefault();
    
    const currentPassword = document.getElementById('current-password').value;
    const newPassword = document.getElementById('new-password').value;
    const confirmPassword = document.getElementById('confirm-password').value;
    const messageDiv = document.getElementById('password-change-message');
    
    messageDiv.style.display = 'none';
    
    if (newPassword !== confirmPassword) {
        messageDiv.className = 'error-message';
        messageDiv.textContent = 'New passwords do not match!';
        messageDiv.style.display = 'block';
        return;
    }
    
    if (newPassword.length < 6) {
        messageDiv.className = 'error-message';
        messageDiv.textContent = 'Password must be at least 6 characters long!';
        messageDiv.style.display = 'block';
        return;
    }
    
    try {
        const response = await fetch(`${API_BASE}/auth/change-password`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            credentials: 'include',
            body: JSON.stringify({
                current_password: currentPassword,
                new_password: newPassword
            })
        });
        
        const data = await response.json();
        
        if (response.ok) {
            messageDiv.className = 'success-message';
            messageDiv.textContent = 'Password changed successfully!';
            messageDiv.style.display = 'block';
            document.getElementById('password-change-form').reset();
        } else {
            messageDiv.className = 'error-message';
            messageDiv.textContent = data.error || 'Failed to change password';
            messageDiv.style.display = 'block';
        }
    } catch (error) {
        messageDiv.className = 'error-message';
        messageDiv.textContent = 'Error: ' + error.message;
        messageDiv.style.display = 'block';
    }
}

// Load system info
async function loadSystemInfo() {
    const container = document.getElementById('system-info-container');
    
    try {
        const response = await fetch(`${API_BASE}/system/info`, {
            credentials: 'include'
        });
        const info = await response.json();
        
        container.innerHTML = `
            <div class="info-item">
                <span class="info-label">CPU Usage:</span>
                <span class="info-value">${info.cpu_usage}%</span>
            </div>
            <div class="info-item">
                <span class="info-label">Memory:</span>
                <span class="info-value">${(info.memory.used / 1024 / 1024).toFixed(0)}MB / ${(info.memory.total / 1024 / 1024).toFixed(0)}MB (${info.memory.percent}%)</span>
            </div>
            <div class="info-item">
                <span class="info-label">Load Average:</span>
                <span class="info-value">${info.load_avg.map(l => l.toFixed(2)).join(', ')}</span>
            </div>
            <div class="info-item">
                <span class="info-label">Uptime:</span>
                <span class="info-value">${formatUptime(info.uptime)}</span>
            </div>
            <div class="info-item">
                <span class="info-label">SOCKS5 Port:</span>
                <span class="info-value">3389</span>
            </div>
        `;
    } catch (error) {
        container.innerHTML = `<div class="error-message">Failed to load system info: ${error.message}</div>`;
    }
}

function formatUptime(seconds) {
    const days = Math.floor(seconds / (24 * 3600));
    seconds %= (24 * 3600);
    const hours = Math.floor(seconds / 3600);
    seconds %= 3600;
    const minutes = Math.floor(seconds / 60);
    
    let parts = [];
    if (days > 0) parts.push(`${days}d`);
    if (hours > 0) parts.push(`${hours}h`);
    if (minutes > 0) parts.push(`${minutes}m`);
    
    return parts.join(' ') || '< 1m';
}

// Load users
async function loadUsers() {
    const container = document.getElementById('users-list');
    container.innerHTML = '<div class="loading">Loading users...</div>';

    try {
        const response = await fetch(`${API_BASE}/users`, {
            credentials: 'include'
        });
        
        if (!response.ok) {
            throw new Error('Failed to fetch users');
        }
        
        const users = await response.json();
        currentUsers = users;

        if (users.length === 0) {
            container.innerHTML = '<div class="loading">No users found. Add your first user!</div>';
            return;
        }

        container.innerHTML = users.map(user => `
            <div class="user-card ${user.is_active ? '' : 'inactive'}">
                <div class="user-header">
                    <h3>👤 ${user.username}</h3>
                    <span class="user-status ${user.is_active ? 'active' : 'inactive'}">
                        ${user.is_active ? 'Active' : 'Inactive'}
                    </span>
                </div>
                <div class="user-info">
                    <div class="user-info-item">
                        <span class="user-info-label">Speed Limit:</span>
                        <span class="user-info-value">
                            ${user.speed_limit_kbps > 0 ? user.speed_limit_kbps + ' KB/s' : 'Unlimited'}
                        </span>
                    </div>
                    <div class="user-info-item">
                        <span class="user-info-label">Daily Quota:</span>
                        <span class="user-info-value">
                            ${user.daily_quota_mb > 0 ? user.daily_quota_mb + ' MB' : 'Unlimited'}
                        </span>
                    </div>
                    <div class="user-info-item">
                        <span class="user-info-label">Blocked Domains:</span>
                        <span class="user-info-value">
                            ${user.blocked_domains || 'None'}
                        </span>
                    </div>
                    <div class="user-info-item">
                        <span class="user-info-label">Blocked IPs:</span>
                        <span class="user-info-value">
                            ${user.blocked_ips || 'None'}
                        </span>
                    </div>
                </div>
                <div class="user-actions">
                    <button class="btn btn-edit" onclick="editUser(${user.id})">✏️ Edit</button>
                    <button class="btn ${user.is_active ? 'btn-secondary' : 'btn-primary'}"
                            onclick="toggleUserStatus(${user.id}, ${!user.is_active})">
                        ${user.is_active ? '⏸️ Disable' : '▶️ Enable'}
                    </button>
                    <button class="btn btn-danger" onclick="deleteUser(${user.id})">🗑️ Delete</button>
                </div>
            </div>
        `).join('');

        updateLogFilter(users);

    } catch (error) {
        if (error.message.includes('401')) {
            checkAuth();
        } else {
            container.innerHTML = '<div class="error-message">Failed to load users: ' + error.message + '</div>';
        }
    }
}

function updateLogFilter(users) {
    const select = document.getElementById('log-user-filter');
    select.innerHTML = '<option value="">All Users</option>' +
        users.map(u => `<option value="${u.username}">${u.username}</option>`).join('');
}

function showAddUserModal() {
    document.getElementById('modal-title').textContent = 'Add New User';
    document.getElementById('user-form').reset();
    document.getElementById('user-id').value = '';
    document.getElementById('username').disabled = false;
    document.getElementById('password').required = true;
    document.getElementById('password').placeholder = '';
    document.getElementById('user-modal').style.display = 'block';
}

function editUser(userId) {
    const user = currentUsers.find(u => u.id === userId);
    if (!user) return;

    document.getElementById('modal-title').textContent = 'Edit User';
    document.getElementById('user-id').value = user.id;
    document.getElementById('username').value = user.username;
    document.getElementById('username').disabled = true;
    document.getElementById('password').required = false;
    document.getElementById('password').placeholder = 'Leave blank to keep current password';
    document.getElementById('speed-limit').value = user.speed_limit_kbps || 0;
    document.getElementById('daily-quota').value = user.daily_quota_mb || 0;
    document.getElementById('blocked-domains').value = user.blocked_domains || '';
    document.getElementById('blocked-ips').value = user.blocked_ips || '';

    document.getElementById('user-modal').style.display = 'block';
}

function closeModal() {
    document.getElementById('user-modal').style.display = 'none';
}

async function saveUser(event) {
    event.preventDefault();

    const userId = document.getElementById('user-id').value;
    const userData = {
        username: document.getElementById('username').value,
        speed_limit_kbps: parseInt(document.getElementById('speed-limit').value) || 0,
        daily_quota_mb: parseInt(document.getElementById('daily-quota').value) || 0,
        blocked_domains: document.getElementById('blocked-domains').value,
        blocked_ips: document.getElementById('blocked-ips').value
    };

    const password = document.getElementById('password').value;
    if (password) {
        userData.password = password;
    } else if (!userId) {
        alert('Password is required for new users');
        return;
    }

    try {
        let response;
        if (userId) {
            response = await fetch(`${API_BASE}/users/${userId}`, {
                method: 'PUT',
                headers: { 'Content-Type': 'application/json' },
                credentials: 'include',
                body: JSON.stringify(userData)
            });
        } else {
            response = await fetch(`${API_BASE}/users`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                credentials: 'include',
                body: JSON.stringify(userData)
            });
        }

        if (response.ok) {
            closeModal();
            loadUsers();
            alert(userId ? 'User updated successfully!' : 'User created successfully!');
        } else {
            const error = await response.json();
            alert('Error: ' + error.error);
        }
    } catch (error) {
        alert('Failed to save user: ' + error.message);
    }
}

async function toggleUserStatus(userId, newStatus) {
    try {
        const response = await fetch(`${API_BASE}/users/${userId}`, {
            method: 'PUT',
            headers: { 'Content-Type': 'application/json' },
            credentials: 'include',
            body: JSON.stringify({ is_active: newStatus })
        });

        if (response.ok) {
            loadUsers();
        } else {
            alert('Failed to update user status');
        }
    } catch (error) {
        alert('Error: ' + error.message);
    }
}

async function deleteUser(userId) {
    if (!confirm('Are you sure you want to delete this user? This action cannot be undone.')) {
        return;
    }

    try {
        const response = await fetch(`${API_BASE}/users/${userId}`, {
            method: 'DELETE',
            credentials: 'include'
        });

        if (response.ok) {
            loadUsers();
            alert('User deleted successfully!');
        } else {
            alert('Failed to delete user');
        }
    } catch (error) {
        alert('Error: ' + error.message);
    }
}

async function loadStats() {
    const container = document.getElementById('stats-list');
    container.innerHTML = '<div class="loading">Loading statistics...</div>';

    try {
        const response = await fetch(`${API_BASE}/stats/usage`, {
            credentials: 'include'
        });
        const stats = await response.json();

        if (stats.length === 0) {
            container.innerHTML = '<div class="loading">No usage data available yet.</div>';
            return;
        }

        container.innerHTML = stats.map(stat => `
            <div class="stat-card">
                <h3>${stat.username}</h3>
                <div class="stat-value">${stat.used_mb.toFixed(2)} MB</div>
            </div>
        `).join('');

    } catch (error) {
        container.innerHTML = '<div class="error-message">Failed to load statistics: ' + error.message + '</div>';
    }
}

async function loadLogs() {
    const container = document.getElementById('logs-list');
    const username = document.getElementById('log-user-filter').value;

    container.innerHTML = '<div class="loading">Loading logs...</div>';

    try {
        const url = username ? `${API_BASE}/logs?username=${username}&limit=50` : `${API_BASE}/logs?limit=50`;
        const response = await fetch(url, {
            credentials: 'include'
        });
        const logs = await response.json();

        if (logs.length === 0) {
            container.innerHTML = '<div class="loading">No logs found.</div>';
            return;
        }

        container.innerHTML = logs.map(log => `
            <div class="log-entry">
                <div class="log-entry-header">
                    <span>👤 ${log.username}</span>
                    <span>🕒 ${new Date(log.timestamp).toLocaleString()}</span>
                </div>
                <div class="log-entry-details">
                    <div>📍 Source: ${log.source_ip || 'N/A'}</div>
                    <div>🎯 Destination: ${log.destination_ip || 'N/A'}</div>
                    <div>🌐 Domain: ${log.destination_domain || 'N/A'}</div>
                    <div>📊 Traffic: ↑${formatBytes(log.bytes_sent)} ↓${formatBytes(log.bytes_received)}</div>
                </div>
            </div>
        `).join('');

    } catch (error) {
        container.innerHTML = '<div class="error-message">Failed to load logs: ' + error.message + '</div>';
    }
}

function formatBytes(bytes) {
    if (bytes === 0) return '0 B';
    const k = 1024;
    const sizes = ['B', 'KB', 'MB', 'GB'];
    const i = Math.floor(Math.log(bytes) / Math.log(k));
    return parseFloat((bytes / Math.pow(k, i)).toFixed(2)) + ' ' + sizes[i];
}

window.onclick = function(event) {
    const modal = document.getElementById('user-modal');
    if (event.target === modal) {
        closeModal();
    }
}

// Initialize on page load
document.addEventListener('DOMContentLoaded', function() {
    checkAuth();
    // Refresh proxy status every 30 seconds
    setInterval(loadProxyStatus, 30000);
});
