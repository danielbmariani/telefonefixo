# Proposta original (23/10/2026)

Texto histórico, escrito antes dos aparelhos chegarem e antes dos testes de bancada. Várias
coisas aqui já foram feitas ou decididas de outra forma; o estado atual está em `bancada/README.md`
e em `docs/08-decisoes-em-aberto.md`. Fica guardado para quem quiser entender de onde o projeto partiu.

---


Proposta para transformar o projeto `telefone_fixo` (rede fechada, meia dúzia de
famílias, aparelho configurado à mão pelo Daniel) numa **rede aberta, sem fins
lucrativos e open source**, operada por uma ONG que trabalha com crianças e telas.

A ideia em uma frase: qualquer família compra um telefone IP Grandstream comum,
entra no site, cria a conta, a criança escolhe um apelido e recebe um ID; o site
configura o telefone; a criança só consegue ligar para quem as duas famílias
autorizaram.

Algo próximo do Tin Can (EUA), mas aberto, sem lucro e com hardware de prateleira.

## A pergunta: é possível?

**Sim.** O hardware é de prateleira: o telefone IP Grandstream GXP1610 (que o
projeto já suporta) custa entre R$ 160 e R$ 300 no varejo brasileiro e liga
direto no roteador. O software já faz quase tudo: autorização mútua, horários,
histórico, chamada em grupo, celular da família. O que falta é de três tipos:

1. **Provisionamento remoto** — hoje o telefone é configurado por um script rodando
   na mesma rede local que ele. Um site não consegue fazer isso diretamente
   (o navegador bloqueia acesso a endereços da rede local). A solução é usar
   os mecanismos de provisionamento automático que o próprio telefone tem.
   Há três caminhos viáveis, detalhados em `docs/02-provisionamento.md`.
2. **Autocadastro e numeração** — hoje é o admin que cria ramais de 3 dígitos e
   reinicia o Asterisk a cada novo ramal. Numa rede aberta o ramal nasce no
   cadastro, sem reiniciar nada (PJSIP realtime), com IDs de 6 dígitos.
3. **Operação de rede pública com crianças** — moderação, abuso, LGPD, ECA Digital,
   suporte, custos. Nada disso é difícil tecnicamente, mas precisa ser
   desenhado antes de abrir a porta.

## Recomendação resumida

**Decisão (23/10/2026): caminho 3, zero-touch.** A família digita o MAC e o
número de série da etiqueta no site, liga o telefone no roteador e ele se
configura sozinho pela nuvem gratuita da Grandstream (GDMS, por API). Kits
preparados pela ONG foram descartados (dão trabalho à ONG) e o arquivo de
configuração fica só como último recurso. O plano detalhado, com auditoria em
cada etapa, está em `docs/09-plano-caminho-3-zero-touch.md`.

Consequência importante: **o GXP1610 não é suportado pelo GDMS**. O telefone de
referência passa a ser o **Grandstream GRP2601** (~R$ 300 no Brasil, linha
atual, feito para zero-touch), com o GRP2602W (Wi-Fi, ~R$ 500) como opção.

| Fase | O que entrega | Provisionamento |
|------|---------------|-----------------|
| Fase 0 (bancada, 2 dias) | Confirmação do zero-touch com 2 GRP2601 reais, P-values e códigos de erro | — |
| MVP (piloto, 20 a 50 famílias) | Site com autocadastro, apelido + ID, amizades por ID, ramais dinâmicos, auditoria completa | Zero-touch: MAC + serial no site |
| v1 | Painel da ONG completo, PWA, fallback por arquivo para casos de conflito | Zero-touch + arquivo (último recurso) |
| v2 | Escala, caixa postal, segunda instância | — |

## Conteúdo desta pasta

```
rede-aberta/
  README.md                          <-- (na época) este texto; hoje o README é só para contribuidores
  docs/
    01-visao-e-modelo.md             <-- o que é, princípios, comparação com Tin Can, papel da ONG
    02-provisionamento.md            <-- a questão central: como o site configura o telefone
    03-arquitetura.md                <-- o que muda em relação ao projeto atual
    04-fluxo-da-familia.md           <-- jornada passo a passo (comprar, cadastrar, ativar, ligar)
    05-seguranca-privacidade-legal.md<-- modelo de segurança, LGPD, ECA Digital, Anatel
    06-custos-escala-operacao.md     <-- custos por tamanho de rede, capacidade, papéis da ONG
    07-roadmap.md                    <-- fases, entregas e estimativas
    08-decisoes-em-aberto.md         <-- o que precisa ser decidido com a ONG
    09-plano-caminho-3-zero-touch.md <-- PLANO DE EXECUÇÃO: zero-touch com auditoria em cada etapa
  portal/                            <-- CÓDIGO (Flask + SQLAlchemy + Postgres), 42 testes passando
    README.md                        <-- como rodar, estrutura, o que a bancada ainda confirma
    rede/                            <-- app, serviços (E1-E10), auditoria, estados, web, templates
    agi/                             <-- check_call, check_group, log_call (usam a lógica do portal)
    deploy/                          <-- extensions.conf, realtime, systemd, nginx, grants.sql, portal.env.exemplo
    tests/
  bancada/
    README.md                        <-- checklist B01-B20 com status e onde cada evidência vai
```

O protótipo inicial foi absorvido pelo `portal/` (os módulos `ids`, `grandstream_xml` e
`gdms_client` viraram parte do pacote `rede`).

## Relação com o projeto atual

Nada aqui altera `telefone_fixo/`. A rede aberta seria **outra instância**
(outro servidor, outro domínio, outro banco), partindo do mesmo código.
A rede atual continua como está. As duas podem conviver indefinidamente;
migrar as famílias atuais para a rede aberta é opcional (ver roadmap).

## Estado (23/10/2026)

- Telefones GRP2601 comprados, ainda não entregues. Conta GDMS criada, org
  "Rede Aberta - bancada" (<org_id>), API funcionando (B01-B03, B05, B06 feitos;
  `bancada/README.md`).
- A referência completa da API (`bancada/referencia-api/`) mostrou que o GDMS
  entrega um XML ao aparelho por API (`device/config/xml`) e avisa por webhook.
  E5 ficou sem operador: implementado no portal (`gdms_client`, `gdms_fila`,
  `/gdms/eventos/<segredo>`), 48 testes passando.
- Servidor da bancada no ar (`https://rede-aberta-bancada.duckdns.org`, Oracle E2.1.Micro,
  `portal/deploy/setup-servidor.sh`): fluxo E1–E8 verificado com curl e um REGISTER SIP
  (`bancada/B07-portal-no-ar.md`). P-values do GRP2601 lidos do GDMS (`bancada/B04-pvalues-grp2601.md`).
- Site redesenhado (`docs/11-design.md`, `docs/12-tin-can-pesquisa.md`): página inicial pública, cadastro em 5 passos,
  reenvio de código, e-mail real (SMTP) na bancada.
- Falta a bancada com o aparelho: B06b (XML a aparelho offline), B06c (webhook),
  B08-B19 (boot, HTTPS no aparelho, reset, conflito).
- Celular da família (Groundwire) ainda não portado.
- Textos legais são rascunhos para revisão jurídica.

## Próximos passos

1. Quando o GRP2601 chegar: B05 com o aparelho real, B06b, B06c, B08-B11 (`bancada/README.md`).
2. Trocar o servidor da bancada para `GDMS_MODO=real` e registrar o webhook (`flask gdms-eventos`).
3. Fechar as decisões do doc 08 com a ONG e a revisão jurídica dos textos.
