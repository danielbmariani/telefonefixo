"""log_call.py (AGI): status e duracao da chamada 1 a 1 a partir do DIALSTATUS e do ANSWEREDTIME."""
import importlib.util
import os

spec = importlib.util.spec_from_file_location('log_call', os.path.join(os.path.dirname(__file__), '..', 'agi', 'log_call.py'))
log_call = importlib.util.module_from_spec(spec); spec.loader.exec_module(log_call)


def test_nao_atendida_nao_e_completada():
    # tocou 8 s e quem ligou desistiu: antes virava ALLOWED 8 s ("Completada")
    assert log_call.classificar('CANCEL', '', '8') == ('CANCEL', None)
    assert log_call.classificar('NOANSWER', '', '60') == ('NOANSWER', None)
    assert log_call.classificar('BUSY', '', '3') == ('BUSY', None)
    assert log_call.classificar('CHANUNAVAIL', '', '1') == ('NOANSWER', None)


def test_atendida_conta_so_o_tempo_atendido():
    assert log_call.classificar('ANSWER', '42', '50') == ('ALLOWED', 42)
    assert log_call.classificar('ANSWER', '', '50') == ('ALLOWED', 50)


def test_sem_dialstatus():
    assert log_call.classificar('', '', '') == ('CANCEL', None)
    assert log_call.classificar('', '', '7') == ('ALLOWED', 7)


def test_agis_chamados_pelo_dialplan_tem_shebang():
    # O Asterisk executa o arquivo direto. Sem a primeira linha "#!", o AGI falha calado e nada e gravado
    # (foi o que aconteceu com o log_call.py de 28/10 a 05/11/2026).
    import glob
    import re
    pasta = os.path.join(os.path.dirname(__file__), '..', 'agi')
    dialplan = open(os.path.join(os.path.dirname(__file__), '..', 'deploy', 'asterisk', 'extensions.conf'), encoding='utf-8').read()
    chamados = set(re.findall(r'AGI\(([a-z_]+\.py)', dialplan))
    assert 'log_call.py' in chamados and 'check_call.py' in chamados
    for nome in chamados:
        with open(os.path.join(pasta, nome), encoding='utf-8') as f:
            assert f.readline().startswith('#!'), nome
    assert {os.path.basename(p) for p in glob.glob(os.path.join(pasta, '*.py')) if not os.path.basename(p).startswith('_')} >= chamados
