import traceback
import logging
from pathlib import Path

try:
    import urllib2
except ImportError:
    pass

import socket
import json
import errno
#from typing import TypeVar

from uwsgi_tasks import set_uwsgi_callbacks
set_uwsgi_callbacks()
# from uwsgiconf import uwsgi

from platformdirs import (
    user_data_dir, 
    site_runtime_dir,
    user_config_dir,
    user_log_dir,
)

# PathLike = TypeVar("PathLike", str, Path, None)

logger = logging.getLogger(__name__)


__app_name__ = "PikeSquares"
__version__ = "0.4.6"

(
    SUCCESS,
    DIR_ERROR,
    FILE_ERROR,
    DB_READ_ERROR,
    DB_WRITE_ERROR,
    JSON_ERROR,
    ID_ERROR,
) = range(7)

ERRORS = {
    DIR_ERROR: "config directory error",
    FILE_ERROR: "config file error",
    DB_READ_ERROR: "database read error",
    DB_WRITE_ERROR: "database write error",
    ID_ERROR: "to-do id error",
}

APP_NAME = "pikesquares"
DEFAULT_DATA_DIR = Path(user_data_dir(APP_NAME, ensure_exists=True))
DEFAULT_LOG_DIR = Path(user_log_dir(APP_NAME, ensure_exists=True))
DEFAULT_RUN_DIR = Path(site_runtime_dir(APP_NAME, ensure_exists=True))
DEFAULT_CONFIG_DIR = Path(user_config_dir(APP_NAME, ensure_exists=True))


def get_first_available_port(port: int = 5500) -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        if s.connect_ex(("localhost", port)) == 0:
            return get_first_available_port(port=port + 1)
        else:
            return port


def is_port_open(port: int, ip: str = "127.0.0.1") -> bool:
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.settimeout(5)
    try:
        is_open = s.connect_ex((ip, port)) == 0 # True if open, False if not
        if is_open:
            s.shutdown(socket.SHUT_RDWR)
    except Exception:
        is_open = False
    s.close()
    return is_open


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
        #print('connection refused')
        pass
    except FileNotFoundError as e:
        #print(f"socket @ {addr} not available")
        pass
    except IOError as e:
        if e.errno != errno.EINTR:
            #uwsgi.log(f"socket @ {addr} not available")
            pass
    except Exception:
        print(traceback.format_exc())
    else:
        try:
            return json.loads(js)
        except json.JSONDecodeError:
            print(traceback.format_exc())
            print(js)

