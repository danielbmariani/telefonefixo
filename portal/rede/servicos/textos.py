"""textos.py — Textos legais versionados. O hash do texto aceito vai no consentimento."""

import pathlib

from ..seguranca import sha256

PASTA = pathlib.Path(__file__).resolve().parent.parent / 'textos'
ARQUIVOS = {'termos': 'termos.md', 'privacidade': 'privacidade.md', 'crianca': 'consentimento-crianca.md'}


def texto(tipo):
    return (PASTA / ARQUIVOS[tipo]).read_text(encoding='utf-8')


def hash_texto(tipo):
    return sha256(texto(tipo))


def versoes(cfg):
    return {'termos': cfg.VERSAO_TERMOS, 'privacidade': cfg.VERSAO_PRIVACIDADE, 'crianca': cfg.VERSAO_CONSENTIMENTO}
