"""seguranca.py — hash de senha (PBKDF2, como no projeto atual), CSRF, rate limit simples, tokens."""

import hashlib
import hmac
import secrets
import string
import time
from collections import defaultdict

from flask import session

_TENTATIVAS = defaultdict(list)  # chave -> [timestamps]


def hash_senha(senha):
    salt = secrets.token_hex(16)
    h = hashlib.pbkdf2_hmac('sha256', senha.encode(), salt.encode(), 100_000).hex()
    return salt + ':' + h


def verificar_senha(senha, senha_hash):
    try:
        salt, h = senha_hash.split(':', 1)
    except ValueError:
        return False
    calc = hashlib.pbkdf2_hmac('sha256', senha.encode(), salt.encode(), 100_000).hex()
    return hmac.compare_digest(calc, h)


def gerar_csrf_token():
    if '_csrf_token' not in session:
        session['_csrf_token'] = secrets.token_hex(32)
    return session['_csrf_token']


def excedeu(chave, maximo, janela_s):
    """Rate limit em memoria (por processo). Suficiente para 1 instancia."""
    agora_ = time.time()
    lista = [t for t in _TENTATIVAS[chave] if agora_ - t < janela_s]
    _TENTATIVAS[chave] = lista
    return len(lista) >= maximo


def registrar_tentativa(chave):
    _TENTATIVAS[chave].append(time.time())


def limpar_tentativas():
    _TENTATIVAS.clear()


def token_url(nbytes=32):
    return secrets.token_urlsafe(nbytes)


def senha_sip():
    return secrets.token_urlsafe(18)


def senha_admin_aparelho():
    alfabeto = string.ascii_letters + string.digits
    return ''.join(secrets.choice(alfabeto) for _ in range(14))


def codigo_numerico(n=6):
    return ''.join(secrets.choice(string.digits) for _ in range(n))


def sha256(texto):
    return hashlib.sha256(texto.encode('utf-8')).hexdigest()


# Senhas que qualquer lista de ataque tenta primeiro (sequencias, repeticoes, as mais vazadas em portugues).
SENHAS_FRACAS = {
    '12345678', '123456789', '1234567890', '87654321', '11111111', '00000000', '12341234', '12121212',
    'password', 'password1', 'senha123', 'senha1234', 'senhasenha', 'qwertyui', 'qwerty123', 'abcd1234', 'abcdefgh',
    'brasil123', 'mudar123', 'telefone', 'telefone1', 'telefonefixo', 'redeaberta', 'crianca1', 'familia1',
    'iloveyou', 'sunshine', 'football', 'baseball', 'princess', 'welcome1', 'letmein1', 'admin123', 'root1234',
    'a1b2c3d4', '1q2w3e4r', 'zaq12wsx', 'asdfghjk', 'aaaaaaaa', 'abc12345', '123abc45', 'master12', 'dragon12',
}


def senha_fraca(senha, email=''):
    """True se a senha e obvia: lista acima, so um caractere repetido, sequencia numerica, ou o proprio e-mail."""
    s = (senha or '').lower()
    if s in SENHAS_FRACAS or len(set(s)) <= 2:
        return True
    if s.isdigit() and (s in '01234567890123456789' or s in '98765432109876543210'):
        return True
    local = (email or '').split('@')[0].lower()
    if local and len(local) >= 4 and (s == local or local in s and len(s) - len(local) < 4):
        return True
    return False
