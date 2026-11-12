"""Prepara os registros, compara os períodos e apresenta as associações."""
from pathlib import Path
import hashlib
import re
import struct
import zipfile
import xml.etree.ElementTree as ET

import numpy as np
import pandas as pd

MUN, TIPO, COD, PROTO = 'Cod_IBGE_Mun', 'descricao_tipologia', 'Cod_Cobrade', 'Protocolo_S2iD'
FAMILIA = ['Alagamentos', 'Chuvas Intensas', 'Enxurradas', 'Inundações']
ROTULO = 'Chuva e processos hidrológicos'
TIPOS = sorted(['Estiagem e Seca', 'Enxurradas', 'Chuvas Intensas', 'Inundações',
    'Vendavais e Ciclones', 'Incêndio Florestal', 'Granizo', 'Alagamentos',
    'Movimento de Massa', 'Outros', 'Erosão', 'Doenças infecciosas', 'Onda de Frio',
    'Onda de Calor e Baixa Umidade', 'Tornado', 'Rompimento/Colapso de barragens'])
UFS = dict(zip('11 12 13 14 15 16 17 21 22 23 24 25 26 27 28 29 31 32 33 35 41 42 43 50 51 52 53'.split(),
    'RO AC AM RR PA AP TO MA PI CE RN PB PE AL SE BA MG ES RJ SP PR SC RS MS MT GO DF'.split()))
BASE_TRATADA = 'dados/tratados/atlas_preparado_entrega_tratado.csv'
SHA256_TRATADO = '60fe9f43f49fba9aa224e54b7e29559255221a1baba51fbf9f0d11188bc4f555'
IBGE_2013 = 'dados/referencias/dtb_2013_municipio.xls'
IBGE_2025 = 'dados/referencias/RELATORIO_DTB_BRASIL_2025_MUNICIPIOS.ods'
HASHES_REFERENCIAS = {
    IBGE_2013: 'a57d3b3ad09babde9a5d5fc9b90a3f7472cea12c42c26bc0f8b7338fd78e7f77',
    IBGE_2025: 'a0606b9706c248138131511287e582a9293ba786096e0395192be36108d029fa',
}


def exigir(condicao, mensagem):
    if not condicao:
        raise ValueError(mensagem)

def hash_arquivo(p):
    with p.open('rb') as f:
        return hashlib.file_digest(f, 'sha256').hexdigest()

def ler_ibge_2013(arquivo):
    """Extrai somente células LABEL do relatório BIFF4 fixado por SHA-256.

    Não é um leitor XLS geral. Formato, cabeçalho e 5.570 códigos são conferidos.
    """
    dados=Path(arquivo).read_bytes()
    exigir(dados[:4]==b'\x09\x04\x06\x00', 'Formato inesperado no relatório IBGE 2013.')
    celulas={}
    pos=0
    while pos+4<=len(dados):
        tipo,tamanho=struct.unpack_from('<HH',dados,pos)
        registro=dados[pos+4:pos+4+tamanho]
        exigir(len(registro)==tamanho,'Registro IBGE 2013 truncado.')
        if tipo==0x204:
            linha,coluna,formato,n=struct.unpack_from('<HHHH',registro)
            exigir(len(registro[8:])==n,'Texto IBGE 2013 truncado.')
            exigir((linha,coluna) not in celulas,'Célula IBGE 2013 duplicada.')
            celulas[(linha,coluna)]=registro[8:8+n].decode('cp1252')
        pos+=4+tamanho
    exigir(celulas[(0,7)]=='Cod Municipio Completo','Cabeçalho IBGE 2013 diferente.')
    linhas=[(celulas[(r,7)],celulas[(r,8)],celulas[(r,0)])
        for r in sorted({r for r,c in celulas if r>0})]
    return pd.DataFrame(linhas,columns=[MUN,'nome_ibge','codigo_uf']).set_index(MUN)

def ler_ibge_2025(arquivo):
    ns={'t':'urn:oasis:names:tc:opendocument:xmlns:table:1.0'}
    with zipfile.ZipFile(arquivo) as z:
        doc=ET.fromstring(z.read('content.xml'))
    linhas=[]
    for linha in doc.findall('.//t:table-row',ns):
        celulas=[]
        for c in linha:
            repeticoes=int(c.attrib.get('{'+ns['t']+'}number-columns-repeated','1'))
            celulas.extend([''.join(c.itertext())]*min(repeticoes,20))
        if len(celulas)>8 and re.fullmatch('[0-9]{7}',celulas[7]):
            linhas.append((celulas[7],celulas[8],celulas[0]))
    return pd.DataFrame(linhas,columns=[MUN,'nome_ibge','codigo_uf']).set_index(MUN)

