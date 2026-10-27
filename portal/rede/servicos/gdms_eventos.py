"""
gdms_eventos.py — Webhook do GDMS (Push subscription). O GDMS chama POST /gdms/eventos/<segredo>
com {"messages": [...]} quando um aparelho da organizacao muda de status ou gera alerta.

O que fazemos com cada mensagem:
  - gravamos em gdms_log (endpoint 'callback', metodo 'RECEBIDO'), sempre;
  - type 1, statusType 0 (deviceStatus): 1 online -> telefones.gdms_online_em + audit; 0 offline -> audit;
  - type 1, statusType 1 (accountStatus): Up -> telefones.gdms_conta_up_em + audit; outro -> audit;
  - type 2 (alerta): 2 reset de fabrica -> caso 'reset_de_fabrica' (media) se o telefone ja tinha config
    (no primeiro boot o GRP2601 tambem manda esse alerta: so audit); 0 falha de registro -> audit;
    demais -> audit.
Nada aqui muda o estado do telefone: a prova de E7 e a requisicao no nosso servidor e a de E8 e o
registro no Asterisk. O evento do GDMS e evidencia auxiliar (diagnostico: "ligou mas nao buscou").
O GDMS nao assina os callbacks; a protecao e o segredo na URL + so aceitar MACs que conhecemos.
"""

import re

from sqlalchemy import insert, update

from .. import db, auditoria
from ..tempo import agora, minutos_desde
from . import telefones as svc_tel, criancas as svc_cri

ALERTAS = {0: 'falha_registro', 2: 'reset_de_fabrica', 5: 'reboot', 7: 'tarefa_falhou', 8: 'voltou_online', 9: 'offline'}


def _mac(m):
    limpo = re.sub(r'[^0-9A-Fa-f]', '', m or '').upper()
    return limpo if len(limpo) == 12 else None


def processar(conn, corpo, ip, cfg):
    """Retorna contagem por resultado. Nunca levanta por conteudo inesperado (grava e segue)."""
    res = {'recebidas': 0, 'desconhecidas': 0, 'ignoradas': 0, 'online': 0, 'offline': 0, 'conta_up': 0, 'alertas': 0}
    mensagens = corpo.get('messages') if isinstance(corpo, dict) else None
    if not isinstance(mensagens, list):
        mensagens = [corpo] if isinstance(corpo, dict) else []
    for m in mensagens:
        if not isinstance(m, dict):
            res['ignoradas'] += 1
            continue
        res['recebidas'] += 1
        mac = _mac(m.get('mac'))
        tel = svc_tel.por_mac_ativo(conn, mac) if mac else None
        conn.execute(insert(db.gdms_log).values(
            ts=agora(), request_id=auditoria.request_id(), telefone_id=tel['id'] if tel else None,
            endpoint='callback', metodo='RECEBIDO', corpo_enviado={'ip': ip}, http_status=None,
            ret_code=None, msg=f"type={m.get('type')} statusType={m.get('statusType')} alertType={m.get('alertType')}",
            corpo_resposta=m, latencia_ms=0, tentativa=1))
        if not tel:
            res['desconhecidas'] += 1
            if mac:
                auditoria.registrar(conn, 'gdms_evento_mac_desconhecido', 'gdms', 'callback', detalhes={'mac': mac, 'type': m.get('type')}, ip=ip)
            continue
        tipo = m.get('type')
        if tipo == 1 and m.get('statusType') == 0:
            if m.get('deviceStatus') == 1:
                conn.execute(update(db.telefones).where(db.telefones.c.id == tel['id']).values(gdms_online_em=agora()))
                auditoria.registrar(conn, 'gdms_aparelho_online', 'gdms', 'callback', 'telefone', tel['id'],
                                    detalhes={'estado': tel['estado']}, ip=ip)
                res['online'] += 1
            else:
                auditoria.registrar(conn, 'gdms_aparelho_offline', 'gdms', 'callback', 'telefone', tel['id'],
                                    detalhes={'estado': tel['estado'], 'deviceStatus': m.get('deviceStatus')}, ip=ip)
                res['offline'] += 1
        elif tipo == 1 and m.get('statusType') == 1:
            status = str(m.get('accountStatus') or '')
            det = {'estado': tel['estado'], 'accountIndex': m.get('accountIndex'), 'accountStatus': status,
                   'userId_confere': _user_id_confere(conn, tel, m.get('userId'))}
            if status.lower() == 'up':
                conn.execute(update(db.telefones).where(db.telefones.c.id == tel['id']).values(gdms_conta_up_em=agora()))
                auditoria.registrar(conn, 'gdms_conta_up', 'gdms', 'callback', 'telefone', tel['id'], detalhes=det, ip=ip)
                res['conta_up'] += 1
            else:
                auditoria.registrar(conn, 'gdms_conta_status', 'gdms', 'callback', 'telefone', tel['id'], detalhes=det, ip=ip)
        elif tipo == 2:
            alerta = m.get('alertType')
            nome = ALERTAS.get(alerta, f'alerta_{alerta}')
            auditoria.registrar(conn, f'gdms_alerta_{nome}', 'gdms', 'callback', 'telefone', tel['id'],
                                detalhes={'estado': tel['estado'], 'level': m.get('level'), 'detail': m.get('detail')}, ip=ip)
            res['alertas'] += 1
            # O GRP2601 manda o alerta "factory reset" no primeiro boot de fabrica, e ele chega junto com
            # "online"/"reboot", depois de o telefone ja ter buscado a nossa configuracao (bancada 26/10/2026:
            # config 12:23:43, alerta 12:23:00; config 13:26:52, alerta 13:27:00). So e caso quando o telefone
            # ja estava conectado e a configuracao e antiga (mais de 15 min): ai um reset e um reset mesmo.
            if alerta == 2 and tel['registrado_em'] and (minutos_desde(tel['config_entregue_em']) or 0) > 15:
                svc_tel._abrir_caso(conn, 'reset_de_fabrica', 'media', tel,
                                    f'GDMS informou reset de fábrica do telefone {tel["mac"]} (estado {tel["estado"]}).',
                                    {'origem': 'gdms_callback'}, unico=True)
        else:
            res['ignoradas'] += 1
    auditoria.registrar(conn, 'gdms_callback_recebido', 'gdms', 'callback', detalhes=res, ip=ip)
    return res


def _user_id_confere(conn, tel, user_id):
    cr = svc_cri.por_id(conn, tel['crianca_id'])
    return bool(cr) and str(user_id or '') == str(cr['id_rede'])


def registrar_assinatura(cliente, cfg):
    """Configura no GDMS a URL do webhook e a assinatura de eventos da organizacao.
    Retorna as duas respostas brutas. A URL precisa estar no ar: o GDMS a testa na hora."""
    if not cfg.GDMS_WEBHOOK_SEGREDO or len(cfg.GDMS_WEBHOOK_SEGREDO) < 32:
        raise ValueError('REDE_GDMS_WEBHOOK_SEGREDO precisa ter pelo menos 32 caracteres')
    url = f'{cfg.SITE_URL}/gdms/eventos/{cfg.GDMS_WEBHOOK_SEGREDO}'
    r1 = cliente.definir_callback(url)
    r2 = cliente.assinar_eventos(cfg.GDMS_ORG_ID)
    return r1, r2
