"""A chamada em grupo dirigida por eventos (rede.grupo.app) com um ARI falso: anuncios, toca em todos, quem
atende entra, quem nao atende e anunciado, ninguem atendeu, sozinho encerra, entrada tardia, tecla *, registro."""
import os

import pytest
from sqlalchemy import text

from rede.grupo.app import AppGrupo, ESPERA_SOZINHO
from rede.servicos import grupos
from test_grupos import rede4, _fam_id  # noqa: F401  (fixture)


class FakeAri:
    def __init__(self):
        self.chamadas = []      # (metodo, args)
        self.n = 0
        self.pontes = set()
        self.canais_vivos = set()

    def _reg(self, m, *a):
        self.chamadas.append((m,) + a)

    def answer(self, canal): self._reg('answer', canal)
    def hangup(self, canal): self._reg('hangup', canal); self.canais_vivos.discard(canal)
    def play_channel(self, canal, medias):
        self.n += 1; self._reg('play_channel', canal, tuple(medias)); return f'pb{self.n}'
    def play_bridge(self, ponte, medias):
        self.n += 1; self._reg('play_bridge', ponte, tuple(medias)); return f'pb{self.n}'
    def originate(self, endpoint, app, app_args, caller_id, timeout, channel_id, variaveis=None):
        self._reg('originate', endpoint, app_args, caller_id, timeout, channel_id); self.canais_vivos.add(channel_id); return channel_id
    def create_bridge(self, nome):
        self.n += 1; b = f'ponte{self.n}'; self.pontes.add(b); self._reg('create_bridge', nome); return b
    def destroy_bridge(self, ponte): self._reg('destroy_bridge', ponte); self.pontes.discard(ponte)
    def add_channel(self, ponte, canal): self._reg('add_channel', ponte, canal)
    def moh_bridge(self, ponte, classe): self._reg('moh', ponte, classe)
    def stop_moh_bridge(self, ponte): self._reg('stop_moh', ponte)

    def so(self, metodo):
        return [c for c in self.chamadas if c[0] == metodo]

    def ultimo(self, metodo):
        xs = self.so(metodo)
        return xs[-1] if xs else None

    def playbacks_pendentes(self):
        return [f'pb{i}' for i in range(1, self.n + 1)]


class FakeTimer:
    def __init__(self, lista, fn):
        self.lista, self.fn, self.cancelado = lista, fn, False
        lista.append(self)

    def cancel(self):
        self.cancelado = True


class Mundo:
    """Orquestra app + ARI falso + relogio + timers e simula os eventos do Asterisk."""
    def __init__(self, app_flask, tmp_path):
        self.ari = FakeAri()
        self.t = 1000.0
        self.timers = []
        cfg = app_flask.cfg
        cfg.VOZ_DIR = str(tmp_path / 'sons')
        self.cfg = cfg
        self.app = AppGrupo(self.ari, app_flask.engine, cfg, lambda: self.t, lambda s, fn: FakeTimer(self.timers, fn))
        self.pb_tocados = 0

    def apelido_existe(self, *ids):
        for i in ids:
            d = os.path.join(self.cfg.VOZ_DIR, 'apelidos'); os.makedirs(d, exist_ok=True)
            open(os.path.join(d, f'{i}.wav'), 'wb').close()

    def grupo_existe(self, gid):
        d = os.path.join(self.cfg.VOZ_DIR, 'grupos'); os.makedirs(d, exist_ok=True)
        open(os.path.join(d, f'{gid}.wav'), 'wb').close()

    def disca(self, canal, id_rede, codigo):
        self.app.evento({'type': 'StasisStart', 'channel': {'id': canal, 'caller': {'number': id_rede}}, 'args': ['chamador', codigo]})

    def playback_acaba(self):
        """Conclui todos os playbacks ainda pendentes (em ordem)."""
        while self.pb_tocados < self.ari.n:
            self.pb_tocados += 1
            self.app.evento({'type': 'PlaybackFinished', 'playback': {'id': f'pb{self.pb_tocados}'}})

    def atende(self, canal_originado):
        _, gid, id_rede = self.ari_args(canal_originado)
        self.app.evento({'type': 'StasisStart', 'channel': {'id': canal_originado, 'caller': {'number': id_rede}},
                         'args': ['membro', gid, id_rede]})

    def ari_args(self, canal):
        for c in self.ari.so('originate'):
            if c[5] == canal:
                return c[2].split(',')
        raise KeyError(canal)

    def desliga(self, canal):
        self.app.evento({'type': 'StasisEnd', 'channel': {'id': canal}})

    def nao_atende(self, canal):
        self.app.evento({'type': 'ChannelDestroyed', 'channel': {'id': canal}})

    def tecla(self, canal, d):
        self.app.evento({'type': 'ChannelDtmfReceived', 'channel': {'id': canal}, 'digit': d})

    def dispara_timers(self):
        for tm in list(self.timers):
            if not tm.cancelado:
                tm.cancelado = True
                tm.fn()

    def medias(self, metodo):
        return [c[2] for c in self.ari.so(metodo)]