def validar_ibge(raiz, dados):
    """Confere os códigos e as UFs publicados nas listas de 2013 e 2025."""
    for ano, ref in ((2013, ler_ibge_2013(raiz / IBGE_2013)), (2025, ler_ibge_2025(raiz / IBGE_2025))):
        exigir(ref.index.is_unique and len(ref) == {2013: 5570, 2025: 5571}[ano],
               'Cadastro municipal incompleto ou duplicado.')
        exigir(dados[MUN].str[:2].eq(dados[MUN].map(ref.codigo_uf)).all(),
               'Código ou UF divergente das referências do IBGE.')
    return int(dados[MUN].nunique())


from collections import Counter
from itertools import combinations

import matplotlib.pyplot as plt
from IPython.display import display

from mineradores import comparar_mineradores, tabela_pares, tabela_regras

PERIODOS = {'1991–2012': (1991, 2012), '2013–2025': (2013, 2025)}
MINIMO = 30
LIFT_MINIMO = 1.20
CALOR = 'Onda de Calor e Baixa Umidade'
COBRADE_CHUVA = dict(zip(FAMILIA, ('12300', '13214', '12200', '12100')))
CORES = ('#167484', '#D96B33')
FONTE = 'Dados: Atlas Digital de Desastres no Brasil (v1.1, 2026)'


def carregar(raiz):
    fontes = {BASE_TRATADA: SHA256_TRATADO, **HASHES_REFERENCIAS}
    exigir({p: hash_arquivo(raiz / p) for p in fontes} == fontes, 'Confira a edição dos dados e do IBGE.')
    dados = pd.read_csv(raiz / BASE_TRATADA, sep=';', dtype='string', keep_default_na=False)
    exigir(dados.shape == (76190, 134), 'Dimensões da edição divergentes.')
    campos = [MUN, TIPO, COD, PROTO, 'Data_Evento_dt', 'Data_Registro_dt', 'Ano_Evento', 'UF_pad']
    vazios = dados.apply(lambda coluna: coluna.str.strip().eq('').sum())
    exigir(vazios.loc[campos].eq(0).all(), 'Há campos essenciais vazios.')
    exigir(dados[PROTO].is_unique and not dados.duplicated().any(), 'Protocolos ou linhas duplicados.')
    exigir(dados[MUN].str.fullmatch(r'\d{7}').all() and dados[COD].str.fullmatch(r'\d{5}').all(),
           'Formato de código municipal ou COBRADE inválido.')
    exigir(dados[MUN].str[:2].map(UFS).eq(dados.UF_pad).all(), 'UF e código municipal divergem.')
    exigir(set(dados[TIPO]) == set(TIPOS), 'Tipologias diferentes das esperadas.')
    for tipo, codigo in COBRADE_CHUVA.items():
        exigir(dados[TIPO].eq(tipo).equals(dados[COD].eq(codigo)), f'Confira o código de {tipo}.')
    evento = pd.to_datetime(dados.Data_Evento_dt, format='%Y-%m-%d')
    registro = pd.to_datetime(dados.Data_Registro_dt, format='%Y-%m-%d')
    dados['ano'] = evento.dt.year
    exigir(dados.ano.eq(pd.to_numeric(dados.Ano_Evento)).all(), 'Ano do evento divergente.')
    exigir(set(dados.ano) == set(range(1991, 2026)), 'A série deve ir de 1991 a 2025.')
    qualidade = {
        'Protocolos distintos': int(dados[PROTO].nunique()),
        'Linhas integralmente duplicadas': 0,
        'Campos vazios entre os usados': int(vazios.loc[campos].sum()),
        'Outras colunas com vazios': int(vazios.gt(0).sum()),
        'Linhas em chaves repetidas de município, data e código': int(
            dados.duplicated([MUN, 'Data_Evento_dt', COD], keep=False).sum()),
        'Protocolos com registro anterior à data do evento': int(registro.lt(evento).sum()),
        'Protocolos recentes registrados em 2026': int((dados.ano.ge(2013) & registro.dt.year.eq(2026)).sum()),
        'Códigos municipais conferidos com o IBGE': validar_ibge(raiz, dados),
    }
    exigir({p: hash_arquivo(raiz / p) for p in fontes} == fontes, 'Uma fonte mudou durante a leitura.')
    return dados[[MUN, 'ano', 'UF_pad', TIPO]], qualidade


