"""Mineração exata de tipos isolados e pares em transações booleanas.

Os três métodos buscam os mesmos conjuntos frequentes. O limite de dois
tipos foi fixado para responder sobre duplas e facilitar a leitura das
regras. O tempo mede só a mineração, com as mesmas entradas em memória.
"""

from collections import Counter, defaultdict
from itertools import combinations
from numbers import Integral
from time import perf_counter

import numpy as np
import pandas as pd


def _validar(x, minimo):
    if not isinstance(x, pd.DataFrame) or x.empty or not x.index.is_unique:
        raise ValueError("Use uma matriz não vazia com transações únicas no índice.")
    if not x.columns.is_unique or any(not isinstance(c, str) or not c.strip() for c in x.columns):
        raise ValueError("Os tipos devem ter nomes únicos, não vazios.")
    if not all(pd.api.types.is_bool_dtype(tipo) for tipo in x.dtypes) or x.isna().any().any():
        raise ValueError("A matriz deve conter apenas verdadeiro ou falso, sem ausências.")
    if isinstance(minimo, (bool, np.bool_)) or not isinstance(minimo, Integral) or not 1 <= minimo <= len(x):
        raise ValueError("O suporte mínimo deve ser uma contagem inteira entre 1 e o número de transações.")
    nomes = tuple(sorted(x.columns))
    return x.loc[:, list(nomes)].to_numpy(dtype=bool), nomes


def _isolados(matriz, minimo):
    totais = matriz.sum(axis=0)
    frequentes = np.flatnonzero(totais >= minimo).tolist()
    return totais, frequentes


def _resultado(nomes, totais, frequentes, pares, minimo):
    encontrados = {(nomes[i],): int(totais[i]) for i in frequentes}
    encontrados.update({
        (nomes[i], nomes[j]): int(n)
        for (i, j), n in pares.items() if n >= minimo
    })
    return encontrados


def _apriori(matriz, nomes, minimo):
    totais, frequentes = _isolados(matriz, minimo)
    # O princípio Apriori descarta toda dupla que contém um tipo não frequente.
    candidatos = Counter()
    for linha in matriz[:, frequentes]:
        presentes = [frequentes[i] for i in np.flatnonzero(linha)]
        candidatos.update(combinations(presentes, 2))
    return _resultado(nomes, totais, frequentes, candidatos, minimo)


class _NoFP:
    def __init__(self, item=None, pai=None):
        self.item = item
        self.pai = pai
        self.contagem = 0
        self.filhos = {}


def _fp_growth(matriz, nomes, minimo):
    totais, frequentes = _isolados(matriz, minimo)
    ordem = sorted(frequentes, key=lambda i: (-totais[i], i))
    raiz = _NoFP()
    cabecalhos = defaultdict(list)
    for linha in matriz[:, ordem]:
        no = raiz
        for posicao in np.flatnonzero(linha):
            item = ordem[posicao]
            filho = no.filhos.get(item)
            if filho is None:
                filho = _NoFP(item, no)
                no.filhos[item] = filho
                cabecalhos[item].append(filho)
            filho.contagem += 1
            no = filho

    # Para cada sufixo, a base condicional é formada pelos caminhos até os
    # seus nós. Para duplas, basta contar cada item prefixo desses caminhos.
    pares = Counter()
    for sufixo, nos in cabecalhos.items():
        for no in nos:
            prefixo = no.pai
            while prefixo.item is not None:
                dupla = tuple(sorted((prefixo.item, sufixo)))
                pares[dupla] += no.contagem
                prefixo = prefixo.pai
    return _resultado(nomes, totais, frequentes, pares, minimo)


def _eclat(matriz, nomes, minimo):
    totais, frequentes = _isolados(matriz, minimo)
    # O formato vertical guarda os identificadores das transações de cada tipo.
    transacoes = {i: set(np.flatnonzero(matriz[:, i])) for i in frequentes}
    pares = {
        (i, j): len(transacoes[i] & transacoes[j])
        for i, j in combinations(frequentes, 2)
    }
    return _resultado(nomes, totais, frequentes, pares, minimo)


def apriori(x, minimo):
    """Conta conjuntos frequentes usando Apriori."""
    matriz, nomes = _validar(x, minimo)
    return _apriori(matriz, nomes, minimo)


def fp_growth(x, minimo):
    """Conta conjuntos frequentes usando uma árvore FP."""
    matriz, nomes = _validar(x, minimo)
    return _fp_growth(matriz, nomes, minimo)


