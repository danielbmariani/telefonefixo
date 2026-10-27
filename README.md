# Telefone Fixo

Código do serviço https://telefonefixo.org: um telefone IP comum (Grandstream GRP2601, com cabo, ou
GRP2602W, Wi-Fi) que a família cadastra no site e que só liga para os amigos que as duas famílias
autorizaram. Sem tela, sem aplicativo, sem gravação. Projeto sem fins lucrativos.

Este repositório existe para quem quer entender como o serviço funciona ou contribuir com ele.
Quem quer usar o telefone não precisa de nada daqui: o caminho é o site.

## O que tem aqui

- `portal/`: o site e a lógica das chamadas (Flask, SQLAlchemy, Postgres, Asterisk PJSIP em realtime).
  Cadastro da família, apelido e ID da criança, provisionamento automático do aparelho pelo GDMS da
  Grandstream, amizades por ID, horários, celulares da família e auditoria. `portal/README.md` explica
  como rodar e a estrutura.
- `docs/`: decisões e pesquisa (arquitetura, provisionamento, LGPD e ECA Digital, segurança,
  design, parceiros). `docs/08-decisoes-em-aberto.md` é o resumo do que foi decidido.
- `bancada/`: registro dos testes com aparelhos reais (GRP2601, GDMS, central, celular dos pais).
  Capturas e documentação de terceiros ficam fora do repositório.

## Rodar e testar

```bash
cd portal
python3 -m venv .venv && . .venv/bin/activate
pip install -r requirements.txt
python3 -m pytest -q
```

Os testes rodam sem rede, em SQLite temporário. Para subir o site localmente, ver `portal/README.md`.

## Contribuir

Abra uma issue descrevendo o problema ou a ideia antes de um pull request grande. Ajuda bem-vinda:
revisão de segurança, acessibilidade e textos do site, testes com outros aparelhos Grandstream,
revisão jurídica dos textos em `portal/rede/textos/`.

Regras do repositório:

- Nunca entram credenciais, chaves, MAC ou número de série de aparelhos reais, nomes ou IDs de
  crianças. Exemplos usam valores fictícios.
- Credenciais ficam em `~/.config/rede-aberta/*.env` (local) e `/etc/rede-aberta/portal.env`
  (servidor); os scripts de `portal/deploy/` leem de lá.

## Licença

GNU AGPL-3.0 (arquivo `LICENSE`). Quem modificar e rodar o serviço para terceiros precisa publicar o
código modificado.
