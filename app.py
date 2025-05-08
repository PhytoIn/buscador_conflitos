import streamlit as st
import fitz  # PyMuPDF
import re
import unicodedata
import itertools
from difflib import SequenceMatcher
import requests

def marcar_inicio_nome(text):
    """Marca o início dos nomes com '@nome' após numeração (ex: '1. ')"""
    return re.sub(r'\b\d+\.\s*', '@nome', text)

def marcar_fim_nome_apos_inicio(text):
    """Marca o fim dos nomes após padrões como '. Palavra' ou '. 2020'"""
    end_pattern = re.compile(r'\.\s([A-ZÀ-Ú][a-zA-ZÀ-ú]{2,}|\d{4})')
    start_idx = 0
    result = []

    while True:
        start_match = re.search(r'@nome', text[start_idx:])
        if not start_match:
            break

        start_pos = start_idx + start_match.start()
        match = end_pattern.search(text[start_pos:])
        if not match:
            break

        pattern_start_global = start_pos + match.start()
        pattern_end_global = start_pos + match.end()

        result.append(text[start_idx:start_pos])
        result.append(text[start_pos:pattern_start_global])
        result.append('@fim_nome')
        result.append(text[pattern_start_global:pattern_end_global])
        start_idx = pattern_end_global

    result.append(text[start_idx:])
    return ''.join(result)

def formatar_quebras_paragrafo(text):
    """Substitui marcadores por quebras de parágrafo"""
    substituicoes = [
        (r'@nome', '\n'),                   
        (r'@fim_nome', '\n'),              
        (r'Integrantes:', '\nIntegrantes:\n'),
        (r'\bIntegrante\b', '\n• '),       
        (r'\bCoordenador\b', '\nCoordenador:\n'),
        (r'\s/\s', '\n'),                  
        (r';', '\n'),                      
        (r'In:', '\nPublicado em:\n'),     
        (r'\.\s*\(Org\.\)', '\n(Organizador)\n'),
        (r'\(Org\.\)', '\n(Organizador)\n')
    ]
    
    for padrao, substituicao in substituicoes:
        text = re.sub(padrao, substituicao, text)
    
    text = re.sub(r' +', ' ', text)         
    text = re.sub(r'\n ', '\n', text)       
    text = re.sub(r'\n{3,}', '\n\n', text)  
    
    return text.strip()

def limpar_texto(text):
    """Aplica todas as regras de limpeza especificadas"""
    linhas_limpas = []
    
    for linha in text.split('\n'):
        original = linha
        linha = linha.strip()
        
        if len(original) >= 60:
            continue
            
        if re.search(r'\d', linha):
            continue
            
        if re.search(r'[:?!]', linha):
            continue
            
        if re.search(r'[\(\)\{\}\[\]]', linha):
            continue
            
        if len(linha.split()) == 1:
            continue
            
        linha = re.sub(r'[-\s]+$', '', linha)
            
        linhas_limpas.append(linha)
    
    return '\n'.join(linhas_limpas)

def normalizar_nomes(text):
    """Padroniza nomes removendo acentos e caracteres especiais"""
    linhas_normalizadas = []
    
    for linha in text.split('\n'):
        linha = unicodedata.normalize('NFKD', linha)
        linha = linha.encode('ASCII', 'ignore').decode('ASCII')
        linha = re.sub(r"[,.'\-]", ' ', linha)
        linha = re.sub(r'\s+', ' ', linha).strip().upper()
        linhas_normalizadas.append(linha)
    
    return '\n'.join(linhas_normalizadas)

def remover_particulas(text):
    """Remove partículas de ligação de nomes com mais de 2 palavras"""
    particulas = {"DA", "DE", "DO", "DAS", "DOS", "VAN", "JR", "JUNIOR"}
    linhas_limpas = []
    
    for linha in text.split('\n'):
        palavras = linha.split()
        if len(palavras) > 2:
            palavras = [p for p in palavras if p not in particulas]
        linhas_limpas.append(' '.join(palavras))
    
    return '\n'.join(linhas_limpas)

def processar_nome(nome):
    """Processa um nome para comparação"""
    nome = unicodedata.normalize('NFKD', nome)
    nome = nome.encode('ASCII', 'ignore').decode('ASCII').upper()
    nome = re.sub(r"[,.'\-]", ' ', nome)
    nome = re.sub(r'\s+', ' ', nome).strip()
    
    partes = nome.split()
    particulas = {"DA", "DE", "DO", "DAS", "DOS", "VAN", "JR", "JUNIOR"}
    if len(partes) > 2:
        partes = [p for p in partes if p not in particulas]
    return ' '.join(partes)