def eclat(x, minimo):
    """Conta conjuntos frequentes usando interseções de transações."""
    matriz, nomes = _validar(x, minimo)
    return _eclat(matriz, nomes, minimo)


def _conferencia_direta(matriz, nomes, minimo):
    # O produto escalar entre duas colunas 0/1 conta a presença conjunta.
    binaria = matriz.astype(np.int64)
    cruzamentos = binaria.T @ binaria
    totais = cruzamentos.diagonal()
    frequentes = np.flatnonzero(totais >= minimo)
    pares = {(i, j): cruzamentos[i, j] for i, j in combinations(frequentes, 2)}
    return _resultado(nomes, totais, frequentes, pares, minimo)


def comparar_mineradores(x, minimo, repeticoes=5):
    """Confere contagens e regras e devolve contagens e tempos em milissegundos."""
    matriz, nomes = _validar(x, minimo)
    if isinstance(repeticoes, (bool, np.bool_)) or not isinstance(repeticoes, Integral) or repeticoes < 3:
        raise ValueError("Use pelo menos três repetições para resumir os tempos.")

    metodos = {"Apriori": _apriori, "FP-Growth": _fp_growth, "Eclat": _eclat}
    referencia = _conferencia_direta(matriz, nomes, minimo)
    regras_referencia = tabela_regras(referencia, len(x))
    tempos = {nome: [] for nome in metodos}
    for nome, metodo in metodos.items():
        obtido = metodo(matriz, nomes, minimo)
        if obtido != referencia or not tabela_regras(obtido, len(x)).equals(regras_referencia):
            raise RuntimeError(f"{nome} divergiu da contagem direta ou das regras de referência.")

    # O aquecimento acima fica fora dos tempos. A ordem gira a cada rodada.
    nomes_metodos = tuple(metodos)
    for rodada in range(repeticoes):
        deslocamento = rodada % len(metodos)
        ordem = nomes_metodos[deslocamento:] + nomes_metodos[:deslocamento]
        for nome in ordem:
            inicio = perf_counter()
            obtido = metodos[nome](matriz, nomes, minimo)
            tempos[nome].append((perf_counter() - inicio) * 1000)
            if obtido != referencia:
                raise RuntimeError(f"{nome} divergiu na rodada {rodada + 1}.")

    medidas = []
    for nome, amostras in tempos.items():
        q1, mediana, q3 = np.percentile(amostras, [25, 50, 75])
        medidas.append({
            "Algoritmo": nome, "Mediana (ms)": mediana, "Q1 (ms)": q1, "Q3 (ms)": q3,
            "Repetições": repeticoes, "Pares": int(sum(len(itens) == 2 for itens in referencia)),
        })
    return referencia, pd.DataFrame(medidas)


def tabela_pares(contagens, n):
    """Exibe métricas das duplas sem confundir a dupla com uma regra direcional."""
    colunas = ["A", "B", "n_A", "n_B", "n_AB", "suporte", "esperado", "lift", "confianca_A_B", "confianca_B_A"]
    if not isinstance(n, Integral) or isinstance(n, (bool, np.bool_)) or n <= 0:
        raise ValueError("O número de transações deve ser um inteiro positivo.")
    linhas = []
    for itens, n_ab in sorted(contagens.items()):
        if len(itens) != 2:
            continue
        a, b = itens
        n_a, n_b = contagens[(a,)], contagens[(b,)]
        if not 0 < n_ab <= min(n_a, n_b) <= max(n_a, n_b) <= n:
            raise ValueError("Contagens de ocorrência e coocorrência inconsistentes.")
        esperado = n_a * n_b / n
        linhas.append((a, b, n_a, n_b, n_ab, n_ab / n, esperado, n_ab / esperado, n_ab / n_a, n_ab / n_b))
    return pd.DataFrame(linhas, columns=colunas)


def tabela_regras(contagens, n):
    """Traduz cada dupla frequente em duas regras, uma para cada direção."""
    colunas = ["antecedente", "consequente", "n_AB", "suporte", "confianca", "lift"]
    linhas = []
    for par in tabela_pares(contagens, n).itertuples(index=False):
        linhas.append((par.A, par.B, par.n_AB, par.suporte, par.confianca_A_B, par.lift))
        linhas.append((par.B, par.A, par.n_AB, par.suporte, par.confianca_B_A, par.lift))
    return pd.DataFrame(linhas, columns=colunas)

