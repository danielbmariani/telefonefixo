#!/usr/bin/env python3
"""
grandstream_xml.py — Gera o arquivo de provisionamento cfgMAC.xml para
telefones Grandstream (GXP1610, GRP26xx) e adaptadores HT80x.

O formato e o dos guias da Grandstream:

    <?xml version="1.0" encoding="UTF-8"?>
    <gs_provision version="1">
      <mac>000B82AABBCC</mac>
      <config version="1">
        <P271>1</P271>
        ...
      </config>
    </gs_provision>

Os P-values de conta SIP, rede e audio sao os mesmos que o
configurar-telefone.sh grava hoje pela API HTTP do aparelho. Os P-values de
provisionamento e de trava estao marcados como A CONFIRMAR: precisam ser
validados em bancada contra o Admin Guide de cada modelo antes de uso real.

Uso como modulo:

    from grandstream_xml import gerar_xml, pvalues_sip, pvalues_provisionamento
    pv = pvalues_sip('sip.rede.org', '345678', 'senha', 'jose07', modelo='gxp')
    pv.update(pvalues_provisionamento('https://prov.rede.org/p/TOKEN'))
    xml = gerar_xml('00:0b:82:aa:bb:cc', pv)

Uso na linha de comando:

    python3 grandstream_xml.py --mac 00:0b:82:aa:bb:cc --servidor sip.rede.org \
        --ramal 345678 --senha S3nh4 --nome jose07 --modelo gxp \
        --config-url https://prov.rede.org/p/TOKEN > cfg000b82aabbcc.xml
"""

import argparse
import hashlib
import re
import sys
from xml.sax.saxutils import escape

MAC_RE = re.compile(r'^[0-9A-F]{12}$')

MODELOS = ('gxp', 'grp', 'grpw', 'ht')   # grpw = GRP2602W (Wi-Fi): mesmos P-values do grp


# Letras que nao existem em hexadecimal e costumam ser lidas no lugar de um digito da etiqueta.
CONFUSOES_HEX = str.maketrans({'O': '0', 'Q': '0', 'D': 'D', 'I': '1', 'L': '1', 'S': '5', 'Z': '2', 'G': '6'})


def normalizar_mac(mac):
    """Aceita '00:0b:82:aa:bb:cc', '00-0B-82-AA-BB-CC' ou '000b82aabbcc'.
    Troca letras que nao existem em hex pelo digito parecido (O->0, I/L->1, S->5, Z->2, G->6):
    como um MAC so tem 0-9 e A-F, a troca nunca e ambigua. Retorna 12 hex maiusculos.
    Levanta ValueError se invalido."""
    limpo = re.sub(r'[^0-9A-Fa-f]', '', (mac or '').upper().translate(CONFUSOES_HEX))
    if not MAC_RE.match(limpo):
        raise ValueError(f'MAC invalido: {mac!r}')
    return limpo


def nome_arquivo(mac):
    """Nome que o aparelho pede ao servidor: cfg<mac minusculo>.xml."""
    return f'cfg{normalizar_mac(mac).lower()}.xml'


def pvalues_sip(servidor, ramal, senha_sip, nome_exibicao, modelo='gxp'):
    """P-values de conta SIP, NAT, transporte e audio.
    Copiados do configurar-telefone.sh (passo [3/7])."""
    if modelo not in MODELOS:
        raise ValueError(f'modelo deve ser um de {MODELOS}')
    if not re.match(r'^\d{3,7}$', ramal):
        raise ValueError(f'ramal invalido: {ramal!r}')
    if not senha_sip or len(senha_sip) < 12:
        raise ValueError('senha SIP deve ter pelo menos 12 caracteres')
    if not nome_exibicao:
        raise ValueError('nome de exibicao vazio')

    pv = {
        'P271': '1',          # Account Active
        'P47': servidor,      # Primary SIP Server
        'P35': ramal,         # SIP User ID
        'P36': ramal,         # SIP Authenticate ID
        'P34': senha_sip,     # SIP Authentication Password
        'P3': nome_exibicao,  # Display Name (apelido; aparece no visor de quem recebe)
        'P52': '2',           # NAT Traversal = Keep-Alive
        'P130': '1',          # SIP Transport = TCP (SIP ALG dos roteadores corrompe UDP)
        'P31': '1',           # SIP Registration = Yes
        'P32': '2',           # Register Expiration = 2 min
        'P81': '1',           # Unregister on Reboot = Yes
        'P57': '9',           # Vocoder 1 = G.722
        'P58': '0',           # Vocoder 2 = PCMU
        'P59': '8',           # Vocoder 3 = PCMA
    }
    if modelo in ('gxp', 'grp', 'grpw'):
        pv['P72'] = '1'       # Use # as Dial Key (ramal + # envia)
    else:
        # Especificos de FXS (HT80x), iguais ao script atual
        pv.update({
            'P133': '1',      # Jitter Buffer Type = Adaptive
            'P132': '1',      # Jitter Buffer Length = Medium
            'P50': '0',       # VAD = Disabled
            'P824': '0',      # Line Echo Canceller = Enabled
            'P4441': '0',     # Network Echo Suppressor = Enabled
            'P291': '1',      # Symmetric RTP = Yes
        })
    return pv


