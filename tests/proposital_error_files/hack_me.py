# tests/proposital_error_files/hack_me.py
import os
import sys

if not os.environ.get("DOXOADE_AUTHORIZED_RUN"):
    print("FATAL: Unauthorized execution. This file is part of a security test lab.")
    sys.exit(1)

user_input = input("Enter something: ")
exec(user_input) # noqa