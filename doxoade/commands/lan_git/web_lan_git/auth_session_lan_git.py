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
import base64
from typing import Dict, Optional, Tuple, Set, List

class LANAuthManager:
    def __init__(self, password: str, max_attempts: int = 5, lockout_seconds: int = 300, session_ttl: int = 3600):
        self._password = password
        self._password_hash = hashlib.sha256(password.encode('utf-8')).hexdigest()
        self.max_attempts = max_attempts
        self.lockout_seconds = lockout_seconds
        self.session_ttl = session_ttl
        self._failed_attempts: Dict[str, List[float]] = {}
        self._active_sessions: Dict[str, Tuple[str, float]] = {}

    def verify_password(self, input_password: str) -> bool:
        input_hash = hashlib.sha256(input_password.encode('utf-8')).hexdigest()
        return hmac.compare_digest(input_hash, self._password_hash)

    def check_rate_limit(self, client_ip: str) -> Tuple[bool, int, int]:
        now = time.time()
        if client_ip not in self._failed_attempts:
            return True, self.max_attempts, 0
        self._failed_attempts[client_ip] = [t for t in self._failed_attempts[client_ip] if now - t < self.lockout_seconds]
        fails = len(self._failed_attempts[client_ip])
        if fails >= self.max_attempts:
            remaining = int(self.lockout_seconds - (now - self._failed_attempts[client_ip][0]))
            return False, 0, max(1, remaining)
        return True, (self.max_attempts - fails), 0

    def record_failed_attempt(self, client_ip: str) -> int:
        now = time.time()
        if client_ip not in self._failed_attempts:
            self._failed_attempts[client_ip] = []
        self._failed_attempts[client_ip].append(now)
        fail_count = len(self._failed_attempts[client_ip])
        time.sleep(min(fail_count * 0.5, 3.0))
        return fail_count

    def record_successful_attempt(self, client_ip: str):
        if client_ip in self._failed_attempts:
            del self._failed_attempts[client_ip]

    def create_session(self, client_ip: str) -> str:
        token = secrets.token_urlsafe(32)
        self._active_sessions[token] = (client_ip, time.time())
        return token

    def validate_session(self, token: Optional[str], client_ip: str) -> bool:
        if not token or token not in self._active_sessions:
            return False
        session_ip, created_at = self._active_sessions[token]
        if time.time() - created_at > self.session_ttl:
            self.invalidate_session(token)
            return False
        return session_ip == client_ip

    def validate_basic_auth(self, auth_header: Optional[str]) -> bool:
        if not auth_header or not auth_header.startswith('Basic '):
            return False
        try:
            encoded = auth_header.split(' ', 1)[1]
            decoded = base64.b64decode(encoded).decode('utf-8')
            _, pwd = decoded.split(':', 1) if ':' in decoded else ('', decoded)
            return self.verify_password(pwd)
        except Exception:
            return False

    def invalidate_session(self, token: str):
        if token in self._active_sessions:
            del self._active_sessions[token]

    @staticmethod
    def validate_host_header(host_header: Optional[str], allowed_ip: str, allowed_port: int) -> bool:
        if not host_header:
            return False
        host_clean = host_header.split(':')[0].strip().lower()
        allowed_clean = allowed_ip.strip().lower()
        return host_clean in (allowed_clean, 'localhost', '127.0.0.1')
