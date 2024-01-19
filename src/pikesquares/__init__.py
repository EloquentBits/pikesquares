import logging

try:
    import urllib2
except ImportError:
    pass

import socket
import json
import errno
from pathlib import Path
from typing import TypeVar
import socket

from uwsgi_tasks import set_uwsgi_callbacks
set_uwsgi_callbacks()

from uwsgiconf import uwsgi

PathLike = TypeVar("PathLike", str, Path, None)

logger = logging.getLogger(__name__)


def get_first_available_port(port: int=5500) -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        if s.connect_ex(("localhost", port)) == 0:
            return get_first_available_port(port=port + 1)
        else:
            return port

def inet_addr(arg):
    sfamily = socket.AF_INET
    host, port = arg.rsplit(':', 1)
    addr = (host, int(port))
    return sfamily, addr, host

def unix_addr(arg):
    sfamily = socket.AF_UNIX
    addr = arg
    return sfamily, addr, socket.gethostname()

def abstract_unix_addr(arg):
    sfamily = socket.AF_UNIX
    addr = '\0' + arg[1:]
    return sfamily, addr, socket.gethostname()

def read_stats(stats_addr):
    js = ''
    http_stats = False
    #stats_addr = args.address

    if stats_addr.startswith('http://'):
        http_stats = True
        addr = stats_addr
        host = addr.split('//')[1].split(':')[0]
    elif ':' in stats_addr:
        sfamily, addr, host = inet_addr(stats_addr)
    elif stats_addr.startswith('@'):
        sfamily, addr, host = abstract_unix_addr(stats_addr)
    else:
        sfamily, addr, host = unix_addr(stats_addr)

    try:
        s = None
        if http_stats:
            r = urllib2.urlopen(addr)
            js = r.read().decode('utf8', 'ignore')
        else:
            s = socket.socket(sfamily, socket.SOCK_STREAM)
            s.connect(addr)
        while True:
            data = s.recv(4096)
            if len(data) < 1:
                break
            js += data.decode('utf8', 'ignore')
        if s:
            s.close()
    except ConnectionRefusedError as e:
        uwsgi.log('connection refused')
    except FileNotFoundError as e:
        uwsgi.log(f"socket @ {addr} not available")
    except IOError as e:
        if e.errno != errno.EINTR:
            uwsgi.log(f"socket @ {addr} not available")
    except:
        uwsgi.log("unable to get stats")
    else:
        try:
            print(js)
            return json.loads(js)
        except json.JSONDecodeError:
            pass

def get_service_status(service_id, client_config):
    stats_socket = (Path(client_config.RUN_DIR) / f"{service_id}-stats.sock")
    if stats_socket.exists() and stats_socket.is_socket():
        socket_path = str(stats_socket.resolve())
        socket_started = read_stats(socket_path) or None
        return 'running' if socket_started else 'stopped'

    print(f"invalid service [{service_id}] stats socket @ {str(stats_socket)}")




