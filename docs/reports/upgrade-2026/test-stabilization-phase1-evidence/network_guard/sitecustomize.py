"""Block socket connections in the pytest process and inherited Python children."""
import socket
import threading

_original_connect = socket.socket.connect
_original_socketpair = socket.socketpair
_local = threading.local()

def _connect(sock, address):
    # Windows implements socketpair over a private loopback listener.
    if getattr(_local, "creating_socketpair", False):
        return _original_connect(sock, address)
    raise OSError("Outbound socket connections disabled for isolated tests")


def _connect_ex(*args, **kwargs):
    raise OSError("Outbound socket connections disabled for isolated tests")


def _socketpair(*args, **kwargs):
    _local.creating_socketpair = True
    try:
        return _original_socketpair(*args, **kwargs)
    finally:
        _local.creating_socketpair = False


socket.socket.connect = _connect
socket.socket.connect_ex = _connect_ex
socket.socketpair = _socketpair
