import socket
import sys
from pathlib import Path
import pytest

sys.path.insert(0, str(Path.cwd()))
original_connect = socket.socket.connect


def local_socketpair():
    listener = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    listener.bind(("127.0.0.1", 0))
    listener.listen(1)
    client = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    try:
        original_connect(client, listener.getsockname())
        server, _ = listener.accept()
        return server, client
    except BaseException:
        client.close()
        raise
    finally:
        listener.close()
def blocked(*args, **kwargs):
    raise OSError('network disabled for isolated phase3 tests')

socket.socket.connect = blocked
socket.socket.connect_ex = blocked
socket.create_connection = blocked
socket.socketpair = local_socketpair
raise SystemExit(pytest.main(sys.argv[1:]))
