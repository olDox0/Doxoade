import sysconfig

def vulcan_binary_name(module_name: str, hash6: str):
    tag = sysconfig.get_config_var("EXT_SUFFIX")
    safe = module_name.replace(".", "__")
    return f"v_{safe}_{hash6}{tag}"