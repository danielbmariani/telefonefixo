"""Grava o fluxo completo (conta -> crianca -> telefone -> amizade) num viewport de celular, com legendas."""
import asyncio, os, re, sys, tempfile, threading, time
sys.path.insert(0, os.getcwd()); sys.path.insert(0, 'tests')
from werkzeug.serving import make_server
from sqlalchemy import text
from rede import create_app, db, seguranca
from rede.config import Config
from rede.servicos import gdms_fila, sip
from conftest import cadastrar_e_entrar, criar_crianca, crianca_row, post

OUT = sys.argv[1]
PORT = 5077
tmp = tempfile.mkdtemp()
cfg = Config(env={}, AMBIENTE='teste', NOME='Telefone Fixo', DATABASE_URL=f'sqlite:///{tmp}/v.db', MAIL_BACKEND='memoria',
             GDMS_MODO='simulado', SITE_URL=f'http://127.0.0.1:{PORT}', PROV_URL=f'http://127.0.0.1:{PORT}', SIP_HOST='sip.teste',
             SECRET_KEY='v' * 64, TRONCO_NUMERO='1151083530')
app = create_app(cfg); db.init_db(app.engine, com_ps_contacts=True); seguranca.limpar_tentativas()
# Familia B ja existe: Casa do Beto
tc = app.test_client()
cadastrar_e_entrar(tc, app, email='casa.do.beto@exemplo.org', senha='Beto-e-amigos-2026', nome='Pai do Beto')
cb = criar_crianca(tc, 'beto'); ID_BETO = crianca_row(app, cb)['id_rede']; tc.get('/sair')
srv = make_server('127.0.0.1', PORT, app, threaded=True)
threading.Thread(target=srv.serve_forever, daemon=True).start()

INIT = r"""
(() => {
  function desenhar() {
    let t=''; try { t = localStorage.getItem('legenda') || ''; } catch (e) {}
    let el = document.getElementById('legenda-video');
    if (!el) { el = document.createElement('div'); el.id = 'legenda-video'; document.documentElement.appendChild(el);
      const s = document.createElement('style'); s.textContent = `
        #legenda-video{position:fixed;left:12px;right:12px;bottom:14px;z-index:99999;background:#1f2328;color:#fff;border-radius:16px;
          padding:16px 18px;font:700 20px/1.3 'Atkinson Hyperlegible',system-ui,sans-serif;box-shadow:0 8px 30px rgba(0,0,0,.35);
          border-left:8px solid #e8542c;opacity:0;transition:opacity .35s}
        #legenda-video.on{opacity:1}
        .toque{position:fixed;width:44px;height:44px;margin:-22px 0 0 -22px;border-radius:50%;background:rgba(232,84,44,.55);
          border:3px solid #e8542c;z-index:99998;animation:toque .6s ease-out forwards;pointer-events:none}
        @keyframes toque{from{transform:scale(.4);opacity:1}to{transform:scale(1.6);opacity:0}}`; document.documentElement.appendChild(s); }
    el.textContent = t; el.className = t ? 'on' : ''; if (document.body) document.body.style.paddingBottom = '130px';
  }
  document.addEventListener('DOMContentLoaded', desenhar); setTimeout(desenhar, 0);
  window.__legenda = (t) => { try { localStorage.setItem('legenda', t); } catch (e) {} desenhar(); };
  function cursor() {
    let c = document.getElementById('cursor-video');
    if (!c) { c = document.createElement('div'); c.id = 'cursor-video';
      c.innerHTML = '<svg viewBox="0 0 24 24" width="38" height="38"><path d="M5 3l14 8.5-6.2 1.3L16 19l-2.6 1.3-3.2-6.3L6 18z" fill="#1f2328" stroke="#fff" stroke-width="1.6" stroke-linejoin="round"/></svg>';
      c.style.cssText = 'position:fixed;z-index:100000;pointer-events:none;transition:left .45s ease,top .45s ease;filter:drop-shadow(0 2px 4px rgba(0,0,0,.4))';
      let x = 200, y = 500; try { x = +sessionStorage.getItem('cx') || x; y = +sessionStorage.getItem('cy') || y; } catch (e) {}
      c.style.left = x + 'px'; c.style.top = y + 'px'; document.documentElement.appendChild(c); }
    return c;
  }
  document.addEventListener('DOMContentLoaded', cursor); setTimeout(cursor, 0);
  window.__mover = (x, y) => { const c = cursor(); c.style.left = x + 'px'; c.style.top = y + 'px'; try { sessionStorage.setItem('cx', x); sessionStorage.setItem('cy', y); } catch (e) {} };
  window.__toque = (x, y) => { window.__mover(x, y); const d = document.createElement('div'); d.className = 'toque'; d.style.left = x + 'px'; d.style.top = y + 'px';
    document.documentElement.appendChild(d); setTimeout(() => d.remove(), 700); };
})();
"""

