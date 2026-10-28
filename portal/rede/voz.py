"""voz.py — Frases faladas para o telefone (doc 16): frases fixas, apelidos e nomes de grupo.

Gera wav 8 kHz mono em VOZ_DIR (/var/lib/rede-aberta/sons), que o Asterisk enxerga como
`rede/...` (link em /usr/share/asterisk/sounds/rede). Backends: piper (voz natural pt-BR, offline)
ou espeak-ng (ja instalado no servidor, voz robotica). Em testes VOZ_BACKEND=nenhum: nao grava nada.
Nunca derruba a operacao que chamou: erro de voz vira registro na auditoria, e a chamada em grupo
segue sem o nome (so com os tons).
"""

import os
import re
import shutil
import subprocess
import tempfile

# Frases fixas, uma ideia por frase, sem pergunta (pesquisa de voz para criancas, doc 16 secao 2.3).
FRASES = {
    'chamada-em-grupo': 'Chamada em grupo.',
    'chamando': 'Chamando',
    'e': 'e',
    'nao-pode-agora': 'não pode agora.',
    'ninguem-pode-agora': 'Ninguém do grupo pode agora. Tente mais tarde.',
    'chamada-em-grupo-de': 'Chamada em grupo de',
    'na-chamada': 'Na chamada:',
    'voce': 'você.',
    'entrou': 'entrou.',
    'saiu': 'saiu.',
    'nao-atendeu': 'não atendeu.',
    'ninguem-atendeu': 'Ninguém atendeu. Tente de novo mais tarde.',
    'voce-e-o-unico': 'Você é o único na chamada.',
    'chamada-terminou': 'A chamada em grupo terminou.',
    'entrando': 'Entrando na chamada em grupo.',
    'chamada-cheia': 'A chamada está cheia. Tente mais tarde.',
    'grupo-nao-existe': 'Esse grupo não existe. Confira o cartão.',
    'fora-do-horario': 'Agora não é horário de telefone.',
    'nao-deu-certo': 'Não deu certo. Tente de novo.',
}


def texto_do_apelido(apelido):
    """'jose07' -> 'jose 0 7' (cada digito lido separado); '_' vira espaco."""
    t = (apelido or '').replace('_', ' ')
    t = re.sub(r'(\d)', r' \1', t)
    return ' '.join(t.split())


def backend_disponivel(cfg):
    b = (cfg.VOZ_BACKEND or 'nenhum').lower()
    if b == 'nenhum':
        return None
    if b in ('auto', 'piper') and shutil.which('piper') and os.path.exists(cfg.VOZ_PIPER_MODELO):
        return 'piper'
    if b in ('auto', 'espeak') and shutil.which('espeak-ng'):
        return 'espeak'
    return None


def caminho(cfg, grupo, nome):
    return os.path.join(cfg.VOZ_DIR, grupo, f'{nome}.wav')


def gerar(cfg, texto, destino):
    """Sintetiza `texto` em `destino` (wav 8 kHz mono 16 bit). Devolve True se gravou."""
    b = backend_disponivel(cfg)
    if not b or not shutil.which('sox'):
        return False
    os.makedirs(os.path.dirname(destino), exist_ok=True)
    with tempfile.TemporaryDirectory() as tmp:
        bruto = os.path.join(tmp, 'bruto.wav')
        if b == 'piper':
            subprocess.run(['piper', '--model', cfg.VOZ_PIPER_MODELO, '--output_file', bruto, '--length_scale', '1.1'],
                           input=texto.encode('utf-8'), check=True, timeout=120, capture_output=True)
        else:
            subprocess.run(['espeak-ng', '-v', 'pt-br', '-s', '140', '-w', bruto, texto], check=True, timeout=60,
                           capture_output=True)
        subprocess.run(['sox', bruto, '-r', '8000', '-c', '1', '-b', '16', destino + '.tmp.wav', 'norm', '-3'],
                       check=True, timeout=60, capture_output=True)
        os.replace(destino + '.tmp.wav', destino)
    return True


def gerar_frases(cfg):
    """Todas as frases fixas (roda no deploy). Devolve quantas gravou."""
    n = 0
    for nome, texto in FRASES.items():
        destino = caminho(cfg, 'frases', nome)
        if os.path.exists(destino):
            continue
        if gerar(cfg, texto, destino):
            n += 1
    return n


def gerar_apelido(cfg, id_rede, apelido):
    return gerar(cfg, texto_do_apelido(apelido), caminho(cfg, 'apelidos', id_rede))


def gerar_grupo(cfg, grupo_id, nome):
    return gerar(cfg, nome, caminho(cfg, 'grupos', str(grupo_id)))


def tem_apelido(cfg, id_rede):
    return os.path.exists(caminho(cfg, 'apelidos', id_rede))


def tem_grupo(cfg, grupo_id):
    return os.path.exists(caminho(cfg, 'grupos', str(grupo_id)))


def gerar_tons(cfg):
    """Tres sons curtos e distintos (ritmo e altura diferentes, doc 16 secao 3.4): entrou (duas notas subindo),
    saiu (duas notas descendo), erro (uma nota grave). E o tom de chamando para a espera (1 s ligado, 4 s
    desligado, 425 Hz, padrao brasileiro). Gera cada nota num arquivo e junta: o sox com dois `synth` na
    mesma linha nao termina."""
    if not shutil.which('sox'):
        return False
    d = os.path.join(cfg.VOZ_DIR, 'tons'); os.makedirs(d, exist_ok=True)
    m = os.path.join(cfg.VOZ_DIR, 'moh-chamando'); os.makedirs(m, exist_ok=True)
    fmt = ['-r', '8000', '-c', '1', '-b', '16']

    def nota(destino, segundos, hz):
        subprocess.run(['sox', '-n'] + fmt + [destino, 'synth', str(segundos), 'sine', str(hz), 'vol', '0.4'], check=True, timeout=30)

    with tempfile.TemporaryDirectory() as tmp:
        a, b = os.path.join(tmp, 'a.wav'), os.path.join(tmp, 'b.wav')
        nota(a, 0.12, 660); nota(b, 0.12, 880)
        subprocess.run(['sox', a, b, os.path.join(d, 'entrou.wav')], check=True, timeout=30)
        subprocess.run(['sox', b, a, os.path.join(d, 'saiu.wav')], check=True, timeout=30)
        nota(os.path.join(d, 'erro.wav'), 0.35, 330)
        nota(a, 1, 425)
        subprocess.run(['sox', a, os.path.join(m, 'chamando.wav'), 'pad', '0', '4'], check=True, timeout=30)
    return True
