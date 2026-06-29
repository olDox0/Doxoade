# doxoade/doxoade/tools/vulcan/template_manager.py
from pathlib import Path

class StubVault:
    def __init__(self):
        self.vault_dir = Path(__file__).resolve().parent.parent / "templates" / "vulcan"
        
    def get_template(self, version: str = "latest") -> str:
        """Puxa o template físico correspondente à versão."""
        target = self.vault_dir / f"embedded_{version}.py"
        if not target.exists():
            raise FileNotFoundError(f"Template versão '{version}' não encontrado no cofre.")
        return target.read_text(encoding="utf-8")

    def list_versions(self) -> list:
        """Lista as versões disponíveis no cofre."""
        if not self.vault_dir.exists():
            return []
        versions = []
        for f in self.vault_dir.glob("embedded_*.py"):
            versions.append(f.stem.replace("embedded_", ""))
        return sorted(versions)

    def rollback_stub(self, project_root: Path, target_version: str):
        """Reverte o stub de um projeto externo para uma versão mais antiga do cofre."""
        vulcan_dir = project_root / ".doxoade" / "vulcan"
        stub_path = vulcan_dir / "vulcan_embedded.py"
        
        if not vulcan_dir.exists():
            raise FileNotFoundError(f"O projeto '{project_root.name}' não possui o motor Vulcan ativo.")
            
        old_code = self.get_template(target_version)
        stub_path.write_text(old_code, encoding="utf-8")
        return stub_path