def pvalues_provisionamento(config_url, intervalo_min=1440, modelo='grp'):
    """P-values para o aparelho continuar buscando configuracao no nosso servidor.
    GRP2601 (lidos do template do GDMS em 2026-10-23, bancada B04):
      P212   Config Upgrade Via: 0=TFTP 1=HTTP 2=HTTPS
      P237   Config Server Path
      P194   Automatic Upgrade: 0=No 1=Yes
      P193   Automatic Upgrade check interval, minutos
      P238   Firmware Upgrade and Provisioning: 0=sempre checa firmware, 1=so se prefixo mudar,
             2=pula firmware (nao servimos firmware; evita 404 a cada boot)
      P145   Allow DHCP Option 43/66 to Override Server: 0 (roteador nao pode redirecionar)
      P1414  3CX Auto Provision: 0 (um PBX 3CX na LAN nao pode capturar o telefone)
    HT80x: Config Upgrade Via e P6767 (guias HT80x); demais iguais. A CONFIRMAR no HT802V2."""
    if not config_url.startswith(('http://', 'https://')):
        raise ValueError('config_url deve comecar com http:// ou https://')
    via = '2' if config_url.startswith('https://') else '1'
    pv = {
        'P237': config_url,
        'P194': '1',
        'P193': str(int(intervalo_min)),
    }
    if modelo == 'ht':
        pv['P6767'] = via
    else:
        pv.update({'P212': via, 'P238': '2', 'P145': '0', 'P1414': '0'})
    return pv


def senha_usuario_aparelho(senha_admin):
    """Senha do nivel 'user' do aparelho (P196), derivada da admin: nao precisa de coluna nova e
    nunca fica igual a padrao de fabrica. So letras e numeros, como o template exige."""
    return hashlib.sha256(('user:' + senha_admin).encode('utf-8')).hexdigest()[:16]


def pvalues_travas(senha_admin, modelo='grp'):
    """Travas para telefone de crianca. Referencia oficial: bancada/referencia-pvalues/
    grp260x_config_1.0.7.74.txt (secao Security Settings) e ht80x_v2_config_1.0.15.3.txt.

    GRP260x (bancada 26/10/2026: sem isso o menu do teclado fica aberto):
      P2     senha admin individual do aparelho
      P196   senha do nivel 'user' (derivada da admin)
      P1357  Configuration via Keypad Menu: 3 = Locked Mode (menu de configuracao fechado)
      P22373 Factory Reset Security Level: 1 = sempre pede senha (crianca nao reseta pelo teclado)
      P1650  Web Access Mode: 0 = so HTTPS (a web so existe na rede da casa, com a senha admin)
      P8469  Enable User Web Access: 0 = desligado
      P276   Enable SSH: 1 = nao (no template 0 = sim, 1 = nao)
    HT80x V2 (sem teclado nem visor): P2, P1650 (0 = HTTPS) e P276 (1 = sem SSH)."""
    if not senha_admin or len(senha_admin) < 8:
        raise ValueError('senha admin deve ter pelo menos 8 caracteres')
    pv = {'P2': senha_admin, 'P1650': '0', 'P276': '1'}
    if modelo != 'ht':
        pv.update({'P196': senha_usuario_aparelho(senha_admin), 'P1357': '3', 'P22373': '1', 'P8469': '0'})
    return pv


