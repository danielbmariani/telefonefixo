"""uso.py — Uso da rede para o painel do operador, sem discriminar criança.

Tudo aqui é total por período: quantos telefones há na rede, quantos ligaram, quantas ligações de cada
tipo (telefone com telefone, telefone para celular, celular para telefone), minutos, famílias e amizades
novas, e em que horas e dias da semana as crianças ligam. Quem ligou para quem fica no histórico de cada
família, nunca neste quadro.

serie(conn, granularidade, n): uma linha por dia, semana, mês ou ano (as n últimas, a atual incluída).
resumo(conn): números do mês atual para o cartão do painel.
"""

import bisect
import math
from collections import Counter
from datetime import date, datetime, timedelta, timezone

from sqlalchemy import select, func, text

from .. import db
from ..tempo import agora, em_sp, TZ_SP
from . import telefones as svc_tel

TIPOS = (('crianca_crianca', 'Telefone com telefone'),
         ('crianca_celular', 'Telefone para celular'),
         ('celular_crianca', 'Celular para telefone'))

# granularidade -> (rótulo, períodos por padrão, máximo)
GRANULARIDADES = {'dia': ('Por dia', 30, 366), 'semana': ('Por semana', 12, 104),
                  'mes': ('Por mês', 12, 60), 'ano': ('Por ano', 5, 20)}

MESES = ['jan', 'fev', 'mar', 'abr', 'mai', 'jun', 'jul', 'ago', 'set', 'out', 'nov', 'dez']
DIAS_SEMANA = ['seg', 'ter', 'qua', 'qui', 'sex', 'sáb', 'dom']
FAIXAS_DURACAO = ((60, 'até 1 min'), (180, '1 a 3 min'), (600, '3 a 10 min'), (1800, '10 a 30 min'), (None, 'mais de 30 min'))


def _tipo(caller, callee):
    if len(caller) == 6 and len(callee) == 6:
        return 'crianca_crianca'
    if len(callee) == 7 and callee[0] in '98':
        return 'crianca_celular'
    if caller.isdigit() and len(caller) in (10, 11):
        return 'celular_crianca'
    return None


def _mes_anterior(hoje):
    ano, mes = (hoje.year, hoje.month - 1) if hoje.month > 1 else (hoje.year - 1, 12)
    return f'{ano:04d}-{mes:02d}'


# --- Períodos ---------------------------------------------------------------

def _inicio_periodo(d, gran):
    if gran == 'dia':
        return d
    if gran == 'semana':
        return d - timedelta(days=d.weekday())
    if gran == 'mes':
        return d.replace(day=1)
    return d.replace(month=1, day=1)


def _periodo_anterior(d, gran):
    if gran == 'dia':
        return d - timedelta(days=1)
    if gran == 'semana':
        return d - timedelta(days=7)
    if gran == 'mes':
        return (d - timedelta(days=1)).replace(day=1)
    return d.replace(year=d.year - 1)


def _rotulo(inicio, fim, gran):
    if gran == 'dia':
        return f'{DIAS_SEMANA[inicio.weekday()]} {inicio:%d/%m}'
    if gran == 'semana':
        return f'{inicio:%d/%m} a {fim - timedelta(days=1):%d/%m}'
    if gran == 'mes':
        return f'{MESES[inicio.month - 1]}/{inicio.year % 100:02d}'
    return str(inicio.year)


def periodos(gran, n, hoje):
    """Lista cronológica de dicts {inicio, fim (exclusivo), rotulo}, datas em São Paulo; o último é o atual."""
    inicios = []
    d = _inicio_periodo(hoje, gran)
    for _ in range(n):
        inicios.append(d)
        d = _periodo_anterior(d, gran)
    inicios.reverse()
    out = []
    for i, ini in enumerate(inicios):
        fim = inicios[i + 1] if i + 1 < len(inicios) else _fim_do_periodo(ini, gran)
        out.append({'inicio': ini, 'fim': fim, 'rotulo': _rotulo(ini, fim, gran), 'atual': i == len(inicios) - 1})
    return out


def _fim_do_periodo(ini, gran):
    if gran == 'dia':
        return ini + timedelta(days=1)
    if gran == 'semana':
        return ini + timedelta(days=7)
    if gran == 'mes':
        return (ini.replace(day=28) + timedelta(days=4)).replace(day=1)
    return ini.replace(year=ini.year + 1)


def _data_sp(dt):
    d = em_sp(dt)
    return d.date() if d else None


def _utc_meia_noite(d):
    return TZ_SP.localize(datetime(d.year, d.month, d.day)).astimezone(timezone.utc)


def _indice(inicios, d):
    """Posição do período que contém a data d, ou None se antes do primeiro."""
    i = bisect.bisect_right(inicios, d) - 1
    return i if i >= 0 else None


