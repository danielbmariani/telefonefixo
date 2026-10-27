-- retencao.sql — prazos da politica de privacidade para as tabelas somente-acrescimo (doc 13).
-- Roda todo dia como postgres (deploy/rede-retencao.cron). O papel do portal nao tem UPDATE/DELETE nelas.
-- Registros tecnicos do telefone e do GDMS: 180 dias.
DELETE FROM prov_log WHERE ts < now() - interval '180 days';
DELETE FROM gdms_log WHERE ts < now() - interval '180 days';
DELETE FROM device_state_history WHERE ts < now() - interval '180 days';
-- Auditoria: fica (sem nome, sem e-mail), mas o IP e o user-agent somem apos 1 ano.
UPDATE audit_log SET ip = NULL, user_agent = NULL WHERE ts < now() - interval '365 days' AND (ip IS NOT NULL OR user_agent IS NOT NULL);
-- Verificacoes de e-mail e tokens de senha usados ou vencidos: 30 dias.
DELETE FROM verificacoes_email WHERE criado_em < now() - interval '30 days';
DELETE FROM password_resets WHERE criado_em < now() - interval '30 days';
