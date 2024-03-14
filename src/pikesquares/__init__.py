import traceback
import sys
import os
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

from tinydb import TinyDB, Query
from uwsgi_tasks import set_uwsgi_callbacks
set_uwsgi_callbacks()
from uwsgiconf import uwsgi

from pikesquares.cli import console
from .conf import ClientConfig

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
    sfamily = None
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
        print('connection refused')
    except FileNotFoundError as e:
        print(f"socket @ {addr} not available")
    except IOError as e:
        if e.errno != errno.EINTR:
            uwsgi.log(f"socket @ {addr} not available")
    except Exception:
        print(traceback.format_exc())
    else:
        try:
            return json.loads(js)
        except json.JSONDecodeError:
            print(traceback.format_exc())
            print(js)

def get_service_status(stats_address: Path):
    """
    read stats socket
    """
    if stats_address.exists() and stats_address.is_socket():
        return 'running' if read_stats(
            str(stats_address)
        ) else 'stopped'

def load_client_conf():
    """
    read TinyDB json
    """

    data_dir = Path(os.environ.get("PIKESQUARES_DATA_DIR", ""))
    if not (Path(data_dir) / "device-db.json").exists():
        console.warning(f"conf db does not exist @ {data_dir}/device-db.json")
        return

    conf_mapping = {}
    pikesquares_version = os.environ.get("PIKESQUARES_VERSION")
    with TinyDB(data_dir / "device-db.json") as db:
        try:
            conf_mapping = db.table('configs').\
                search(Query().version == pikesquares_version)[0]
        except IndexError:
            console.warning(f"unable to load v{pikesquares_version} conf from {str(data_dir)}/device-db.json")
            return

    return ClientConfig(**conf_mapping)


def write_master_fifo(fifo_file, command):
    """
    Write command to master fifo named pipe

    ‘0’ to ‘9’ - set the fifo slot (see below)
    ‘+’ - increase the number of workers when in cheaper mode (add --cheaper-algo manual for full control)
    ‘-’ - decrease the number of workers when in cheaper mode (add --cheaper-algo manual for full control)
    ‘B’ - ask Emperor for reinforcement (broodlord mode, requires uWSGI >= 2.0.7)
    ‘C’ - set cheap mode
    ‘c’ - trigger chain reload
    ‘E’ - trigger an Emperor rescan
    ‘f’ - re-fork the master (dangerous, but very powerful)
    ‘l’ - reopen log file (need –log-master and –logto/–logto2)
    ‘L’ - trigger log rotation (need –log-master and –logto/–logto2)
    ‘p’ - pause/resume the instance
    ‘P’ - update pidfiles (can be useful after master re-fork)
    ‘Q’ - brutally shutdown the instance
    ‘q’ - gracefully shutdown the instance
    ‘R’ - send brutal reload
    ‘r’ - send graceful reload
    ‘S’ - block/unblock subscriptions
    ‘s’ - print stats in the logs
    ‘W’ - brutally reload workers
    ‘w’ - gracefully reload workers
    """

    if not command in ["r", "q", "s"]:
        console.warning("unknown master fifo command '{command}'")
        return

    with open(fifo_file, "w") as master_fifo:
       master_fifo.write(command)
