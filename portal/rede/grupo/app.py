"""app.py — A chamada em grupo, dirigida por eventos do ARI (doc 16, secao 3.2).

Fluxo: a crianca disca 0 + codigo -> dialplan Stasis(grupo,chamador,<codigo>) -> aqui.
  1. decide (grupos.decidir): quem pode ser chamado agora; anuncia "Chamada em grupo: <nome>. Chamando A, B e C."
  2. poe quem ligou numa ponte com tom de chamando e origina uma chamada para cada membro, com o visor
     "Grupo: <nome> (<apelido>)".
  3. quem atende ouve "Chamada em grupo de <apelido>: <nome>. Na chamada: ..." e entra; todos ouvem o tom e
     "<apelido> entrou". Quem nao atende: "<apelido> nao atendeu". Ninguem: "Ninguem atendeu" e desliga.
  4. quem sai: tom e "<apelido> saiu". Sobrou um: "Voce e o unico na chamada" e, 30 s depois, encerra.
  5. membro que disca o codigo enquanto a chamada existe entra nela; `*` le quem esta.
  6. no fim, uma linha de call_logs por participante com o tempo em comum com cada um dos outros.

Tudo que depende do Asterisk passa por `ari` (interface de rede.grupo.ari.Ari); os testes usam um falso.
Tempo e timers sao injetados (relogio, agendar) para os testes. Nenhuma excecao escapa de um evento:
vira registro e, se der, "Nao deu certo" para o canal envolvido.
"""

import logging

from .. import voz
from ..servicos import grupos, chamadas
from ..tempo import agora, em_sp, agora_sp_texto

log = logging.getLogger('rede.grupo')

APP = 'grupo'
TIMEOUT_TOCAR = 40          # segundos tocando em cada casa
ESPERA_SOZINHO = 30         # segundos sozinho antes de encerrar
MOH_CHAMANDO = 'rede-chamando'


def som(nome):
    return f'sound:rede/{nome}'


class Chamada:
    def __init__(self, grupo_id, nome, ponte, iniciado_em):
        self.grupo_id = grupo_id
        self.nome = nome
        self.ponte = ponte
        self.iniciado_em = iniciado_em
        self.quando_texto = agora_sp_texto()
        self.participantes = {}     # canal -> {'id_rede', 'apelido', 'entrou_em'}
        self.tocando = {}           # canal -> {'id_rede', 'apelido'}
        self.tempos = {}            # id_rede -> [(inicio, fim)]
        self.alguem_entrou = False  # alem de quem ligou
        self.moh = False
        self.timer_sozinho = None
        self.encerrando = False

    def ids(self):
        return [p['id_rede'] for p in self.participantes.values()]


