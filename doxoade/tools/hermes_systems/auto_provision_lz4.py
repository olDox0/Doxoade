# doxoade/tools/hermes_systems/auto_provision_lz4.py
import urllib.request
from pathlib import Path

NATIVE_DIR = Path("doxoade/tools/hermes_systems/native")
LZ4_H_URL = "https://raw.githubusercontent.com/lz4/lz4/dev/lib/lz4.h"
LZ4_C_URL = "https://raw.githubusercontent.com/lz4/lz4/dev/lib/lz4.c"
LZ4_LICENSE_URL = "https://raw.githubusercontent.com/lz4/lz4/dev/LICENSE" # 🆕

def provision_lz4():
    print("🔍 [AUTO-PROVISION] Verificando dependências do LZ4...")
    NATIVE_DIR.mkdir(parents=True, exist_ok=True)
    
    h_file = NATIVE_DIR / "lz4.h"
    c_file = NATIVE_DIR / "lz4.c"
    license_file = NATIVE_DIR / "LZ4_LICENSE" # 🆕

    needs_download = not h_file.exists() or not c_file.exists() or not license_file.exists()

    if needs_download:
        print("  ⚠️  Arquivos do LZ4 ausentes. Iniciando download automático...")
        try:
            print(f"  ⬇️  Baixando {h_file.name}...")
            urllib.request.urlretrieve(LZ4_H_URL, h_file)
            print(f"  ⬇️  Baixando {c_file.name}...")
            urllib.request.urlretrieve(LZ4_C_URL, c_file)
            print(f"  ⬇️  Baixando Licença Oficial (LZ4_LICENSE)...") # 🆕
            urllib.request.urlretrieve(LZ4_LICENSE_URL, license_file) # 🆕
            print("  ✔ LZ4 provisionado com sucesso (incluindo licença)!")
        except Exception as e:
            print(f"  ✘ Falha no download: {e}")
            return False
    else:
        print("  ✔ LZ4 e Licença já estão presentes.")

    # Garantir que o builder saiba sobre o lz4.c
    builder_path = NATIVE_DIR / "hermes_bridge_builder.py"
    if builder_path.exists():
        content = builder_path.read_text(encoding='utf-8')
        updated = False
        
        # 1. Adicionar lz4.c na lista de fontes
        if "'lz4.c'" not in content and "lz4.c" not in content:
            content = content.replace(
                "self.native_dir / 'hermes_async_log.c',",
                "self.native_dir / 'hermes_async_log.c',\n            self.native_dir / 'lz4.c',"
            )
            updated = True
            
        # 2. Adicionar o include path
        if "f'-I{self.native_dir}'" not in content:
            content = content.replace(
                "f'-I{include_dir}',",
                "f'-I{include_dir}',\n            f'-I{self.native_dir}',  # Para lz4.h"
            )
            updated = True
            
        if updated:
            builder_path.write_text(content, encoding='utf-8')
            print("  ✔ hermes_bridge_builder.py atualizado para incluir LZ4.")
        else:
            print("  ✔ hermes_bridge_builder.py já está configurado corretamente.")
            
    # Limpar cache de build para forçar recompilação com LZ4
    cache_file = NATIVE_DIR / ".bridge_build_cache.json"
    if cache_file.exists():
        cache_file.unlink()
        print("  🧹 Cache de build limpo para forçar recompilação com LZ4.")
        
    print("\n🎉 Provisionamento concluído! O sistema está pronto.")
    return True

if __name__ == "__main__":
    provision_lz4()