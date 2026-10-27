# 06 — Custos, escala e operação

## Custo para a família

| Item | Faixa (R$) | Observação |
|---|---|---|
| Telefone IP GXP1610 | 160 a 300 | varejo brasileiro, out/2026 (Kabum, Magazine Luiza) |
| GRP2601W (Wi-Fi) | a confirmar no Brasil | ~£36 no exterior, mais importação |
| Mensalidade | 0 | nenhuma |
| Ligação | 0 | nenhuma |

Em comparação: Tin Can, US$ 75 a 100 pelo aparelho mais US$ 9,99/mês se quiser
ligar para fora; não vendido no Brasil.

Se a ONG comprar em lote, o preço unitário cai e ela pode repassar a custo ou
subsidiar famílias que não podem pagar. Modelo de "doe um telefone" é natural.

## Custo de infraestrutura

| Tamanho da rede | Infra | Custo mensal estimado |
|---|---|---|
| até ~2.000 crianças | 1 VM Oracle Ampere A1 (free tier) + Postgres local + object storage free | R$ 0 (domínio ~R$ 40/ano, e-mail transacional grátis até alguns milhares/mês) |
| 2.000 a 10.000 | VM paga de 4 vCPU/8 GB (ou A1 pago) + Postgres gerenciado pequeno + e-mail pago | R$ 300 a 800 |
| acima de 10.000 | 2 servidores SIP + Postgres gerenciado + monitoramento | R$ 1.500 a 3.000 |

Hipóteses: pico de 2 a 3% das crianças em chamada ao mesmo tempo; chamadas sem
transcodificação; áudio passando pelo servidor (sem `direct_media`, como
hoje, porque NAT). Banda no pico de 10.000 crianças: ~250 chamadas × 180 kbit/s
≈ 45 Mbit/s, dentro de qualquer VPS razoável.

A dependência do free tier da Oracle é um risco (podem encerrar contas ociosas
ou mudar as regras). O `setup-servidor.sh` deveria funcionar em qualquer
Ubuntu, para migrar em uma tarde. Backup fora da Oracle.

## Carga de trabalho da ONG

Estimativa por 100 famílias ativas, depois do piloto:

| Atividade | Horas/mês | Quem |
|---|---|---|
| Suporte de instalação (cabo, SIP ALG, "não registra") | 4 a 8 | voluntário com roteiro; cai com o diagnóstico automático no portal |
| Preparar e enviar kits | 2 a 4 (por lote de 20) | voluntário |
| Moderação e denúncias | 1 a 2 | pessoa designada da ONG |
| Infra (atualizações, backup, incidentes) | 2 a 4 | pessoa técnica de referência |
| Comunicação com famílias e escolas | variável | equipe da ONG |

O piloto vai ter o dobro disso porque o processo ainda não está liso.

## Papéis mínimos

1. **Responsável técnico**: mantém servidor e código; decide incidentes. Pode
   ser o Daniel no começo, mas precisa de um segundo nome com acesso.
2. **Atendimento**: responde famílias em canal único (e-mail ou WhatsApp da
   ONG), com roteiro de diagnóstico.
3. **Encarregado de dados e moderação**: recebe denúncias, aplica a política,
   responde a titulares, fala com a ANPD se precisar.
4. **Logística**: compras, kits, cartões, correio.

## Sustentabilidade

- Custo recorrente quase zero até alguns milhares de crianças: o projeto
  sobrevive sem receita.
- Fontes possíveis: doação de aparelhos, editais de infância/educação,
  parcerias com escolas (a escola compra o lote), "adote um telefone".
- Nunca: mensalidade, anúncio, venda de dados. Isso é parte da proposta.

## Riscos operacionais e mitigação

| Risco | Mitigação |
|---|---|
| GXP1610 sai do mercado | homologar o GRP2601/2601W cedo; o código suporta vários modelos |
| Oracle encerra o free tier | setup reproduzível em qualquer VPS; backup externo; R$ 300/mês cobre |
| Grandstream desliga o GDMS | é só o caminho C; A e B não dependem |
| Pessoa técnica some | documentação (já é boa), segundo administrador, senhas em cofre da ONG |
| Incidente de segurança | plano de resposta, logs, capacidade de rotacionar todas as senhas SIP pelo portal |
| Falta de amigos na rede (criança sem para quem ligar) | adesão por escola/turma; a ONG promove "rodas" de famílias |
