"""Tiny TCP transport: newline-delimited JSON messages.

Reader threads push (kind, conn_id, payload) tuples onto an inbox queue that
the game loop drains each frame; kind is "connect", "msg" or "disconnect".
"""
import json
import queue
import socket
import threading

DEFAULT_PORT = 5555
MAX_LINE = 64 * 1024


class Connection:
    def __init__(self, sock, cid, inbox):
        self.sock = sock
        self.cid = cid
        self.inbox = inbox
        self.alive = True
        self._lock = threading.Lock()
        threading.Thread(target=self._reader, daemon=True).start()

    def _reader(self):
        try:
            f = self.sock.makefile("rb")
            while True:
                line = f.readline(MAX_LINE)
                if not line or not line.endswith(b"\n"):
                    break  # closed, or an over-long line
                try:
                    msg = json.loads(line)
                except ValueError:
                    continue
                if isinstance(msg, dict):
                    self.inbox.put(("msg", self.cid, msg))
        except OSError:
            pass
        finally:
            self.alive = False
            self.inbox.put(("disconnect", self.cid, None))

    def send(self, msg):
        data = (json.dumps(msg, separators=(",", ":")) + "\n").encode()
        with self._lock:
            try:
                self.sock.sendall(data)
            except OSError:
                self.alive = False

    def close(self):
        self.alive = False
        try:
            self.sock.shutdown(socket.SHUT_RDWR)
        except OSError:
            pass
        self.sock.close()


class Server:
    def __init__(self, port=DEFAULT_PORT):
        self.inbox = queue.Queue()
        self.sock = socket.create_server(("", port))
        self.port = self.sock.getsockname()[1]
        self.conns = {}
        self._lock = threading.Lock()
        self._next_id = 1
        self._open = True
        threading.Thread(target=self._accept_loop, daemon=True).start()

    def _accept_loop(self):
        while self._open:
            try:
                sock, addr = self.sock.accept()
            except OSError:
                return
            sock.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
            with self._lock:
                cid = self._next_id
                self._next_id += 1
                self.conns[cid] = Connection(sock, cid, self.inbox)
            self.inbox.put(("connect", cid, addr[0]))

    def send(self, cid, msg):
        with self._lock:
            conn = self.conns.get(cid)
        if conn:
            conn.send(msg)

    def broadcast(self, msg):
        with self._lock:
            conns = list(self.conns.values())
        for conn in conns:
            conn.send(msg)

    def drop(self, cid):
        with self._lock:
            conn = self.conns.pop(cid, None)
        if conn:
            conn.close()

    def close(self):
        self._open = False
        self.sock.close()
        with self._lock:
            conns, self.conns = list(self.conns.values()), {}
        for conn in conns:
            conn.close()


class Client:
    def __init__(self, host, port=DEFAULT_PORT, timeout=5.0):
        self.inbox = queue.Queue()
        sock = socket.create_connection((host, port), timeout=timeout)
        sock.settimeout(None)
        sock.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
        self.conn = Connection(sock, 0, self.inbox)

    def send(self, msg):
        self.conn.send(msg)

    def close(self):
        self.conn.close()


def local_ip():
    """Best guess at this machine's LAN address (a UDP connect sends no packets)."""
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        s.connect(("10.255.255.255", 1))
        return s.getsockname()[0]
    except OSError:
        return "127.0.0.1"
    finally:
        s.close()