def gerar_combinacoes_nomes(partes):
    """Gera variações possíveis para os nomes"""
    combinacoes = []
    n = len(partes)
    
    # Combinações não abreviadas
    if n >= 2:
        combinacoes.append(' '.join(partes))
        combinacoes.append(f"{partes[-1]} {' '.join(partes[:-1])}")
        
        if n >= 3:
            combinacoes.append(f"{' '.join(partes[-2:])} {' '.join(partes[:-2])}")

    # Abreviações progressivas
    if n >= 3:
        if n == 3:
            combinacoes.append(f"{partes[0]} {partes[1][0]} {partes[2]}")
        else:
            for qtd in range(1, n-1):
                for inicio in range(1, (n-1) - qtd + 1):
                    temp = partes.copy()
                    for i in range(inicio, inicio + qtd):
                        temp[i] = temp[i][0]
                    combinacoes.append(' '.join(temp))

    # Último nome primeiro com abreviações
    if n >= 2:
        ultimo = [partes[-1]]
        demais = partes[:-1]
        
        for qtd in range(1, len(demais)+1):
            for inicio in range(len(demais) - qtd + 1):
                temp = []
                for i, p in enumerate(demais):
                    if inicio <= i < inicio + qtd:
                        temp.append(p[0])
                    else:
                        temp.append(p)
                combinacoes.append(f"{' '.join(ultimo)} {' '.join(temp)}")

    # Dois últimos primeiro com abreviações
    if n >= 3:
        dois_ultimos = partes[-2:]
        demais = partes[:-2]
        
        if demais:
            if n == 3:
                combinacoes.append(f"{' '.join(dois_ultimos)} {demais[0][0]}")
                combinacoes.append(f"{' '.join(dois_ultimos)} {demais[0]}")
            else:
                for qtd in range(1, len(demais)+1):
                    for inicio in range(len(demais) - qtd + 1):
                        temp = []
                        for i, p in enumerate(demais):
                            if inicio <= i < inicio + qtd:
                                temp.append(p[0])
                            else:
                                temp.append(p)
                        combinacoes.append(f"{' '.join(dois_ultimos)} {' '.join(temp)}")

    return list(set(combinacoes))

# Função modificada para compatibilidade
def get_authors_from_doi(doi):
    url = f"https://api.crossref.org/works/{doi}"
    try:
        response = requests.get(url, timeout=10)
        if response.ok:
            data = response.json()
            author_data = data['message'].get('author', [])
            author_names = ["{} {}".format(author.get('given', ''), author.get('family', '')).strip() 
                          for author in author_data]
            return author_names, None
        return None, None
    except Exception as e:
        return None, None

# Interface Streamlit
st.set_page_config(page_title="Buscador de Conflitos de Interesse", layout="centered")
st.title("Buscador de Conflitos de Interesse")
st.write("Versão 2.0 - 08/05/2025")
st.write("Autor: Rodrigo A. S. Pereira (Faculdade de Filosofia, Ciências e Letras de Ribeirão Preto, USP) <br>e-mail: raspereira@usp.br",
         unsafe_allow_html=True)
st.write("Este programa realiza a comparação entre uma lista de nomes (por exemplo, candidatos a um concurso) e nomes extraídos de colaborações acadêmicas. <br>Confira sempre o resultado. Este aplicativo pode cometer erros ou detectar homônimos.",
         unsafe_allow_html=True)

# Seção de entrada de dados
st.subheader("Nomes para Comparação")
candidates_input = st.text_area(
    "Insira os nomes completos dos candidatos (separados por vírgula):",
    placeholder="Ex: Maria Silva Oliveira, José Carlos Pereira",
    height=100,
    key="candidates_input"
)

precision = st.slider(
    "Nível de precisão na comparação:",
    min_value=50,
    max_value=100,
    value=90,
    help="100% exige correspondência exata entre os nomes",
    key="precision_slider"
)
st.write("Limiares mais elevados tornam a busca mais precisa. Limiares abaixo de 85% aumentam o risco de falsos positivos.")

# Seleção de método de comparação
metodo_comparacao = st.radio(
    "Método de comparação:",
    options=['Comparar ao PDF de um currículo Lattes', 'Comparar à lista de autores de uma publicação'],
    index=0
)

