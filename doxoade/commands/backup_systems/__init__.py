# -*- coding: utf-8 -*-
# doxoade/commands/backup_systems/__init__.py
"""
Doxoade Backup Systems — Sistema de backup manual com suporte a delta.
======================================================================
Substitui a necessidade de repositório git para versionamento de código.
Suporta:
• Backup completo (snapshot)
• Backup delta (apenas mudanças desde o último backup)
• Compressão zstd com dicionário treinado
• Rewind para qualquer ponto no tempo via backups
"""

from doxoade.commands.backup_systems.backup_cmd import backup
from doxoade.commands.backup_systems.rewind     import rewind

__all__ = ['backup', 'rewind']
