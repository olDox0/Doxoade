# doxoade/tools/engine_daemon/launcher.py
import sys
import os
from doxoade.tools.engine_daemon.server import start_daemon

def main():
    try:
        start_daemon()
    except Exception as e:
        sys.exit(1)

if __name__ == '__main__':
    main()