def transacoes(dados, inicio, fim, harmonizar=True):
    recorte = dados.loc[dados.ano.between(inicio, fim)]
    tipos = recorte[TIPO].replace(dict.fromkeys(FAMILIA, ROTULO)) if harmonizar else recorte[TIPO]
    matriz = pd.crosstab([recorte[MUN], recorte.ano, recorte.UF_pad], tipos).gt(0)
    categorias = sorted(set(TIPOS) - {CALOR} - set(FAMILIA) | {ROTULO}) if harmonizar else TIPOS
    # Inclui município-anos cujo único rótulo foi retirado, preservando o denominador.
    return matriz.reindex(columns=categorias, fill_value=False)


def estatisticas_pares(x):
    inteiros = x.to_numpy(dtype=np.int64)
    cruzamentos = inteiros.T @ inteiros
    contagens = {(a,): int(cruzamentos[i, i]) for i, a in enumerate(x.columns)}
    contagens.update({(a, b): int(cruzamentos[i, j])
                     for (i, a), (j, b) in combinations(enumerate(x.columns), 2)
                     if cruzamentos[i, j]})
    return tabela_pares(contagens, len(x))


def destacar(pares, minimo=MINIMO):
    return pares.loc[pares.n_AB.ge(minimo) & pares.lift.ge(LIFT_MINIMO)].copy()


def detalhar_par(x, a, b):
    contagens = x[[a, b]].groupby(level=['ano', 'UF_pad']).sum()
    tamanhos = x.groupby(level=['ano', 'UF_pad']).size()
    esperado_uf_ano = (contagens[a] * contagens[b] / tamanhos).sum()
    juntos = x[a] & x[b]
    observado = int(juntos.sum())
    esperado = x[a].sum() * x[b].sum() / len(x)
    return {
        'Município-anos': len(x), 'Juntos': observado, 'Suporte (%)': observado / len(x) * 100,
        'Esperado geral': esperado, 'Lift': observado / esperado if esperado else np.nan,
        'Esperado por UF e ano': esperado_uf_ano,
        'Observado / esperado por UF e ano': observado / esperado_uf_ano if esperado_uf_ano else np.nan,
        'Casos no Sul': int(juntos.loc[x.index.get_level_values('UF_pad').isin(['PR', 'SC', 'RS'])].sum()),
    }


