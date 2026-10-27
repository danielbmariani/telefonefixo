# 07 — Roadmap

Fases curtas, cada uma com algo usável no fim. Estimativas em dias de trabalho
de uma pessoa (o Daniel ou alguém com o mesmo contexto). Não inclui o trabalho
da ONG (jurídico, comunicação, logística).

## Fase 0 — Decisões e validação em bancada (1 a 2 semanas)

- Fechar as decisões do doc 08 com a ONG (nome, hardware, moderação, legal).
- Comprar 2 GRP2601 (lojas diferentes) e, se possível, 1 GRP2602W.
- Rodar a bancada B01 a B20 do doc 09 (zero-touch de ponta a ponta, com
  evidências em `bancada/`). Resultado: P-values confirmados do GRP2601,
  códigos de erro do GDMS, decisão RPS × template e API × operador no E5.
- Documentar que o GXP1610 não serve ao zero-touch (B17).
- Registrar domínio.

Esforço técnico: 3 a 4 dias.

## Fase 1 — MVP e piloto (6 a 8 semanas)

Instância nova, com o código atual como base.

1. **Servidor**: Oracle A1, Postgres, Asterisk com PJSIP realtime, `setup-servidor.sh`
   adaptado. (3 dias)
2. **Portal**: autocadastro, verificação de e-mail, consentimento, apelido + ID,
   amizades por ID com pedido/aceite, estado do telefone, termos e privacidade,
   denúncia, painel básico da ONG. Reaproveita horários, histórico, família,
   exclusão de conta. (10 a 12 dias)
3. **Provisionamento**: endpoint `/boot` e `/p/<token>`, gerador de XML (o
   protótipo), log de acessos, "reconfigurar". (3 dias)
4. **Dialplan e AGIs** com IDs de 6 dígitos, mensagem nova de "não está na
   lista de amigos". (2 dias)
5. **Script de kits** em lote + API administrativa para cadastrar MACs. (2 dias)
6. **Documentação para a família** no site: fotos, FAQ, diagnóstico. (2 dias)
7. **Revisão de segurança** e jurídica. (externo)
8. **Piloto**: 20 a 50 famílias de uma ou duas escolas ligadas à ONG, kits
   preparados. Quatro semanas de uso com canal de suporte aberto.

Esforço técnico: 22 a 26 dias na versão original. **Com o caminho 3 e a
auditoria em cada etapa, a fase 1 revisada está na seção 8 do doc 09: 36 a 38
dias.** O doc 09 prevalece.

## Fase 2 — Abrir o cadastro (4 a 6 semanas)

- Caminho B (baixar configuração + passo a passo com fotos) e caminho C
  (MAC + serial via API do GDMS), se validado na fase 0. (5 dias)
- PWA com notificação de pedido de amizade. (3 dias)
- Painel da ONG completo: métricas, fila de denúncias, suspensão. (4 dias)
- Suporte a GRP2601/2601W no script de kits e no XML. (2 a 3 dias)
- Monitoramento e alertas. (1 dia)
- Opcional: migrar as famílias da rede atual (os ramais de 3 dígitos viram IDs
  de 6; é possível manter os 3 dígitos antigos como "apelidos numéricos" por um
  tempo, mas é mais simples renumerar e imprimir cartões novos).

Esforço técnico: 15 a 18 dias.

## Fase 3 — Escala e extras (contínuo)

- Caixa postal entre amigos (se a ONG decidir), com retenção curta.
- TLS/SRTP no SIP.
- Segunda instância (outra cidade/ONG) a partir do mesmo setup; estudo de
  federação.
- Telefone com Wi-Fi como padrão de kit.
- Relatórios agregados para a ONG (sem dados individuais) para captação e
  pesquisa.

## Critérios para sair do piloto

- 80% das famílias instalaram sem falar com o suporte.
- Nenhum incidente de segurança ou privacidade.
- Pelo menos metade das crianças fez uma chamada por semana no último mês
  (sinal de que a rede tem valor, não só novidade).
- Carga de suporte abaixo de 1 hora por família por mês.
