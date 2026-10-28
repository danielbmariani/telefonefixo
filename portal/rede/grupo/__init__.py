"""Chamada em grupo (doc 16): servico que controla a chamada pelo ARI do Asterisk.

- ari.py      cliente REST minimo (urllib, sem dependencias)
- app.py      a logica da chamada, dirigida por eventos; testavel com um ARI falso
- servico.py  o processo: websocket de eventos do Asterisk -> app; timers; reconexao
"""
