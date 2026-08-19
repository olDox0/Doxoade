# doxoade/commands/lan_git/web_lan_git/auth_session_lan_git.py
# Autenticação Timing-Safe, CSPRNG tokens e Fail2Ban de IP
""" Módulo de Autenticação Segura e Gerenciamento de Sessões para o Portal Web.
Implementa: Timing-Safe Check (hmac.compare_digest), CSPRNG Sessions e Anti-Brute-Force.

Armazenar a senha/PIN em memória aplicando hash SHA-256 imediato.
Validação via `hmac.compare_digest` para neutralizar ataques de temporização (Timing Attacks).
Gerenciamento de sessões efêmeras geradas por `secrets.token_urlsafe(32)` com TTL (tempo de expiração de 1 hora).
Rastreador de tentativas incorretas por IP (5 erros = 5 minutos de lockout).
Validador do cabeçalho `Host:` para blindar contra DNS Rebinding. """

import time
import secrets
import hashlib
import hmac
from typing import Dict, Optional, Tuple, Set


class LANAuthManager:
    """Controlador central de autenticação e proteção contra abuso."""

    def __init__(self, password: str, max_attempts: int = 5, lockout_seconds: int = 300, session_ttl: int = 3600):
        # Armazena o hash SHA-256 da senha original
        self._password_hash = hashlib.sha256(password.encode("utf-8")).hexdigest()
        self.max_attempts = max_attempts
        self.lockout_seconds = lockout_seconds
        self.session_ttl = session_ttl

        # Estruturas em memória:
        # _failed_attempts: {ip: [timestamps_de_falha]}
        # _active_sessions: {token: (ip, timestamp_criacao)}
        self._failed_attempts: Dict[str, list] = {}
        self._active_sessions: Dict[str, Tuple[str, float]] = {}

    def verify_password(self, input_password: str) -> bool:
        """Compara a senha em tempo estritamente constante (Anti-Timing Attack)."""
        input_hash = hashlib.sha256(input_password.encode("utf-8")).hexdigest()
        return hmac.compare_digest(input_hash, self._password_hash)

    def check_rate_limit(self, client_ip: str) -> Tuple[bool, int]:
        """
        Verifica se o IP está bloqueado por força bruta.
        Retorna (permitido: bool, segundos_restantes_de_bloqueio: int).
        """
        now = time.time()
        if client_ip not in self._failed_attempts:
            return True, 0

        # Remove falhas fora da janela de lockout
        self._failed_attempts[client_ip] = [
            t for t in self._failed_attempts[client_ip] if now - t < self.lockout_seconds
        ]

        attempts = len(self._failed_attempts[client_ip])
        if attempts >= self.max_attempts:
            oldest_relevant = self._failed_attempts[client_ip][0]
            remaining = int(self.lockout_seconds - (now - oldest_relevant))
            return False, max(1, remaining)

        return True, 0

    def record_failed_attempt(self, client_ip: str):
        """Registra uma tentativa incorreta de autenticação."""
        now = time.time()
        if client_ip not in self._failed_attempts:
            self._failed_attempts[client_ip] = []
        self._failed_attempts[client_ip].append(now)

    def record_successful_attempt(self, client_ip: str):
        """Limpa o histórico de falhas do IP após sucesso."""
        if client_ip in self._failed_attempts:
            del self._failed_attempts[client_ip]

    def create_session(self, client_ip: str) -> str:
        """Gera um token de sessão criptograficamente seguro (CSPRNG 256-bit)."""
        token = secrets.token_urlsafe(32)
        self._active_sessions[token] = (client_ip, time.time())
        return token

    def validate_session(self, token: Optional[str], client_ip: str) -> bool:
        """Valida se o token de sessão existe, não expirou e pertence ao IP correto."""
        if not token or token not in self._active_sessions:
            return False

        session_ip, created_at = self._active_sessions[token]
        now = time.time()

        # Checagem de expiração (TTL)
        if now - created_at > self.session_ttl:
            self.invalidate_session(token)
            return False

        # Validação de IP (Bind de Sessão contra Hijacking)
        if session_ip != client_ip:
            return False

        return True

    def invalidate_session(self, token: str):
        """Revoga o token de sessão."""
        if token in self._active_sessions:
            del self._active_sessions[token]

    @staticmethod
    def validate_host_header(host_header: Optional[str], allowed_ip: str, allowed_port: int) -> bool:
        """Protege contra ataques de DNS Rebinding."""
        if not host_header:
            return False
        
        host_clean = host_header.split(":")[0].strip().lower()
        allowed_clean = allowed_ip.strip().lower()
        
        return host_clean in (allowed_clean, "localhost", "127.0.0.1")