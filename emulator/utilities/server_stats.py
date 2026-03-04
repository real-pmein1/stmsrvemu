import os
import json
import time
from utilities.database import statistics_db

STATS_LOG = os.path.join('logs', 'server_stats.log')
os.makedirs('logs', exist_ok=True)

online_users = {}
user_tickets = {}
download_stats = {}
connection_tokens = {}


def _write_log(entry):
    with open(STATS_LOG, 'a') as f:
        f.write(json.dumps(entry) + '\n')


def mark_login(user_id, ip, ticket_hex, expires, game=None):
    """Record a successful login for the given user."""
    online_users[user_id] = {'ip': ip, 'last_seen': time.time(), 'expires': expires}
    user_tickets.setdefault(user_id, []).append({'ticket': ticket_hex, 'expires': expires})
    _write_log({'event': 'login', 'user_id': user_id, 'ip': ip, 'ticket': ticket_hex, 'expires': expires, 'game': game})
    if game:
        statistics_db.record_gameplay(game, user_id)


def mark_ticket_renew(user_id, ip):
    """Update the last seen time for an authenticated user."""
    if user_id in online_users:
        online_users[user_id]['last_seen'] = time.time()
        online_users[user_id]['ip'] = ip


def expire_old(max_age=3600):
    now = time.time()
    to_remove = [uid for uid, info in online_users.items()
                 if now - info['last_seen'] > max_age or info['expires'] < now]
    for uid in to_remove:
        del online_users[uid]
        _write_log({'event': 'offline', 'user_id': uid})


def expire_user_tickets(user_id):
    user_tickets[user_id] = []


def start_download(user_id, storage, server=None, game=None):
    download_stats[user_id] = {'storage': storage, 'start': time.time(), 'bytes': 0}
    _write_log({'event': 'download_start', 'user_id': user_id, 'storage': storage, 'game': game})
    if server:
        statistics_db.record_content_load(server, 'start')
    if game:
        statistics_db.record_gameplay(game, user_id)


def update_download(user_id, byte_count):
    if user_id in download_stats:
        download_stats[user_id]['bytes'] += byte_count


def finish_download(user_id, server=None):
    info = download_stats.pop(user_id, None)
    if info:
        duration = time.time() - info['start']
        _write_log({'event': 'download_end', 'user_id': user_id,
                    'storage': info['storage'],
                    'bytes': info['bytes'],
                    'duration': duration})
        if server:
            statistics_db.record_content_load(server, 'end')


def add_connection_token(user_id, token_hex, expires):
    """Track a new connection token for the user."""
    connection_tokens.setdefault(user_id, []).append({'token': token_hex, 'expires': expires})
    _write_log({'event': 'add_token', 'user_id': user_id, 'token': token_hex, 'expires': expires})


def revoke_connection_token(user_id, token_hex):
    """Remove a connection token from tracking."""
    tokens = connection_tokens.get(user_id, [])
    connection_tokens[user_id] = [t for t in tokens if t['token'] != token_hex]
    _write_log({'event': 'revoke_token', 'user_id': user_id, 'token': token_hex})


def list_connection_tokens(user_id):
    """Return active tokens for a user."""
    return connection_tokens.get(user_id, [])
