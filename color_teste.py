from doxoade.tools.doxcolors import Style, Fore
from click import echo
echo(Fore.YELLOW + "TESTE 1")
echo(f"{Fore.CYAN}{Style.BRIGHT}TESTE 2")
echo(f"{Fore.WHITE}TESTE 3")
echo(f"{Fore.GREEN}{Style.BRIGHT}TESTE 4")
print(Fore.YELLOW + "TESTE OK" + Style.RESET_ALL)