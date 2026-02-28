# -*- coding: utf-8 -*-
"""
Simple error information renderer for doxoade.
Human-readable, low-noise, zero dependency.
"""

import os
import sys
from traceback import print_tb

class DoxoadeError(Exception):
    """Base error for doxoade."""

    def show_error(exc: Exception, title: str = "ERROR") -> None:
        _, exc_obj, exc_tb = sys.exc_info()

        if exc_tb is None:
            print(f"\033[31m[{title}] {exc}\033[0m")
            return

        fname = os.path.split(exc_tb.tb_frame.f_code.co_filename)[1]
        line_number = exc_tb.tb_lineno

        print(
            f"\033[31m"
            f" ■ {title}\n"
            f" ■ File: {fname} | line: {line_number}\n"
            f" ■ Exception type: {type(exc).__name__}\n"
            f" ■ Exception value:\n"
            f"   >>> {'\n   >>> '.join(str(exc_obj).split())}\n"
            f"\033[0m"
        )

        print_tb(exc_tb)