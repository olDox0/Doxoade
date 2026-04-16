# doxoade/commands_test/crash_bug.py
x = 10
y = 0

def calc(a, b):
    local_val = 50
    return a / b
calc(x, y)