uploaded_file = None
doi_input = None

if metodo_comparacao == 'Comparar ao PDF de um currículo Lattes':
    with st.expander("Como baixar o arquivo PDF do Lattes"):
        st.markdown("""
        1. Acesse o currículo Lattes da pessoa no site do CNPq
        2. Role a tela até o final do currículo
        3. Clique no botão azul 'Imprimir Currículo'
        4. Na tela de impressão, escolha 'Salvar como PDF'
        5. Faça upload do PDF neste aplicativo
        """)
        
    uploaded_file = st.file_uploader("Carregue o PDF para análise:", type="pdf", key="pdf_uploader")
else:
    doi_input = st.text_input("Insira o DOI da publicação (ex: 10.1234/abc.2021.11.002):", key="doi_input")

# Controle do botão de busca
buscar_nomes = False
if ((metodo_comparacao == 'Comparar ao PDF de um currículo Lattes' and uploaded_file is not None) or
    (metodo_comparacao == 'Comparar à lista de autores de uma publicação' and doi_input)):
    
    if candidates_input.strip():
        buscar_nomes = st.button("Comparar Nomes", key="buscar_button")

# Processamento principal
if buscar_nomes:
    try:
        # Processar nomes dos candidatos
        nomes_candidatos = [nome.strip() for nome in candidates_input.split(',') if nome.strip()]
        candidatos = []
        
        for nome in nomes_candidatos:
            processado = processar_nome(nome)
            partes = processado.split()
            combinacoes = gerar_combinacoes_nomes(partes)
            candidatos.append({
                'original': nome,
                'combinations': combinacoes
            })

        # Obter nomes para comparação
        nomes_comparacao = []
        
        if metodo_comparacao == 'Comparar ao PDF de um currículo Lattes':
            # Processar PDF
            doc = fitz.open(stream=uploaded_file.getvalue(), filetype="pdf")
            raw_text = "".join(page.get_text() + "\n" for page in doc)
            cleaned_text = re.sub(r'\s+', ' ', raw_text)

            texto_marcado = marcar_inicio_nome(cleaned_text)
            texto_marcado = marcar_fim_nome_apos_inicio(texto_marcado)
            texto_formatado = formatar_quebras_paragrafo(texto_marcado)
            texto_limpo = limpar_texto(texto_formatado)
            texto_normalizado = normalizar_nomes(texto_limpo)
            texto_sem_particulas = remover_particulas(texto_normalizado)
            texto_final = texto_sem_particulas

            nomes_comparacao = [linha.strip() for linha in texto_final.split('\n') if linha.strip()]
            
        else:
            # Processar DOI
            autores, _ = get_authors_from_doi(doi_input.strip())
            if not autores:
                st.error("DOI inválido ou não encontrado. Verifique o número e tente novamente.")
                st.stop()  # Corrigido
                
            texto_autores = '\n'.join(autores)
            texto_normalizado = normalizar_nomes(texto_autores)
            texto_sem_particulas = remover_particulas(texto_normalizado)
            nomes_comparacao = [linha.strip() for linha in texto_sem_particulas.split('\n') if linha.strip()]

        # Realizar comparações
        threshold = precision / 100.0
        resultados = []
        
        for candidato in candidatos:
            encontrados = []
            
            for combinacao in candidato['combinations']:
                for nome in nomes_comparacao:
                    similaridade = SequenceMatcher(None, combinacao, nome).ratio()
                    if similaridade >= threshold:
                        encontrados.append(nome)
            
            # Remover duplicatas mantendo a ordem
            vistos = set()
            unicos = []
            for nome in encontrados:
                if nome not in vistos:
                    vistos.add(nome)
                    unicos.append(nome)
            
            if unicos:
                resultados.append({
                    'buscado': candidato['original'],
                    'encontrados': unicos
                })

        # Exibir resultados
        st.subheader("Resultados da Busca")
        
        if resultados:
            for resultado in resultados:
                st.write(f"**Nome buscado:** {resultado['buscado']}")
                st.write("**Nome(s) encontrado(s):**")
                for encontrado in resultado['encontrados']:
                    st.write(encontrado)
                st.write("---")
        else:
            st.write("**Nenhuma correspondência encontrada**")

    except Exception as e:
        st.error(f"Erro durante o processamento: {str(e)}")
elif uploaded_file is not None and not candidates_input:
    st.warning("Por favor, insira os nomes dos candidatos para comparação.")
