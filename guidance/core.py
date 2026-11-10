#!/usr/bin/env python3
"""Local, manual guidance interface. Python standard library only."""
import csv
import io
import json
import os
import secrets
import threading
import time
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler
from pathlib import Path
from urllib.parse import parse_qs, urlsplit
import uuid


WEB = Path(__file__).with_name('web')
ASSETS = {
    '/operator': ('operator.html', 'text/html; charset=utf-8'),
    '/student': ('student.html', 'text/html; charset=utf-8'),
    '/style.css': ('style.css', 'text/css; charset=utf-8'),
    '/common.js': ('common.js', 'text/javascript; charset=utf-8'),
    '/operator.js': ('operator.js', 'text/javascript; charset=utf-8'),
    '/student.js': ('student.js', 'text/javascript; charset=utf-8'),
}


class Session:
    def __init__(self, root, group, origin):
        self.lock = threading.RLock()
        self.started = time.monotonic()
        self.session_id = datetime.now().strftime('%Y%m%d_%H%M%S_') + secrets.token_hex(3)
        self.folder = root / self.session_id
        self.folder.mkdir(mode=0o700, parents=True, exist_ok=False)
        self.group = group
        self.origin = origin
        self.operator_token = secrets.token_urlsafe(32)
        self.student_token = secrets.token_urlsafe(32)
        self.active = True
        self.messages = []
        self.requests = {}
        self.clients = {}
        self.csv_error = None
        self.log('session_started', {'group': self.group})
        self.persist_recap()

    def link(self, role):
        token = self.operator_token if role == 'operator' else self.student_token
        return f'{self.origin}/{role}#token={token}'

    def stamp(self):
        return {'utc': datetime.now(timezone.utc).isoformat(timespec='milliseconds'),
                'elapsed_s': round(time.monotonic() - self.started, 3)}

    def log(self, event, fields):
        record = {'session_id': self.session_id, 'event': event, **self.stamp(), **fields}
        with (self.folder / 'events.jsonl').open('a', encoding='utf-8') as file:
            file.write(json.dumps(record, ensure_ascii=False) + '\n')
            file.flush()
            os.fsync(file.fileno())
        return record

    def end(self):
        with self.lock:
            if self.active:
                self.log('session_ended', {})
                self.active = False
            self.persist_recap()

    def state(self, operator=False):
        with self.lock:
            state = {'session_id': self.session_id, 'group': self.group, 'active': self.active,
                     'elapsed_s': self.stamp()['elapsed_s']}
            if operator:
                state.update(messages=self.messages,
                    csv_saved=self.csv_error is None,
                    online_clients=sum(time.monotonic()-t < 5 for t in self.clients.values()),
                    student_url=self.link('student'))
            else:
                state['messages'] = [{k: m[k] for k in ('id', 'text', 'priority', 'sent_utc', 'sent_elapsed_s')}
                                     for m in self.messages]
            # Take a snapshot before releasing the lock.
            return json.loads(json.dumps(state))

    def persist_recap(self):
        """Replace the CSV snapshot atomically; the fsynced journal is primary."""
        with self.lock:
            temporary = self.folder / 'guidance_recap.csv.tmp'
            try:
                with temporary.open('wb') as file:
                    file.write(self.export())
                    file.flush()
                    os.fsync(file.fileno())
                temporary.replace(self.folder / 'guidance_recap.csv')
                self.csv_error = None
                return True
            except OSError as error:
                self.csv_error = str(error)
                print(f'CSV save warning: {error}. Guidance events remain in events.jsonl.', flush=True)
                return False

    def export(self):
        with self.lock:
            output = io.StringIO(newline='')
            writer = csv.writer(output)
            writer.writerow(['session_id', 'message_id', 'sent_utc', 'sent_elapsed_s',
                             'text', 'category', 'operator_note', 'priority', 'first_displayed_utc',
                             'first_displayed_elapsed_s', 'display_confirmations'])
            def cell(value):
                # Prevent spreadsheet formulas if free text begins with a formula character.
                return "'" + value if isinstance(value, str) and value.lstrip().startswith(('=', '+', '-', '@')) else value
            for message in self.messages:
                first = message['deliveries'][0] if message['deliveries'] else {}
                writer.writerow([cell(v) for v in [self.session_id, message['id'],
                    message['sent_utc'], message['sent_elapsed_s'], message['text'],
                    message['category'], message['operator_note'], message['priority'], first.get('displayed_utc', ''),
                    first.get('displayed_elapsed_s', ''), len(message['deliveries'])]])
            return output.getvalue().encode('utf-8-sig')


