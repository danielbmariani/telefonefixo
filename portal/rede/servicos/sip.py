"""
sip.py — E8: observa ps_contacts (escrita pelo Asterisk) e aplica timeouts (E6/E8).
Roda a cada minuto (flask jobs-rapidos).
"""

import re
from datetime import timedelta

from sqlalchemy import select, update, insert, and_, text

from .. import db, auditoria, estados
from ..tempo import agora, utc
from . import telefones as svc_tel, criancas as svc_cri, historico


def ip_do_contato(uri, via_addr):
    """IP de origem do registro. Com rewrite_contact=yes o Asterisk grava na URI do contato o endereco
    de onde o pacote veio (IP publico do roteador da familia); via_addr e o que o telefone escreveu no
    cabecalho Via, normalmente o IP privado da casa (192.168.x.x), inutil para comparar com o IP do
    provisionamento. Bancada 26/10/2026: uri=sip:7XX534@191.32.207.123:40134, via_addr=192.168.1.32."""
    host = ''
    if uri and '@' in uri:
        host = uri.split('@', 1)[1]
        if host.startswith('['):                       # IPv6 entre colchetes
            host = host[1:].split(']', 1)[0]
        else:
            host = re.split(r'[:;^?]', host, 1)[0]
    return host or via_addr


def contatos_registrados(conn):
    """{id_rede: {'ip':..., 'ua':...}} a partir de ps_contacts. Vazio se a tabela nao existe."""
    if not db.tabela_existe(conn, 'ps_contacts'):
        return {}
    rows = conn.execute(text("SELECT endpoint, via_addr, user_agent, uri FROM ps_contacts")).all()
    out = {}
    for endpoint, via_addr, ua, uri in rows:
        if endpoint:
            out[endpoint] = {'ip': ip_do_contato(uri, via_addr), 'ua': ua, 'uri': uri}
    return out