@pytest.fixture
def mundo(app, tmp_path, rede4):
    m = Mundo(app, tmp_path)
    with app.engine.begin() as conn:
        g = grupos.criar(conn, _fam_id(app, rede4['jose']), rede4['jose'], 'Turma', [rede4['beto']['id'], rede4['alice']['id'], rede4['theo']['id']])
    m.gid = g['id']
    m.grupo_existe(g['id'])
    m.apelido_existe(*(c['id_rede'] for c in rede4.values()))
    m.r = rede4
    return m


def _medias(m, metodo):
    return m.medias(metodo)


def test_fluxo_completo(mundo, app):
    m, r = mundo, mundo.r
    j, b, a, t = r['jose'], r['beto'], r['alice'], r['theo']
    m.disca('cj', j['id_rede'], '1')
    # anuncio para quem ligou: chamada em grupo, nome, chamando beto e alice, theo nao pode agora (sem dizer por que)
    assert m.ari.so('answer')[0][1] == 'cj'
    an = m.medias('play_channel')[0]
    assert an == ('sound:rede/frases/chamada-em-grupo', f'sound:rede/grupos/{m.gid}', 'sound:rede/frases/chamando',
                  f'sound:rede/apelidos/{b["id_rede"]}', 'sound:rede/frases/e', f'sound:rede/apelidos/{a["id_rede"]}',
                  f'sound:rede/apelidos/{t["id_rede"]}', 'sound:rede/frases/nao-pode-agora')
    assert not m.ari.so('originate')          # ainda nao tocou em ninguem: espera o anuncio acabar
    m.playback_acaba()
    # quem ligou entrou na ponte com tom de chamando; dois originates com o visor "Grupo: Turma (jose)"
    assert m.ari.ultimo('add_channel')[2] == 'cj' and m.ari.ultimo('moh')[2] == 'rede-chamando'
    origs = m.ari.so('originate')
    assert [o[1] for o in origs] == [f'PJSIP/{b["id_rede"]}', f'PJSIP/{a["id_rede"]}']
    assert origs[0][3] == f'"Grupo: Turma (jose)" <{j["id_rede"]}>' and origs[0][4] == 40
    cb, ca = origs[0][5], origs[1][5]
    # beto atende: ouve "chamada em grupo de jose: Turma. Na chamada: jose", entra, todos ouvem tom + "beto entrou"
    m.atende(cb)
    assert m.medias('play_channel')[-1] == ('sound:rede/frases/chamada-em-grupo-de', f'sound:rede/apelidos/{j["id_rede"]}',
                                            f'sound:rede/grupos/{m.gid}', 'sound:rede/frases/na-chamada', f'sound:rede/apelidos/{j["id_rede"]}')
    m.playback_acaba()
    assert m.ari.ultimo('add_channel')[2] == cb and m.ari.so('stop_moh')
    assert m.medias('play_bridge')[-1] == ('sound:rede/tons/entrou', f'sound:rede/apelidos/{b["id_rede"]}', 'sound:rede/frases/entrou')
    # alice nao atende: todos ouvem "alice nao atendeu"
    m.t += 40; m.nao_atende(ca)
    assert m.medias('play_bridge')[-1] == (f'sound:rede/apelidos/{a["id_rede"]}', 'sound:rede/frases/nao-atendeu')
    # tecla * do beto: "na chamada: jose e voce"
    m.tecla(cb, '*')
    assert m.medias('play_channel')[-1] == ('sound:rede/frases/na-chamada', f'sound:rede/apelidos/{j["id_rede"]}', 'sound:rede/frases/e', 'sound:rede/frases/voce')
    # jose desliga: beto ouve "jose saiu" e "voce e o unico"; 30 s depois "a chamada terminou" e desliga
    m.t += 100; m.desliga('cj')
    pb = m.medias('play_bridge')
    assert pb[-2] == ('sound:rede/tons/saiu', f'sound:rede/apelidos/{j["id_rede"]}', 'sound:rede/frases/saiu') and pb[-1] == ('sound:rede/frases/voce-e-o-unico',)
    assert m.timers and not m.timers[-1].cancelado
    m.t += ESPERA_SOZINHO; m.dispara_timers()
    assert m.medias('play_bridge')[-1] == ('sound:rede/frases/chamada-terminou',)
    m.playback_acaba()
    assert m.ari.ultimo('hangup')[1] == cb
    m.t += 1; m.desliga(cb)
    assert m.ari.so('destroy_bridge') and not m.app.chamadas and not m.app.canal_grupo
    with app.engine.begin() as conn:
        rows = {r_[0]: r_ for r_ in conn.execute(text("SELECT caller_ext, status, duration_seconds, block_reason FROM call_logs WHERE callee_ext='GRUPO'")).all()}
    assert set(rows) == {j['id_rede'], b['id_rede']}
    assert rows[j['id_rede']][1] == 'ALLOWED' and rows[j['id_rede']][2] == 140 and rows[j["id_rede"]][3] == f"{b['id_rede']}:140"
    assert rows[b["id_rede"]][3] == f"{j['id_rede']}:140"


