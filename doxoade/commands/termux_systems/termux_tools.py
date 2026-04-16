# doxoade/doxoade/commands/termux_systems/termux_tools.py
def setup_extra_keys():
    import os
    termux_dir = os.path.expanduser('~/.termux')
    prop_file = os.path.join(termux_dir, 'termux.properties')
    os.makedirs(termux_dir, exist_ok=True)
    extra_keys_value = "extra-keys = [['ESC','SHIFT' ,'/','*',';','HOME','UP','END','PGUP'],['TAB','CTRL','ALT','LEFT','DOWN','RIGHT','PGDN'],['(',')','{','}','+','-',]]"
    lines = []
    if os.path.exists(prop_file):
        with open(prop_file, 'r', encoding='utf-8') as f:
            lines = f.readlines()
    import re
    new_lines = [line for line in lines if not re.match('^\\s*#?\\s*extra-keys\\s*=', line)]
    if new_lines and (not new_lines[-1].endswith('\n')):
        new_lines.append('\n')
    new_lines.append(extra_keys_value + '\n')
    with open(prop_file, 'w', encoding='utf-8') as f:
        f.writelines(new_lines)
    from doxoade.tools.exec_safe import run_safe
    try:
        run_safe('termux-reload-settings')
    except Exception as e:
        from doxoade.tools.error_info import handle_error
        handle_error(e, context='termux-reload-settings')