def observar(conn, cfg, ref=None):
    ref = ref or agora()
    res = {'registrados': 0, 'ativos': 0, 'timeout_boot': 0, 'timeout_registro': 0, 'vinculos_expirados': 0}
    contatos = contatos_registrados(conn)

    for tel in conn.execute(select(db.telefones).where(db.telefones.c.estado != 'desativado')).mappings().all():
        cr = svc_cri.por_id(conn, tel['crianca_id'])
        if not cr:
            continue
        c = contatos.get(cr['id_rede'])
        if c:
            # Registro antes do fluxo permitir = credencial fora de lugar
            if tel['estado'] in ('dados_informados', 'gdms_cadastrado', 'aguardando_boot', 'erro_dados', 'erro_gdms_conflito'):
                if not _caso_aberto(conn, 'credencial_vazada', tel['id']):
                    svc_cri.rotacionar_senha_sip(conn, cr['id'], 'sistema', 'sip_observer', 'registro_fora_de_fluxo')
                    _caso(conn, tel, cr, 'credencial_vazada', 'alta',
                          f'Ramal {cr["id_rede"]} registrou de {c["ip"]} antes do telefone buscar configuração. Senha SIP rotacionada.',
                          {'ip': c['ip'], 'ua': c['ua'], 'estado': tel['estado']})
                    auditoria.registrar(conn, 'alerta_credencial_vazada', 'sistema', 'sip_observer', 'telefone', tel['id'],
                                        detalhes={'ip': c['ip'], 'estado': tel['estado']})
                continue
            vals = {'ultimo_sip_em': ref, 'ultimo_sip_ip': c['ip'], 'ultimo_sip_ua': (c['ua'] or '')[:300]}
            conn.execute(update(db.telefones).where(db.telefones.c.id == tel['id']).values(**vals))
            if estados.pode(tel['estado'], 'sip_registrado'):
                estados.transicionar(conn, tel['id'], 'sip_registrado', 'telefone', cr['id_rede'],
                                     detalhes={'ip': c['ip'], 'user_agent': (c['ua'] or '')[:120]})
                res['registrados'] += 1
                if tel['ultimo_prov_ip'] and c['ip'] and tel['ultimo_prov_ip'] != c['ip']:
                    _caso(conn, tel, cr, 'ip_divergente_sip', 'baixa',
                          f'IP do registro SIP ({c["ip"]}) difere do IP do provisionamento ({tel["ultimo_prov_ip"]}).',
                          {'ip_sip': c['ip'], 'ip_prov': tel['ultimo_prov_ip']}, unico=True)
            elif tel['estado'] == 'registrado' and historico.primeira_chamada_registrada(conn, cr['id_rede'], tel['registrado_em']):
                estados.transicionar(conn, tel['id'], 'primeira_chamada', 'telefone', cr['id_rede'])
                res['ativos'] += 1
            elif tel['ultimo_sip_ip'] and c['ip'] and tel['ultimo_sip_ip'] != c['ip']:
                auditoria.registrar(conn, 'sip_registrou_de_ip_novo', 'telefone', cr['id_rede'], 'telefone', tel['id'],
                                    detalhes={'de': tel['ultimo_sip_ip'], 'para': c['ip']})
        else:
            if tel['estado'] == 'registrado' and not historico.primeira_chamada_registrada(conn, cr['id_rede'], tel['registrado_em']):
                pass
            if tel['estado'] in ('registrado', 'ativo') and tel['ultimo_sip_em'] \
                    and utc(tel['ultimo_sip_em']) < ref - timedelta(hours=1) \
                    and not _ja_registrado(conn, 'sip_perdeu_registro', tel['id'], ref - timedelta(hours=24)):
                auditoria.registrar(conn, 'sip_perdeu_registro', 'sistema', 'sip_observer', 'telefone', tel['id'],
                                    detalhes={'ultimo_sip_em': str(tel['ultimo_sip_em'])})
            # primeira chamada tambem conta sem contato ativo (telefone pode ter saido do ar depois)
            if tel['estado'] == 'registrado' and historico.primeira_chamada_registrada(conn, cr['id_rede'], tel['registrado_em']):
                estados.transicionar(conn, tel['id'], 'primeira_chamada', 'telefone', cr['id_rede'])
                res['ativos'] += 1

        # Timeouts
        if tel['estado'] == 'aguardando_boot':
            inicio = tel['familia_ligou_em'] or tel['config_enviada_em']
            if inicio and utc(inicio) < ref - timedelta(minutes=cfg.PRAZO_SEM_BOOT_MIN):
                estados.transicionar(conn, tel['id'], 'timeout_boot', 'sistema', 'sip_observer')
                _caso(conn, tel, cr, 'sem_boot', 'media',
                      f'Telefone {tel["mac"]} não buscou configuração em {cfg.PRAZO_SEM_BOOT_MIN} min.', {})
                res['timeout_boot'] += 1
        elif tel['estado'] == 'config_entregue':
            if tel['config_entregue_em'] and utc(tel['config_entregue_em']) < ref - timedelta(minutes=cfg.PRAZO_SEM_REGISTRO_MIN):
                estados.transicionar(conn, tel['id'], 'timeout_registro', 'sistema', 'sip_observer')
                _caso(conn, tel, cr, 'sem_registro', 'media',
                      f'Telefone {tel["mac"]} recebeu configuração mas não registrou em {cfg.PRAZO_SEM_REGISTRO_MIN} min.',
                      {'ua': tel['ultimo_prov_ua'], 'ip': tel['ultimo_prov_ip']})
                res['timeout_registro'] += 1
        # Vinculo provisorio expirado
        if tel['estado'] in ('dados_informados', 'gdms_cadastrado', 'aguardando_boot', 'sem_boot', 'erro_dados', 'erro_gdms_conflito') \
                and tel['informado_em'] and utc(tel['informado_em']) < ref - timedelta(days=cfg.VINCULO_EXPIRA_DIAS):
            svc_tel.desativar(conn, tel['id'], 'sistema', 'sip_observer', motivo='vinculo_expirado', cfg=cfg, evento='vinculo_expirado')
            res['vinculos_expirados'] += 1
    auditoria.registrar(conn, 'jobs_rapidos_executados', 'sistema', 'sip_observer', detalhes=res)
    return res


def _caso_aberto(conn, tipo, telefone_id):
    return conn.execute(select(db.casos.c.id).where(and_(db.casos.c.tipo == tipo, db.casos.c.telefone_id == telefone_id,
                                                         db.casos.c.estado == 'aberto'))).first() is not None


def _ja_registrado(conn, acao, telefone_id, desde):
    return conn.execute(select(db.audit_log.c.id).where(and_(db.audit_log.c.acao == acao,
                                                             db.audit_log.c.objeto_tipo == 'telefone',
                                                             db.audit_log.c.objeto_id == str(telefone_id),
                                                             db.audit_log.c.ts >= desde))).first() is not None


def _caso(conn, tel, cr, tipo, gravidade, descricao, detalhes, unico=False):
    if unico and _caso_aberto(conn, tipo, tel['id']):
        return
    conn.execute(insert(db.casos).values(tipo=tipo, gravidade=gravidade, telefone_id=tel['id'], crianca_id=cr['id'],
                                         familia_id=cr['familia_id'], descricao=descricao, detalhes=detalhes,
                                         estado='aberto', criado_em=agora()))
