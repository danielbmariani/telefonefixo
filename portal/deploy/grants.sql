-- grants.sql — Papeis do Postgres (rodar como superusuario depois de criar as tabelas)
-- portal: le/escreve negocio; so INSERT/SELECT em auditoria.
-- asterisk: le ps_endpoints/ps_auths/ps_aors e escreve ps_contacts; le/escreve call_logs? Nao: os AGIs
--           rodam com o papel 'portal' via REDE_DATABASE_URL (eles importam o pacote rede).
CREATE ROLE portal LOGIN PASSWORD 'TROCAR';
CREATE ROLE asterisk LOGIN PASSWORD 'TROCAR';

-- Tabelas pertencem ao postgres (REASSIGN OWNED BY portal TO postgres se foram criadas pelo portal):
-- a checagem de FK para audit_log usa SELECT FOR KEY SHARE, que exige UPDATE do dono.
REASSIGN OWNED BY portal TO postgres;
GRANT USAGE ON SCHEMA public TO portal, asterisk;
GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA public TO portal;
GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA public TO portal;
-- Auditoria append-only
REVOKE UPDATE, DELETE, TRUNCATE ON audit_log, device_state_history, prov_log, gdms_log FROM portal;

GRANT SELECT ON ps_endpoints, ps_auths, ps_aors TO asterisk;
GRANT SELECT, INSERT, UPDATE, DELETE ON ps_contacts TO asterisk;
-- Teste: \c telefone portal; UPDATE audit_log SET acao='x' WHERE id=1;  -> deve falhar com permission denied