# Teclas do GRP260x que podem virar discagem rapida (referencia: bancada/referencia-pvalues/
# grp260x_config_1.0.7.74.txt, secao Virtual Multi-Purpose Keys). A VPK 1 fica como linha (P1363=31,
# e o que o monofone usa). Cada tecla: (modo, conta, descricao, valor). Modo 0 = SpeedDial.
TECLAS_GRP = (('P1365', 'P1366', 'P1467', 'P1468'),        # VPK 2 (segunda tecla de linha do 2601)
              ('P23800', 'P23801', 'P23802', 'P23803'),    # VPK 7 (dinamica)
              ('P23804', 'P23805', 'P23806', 'P23807'))    # VPK 8 (dinamica)


def pvalues_teclas(amigos, modelo='grp'):
    """Discagem rapida nas teclas do aparelho: amigos = [(apelido, id_rede), ...] na ordem das teclas.
    So GRP; o HT80x nao tem teclas. Teclas sem amigo voltam ao padrao (VPK 2 = linha; dinamicas = nada),
    para que remover uma amizade tambem limpe a tecla. Item 2 do doc 12; conferir no aparelho (B21)."""
    if modelo == 'ht':
        return {}
    pv = {}
    for i, (p_modo, p_conta, p_desc, p_valor) in enumerate(TECLAS_GRP):
        if i < len(amigos):
            apelido, id_rede = amigos[i]
            pv.update({p_modo: '0', p_conta: '0', p_desc: str(apelido)[:32], p_valor: str(id_rede)})
        else:
            pv.update({p_modo: '31' if i == 0 else '-1', p_conta: '0', p_desc: '', p_valor: ''})
    return pv


def gerar_xml(mac, pvalues, versao=1, incluir_mac=True):
    """Monta o XML. incluir_mac=False gera um arquivo generico (aceito no
    upload manual por qualquer aparelho)."""
    linhas = ['<?xml version="1.0" encoding="UTF-8"?>',
              '<gs_provision version="1">']
    if incluir_mac:
        linhas.append(f'  <mac>{normalizar_mac(mac)}</mac>')
    linhas.append(f'  <config version="{int(versao)}">')
    for chave in sorted(pvalues, key=lambda k: int(k[1:])):
        if not re.match(r'^P\d+$', chave):
            raise ValueError(f'chave invalida: {chave!r}')
        linhas.append(f'    <{chave}>{escape(str(pvalues[chave]))}</{chave}>')
    linhas.append('  </config>')
    linhas.append('</gs_provision>')
    return '\n'.join(linhas) + '\n'


def main(argv=None):
    p = argparse.ArgumentParser(description='Gera cfgMAC.xml Grandstream')
    p.add_argument('--mac', required=True)
    p.add_argument('--servidor', required=True, help='IP ou host SIP')
    p.add_argument('--ramal', required=True, help='ID de 6 digitos (ou ramal)')
    p.add_argument('--senha', required=True, help='senha SIP')
    p.add_argument('--nome', required=True, help='apelido (display name)')
    p.add_argument('--modelo', default='gxp', choices=MODELOS)
    p.add_argument('--config-url', help='URL do servidor de provisionamento')
    p.add_argument('--senha-admin', help='senha admin nova do aparelho')
    p.add_argument('--versao', type=int, default=1)
    p.add_argument('--sem-mac', action='store_true', help='XML generico, sem <mac>')
    a = p.parse_args(argv)

    pv = pvalues_sip(a.servidor, a.ramal, a.senha, a.nome, a.modelo)
    if a.config_url:
        pv.update(pvalues_provisionamento(a.config_url, modelo=a.modelo))
    if a.senha_admin:
        pv.update(pvalues_travas(a.senha_admin, a.modelo))
    sys.stdout.write(gerar_xml(a.mac, pv, a.versao, incluir_mac=not a.sem_mac))
    return 0


if __name__ == '__main__':
    sys.exit(main())