def executar(raiz):
    dados, qualidade = carregar(raiz)
    matrizes = {nome: transacoes(dados, *anos) for nome, anos in PERIODOS.items()}
    pares, tempos, regras, resumo = {}, {}, {}, {}
    for nome, x in matrizes.items():
        contagens, tempos[nome] = comparar_mineradores(x, MINIMO, repeticoes=7)
        pares[nome] = tabela_pares(contagens, len(x))
        regras[nome] = tabela_regras(contagens, len(x))
        inicio, fim = PERIODOS[nome]
        total = int(dados.ano.between(inicio, fim).sum())
        resumo[nome] = {'Protocolos': total, 'Município-anos': len(x),
                        'Com 2+ categorias comparáveis': int(x.sum(axis=1).ge(2).sum()),
                        'Pares em destaque': len(destacar(pares[nome]))}

    conjuntos = [set(destacar(p).set_index(['A','B']).index) for p in pares.values()]
    comuns = sorted(set.intersection(*conjuntos))
    historico, recente = matrizes.values()
    exigir(comuns == [('Granizo', 'Vendavais e Ciclones')], 'Confira os destaques antes de atualizar a interpretação.')
    a, b = comuns[0]
    ids = historico.index.get_level_values(MUN).unique().intersection(recente.index.get_level_values(MUN).unique())
    def painel(x, municipios):
        return x.loc[x.index.get_level_values(MUN).isin(municipios)]
    sem_2024 = recente.loc[recente.index.get_level_values('ano') != 2024]
    sem_rs_2024 = recente.loc[~((recente.index.get_level_values('ano') == 2024)
                                 & (recente.index.get_level_values('UF_pad') == 'RS'))]
    historico_13 = historico.loc[historico.index.get_level_values('ano') >= 2000]
    ids_13 = historico_13.index.get_level_values(MUN).unique().intersection(
        recente.index.get_level_values(MUN).unique())
    cenarios = {
        '1991–2012': historico, '2013–2025': recente,
        'Municípios em ambos · 1991–2012': painel(historico, ids),
        'Municípios em ambos · 2013–2025': painel(recente, ids),
        'Janelas de 13 anos · 2000–2012': painel(historico_13, ids_13),
        'Janelas de 13 anos · 2013–2025': painel(recente, ids_13),
        '2013–2025, sem 2024': sem_2024,
        '2013–2025, sem RS em 2024': sem_rs_2024,
    }
    robustez = pd.DataFrame({nome: detalhar_par(x, a, b) for nome, x in cenarios.items()}).T

    alternativos = {nome: transacoes(dados, *anos, harmonizar=False)
                    for nome, anos in PERIODOS.items()}
    sensibilidade = {
        f'Mínimo de {m}': len(set.intersection(*[set(destacar(p, m).set_index(['A','B']).index)
            for p in (estatisticas_pares(x) for x in matrizes.values())])) for m in (15, 30, 50)
    }
    separado = [detalhar_par(x, a, b) for x in alternativos.values()]
    assert all(np.isclose(r['Lift'], robustez.loc[nome, 'Lift']) for nome, r in zip(PERIODOS, separado))
    assert robustez.loc[list(PERIODOS), 'Juntos'].tolist() == [90, 221]
    assert len(ids) == 4413
    contagem, quadro, alternativa = conferir_duplas(dados, matrizes)
    return (pd.DataFrame(resumo).T, qualidade, pd.concat(tempos, names=['Período']),
            pares, regras, robustez, sensibilidade, contagem, quadro, alternativa)


def grafico_principal(robustez):
    fig, eixos = plt.subplots(1, 2, figsize=(10.6, 3.7), sharex=True, layout='constrained')
    fig.suptitle('Granizo com vendavais e ciclones: registros do Atlas e valores de referência',
                 fontsize=13, fontweight='bold')
    rotulos = ['Encontrados no Atlas', 'Referência nacional', 'Referência por estado e ano']
    campos = ['Juntos', 'Esperado geral', 'Esperado por UF e ano']
    principal = robustez.loc[list(PERIODOS), campos]
    limite = principal.to_numpy().max() * 1.16
    for ax, (periodo, valores) in zip(eixos, principal.iterrows()):
        barras = ax.barh(rotulos, valores, color=['#233B4F', *CORES], height=.56)
        ax.bar_label(barras, labels=[f'{v:.0f}' for v in valores], padding=5, fontweight='bold')
        ax.set(title=periodo, xlabel='Casos (uma cidade em um ano)', xlim=(0, limite))
        ax.invert_yaxis()
        ax.grid(axis='x', alpha=.18)
        ax.set_axisbelow(True)
        for lado in ('top', 'right'):
            ax.spines[lado].set_visible(False)
    fig.supxlabel(FONTE + '  |  Valores esperados arredondados', fontsize=8, color='#445367')
    plt.show()


def grafico_periodos(resumo):
    fig, ax = plt.subplots(figsize=(8.5, 3.5), layout='constrained')
    com_duas = resumo['Com 2+ categorias comparáveis']
    totais = resumo['Município-anos']
    proporcoes = 100 * com_duas / totais
    barras = ax.barh(resumo.index, proporcoes, color=CORES, height=.6)
    rotulos = [
        f"{pct:.1f}".replace('.', ',') + '%  (' + f'{n:,} de {total:,}'.replace(',', '.') + ')'
        for pct, n, total in zip(proporcoes, com_duas, totais)
    ]
    ax.bar_label(barras, labels=rotulos, padding=7)
    ax.set(title='Dois ou mais tipos no mesmo município e ano',
           xlabel='% de cidades e anos com algum registro', xlim=(0, 30))
    ax.invert_yaxis()
    ax.grid(axis='x', alpha=.18)
    ax.set_axisbelow(True)
    fig.supxlabel(FONTE, fontsize=8, color='#445367')
    plt.show()


