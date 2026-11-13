"""geoip.py — Localizacao provavel de um endereco IP, pela base GeoLite2-City da MaxMind lida no proprio servidor.

Nada sai para terceiros: a base (arquivo .mmdb) e baixada pelo geoipupdate (deploy/geoip.sh) e consultada
localmente. Usos: (1) conferencia do fuso. O fuso da familia vem do navegador no cadastro e da pagina /fuso
(rede/fusos.py); o IP de onde o telefone busca a configuracao so serve para abrir um caso no painel quando os
dois nao batem (telefones.conferir_fuso) e como ultimo recurso no cadastro, quando o navegador nao mandou fuso.
(2) Sugestao do DDD da casa (rede/ddd.py), pela cidade e pelas coordenadas do IP do telefone.
Sem a base (REDE_GEOIP_DB inexistente) tudo devolve None e nada acontece. Limites: CGNAT e 4G costumam cair
na capital do estado ou em Sao Paulo, por isso e aviso ou sugestao para gente olhar, nunca correcao automatica.
"""

import ipaddress
import os
import threading

from .fusos import zona

_trava = threading.Lock()
_leitor = None
_assinatura = None   # (caminho, mtime) do arquivo aberto; geoipupdate troca o arquivo e o portal reabre sozinho


def disponivel(cfg):
    return bool(cfg.GEOIP_DB) and os.path.isfile(cfg.GEOIP_DB)


def _abrir(caminho):
    global _leitor, _assinatura
    import maxminddb
    assinatura = (caminho, os.stat(caminho).st_mtime_ns)
    with _trava:
        if _assinatura != assinatura:
            if _leitor:
                _leitor.close()
            _leitor = maxminddb.open_database(caminho)
            _assinatura = assinatura
        return _leitor


def _nome(bloco):
    nomes = (bloco or {}).get('names') or {}
    return nomes.get('pt-BR') or nomes.get('en') or None


def registro(ip, cfg):
    """O que a base diz do IP: {'pais', 'cidade', 'uf', 'lat', 'lon', 'raio_km', 'fuso'} (valores podem ser None),
    ou None (IP privado ou invalido, fora da base, base ausente, erro)."""
    try:
        end = ipaddress.ip_address((ip or '').strip())
        if not end.is_global or not disponivel(cfg):
            return None
        reg = _abrir(cfg.GEOIP_DB).get(str(end))
        if not reg:
            return None
        loc = reg.get('location') or {}
        subdivisoes = reg.get('subdivisions') or [{}]
        return {'pais': (reg.get('country') or {}).get('iso_code'),
                'cidade': _nome(reg.get('city')),
                'uf': (subdivisoes[0] or {}).get('iso_code'),
                'lat': loc.get('latitude'), 'lon': loc.get('longitude'), 'raio_km': loc.get('accuracy_radius'),
                'fuso': loc.get('time_zone')}
    except Exception:
        return None


def fuso_do_ip(ip, cfg):
    """Nome IANA do fuso onde o IP parece estar, ou None (IP privado, fora da base, base ausente, erro)."""
    reg = registro(ip, cfg)
    nome = (reg or {}).get('fuso')
    try:
        return nome if nome and zona(nome).key == nome else None
    except Exception:
        return None


def divergente(fuso_familia, fuso_ip, ref=None):
    """True se os dois fusos marcam horas diferentes agora. Cuiaba e Campo Grande nao divergem (ambos UTC-4);
    Sao Paulo e Manaus divergem. Com um dos dois ausente, nao ha o que comparar."""
    from datetime import datetime, timezone
    if not fuso_ip:
        return False
    ref = ref or datetime.now(timezone.utc)
    return ref.astimezone(zona(fuso_familia)).utcoffset() != ref.astimezone(zona(fuso_ip)).utcoffset()