async def main():
    from playwright.async_api import async_playwright
    async with async_playwright() as p:
        b = await p.chromium.launch()
        ctx = await b.new_context(viewport={'width': 390, 'height': 844}, device_scale_factor=2, is_mobile=True, has_touch=True, locale='pt-BR')
        await ctx.add_init_script(INIT)
        pg = await ctx.new_page()
        U = f'http://127.0.0.1:{PORT}'
        os.makedirs(OUT, exist_ok=True)
        estado = {'n': 0, 'ativo': True}
        async def capturar():
            while estado['ativo']:
                try:
                    await pg.screenshot(path=f"{OUT}/f{estado['n']:05d}.jpg", type='jpeg', quality=85, animations='allow', caret='initial')
                    estado['n'] += 1
                except Exception:
                    pass
                await asyncio.sleep(0.02)
        tarefa = asyncio.create_task(capturar())

        async def legenda(t, espera=2.6):
            await pg.evaluate('t => window.__legenda(t)', t); await pg.wait_for_timeout(int(espera * 1000))
        async def toque(sel, espera=0.9):
            loc = pg.locator(sel).first
            await loc.scroll_into_view_if_needed(); await pg.wait_for_timeout(500)
            box = await loc.bounding_box()
            await pg.evaluate('([x,y]) => window.__toque(x,y)', [box['x'] + box['width'] / 2, box['y'] + box['height'] / 2])
            await pg.wait_for_timeout(450); await loc.click(); await pg.wait_for_timeout(int(espera * 1000))
        async def digitar(sel, texto):
            loc = pg.locator(sel).first
            await loc.scroll_into_view_if_needed(); await pg.wait_for_timeout(300)
            box = await loc.bounding_box()
            await pg.evaluate('([x,y]) => window.__toque(x,y)', [box['x'] + 24, box['y'] + box['height'] / 2]); await pg.wait_for_timeout(450)
            await loc.click()
            await pg.locator(sel).first.type(texto, delay=55); await pg.wait_for_timeout(500)
        async def cartao(titulo, sub, espera):
            await pg.goto('about:blank'); await pg.set_content(f"""<html><body style="margin:0;height:100vh;display:flex;align-items:center;justify-content:center;background:#fff;font-family:'Atkinson Hyperlegible',system-ui,sans-serif;text-align:center;padding:32px">
              <link href="https://fonts.googleapis.com/css2?family=Atkinson+Hyperlegible:wght@400;700&display=swap" rel="stylesheet">
              <div><div style="width:120px;height:120px;border-radius:50%;background:#e8542c;margin:0 auto 28px;display:flex;align-items:center;justify-content:center"><svg viewBox="0 0 64 64" width="70"><path d="M22 17c2-2 5-1 6 1l3 6c1 2 0 4-2 5l-2 1c2 5 6 9 11 11l1-2c1-2 3-3 5-2l6 3c2 1 3 4 1 6l-3 3c-2 2-5 2-8 1-12-4-21-13-25-25-1-3-1-6 1-8z" fill="#fff"/></svg></div>
              <h1 style="font-size:40px;line-height:1.1;margin:0 0 18px;color:#1f2328">{titulo}</h1><p style="font-size:22px;color:#3b4149;margin:0">{sub}</p></div></body></html>""")
            await pg.wait_for_timeout(int(espera * 1000))

        await cartao('Telefone Fixo', 'Como funciona, do zero ao primeiro amigo.<br><br>Dois minutos.', 3.5)
        # 1. landing
        await pg.goto(U + '/'); await pg.evaluate("localStorage.setItem('legenda','')"); await pg.wait_for_timeout(800)
        await legenda('1. A família entra em telefonefixo.org e cria a conta.', 3)
        await toque('.topo-acoes a:has-text("Criar conta")')
        # 2. cadastro
        await legenda('Nome, e-mail e senha. Só isso.', 1.5)
        await digitar('#nome', 'Mãe do José'); await digitar('#email', 'mae.do.jose@exemplo.org')
        await digitar('#senha', 'Jose-liga-2026'); await digitar('#senha2', 'Jose-liga-2026')
        await toque('button:has-text("Criar conta"), button[type=submit]')
        # 3. codigo
        await legenda('Chega um código de 6 dígitos no e-mail.', 2)
        m = app.mailer.ultimo_para('mae.do.jose@exemplo.org'); codigo = re.search(r'\b(\d{6})\b', m['corpo']).group(1)
        await digitar('#codigo', codigo); await toque('button[type=submit]')
        # 4. consentimento
        await legenda('A lei pede: o responsável lê e autoriza o uso dos dados da criança.', 3)
        for t in ('termos', 'privacidade', 'crianca'):
            await toque(f'#aceito_{t}', 0.4)
        await toque('button:has-text("Continuar")')
        # 5. crianca
        await legenda('A criança tem só um apelido. Sem nome completo, sem idade.', 2.5)
        await digitar('#apelido', 'jose'); await toque('button:has-text("Criar e gerar o ID")', 1.2)
        await legenda('O site sorteia um número de 6 dígitos: é o ID do José.', 3)
        # 6. telefone
        await legenda('Agora o telefone. Escolha o modelo e copie os dois códigos da etiqueta de baixo.', 3)
        await toque('label[for=modelo-grp]', 0.6)
        await digitar('#serial', '35103ZC1D2'); await digitar('#mac', 'C074AD1A2B3C')
        await toque('button:has-text("Registrar telefone")', 1.5)
        await legenda('O site registra o telefone na Grandstream sozinho. Nada a fazer.', 2.5)
        with app.engine.begin() as c:
            for _ in range(3): gdms_fila.processar(c, app.cfg)
        await pg.reload(); await pg.wait_for_timeout(800)
        # desenho dos cabos centralizado entre as abas e a legenda, antes de a legenda aparecer
        await pg.evaluate("document.querySelector('.cabos svg').scrollIntoView({block:'center'})"); await pg.wait_for_timeout(600)
        await legenda('Ligue os cabos como no desenho. Internet, fone e energia.', 5.0)
        await pg.evaluate("window.scrollBy({top: 330, behavior: 'smooth'})"); await pg.wait_for_timeout(3000)
        await toque('button:has-text("Já liguei o telefone")', 1.2)
        await legenda('O telefone liga, busca a configuração e se conecta. Uns 2 minutos, sem mexer no teclado.', 2.5)
        # simula: busca do cfg + registro SIP
        with app.engine.begin() as c:
            tok = c.execute(text("SELECT token FROM prov_tokens WHERE ativo=1 ORDER BY id DESC LIMIT 1")).scalar()
        app.test_client().get(f'/p/{tok}/cfgC074AD1A2B3C.xml')
        with app.engine.begin() as c:
            idr = c.execute(text("SELECT id_rede FROM criancas WHERE apelido='jose'")).scalar()
            c.execute(text("INSERT OR REPLACE INTO ps_contacts (id, uri, user_agent, via_addr, via_port, endpoint) VALUES (:i, 'sip:x@200.1.2.3', 'Grandstream GRP2601', '200.1.2.3', 5060, :e)"), {'i': idr + '^1', 'e': idr})
            sip.observar(c, app.cfg)
        await pg.reload(); await pg.wait_for_timeout(600)
        await legenda('Conectado. Pode tirar do gancho e discar 100 para ouvir a hora certa.', 3)
        await pg.locator('#etapa-ativo').scroll_into_view_if_needed(); await pg.wait_for_timeout(1200)
        # 9. amigos
        await legenda('Agora, os amigos. Toque em "Autorizar amigos".', 1.8)
        await toque('a:has-text("Autorizar amigos")')
        await legenda('Digite o ID do amigo e diga quem é o seu filho para a outra família.', 2.5)
        await digitar('#id_rede', ID_BETO); await digitar('#mensagem', 'José, da 4ª série da Escola do Bairro')
        await toque('button:has-text("Pedir amizade")', 1.5)
        await legenda('O pedido foi. Só vale quando a outra família aceitar.', 2.5)
        # 11. casa do Beto
        await pg.goto(U + '/sair'); await pg.goto(U + '/entrar'); await pg.wait_for_timeout(500)
        await legenda('Na casa do Beto, a família entra no site e vê o pedido.', 2)
        await digitar('#email', 'casa.do.beto@exemplo.org'); await digitar('#senha', 'Beto-e-amigos-2026')
        await toque('button:has-text("Entrar")', 1.2)
        await pg.goto(U + f'/crianca/{cb}/contatos'); await pg.wait_for_timeout(800)
        await legenda('Vê o apelido, o ID e a apresentação. Se não reconhecer, recusa.', 3)
        await pg.locator('.mensagem-pedido').first.scroll_into_view_if_needed(); await pg.wait_for_timeout(800)
        await toque('form:has(input[name=acao][value=aceitar]) button', 1.5)
        await legenda('Pronto. José e Beto podem se ligar. Ninguém de fora consegue.', 3.5)
        await cartao('telefonefixo.org', 'Sem tela, sem aplicativo.<br>Só quem a família autoriza.<br><br>Projeto sem fins lucrativos, de código aberto.', 4)
        estado['ativo'] = False; await tarefa
        await ctx.close(); await b.close()
    srv.shutdown()
    print('quadros', estado['n'])

asyncio.run(main())
print('gravado em', OUT)