class AppGrupo:
    def __init__(self, ari, engine, cfg, relogio, agendar):
        """relogio() -> epoch; agendar(segundos, fn) -> objeto com .cancel()"""
        self.ari, self.engine, self.cfg = ari, engine, cfg
        self.relogio, self.agendar = relogio, agendar
        self.chamadas = {}      # grupo_id -> Chamada
        self.canal_grupo = {}   # canal -> grupo_id
        self.apos = {}          # playback id -> fn

    # --- utilidades de audio ---
    def _apelido(self, id_rede):
        return [som(f'apelidos/{id_rede}')] if voz.tem_apelido(self.cfg, id_rede) else []

    def _nome_grupo(self, grupo_id):
        return [som(f'grupos/{grupo_id}')] if voz.tem_grupo(self.cfg, grupo_id) else []

    def _nomes(self, ids_):
        """[a, b, c] -> apelido a, apelido b, 'e', apelido c (quem nao tem audio e pulado)."""
        partes = [self._apelido(i) for i in ids_]
        partes = [p for p in partes if p]
        out = []
        for n, p in enumerate(partes):
            if n == len(partes) - 1 and n > 0:
                out.append(som('frases/e'))
            out.extend(p)
        return out

    def _tocar_canal(self, canal, medias, depois=None):
        if not medias:
            if depois:
                depois()
            return
        pid = self.ari.play_channel(canal, medias)
        if depois:
            self.apos[pid] = depois

    def _tocar_ponte(self, ch, medias, depois=None):
        if not medias or not ch.participantes:
            if depois:
                depois()
            return
        pid = self.ari.play_bridge(ch.ponte, medias)
        if depois:
            self.apos[pid] = depois

    def _despedir(self, canal, medias):
        """Toca e desliga."""
        self._tocar_canal(canal, medias, depois=lambda: self.ari.hangup(canal))

    # --- eventos ---
    def evento(self, ev):
        tipo = ev.get('type')
        try:
            if tipo == 'StasisStart':
                self._inicio(ev)
            elif tipo == 'PlaybackFinished':
                fn = self.apos.pop(ev['playback']['id'], None)
                if fn:
                    fn()
            elif tipo in ('StasisEnd', 'ChannelDestroyed'):
                self._fim_canal(ev['channel']['id'])
            elif tipo == 'ChannelLeftBridge':
                self._fim_canal(ev['channel']['id'])
            elif tipo == 'ChannelDtmfReceived':
                self._dtmf(ev['channel']['id'], ev.get('digit'))
        except Exception as e:  # noqa: BLE001
            log.exception('evento %s falhou: %s', tipo, e)
            canal = (ev.get('channel') or {}).get('id')
            if canal and tipo == 'StasisStart':
                try:
                    self._despedir(canal, [som('frases/nao-deu-certo')])
                except Exception:  # noqa: BLE001
                    pass

    def _inicio(self, ev):
        canal = ev['channel']['id']
        args = ev.get('args') or []
        if not args:
            self.ari.hangup(canal)
            return
        if args[0] == 'chamador':
            self._chamador(canal, (ev['channel'].get('caller') or {}).get('number', ''), args[1] if len(args) > 1 else '')
        elif args[0] == 'membro' and len(args) >= 3:
            self._membro_atendeu(canal, int(args[1]), args[2])
        else:
            self.ari.hangup(canal)

    # --- quem liga ---
    def _chamador(self, canal, id_rede, codigo):
        self.ari.answer(canal)
        with self.engine.begin() as conn:
            d = grupos.decidir(conn, id_rede, codigo, em_sp(agora()))
            if d['resultado'] != 'ALLOW':
                chamadas.registrar_bloqueio(conn, id_rede, f'0{codigo}', d.get('motivo', 'GRUPO'))
        log.info('chamador %s codigo %s -> %s %s', id_rede, codigo, d['resultado'],
                 ('chamar=' + ','.join(c['apelido'] for c in d['chamar']) + ' fora=' + ','.join(f"{f['apelido']}:{f['motivo']}" for f in d['fora'])) if d['resultado'] == 'ALLOW' else d.get('motivo'))
        if d['resultado'] == 'BLOCK_SCHEDULE_CALLER':
            self._despedir(canal, [som('frases/fora-do-horario')])
            return
        if d['resultado'] != 'ALLOW':
            self._despedir(canal, [som('frases/grupo-nao-existe')])
            return
        gid = d['grupo']['id']
        ch = self.chamadas.get(gid)
        if ch and not ch.encerrando:
            self._entrada_tardia(canal, ch, d['caller'])
            return
        if not d['chamar']:
            self._despedir(canal, [som('frases/chamada-em-grupo')] + self._nome_grupo(gid) + [som('frases/ninguem-pode-agora')])
            return
        ponte = self.ari.create_bridge(f'grupo-{gid}')
        ch = Chamada(gid, d['grupo']['nome'], ponte, self.relogio())
        self.chamadas[gid] = ch
        self.canal_grupo[canal] = gid
        medias = [som('frases/chamada-em-grupo')] + self._nome_grupo(gid) + [som('frases/chamando')] \
            + self._nomes([c['id_rede'] for c in d['chamar']])
        for f in d['fora']:
            medias += self._apelido(f['id_rede']) + [som('frases/nao-pode-agora')]
        caller = d['caller']
        chamar = d['chamar']

        def depois():
            if canal not in self.canal_grupo:   # desligou durante o anuncio
                return
            self._adicionar(ch, canal, caller['id_rede'], caller['apelido'], anunciar=False)
            self.ari.moh_bridge(ponte, MOH_CHAMANDO)
            ch.moh = True
            for n, c in enumerate(chamar):
                cid = f'grupo-{gid}-{c["id_rede"]}-{int(self.relogio())}-{n}'
                try:
                    self.ari.originate(f'PJSIP/{c["id_rede"]}', APP, f'membro,{gid},{c["id_rede"]}',
                                       f'"Grupo: {ch.nome} ({caller["apelido"]})" <{caller["id_rede"]}>',
                                       TIMEOUT_TOCAR, cid)
                except Exception as e:  # noqa: BLE001
                    log.warning('originate %s falhou: %s', c['id_rede'], e)
                    self._tocar_ponte(ch, self._apelido(c['id_rede']) + [som('frases/nao-atendeu')])
                    continue
                ch.tocando[cid] = c
                self.canal_grupo[cid] = gid
            if not ch.tocando:
                self._ninguem(ch)
        self._tocar_canal(canal, medias, depois)

    def _entrada_tardia(self, canal, ch, quem):
        with self.engine.begin() as conn:
            pode = grupos.pode_entrar(conn, quem['id_rede'], ch.ids())
        if not pode:
            self._despedir(canal, ['sound:telefone/nao-esta-na-lista'])
            return
        if len(ch.participantes) >= self.cfg.GRUPO_MAX_NA_CHAMADA:
            self._despedir(canal, [som('frases/chamada-cheia')])
            return
        self.canal_grupo[canal] = ch.grupo_id
        medias = [som('frases/entrando'), som('frases/na-chamada')] + self._nomes(ch.ids())
        self._tocar_canal(canal, medias, lambda: canal in self.canal_grupo and self._adicionar(ch, canal, quem['id_rede'], quem['apelido']))

    # --- quem atende ---
    def _membro_atendeu(self, canal, gid, id_rede):
        log.info('membro %s atendeu (grupo %s)', id_rede, gid)
        ch = self.chamadas.get(gid)
        if not ch or ch.encerrando:
            self.ari.hangup(canal)
            return
        quem = ch.tocando.pop(canal, None) or {'id_rede': id_rede, 'apelido': ''}
        with self.engine.begin() as conn:
            pode = grupos.pode_entrar(conn, id_rede, ch.ids())
        if not pode:
            self._despedir(canal, ['sound:telefone/nao-esta-na-lista'])
            return
        if len(ch.participantes) >= self.cfg.GRUPO_MAX_NA_CHAMADA:
            self._despedir(canal, [som('frases/chamada-cheia')])
            return
        self.ari.answer(canal)
        chamador = next(iter(ch.participantes.values()), None)
        medias = [som('frases/chamada-em-grupo-de')] + (self._apelido(chamador['id_rede']) if chamador else []) \
            + self._nome_grupo(gid) + [som('frases/na-chamada')] + self._nomes(ch.ids())
        self._tocar_canal(canal, medias, lambda: canal in self.canal_grupo and self._adicionar(ch, canal, quem['id_rede'], quem['apelido']))

    def _adicionar(self, ch, canal, id_rede, apelido, anunciar=True):
        log.info('grupo %s: %s entrou na ponte (%d na chamada)', ch.grupo_id, id_rede, len(ch.participantes) + 1)
        self.ari.add_channel(ch.ponte, canal)
        if ch.moh:
            self.ari.stop_moh_bridge(ch.ponte)
            ch.moh = False
        if ch.timer_sozinho:
            ch.timer_sozinho.cancel()
            ch.timer_sozinho = None
        ch.participantes[canal] = {'id_rede': id_rede, 'apelido': apelido, 'entrou_em': self.relogio()}
        ch.tempos.setdefault(id_rede, []).append([self.relogio(), None])
        self.canal_grupo[canal] = ch.grupo_id
        if anunciar:
            ch.alguem_entrou = True
            self._tocar_ponte(ch, [som('tons/entrou')] + self._apelido(id_rede) + [som('frases/entrou')])

    # --- saidas ---
    def _fim_canal(self, canal):
        gid = self.canal_grupo.pop(canal, None)
        if gid is None:
            return
        ch = self.chamadas.get(gid)
        if not ch:
            return
        if canal in ch.tocando:
            quem = ch.tocando.pop(canal)
            if not ch.encerrando:
                if ch.alguem_entrou or len(ch.participantes) > 1:
                    self._tocar_ponte(ch, self._apelido(quem['id_rede']) + [som('frases/nao-atendeu')])
                elif not ch.tocando:
                    self._ninguem(ch)
            self._talvez_terminar(ch)
            return
        p = ch.participantes.pop(canal, None)
        if p:
            for iv in ch.tempos.get(p['id_rede'], []):
                if iv[1] is None:
                    iv[1] = self.relogio()
            if not ch.encerrando and ch.participantes:
                self._tocar_ponte(ch, [som('tons/saiu')] + self._apelido(p['id_rede']) + [som('frases/saiu')])
        self._talvez_terminar(ch)

    def _ninguem(self, ch):
        """Ninguem atendeu: avisa quem ligou e desliga."""
        ch.encerrando = True
        if ch.moh:
            self.ari.stop_moh_bridge(ch.ponte)
            ch.moh = False
        canais = list(ch.participantes)
        self._tocar_ponte(ch, [som('frases/ninguem-atendeu')], depois=lambda: [self.ari.hangup(c) for c in canais])

    def _talvez_terminar(self, ch):
        if ch.encerrando and not ch.participantes and not ch.tocando:
            self._finalizar(ch)
            return
        if not ch.participantes and not ch.tocando:
            self._finalizar(ch)
            return
        if not ch.participantes and ch.tocando:
            # quem ligou desistiu antes de alguem atender: para de tocar nas outras casas
            ch.encerrando = True
            for c in list(ch.tocando):
                self.ari.hangup(c)
            return
        if len(ch.participantes) == 1 and not ch.tocando and not ch.encerrando and ch.alguem_entrou:
            self._tocar_ponte(ch, [som('frases/voce-e-o-unico')])
            if ch.timer_sozinho:
                ch.timer_sozinho.cancel()
            ch.timer_sozinho = self.agendar(ESPERA_SOZINHO, lambda: self._sozinho_acabou(ch))

    def _sozinho_acabou(self, ch):
        ch.timer_sozinho = None
        if len(ch.participantes) != 1 or ch.tocando or ch.encerrando:
            return
        ch.encerrando = True
        canais = list(ch.participantes)
        self._tocar_ponte(ch, [som('frases/chamada-terminou')], depois=lambda: [self.ari.hangup(c) for c in canais])

    def _finalizar(self, ch):
        log.info('grupo %s: chamada terminou; participantes=%s', ch.grupo_id, list(ch.tempos))
        self.chamadas.pop(ch.grupo_id, None)
        if ch.timer_sozinho:
            ch.timer_sozinho.cancel()
        for c in list(ch.tocando):
            self.canal_grupo.pop(c, None)
            try:
                self.ari.hangup(c)
            except Exception:  # noqa: BLE001
                pass
        try:
            self.ari.destroy_bridge(ch.ponte)
        except Exception:  # noqa: BLE001
            pass
        agora = self.relogio()
        tempos = {}
        for pid, ivs in ch.tempos.items():
            tempos[pid] = [(i, f if f is not None else agora) for i, f in ivs]
        if tempos:
            try:
                with self.engine.begin() as conn:
                    grupos.registrar_chamada(conn, tempos, ch.quando_texto, atendida=ch.alguem_entrou)
            except Exception as e:  # noqa: BLE001
                log.exception('registro da chamada falhou: %s', e)

    # --- tecla * ---
    def _dtmf(self, canal, digito):
        if digito != '*':
            return
        gid = self.canal_grupo.get(canal)
        ch = self.chamadas.get(gid) if gid is not None else None
        if not ch or canal not in ch.participantes:
            return
        outros = [p['id_rede'] for c, p in ch.participantes.items() if c != canal]
        medias = [som('frases/na-chamada')] + self._nomes(outros)
        if outros:
            medias.append(som('frases/e'))
        medias.append(som('frases/voce'))
        self._tocar_canal(canal, medias)