# --- Série por período -------------------------------------------------------

def _linha_vazia(p):
    return {**p, 'familias_novas': 0, 'telefones_novos': 0, 'amizades_novas': 0,
            'familias': 0, 'telefones': 0, 'ativos': 0,
            'tipos': {t: {'ligacoes': 0, 'minutos': 0, 'segundos': 0, 'nao_completadas': 0} for t, _ in TIPOS},
            'troncos': {'vono': 0, 'nvoip': 0},
            'ligacoes': 0, 'minutos': 0, 'segundos': 0, 'nao_completadas': 0, 'antigas': 0}


def serie(conn, gran='mes', n=None, ref=None):
    if gran not in GRANULARIDADES:
        gran = 'mes'
    padrao, maximo = GRANULARIDADES[gran][1:]
    n = max(1, min(int(n or padrao), maximo))
    hoje = em_sp(ref or agora()).date()
    ps = periodos(gran, n, hoje)
    inicios = [p['inicio'] for p in ps]
    linhas = [_linha_vazia(p) for p in ps]
    desde = inicios[0]
    desde_utc = _utc_meia_noite(desde)
    ativos = [set() for _ in ps]
    horas, dias_semana, duracoes = Counter(), Counter(), Counter()

    # Ligações do período (call_logs tem a hora local em texto)
    rows = conn.execute(text("SELECT caller_ext, callee_ext, timestamp, status, duration_seconds, tronco FROM call_logs "
                             "WHERE timestamp >= :d"), {'d': f'{desde:%Y-%m-%d} 00:00:00'}).mappings().all()
    for r in rows:
        try:
            quando = datetime.strptime(r['timestamp'][:19], '%Y-%m-%d %H:%M:%S')
        except (TypeError, ValueError):
            continue
        i = _indice(inicios, quando.date())
        t = _tipo(r['caller_ext'] or '', r['callee_ext'] or '')
        if i is None or not t:
            continue
        lt = linhas[i]['tipos'][t]
        if r['status'] == 'ALLOWED' and r['duration_seconds']:
            lt['ligacoes'] += 1
            lt['segundos'] += r['duration_seconds']
            if t != 'crianca_crianca':   # minutos com celular por tronco; antigas sem tronco contam como Nvoip
                linhas[i]['troncos']['vono' if r['tronco'] == 'vono' else 'nvoip'] += math.ceil(r['duration_seconds'] / 60)
            for ext in (r['caller_ext'], r['callee_ext']):
                if len(ext) == 6:
                    ativos[i].add(ext)
            horas[quando.hour] += 1
            dias_semana[quando.weekday()] += 1
            for lim, nome in FAIXAS_DURACAO:
                if lim is None or r['duration_seconds'] <= lim:
                    duracoes[nome] += 1
                    break
        else:
            lt['nao_completadas'] += 1
    # Dias já resumidos pela retenção: só totais, sem tipo
    if db.tabela_existe(conn, 'chamadas_resumo'):
        for r in conn.execute(select(db.chamadas_resumo).where(db.chamadas_resumo.c.dia >= f'{desde:%Y-%m-%d}')).mappings():
            i = _indice(inicios, date.fromisoformat(r['dia']))
            if i is None:
                continue
            linhas[i]['antigas'] += r['chamadas'] - r['bloqueadas']
            linhas[i]['segundos'] += r['segundos']
            linhas[i]['nao_completadas'] += r['bloqueadas']

    # Famílias, telefones e amizades (datas em UTC no banco)
    fam = conn.execute(select(db.familias.c.criado_em).where(db.familias.c.papel == 'familia')).scalars().all()
    tel = conn.execute(select(db.telefones.c.informado_em, db.telefones.c.desativado_em, db.telefones.c.estado)).mappings().all()
    ami = conn.execute(select(db.amizades.c.respondido_em).where(db.amizades.c.estado.in_(('aceita', 'removida')),
                                                                db.amizades.c.respondido_em.isnot(None))).scalars().all()
    datas_fam = sorted(d for d in (_data_sp(x) for x in fam) if d)
    for d in datas_fam:
        i = _indice(inicios, d)
        if i is not None:
            linhas[i]['familias_novas'] += 1
    for d in (_data_sp(x) for x in ami):
        i = _indice(inicios, d) if d else None
        if i is not None:
            linhas[i]['amizades_novas'] += 1
    tels = []
    for r in tel:
        entrou = _data_sp(r['informado_em'])
        saiu = _data_sp(r['desativado_em']) if r['estado'] in svc_tel.ESTADOS_REMOVIDO else None
        if r['estado'] in svc_tel.ESTADOS_REMOVIDO and saiu is None:
            saiu = entrou                                   # removido sem data: nunca conta como "na rede"
        tels.append((entrou, saiu))
        i = _indice(inicios, entrou) if entrou else None
        if i is not None:
            linhas[i]['telefones_novos'] += 1

    for i, l in enumerate(linhas):
        fim = l['fim']
        l['familias'] = sum(1 for d in datas_fam if d < fim)
        l['telefones'] = sum(1 for e, s in tels if e and e < fim and (s is None or s >= fim))
        l['ativos'] = len(ativos[i])
        for t in l['tipos'].values():
            t['minutos'] = int(math.ceil(t['segundos'] / 60)) if t['segundos'] else 0
            l['ligacoes'] += t['ligacoes']
            l['segundos'] += t['segundos']
            l['nao_completadas'] += t['nao_completadas']
        l['ligacoes'] += l['antigas']
        l['minutos'] = int(math.ceil(l['segundos'] / 60)) if l['segundos'] else 0
        l['media_min'] = round(l['segundos'] / 60 / l['ligacoes'], 1) if l['ligacoes'] else None
        l['pct_ativos'] = round(100 * l['ativos'] / l['telefones']) if l['telefones'] else None

    total_lig = sum(horas.values())
    return {
        'granularidade': gran, 'n': n, 'periodos': linhas,
        'atual': linhas[-1], 'anterior': linhas[-2] if len(linhas) > 1 else None,
        'horas': [horas.get(h, 0) for h in range(24)],
        'dias_semana': [(DIAS_SEMANA[i], dias_semana.get(i, 0)) for i in range(7)],
        'duracoes': [(nome, duracoes.get(nome, 0)) for _, nome in FAIXAS_DURACAO],
        'total_ligacoes': total_lig,
        'tipos': TIPOS,
    }