def test_ninguem_atendeu(mundo, app):
    m, r = mundo, mundo.r
    j = r['jose']
    m.disca('cj', j['id_rede'], '1'); m.playback_acaba()
    cb, ca = [o[5] for o in m.ari.so('originate')]
    m.t += 40; m.nao_atende(cb)
    assert m.medias('play_bridge') == []          # ainda toca na casa da alice: nada a dizer
    m.nao_atende(ca)
    assert m.medias('play_bridge')[-1] == ('sound:rede/frases/ninguem-atendeu',) and m.ari.so('stop_moh')
    m.playback_acaba()
    assert m.ari.ultimo('hangup')[1] == 'cj'
    m.desliga('cj')
    with app.engine.begin() as conn:
        rows = conn.execute(text("SELECT caller_ext, status FROM call_logs WHERE callee_ext='GRUPO'")).all()
    assert rows == [(j['id_rede'], 'NOANSWER')]
    assert not m.app.chamadas


def test_quem_ligou_desiste_antes(mundo):
    m, r = mundo, mundo.r
    m.disca('cj', r['jose']['id_rede'], '1'); m.playback_acaba()
    tocando = [o[5] for o in m.ari.so('originate')]
    m.desliga('cj')
    assert all(('hangup', c) in m.ari.chamadas for c in tocando)
    for c in tocando:
        m.nao_atende(c)
    assert not m.app.chamadas and m.ari.so('destroy_bridge')


def test_entrada_tardia_e_limite(mundo, app):
    m, r = mundo, mundo.r
    j, b, a, t = r['jose'], r['beto'], r['alice'], r['theo']
    m.disca('cj', j['id_rede'], '1'); m.playback_acaba()
    cb, ca = [o[5] for o in m.ari.so('originate')]
    m.atende(cb); m.playback_acaba()
    # alice nao atendeu, mas disca o codigo dela depois: entra na chamada que existe
    m.nao_atende(ca)
    m.disca('calice', a['id_rede'], '1')
    assert m.medias('play_channel')[-1][:2] == ('sound:rede/frases/entrando', 'sound:rede/frases/na-chamada')
    assert len(m.ari.so('create_bridge')) == 1
    m.playback_acaba()
    assert m.ari.ultimo('add_channel')[2] == 'calice' and len(m.app.chamadas[m.gid].participantes) == 3
    # theo nao e amigo de beto: tentando entrar, ouve que nao esta na lista
    m.disca('ctheo', t['id_rede'], '1')
    assert m.medias('play_channel')[-1] == ('sound:telefone/nao-esta-na-lista',)
    m.playback_acaba()
    assert m.ari.ultimo('hangup')[1] == 'ctheo'
    # limite de 4: um quinto amigo nao entra
    m.cfg.GRUPO_MAX_NA_CHAMADA = 3
    with app.engine.begin() as conn:
        from test_grupos import _amigos
        extra, = __import__('test_grupos')._familia(app.test_client(), app, 'e@x.com', ['edu'])
        for x in (j, b, a):
            _amigos(app, extra, x)
        g = grupos.por_id(conn, m.gid)
    m.disca('cedu', extra['id_rede'], '1')   # edu nao esta no grupo: nao existe para ele
    assert m.medias('play_channel')[-1] == ('sound:rede/frases/grupo-nao-existe',)
    assert g['ativo']


def test_bloqueios_de_quem_liga(mundo, app):
    m, r = mundo, mundo.r
    j = r['jose']
    m.disca('c1', j['id_rede'], '9')
    assert m.medias('play_channel')[-1] == ('sound:rede/frases/grupo-nao-existe',)
    from rede.servicos import horarios as svc_hor
    with app.engine.begin() as conn:
        svc_hor.silenciar(conn, j['id'], '1h', _fam_id(app, j))
    m.disca('c2', j['id_rede'], '1')
    assert m.medias('play_channel')[-1] == ('sound:rede/frases/fora-do-horario',)
    m.playback_acaba()
    assert [c[1] for c in m.ari.so('hangup')] == ['c1', 'c2']
    with app.engine.begin() as conn:
        assert conn.execute(text("SELECT count(*) FROM call_logs WHERE status='BLOCKED'")).scalar() == 2


def test_sem_audio_de_apelido_segue_so_com_tons(app, tmp_path, rede4):
    m = Mundo(app, tmp_path)
    with app.engine.begin() as conn:
        g = grupos.criar(conn, _fam_id(app, rede4['jose']), rede4['jose'], 'Dupla', [rede4['beto']['id']])
    m.disca('cj', rede4['jose']['id_rede'], '1')
    assert m.medias('play_channel')[-1] == ('sound:rede/frases/chamada-em-grupo', 'sound:rede/frases/chamando')
    m.playback_acaba()
    cb = m.ari.so('originate')[0][5]
    m.atende(cb); m.playback_acaba()
    assert m.medias('play_bridge')[-1] == ('sound:rede/tons/entrou', 'sound:rede/frases/entrou')
    assert g['ativo']
