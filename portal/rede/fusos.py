"""fusos.py — Fuso horario da casa (por familia). Nomes IANA (zoneinfo).

O fuso vale para o relogio do visor do telefone, os horarios permitidos, o 'silenciar ate amanha as 8h',
a hora certa (100) e as datas que a familia ve no site. O padrao e Brasilia; no cadastro o navegador
sugere o fuso do aparelho do responsavel (Intl.DateTimeFormat), e a familia pode trocar na pagina /fuso.
"""

from datetime import datetime, timezone
from zoneinfo import ZoneInfo, available_timezones

PADRAO = 'America/Sao_Paulo'

# Fusos do Brasil, do mais comum ao mais raro. O oeste do Amazonas (Tabatinga, Eirunepe, Alto Solimoes) e UTC-5,
# como o Acre. Noronha so por completude.
BRASIL = [
    ('America/Sao_Paulo', 'Brasília: SP, RJ, MG, ES, Sul, Nordeste, GO, DF, TO, PA, AP, MA, PI'),
    ('America/Manaus', 'Amazonas (maior parte) e Roraima'),
    ('America/Cuiaba', 'Mato Grosso'),
    ('America/Campo_Grande', 'Mato Grosso do Sul'),
    ('America/Porto_Velho', 'Rondônia'),
    ('America/Rio_Branco', 'Acre e oeste do Amazonas'),
    ('America/Noronha', 'Fernando de Noronha'),
]

_REGIOES = ('Africa', 'America', 'Antarctica', 'Asia', 'Atlantic', 'Australia', 'Europe', 'Indian', 'Pacific')


def validar(nome):
    """Nome IANA conhecido pelo sistema (ex.: 'America/Manaus', 'Europe/Lisbon') ou None."""
    nome = (nome or '').strip()
    if not nome or len(nome) > 64 or nome not in available_timezones():
        return None
    return nome


def zona(nome):
    """ZoneInfo do fuso; qualquer nome invalido cai no padrao (nunca quebra uma ligacao por causa do relogio)."""
    return ZoneInfo(validar(nome) or PADRAO)


def deslocamento_texto(nome, ref=None):
    """'UTC-3', 'UTC+5:30'. No horario de verao mostra o deslocamento de agora."""
    seg = int((ref or datetime.now(timezone.utc)).astimezone(zona(nome)).utcoffset().total_seconds())
    h, m = divmod(abs(seg) // 60, 60)
    return f"UTC{'+' if seg >= 0 else '-'}{h}" + (f':{m:02d}' if m else '')


def descrever(nome):
    """Texto curto para a familia: 'Brasília (UTC-3)' ou 'Europe/Lisbon (UTC+0)'."""
    nome = validar(nome) or PADRAO
    rotulos = dict(BRASIL)
    curto = rotulos[nome].split(':')[0] if nome in rotulos else nome
    return f'{curto} ({deslocamento_texto(nome)})'


def opcoes():
    """[(grupo, [(nome, rotulo), ...])] para o <select>: Brasil primeiro, depois o resto do mundo por regiao."""
    brasil = [(n, f'{r} ({deslocamento_texto(n)})') for n, r in BRASIL]
    conhecidos = {n for n, _ in BRASIL}
    mundo = {}
    for n in sorted(available_timezones()):
        regiao, _, resto = n.partition('/')
        if regiao not in _REGIOES or not resto or n in conhecidos:
            continue
        mundo.setdefault(regiao, []).append((n, f"{resto.replace('_', ' ')} ({deslocamento_texto(n)})"))
    return [('Brasil', brasil)] + [(r, mundo[r]) for r in _REGIOES if r in mundo]
