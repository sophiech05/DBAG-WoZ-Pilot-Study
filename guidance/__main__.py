"""Launch three independent guidance sessions from one terminal."""
import argparse
from contextlib import ExitStack
from http.server import ThreadingHTTPServer
from pathlib import Path
import queue
import re
import shutil
import signal
import subprocess
import threading
import time

from .core import Handler, Session


TUNNEL_URL = re.compile(r'https://[a-z0-9-]+\.trycloudflare\.com\b')


def stop_tunnel(process):
    if process.poll() is None:
        process.terminate()
        try:
            process.wait(timeout=5)
        except subprocess.TimeoutExpired:
            process.kill()
            process.wait()


def start_tunnel(executable, target, stack):
    process = subprocess.Popen(
        [executable, 'tunnel', '--url', target],
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        start_new_session=True,
    )
    stack.callback(stop_tunnel, process)
    urls = queue.Queue()
    recent_lines = []

    def read_output():
        found = False
        with process.stdout:
            for line in process.stdout:
                recent_lines.append(line.strip())
                if len(recent_lines) > 8:
                    recent_lines.pop(0)
                match = TUNNEL_URL.search(line)
                if match and not found:
                    urls.put(match.group())
                    found = True
        urls.put(None)

    reader = threading.Thread(target=read_output, daemon=True)
    reader.start()
    try:
        origin = urls.get(timeout=60)
    except queue.Empty:
        origin = None
    if origin is None:
        details = '\n'.join(recent_lines)
        raise RuntimeError(f'cloudflared did not provide a URL for {target}.\n{details}')
    return origin, process


def stop_server(server, thread):
    server.shutdown()
    thread.join()
    server.server_close()
    session = server.session
    session.end()
    recap = session.folder / 'guidance_recap.csv'
    if session.csv_error:
        print(f'Group {session.group} CSV save failed. Journal: {session.folder / "events.jsonl"}', flush=True)
    else:
        print(f'Group {session.group} saved: {recap}', flush=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--local', action='store_true', help='Use local browser links for a rehearsal.')
    parser.add_argument('--data-dir', type=Path, default=Path('guidance_sessions'))
    args = parser.parse_args()
    executable = shutil.which('cloudflared') if not args.local else None
    if not args.local and not executable:
        parser.error('Install cloudflared on this Mac (brew install cloudflared), or use --local.')

    def interrupt(_signum, _frame):
        raise KeyboardInterrupt

    signal.signal(signal.SIGTERM, interrupt)
    try:
        with ExitStack() as stack:
            servers = [
                stack.enter_context(ThreadingHTTPServer(('127.0.0.1', 0), Handler))
                for _ in range(3)
            ]
            tunnels = {}
            for group, server in enumerate(servers, 1):
                print(f'Starting group {group}…', flush=True)
                local = f'http://127.0.0.1:{server.server_port}'
                origin = local
                if executable:
                    origin, tunnels[group] = start_tunnel(executable, local, stack)
                session = Session(args.data_dir.resolve() / f'group-{group}', group, origin)
                server.session = session
                server.daemon_threads = False
                thread = threading.Thread(target=server.serve_forever)
                thread.start()
                stack.callback(stop_server, server, thread)

            for server in servers:
                session = server.session
                print(f'\nGroup {session.group}', flush=True)
                print(f'  Operator: {session.link("operator")}', flush=True)
                print(f'  Students: {session.link("student")}', flush=True)
            print('\nKeep this terminal open. Press Control+C to save and stop all three sessions.', flush=True)
            while True:
                time.sleep(1)
                for group, process in list(tunnels.items()):
                    if process.poll() is not None:
                        print(f'Group {group} tunnel stopped. Its recap will be saved with the others.', flush=True)
                        del tunnels[group]
    except KeyboardInterrupt:
        return
    except (RuntimeError, OSError) as error:
        parser.exit(1, f'Could not run guidance sessions: {error}\n')


if __name__ == '__main__':
    main()