def grafico_algoritmos(tempos):
    quadro = tempos.reset_index(level=0).pivot(index='Algoritmo', columns='Período', values='Mediana (ms)')
    ax = quadro.reindex(['Apriori', 'FP-Growth', 'Eclat']).plot.barh(
        figsize=(8.5, 3.8), color=CORES, width=.7)
    for barras in ax.containers:
        ax.bar_label(barras, labels=[f'{b.get_width():.2f}'.replace('.', ',') for b in barras],
                     padding=5, fontsize=9)
    ax.set(title='Tempo de mineração por algoritmo', xlabel='Tempo mediano (ms)',
           ylabel='', xlim=(0, quadro.to_numpy().max() * 1.17))
    ax.invert_yaxis()
    ax.grid(axis='x', alpha=.18)
    ax.legend(title='Período', loc='lower right', frameon=False)
    ax.figure.text(.5, .01, 'Sete execuções por algoritmo e período, após aquecimento',
                   ha='center', fontsize=8)
    plt.tight_layout(rect=(0, .05, 1, 1))
    plt.show()


def conferir_duplas(dados, matrizes):
    completas = [estatisticas_pares(x).set_index(['A', 'B']) for x in matrizes.values()]
    nomes = list(matrizes)
    comuns = completas[0].join(completas[1], how='inner', lsuffix='_antigo', rsuffix='_recente')
    repetidas = comuns.loc[comuns.n_AB_antigo.ge(MINIMO) & comuns.n_AB_recente.ge(MINIMO)]
    linhas = []
    for a, b in repetidas.index:
        linha = {'Dupla': f'{a} + {b}'}
        for nome, x in matrizes.items():
            d = detalhar_par(x, a, b)
            linha[f'Juntos · {nome}'] = d['Juntos']
            linha[f'Lift · {nome}'] = d['Lift']
            linha[f'Por UF e ano · {nome}'] = d['Observado / esperado por UF e ano']
        linhas.append(linha)
    quadro = pd.DataFrame(linhas).set_index('Dupla')
    bruto = quadro[[f'Lift · {n}' for n in nomes]].ge(LIFT_MINIMO).all(axis=1)
    estratificado = quadro[[f'Por UF e ano · {n}' for n in nomes]].ge(LIFT_MINIMO).all(axis=1)
    contagem = pd.Series({
        'Apareceram nos dois períodos': len(comuns),
        'Pelo menos 30 vezes em cada': len(repetidas),
        'Lift geral ≥ 1,20 nos dois': int(bruto.sum()),
        'Razão por UF e ano ≥ 1,20 nos dois': int(estratificado.sum()),
    })
    alternativas = {nome: transacoes(dados, *anos, harmonizar=False) for nome, anos in PERIODOS.items()}
    destaques = [set(destacar(estatisticas_pares(x)).set_index(['A','B']).index) for x in alternativas.values()]
    duplas = sorted(set.intersection(*destaques))
    teste = pd.DataFrame([
        {'Dupla': f'{a} + {b}', 'Período': nome,
         **detalhar_par(x, a, b)} for a, b in duplas for nome, x in alternativas.items()
    ]).set_index(['Dupla', 'Período'])
    assert contagem.tolist() == [33, 8, 1, 0]
    return contagem, quadro.sort_values(f'Juntos · {nomes[1]}', ascending=False), teste


def grafico_triagem(contagem):
    fig, eixos = plt.subplots(1, 2, figsize=(10, 3.7), layout='constrained')
    fig.suptitle('Combinações registradas em 1991–2012 e também em 2013–2025', fontsize=14, fontweight='bold')
    paineis = (
        (['Registradas nos dois períodos', 'Pelo menos 30 casos\nem cada período'],
         contagem.iloc[:2], ['#3E638B', '#167484'], 'De 33 combinações a 8', 38),
        (['Comparação nacional', 'Por estado e ano'],
         contagem.iloc[2:], list(CORES), 'Das 8, quantas ficaram pelo menos\n20% acima nos dois períodos?', 8),
    )
    for ax, (rotulos, valores, cores, titulo, limite) in zip(eixos, paineis):
        barras = ax.barh(rotulos, valores, color=cores, height=.6)
        ax.bar_label(barras, padding=6, fontsize=10, fontweight='bold')
        ax.set(title=titulo, xlabel='Número de combinações', xlim=(0, limite))
        ax.invert_yaxis()
        ax.grid(axis='x', alpha=.16)
        ax.set_axisbelow(True)
    fig.supxlabel(FONTE, fontsize=8, color='#445367')
    plt.show()
