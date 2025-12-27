# doxoade/commands/think.py
import click
import time
from colorama import Fore, Style
from ..thinking.core import ThinkingCore

@click.command('think')
@click.argument('query', nargs=-1, required=True)
@click.option('--context', '-c', help='Arquivo de contexto para análise.')
def think(query, context):
    """
    Usa o System 2 (Córtex) para planejar uma solução antes de agir.
    """
    user_input = " ".join(query)
    click.echo(Fore.CYAN + f"🧠 [THINKING] Processando: '{user_input}'...")
    
    # Simula latência de pensamento (opcional, mas dá um feedback tátil)
    start = time.perf_counter()
    
    try:
        brain = ThinkingCore()
        file_content = None
        
        if context:
            try:
                with open(context, 'r', encoding='utf-8', errors='ignore') as f:
                    file_content = f.read()
            except Exception as e:
                click.echo(Fore.RED + f"[ERRO] Não foi possível ler o contexto: {e}")

        # O Grande Processamento
        result = brain.process_thought(user_input, file_context=file_content)
        
        duration = (time.perf_counter() - start) * 1000
        
        # --- EXIBIÇÃO DO RESULTADO (UI Neural) ---
        click.echo(Fore.GREEN + f"\n[CONCLUSÃO] ({duration:.1f}ms)")
        
        click.echo(Fore.YELLOW + "🔎 Foco de Atenção:")
        click.echo(f"   {', '.join(result['focus'])}")
        
        click.echo(Fore.MAGENTA + "🕸️  Associações (Memória Parietal):")
        if result['associations']:
            click.echo(f"   {', '.join(result['associations'])}")
        else:
            click.echo("   (Nenhuma associação prévia forte encontrada)")
            
        click.echo(Fore.CYAN + "📋 Estratégia Executiva (Plano):")
        for step in result['plan']:
            click.echo(f"   ► {step}")
            
    except Exception as e:
        click.echo(Fore.RED + f"\n[LOBOTOMIA] Ocorreu um erro no núcleo de pensamento: {e}")
        if 'importerror' in str(e).lower():
            click.echo("Dica: Verifique se os arquivos em doxoade/thinking/ existem.")