def csv(dados):
    cab = ['periodo', 'inicio', 'fim', 'familias_novas', 'familias', 'telefones_novos', 'telefones', 'telefones_ativos',
           'amizades_novas'] + [f'{t}_{m}' for t, _ in TIPOS for m in ('ligacoes', 'minutos', 'nao_completadas')] + \
          ['ligacoes', 'minutos', 'nao_completadas', 'min_celular_vono', 'min_celular_nvoip']
    out = [';'.join(cab)]
    for l in dados['periodos']:
        vals = [l['rotulo'], l['inicio'].isoformat(), (l['fim'] - timedelta(days=1)).isoformat(), l['familias_novas'], l['familias'],
                l['telefones_novos'], l['telefones'], l['ativos'], l['amizades_novas']]
        for t, _ in TIPOS:
            vals += [l['tipos'][t]['ligacoes'], l['tipos'][t]['minutos'], l['tipos'][t]['nao_completadas']]
        vals += [l['ligacoes'], l['minutos'], l['nao_completadas'], l['troncos']['vono'], l['troncos']['nvoip']]
        out.append(';'.join(str(v) for v in vals))
    return '\n'.join(out) + '\n'


# --- Cartão do painel (mês atual) -------------------------------------------

def _ligacoes_do_mes(conn, mes):
    rows = conn.execute(text("SELECT caller_ext, callee_ext, status, duration_seconds FROM call_logs WHERE timestamp LIKE :m"),
                        {'m': mes + '%'}).mappings().all()
    out = {t: {'ligacoes': 0, 'minutos': 0, 'nao_completadas': 0, 'segundos': 0} for t, _ in TIPOS}
    for r in rows:
        t = _tipo(r['caller_ext'] or '', r['callee_ext'] or '')
        if not t:
            continue
        if r['status'] == 'ALLOWED' and r['duration_seconds']:
            out[t]['ligacoes'] += 1
            out[t]['segundos'] += r['duration_seconds']
        else:
            out[t]['nao_completadas'] += 1
    for t in out:
        out[t]['minutos'] = int(math.ceil(out[t].pop('segundos') / 60)) if out[t]['ligacoes'] else 0
    return out


def resumo(conn, ref=None):
    hoje = em_sp(ref or agora())
    mes, anterior = hoje.strftime('%Y-%m'), _mes_anterior(hoje)
    cadastrados = conn.execute(select(func.count()).select_from(db.telefones)
                               .where(db.telefones.c.estado.notin_(svc_tel.ESTADOS_REMOVIDO))).scalar()
    ativos = conn.execute(select(func.count()).select_from(db.telefones).where(db.telefones.c.estado == 'ativo')).scalar()
    conectados = None
    if db.tabela_existe(conn, 'ps_contacts'):
        conectados = conn.execute(text("SELECT count(*) FROM ps_contacts WHERE length(endpoint) = 6")).scalar()
    return {'mes': mes, 'mes_anterior': anterior,
            'telefones': {'cadastrados': cadastrados, 'conectados': conectados, 'ativos': ativos},
            'tipos': TIPOS, 'atual': _ligacoes_do_mes(conn, mes), 'anterior': _ligacoes_do_mes(conn, anterior)}
