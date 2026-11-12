# Brasil sobre Impacto 2 | Guia da análise

**Mineração de Dados · Atividade 2**

Felipe Cintra Silva, Ítalo Dias Moreira Campos e Rakel Garcia da Silva.

## Pergunta e resposta

**Quais tipos de desastre são registrados juntos no mesmo município e ano, e quais dessas combinações se repetem nos dois períodos do Atlas, de 1991–2012 e de 2013–2025?**

Das 66 duplas possíveis, 33 apareceram nos dois períodos e oito apareceram em pelo menos 30 casos em cada um. Entre elas, granizo com vendavais e ciclones foi a única dupla com frequência conjunta pelo menos 20% acima do esperado pela comparação nacional nos dois períodos. Foram 90 casos no primeiro período e 221 no segundo. Cada caso é uma cidade em um ano em que os dois tipos foram registrados. Ao calcular a expectativa separadamente por unidade da Federação (UF) e ano, o excesso desapareceu.

O [caderno principal](../cadernos/Brasil_sob_Impacto.ipynb) abre com a resposta e os gráficos. Nele, explicamos o recorte, a qualidade da base, os critérios de comparação e os limites dos resultados.

## Como fizemos

Usamos os 76.190 protocolos da base tratada da Atividade 1. Em cada município e ano com registros, marcamos os tipos presentes. Repetições do mesmo tipo contam uma vez. Comparamos 1991–2012 e 2013–2025 separadamente porque a forma de coletar e classificar os registros mudou. Agrupamos quatro rótulos ligados a chuva em uma família e testamos o que acontece quando ficam separados.

Apriori, FP-Growth e Eclat produziram os mesmos pares e as mesmas contagens. Eclat teve o menor tempo mediano nas duas janelas no ambiente testado. A coocorrência é anual e administrativa. Dois tipos podem ter sido registrados no mesmo município e ano em episódios diferentes.

## Onde estão as bases

| Arquivo | Onde encontrar | Para que usamos |
| --- | --- | --- |
| CSV original do Atlas, edição v1.1 de agosto de 2026 | Na pasta da Atividade 1, em `01_Dados/Originais/BD_Atlas_1991_2025_v1.1_2026.08.06_Consolidado.csv` | Conferir a origem dos registros e da preparação. |
| CSV tratado da Atividade 1 | Na Atividade 1, em `01_Dados/Tratados/atlas_preparado_entrega.csv`. Na Atividade 2, em `dados/tratados/atlas_preparado_entrega_tratado.csv`. | Alimentar o notebook. A conferência SHA-256 confirmou que as duas cópias são idênticas. |

A passagem de uma versão para a outra preservou os 76.190 protocolos. O CSV original tinha 70 colunas, a saída do Power Query tinha 139, e a versão de entrega ficou com 134 depois de retirar cinco campos de descrição livre.

## Como apresentar

1. Abra **Resposta à pergunta** e diga quais tipos apareceram juntos com mais frequência.
2. No primeiro gráfico, compare os 221 casos observados de granizo e vendavais com os 92 esperados pela referência nacional e os 227 esperados por estado e ano.
3. Mostre os nomes das oito combinações na tabela. Termine na seção **Comparação dos algoritmos**, onde os três métodos encontraram os mesmos pares e Eclat teve o menor tempo mediano no teste.

## Como abrir e reproduzir

Para ler, abra `cadernos/Brasil_sob_Impacto.ipynb` no Jupyter. Os gráficos já estão salvos. No Jupyter do navegador, as células de código começam recolhidas e podem ser expandidas. O projeto foi verificado no Windows com Python 3.11.

Para recalcular em outro computador Windows, abra o terminal na pasta do projeto e rode:

```powershell
py -3.11 -m venv .venv
& .\.venv\Scripts\python.exe -m pip install -r requirements.txt
& .\.venv\Scripts\python.exe -m pip check
& .\.venv\Scripts\python.exe -m ipykernel install --sys-prefix --name brasil-sob-impacto-atividade-2 --display-name "Python | Brasil sobre Impacto 2"
& .\.venv\Scripts\python.exe -m notebook
```

Abra o caderno no endereço que o Jupyter mostrar. Selecione **Python | Brasil sobre Impacto 2**, reinicie o kernel e execute todas as células. A base tratada e os dois cadastros do IBGE são conferidos por uma impressão digital do arquivo (SHA-256). O caderno refaz as transações em memória e mantém os arquivos de entrada intactos.

A pasta `dados/referencias/` contém os cadastros do Instituto Brasileiro de Geografia e Estatística (IBGE) usados para validar os códigos dos municípios e suas UFs. Os resultados publicados são agregados. Os detalhes dos três algoritmos ficam em `codigo/`.