class Handler(BaseHTTPRequestHandler):
    server_version = 'GuidanceOnly/1.0'
    timeout = 8

    def log_message(self, *args):
        pass

    @property
    def session(self):
        return self.server.session

    def reply(self, status, data, mime='application/json; charset=utf-8', attachment=None):
        if not isinstance(data, bytes):
            data = (json.dumps(data, ensure_ascii=False) if mime.startswith('application/json') else data).encode('utf-8')
        self.send_response(status)
        self.send_header('Content-Type', mime)
        self.send_header('Content-Length', str(len(data)))
        self.send_header('Cache-Control', 'no-store')
        self.send_header('Referrer-Policy', 'no-referrer')
        self.send_header('X-Content-Type-Options', 'nosniff')
        self.send_header('X-Frame-Options', 'DENY')
        self.send_header('Content-Security-Policy', "default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline'; connect-src 'self'; frame-ancestors 'none'; base-uri 'none'")
        if attachment:
            self.send_header('Content-Disposition', f'attachment; filename="{attachment}"')
        self.end_headers()
        try:
            self.wfile.write(data)
        except (BrokenPipeError, ConnectionResetError, TimeoutError):
            pass

    def authorized(self, role):
        token = self.session.operator_token if role == 'operator' else self.session.student_token
        provided = self.headers.get('Authorization', '')
        return provided.isascii() and secrets.compare_digest(provided, f'Bearer {token}')

    def do_GET(self):
        url = urlsplit(self.path)
        query = parse_qs(url.query)
        if url.path in ASSETS:
            filename, mime = ASSETS[url.path]
            return self.reply(200, (WEB / filename).read_bytes(), mime)
        if url.path in ('/api/operator', '/api/export'):
            if not self.authorized('operator'):
                return self.reply(403, {'error': 'Operator access required.'})
            if url.path == '/api/export':
                return self.reply(200, self.session.export(), 'text/csv; charset=utf-8', 'guidance_recap.csv')
            return self.reply(200, self.session.state(operator=True))
        if url.path == '/api/student':
            if not self.authorized('student'):
                return self.reply(403, {'error': 'Student access required.'})
            client = query.get('client_id', [''])[0]
            if not client or len(client) > 100:
                return self.reply(400, {'error': 'Invalid client identifier.'})
            with self.session.lock:
                self.session.clients[client] = time.monotonic()
            return self.reply(200, self.session.state())
        return self.reply(404, {'error': 'Not found.'})

    def do_POST(self):
        # Browser requests must originate from this server, not another website.
        if self.headers.get('Origin') != self.session.origin:
            return self.reply(403, {'error': 'Same-origin browser request required.'})
        path = urlsplit(self.path).path
        roles = {'/api/send': 'operator', '/api/displayed': 'student'}
        if path not in roles:
            return self.reply(404, {'error': 'Not found.'})
        if not self.authorized(roles[path]):
            return self.reply(403, {'error': 'Invalid session credentials.'})
        try:
            if self.headers.get_content_type() != 'application/json':
                return self.reply(415, {'error': 'JSON required.'})
            length = int(self.headers.get('Content-Length', '0'))
            if not 0 < length <= 55000:
                raise ValueError('Invalid body size.')
            data = json.loads(self.rfile.read(length))
            if not isinstance(data, dict):
                raise ValueError('Expected an object.')
        except (ValueError, UnicodeError):
            return self.reply(400, {'error': 'Invalid request.'})
        try:
            with self.session.lock:
                status, payload = self.record_message(data) if path == '/api/send' else self.record_display(data)
        except OSError as error:
            print(f'Group {self.session.group} journal write failed: {error}', flush=True)
            return self.reply(503, {'error': 'Écriture du journal impossible sur le Mac hôte.'})
        return self.reply(status, payload)

    def record_message(self, data):
        request = data.get('request_id', '')
        if not isinstance(request, str) or not 1 <= len(request) <= 100:
            return 400, {'error': 'Invalid request identifier.'}
        if request in self.session.requests:
            self.session.persist_recap()
            return 200, {'message_id': self.session.requests[request]}
        if not self.session.active:
            return 409, {'error': 'Session terminée. Relancez le serveur pour une nouvelle session.'}
        text, note = data.get('text', ''), data.get('operator_note', '')
        category = data.get('category', 'unspecified')
        if not isinstance(text, str) or not 1 <= len(text.strip()) <= 2000 or not isinstance(note, str) or len(note) > 2000:
            return 400, {'error': 'Message ou note invalide.'}
        try:
            text.encode('utf-8')
            note.encode('utf-8')
        except UnicodeError:
            return 400, {'error': 'Message ou note invalide.'}
        if category not in ('unspecified', 'uncertainty', 'data_quality', 'alternatives', 'next_step', 'other'):
            return 400, {'error': 'Catégorie invalide.'}
        priority = data.get('priority', False)
        if not isinstance(priority, bool):
            return 400, {'error': 'Priorité invalide.'}
        message_id = str(uuid.uuid4())
        event = self.session.log('guidance_sent', {'message_id': message_id,
            'text': text.strip(), 'category': category, 'priority': priority, 'operator_note': note.strip()})
        self.session.messages.append({'id': message_id, 'text': text.strip(),
            'category': category, 'priority': priority, 'operator_note': note.strip(), 'sent_utc': event['utc'],
            'sent_elapsed_s': event['elapsed_s'], 'deliveries': []})
        self.session.requests[request] = message_id
        self.session.persist_recap()
        return 200, {'message_id': message_id}

    def record_display(self, data):
        client, message_id = data.get('client_id'), data.get('message_id')
        if not isinstance(client, str) or not client.isascii() or not 1 <= len(client) <= 100:
            return 400, {'error': 'Invalid client identifier.'}
        message = next((m for m in self.session.messages if m['id'] == message_id), None)
        if message is None:
            return 404, {'error': 'Unknown message.'}
        if not any(d['client_id'] == client for d in message['deliveries']):
            event = self.session.log('guidance_display_confirmed', {'message_id': message_id, 'client_id': client})
            message['deliveries'].append({'client_id': client,
                'displayed_utc': event['utc'], 'displayed_elapsed_s': event['elapsed_s']})
        self.session.persist_recap()
        return 200, {'ok': True}
