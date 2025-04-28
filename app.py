import streamlit as st
from lxml import etree
import unidecode
from fuzzywuzzy import fuzz
import requests
import io

# Função auxiliar para remover acentos de uma string
def remove_accents(string):
    return unidecode.unidecode(string)

# Função auxiliar para gerar possíveis abreviações e variações de um nome
def generate_abbreviations(name):
    name_parts = name.split()
    abbreviations = {'completo': name}
    
    # Adicionando diferentes variações de nome
    if len(name_parts) > 1:
        abbreviations['sobrenome_nome_completo'] = "{}, {}".format(name_parts[-1], ' '.join(name_parts[:-1]))
        abbreviations['sobrenome_inicial_nome'] = "{}, {}.".format(name_parts[-1], name_parts[0][0])
        if len(name_parts) > 2:
            initials = '. '.join([p[0] for p in name_parts[:-1]]) + '.'
            abbreviations['sobrenome_iniciais'] = "{}, {}".format(name_parts[-1], initials)
            abbreviations['invertido'] = ' '.join(reversed(name_parts))
            abbreviated_name = [name_parts[0]] + ["{}.".format(p[0]) for p in name_parts[1:-1]] + [name_parts[-1]]
            abbreviations['abreviado'] = ' '.join(abbreviated_name)
    
    return abbreviations

# Função para realizar a correspondência fuzzy de nomes
def fuzzy_name_match(input_names, author_names, threshold):
    matched_results = []
    
    for input_name in input_names:
        matches_for_this_name = []
        input_name_no_accents = remove_accents(input_name)
        input_name_variations = generate_abbreviations(input_name_no_accents)
        
        for author_name in author_names:
            author_name_no_accents = remove_accents(author_name)
            
            for variation_type, variation in input_name_variations.items():
                ratio = fuzz.token_sort_ratio(variation, author_name_no_accents)
                
                if ratio >= threshold:
                    matches_for_this_name.append({
                        "nome_inserido": input_name,
                        "nome_encontrado": author_name,
                        "similaridade": ratio,
                        "variacao_usada": variation_type
                    })
                    break
        
        if matches_for_this_name:
            # Ordenar por similaridade, do maior para o menor
            matches_for_this_name.sort(key=lambda x: x["similaridade"], reverse=True)
            matched_results.extend(matches_for_this_name)
    
    return matched_results

# Função para extrair nomes do XML do CV Lattes
def extract_names_from_lattes_xml(xml_file):
    try:
        tree = etree.parse(xml_file)
        integrantes = tree.xpath(".//INTEGRANTES-DO-PROJETO/@NOME-COMPLETO")
        autores = tree.xpath(".//AUTORES/@NOME-COMPLETO-DO-AUTOR")
        orientados = tree.xpath(".//NOME-DO-ORIENTADO/text()")
        combined_names = list(set(integrantes + autores + orientados))
        return combined_names
    except Exception as e:
        st.error(f"Erro ao analisar o XML: {e}")
        return []

# Função para obter autores de um DOI
def get_authors_from_doi(doi):
    url = f"https://api.crossref.org/works/{doi}"
    response = requests.get(url)
    if response.ok:
        data = response.json()
        author_data = data['message'].get('author', [])
        article_title = data['message'].get('title', [''])[0]
        author_names = ["{} {}".format(author.get('given', ''), author.get('family', '')).strip() for author in author_data]
        return author_names, article_title
    else:
        return None, None

# Interface principal do aplicativo
def main():
    st.title("Buscador de Conflitos")
    st.write("Versão 2.0 - 28/04/2025")
    st.write("Autor: Rodrigo A. S. Pereira (Faculdade de Filosofia, Ciências e Letras de Ribeirão Preto, USP), e-mail: raspereira@usp.br")
    st.write("Este programa realiza a comparação entre uma lista de nomes (por exemplo, candidatos a um concurso) e os nomes extraídos de colaborações acadêmicas.")
    
    # Entrada de nomes separados por vírgula
    input_names_str = st.text_area("Digite os nomes (separados por vírgula):")
    
    # Seleção do método de comparação
    metodo = st.radio(
        "Escolha o método de comparação:",
        ["Comparar a um currículo Lattes", "Comparar a uma publicação"]
    )
    
    # Limiar comum a ambos os métodos
    threshold = st.slider("Limite de similaridade (%)", min_value=50, max_value=100, value=90, step=1)
    st.write("Limiares mais elevados tornam a busca mais precisa. Similaridades abaixo de 80% aumentam o risco de falsos positivos.")
    
    # Expander para o método do Lattes
    if metodo == "Comparar a um currículo Lattes":
        with st.expander("Como baixar o arquivo XML do Lattes"):
            st.markdown("""
            1. Acesse o currículo Lattes da pessoa no site do CNPq
            2. No canto superior direito da página, procure o ícone XML (destacado em amarelo na imagem)
            3. Clique no ícone para baixar o arquivo XML
            4. Salve o arquivo em seu computador
            5. Faça upload deste arquivo nesta aplicação
            """)
            
            # URL da imagem no GitHub - corrigido
            imagem_url = "https://raw.githubusercontent.com/PhytoIn/buscador_conflitos/refs/heads/main/xml_lattes.png"
            st.image(imagem_url, caption="Como baixar o XML do Lattes")
        
        # Upload do arquivo XML
        uploaded_file = st.file_uploader("Faça upload do arquivo XML do Lattes", type=["xml"])
        
        if st.button("Comparar Nomes"):
            if not input_names_str:
                st.warning("Por favor, digite os nomes para comparação.")
                return
                
            if not uploaded_file:
                st.warning("Por favor, faça upload de um arquivo XML do Lattes.")
                return
                
            try:
                input_names = [name.strip() for name in input_names_str.split(',')]
                
                # Processando o arquivo carregado
                xml_bytes = io.BytesIO(uploaded_file.getvalue())
                
                # Extração de nomes do XML
                lattes_names = extract_names_from_lattes_xml(xml_file=xml_bytes)
                if not lattes_names:
                    st.warning("Nenhum nome encontrado no arquivo XML.")
                    return
                    
                # Apenas indicar o número de nomes encontrados, sem listá-los
                st.info(f"Foram encontrados {len(lattes_names)} nomes no currículo Lattes.")
                
                # Busca de correspondências
                matched_results = fuzzy_name_match(input_names, lattes_names, threshold)
                
                mostrar_resultados(matched_results, input_names)
                
            except Exception as e:
                st.error(f"Ocorreu um erro: {e}")
    
    # Expander para o método do DOI
    else:  # "Comparar a uma publicação"
        # Entrada do DOI
        doi = st.text_input("Digite o DOI da publicação:")
        
        if st.button("Comparar Nomes"):
            if not input_names_str:
                st.warning("Por favor, digite os nomes para comparação.")
                return
                
            if not doi:
                st.warning("Por favor, digite o DOI da publicação.")
                return
                
            try:
                input_names = [name.strip() for name in input_names_str.split(',')]
                
                # Busca de autores através do DOI
                author_names, article_title = get_authors_from_doi(doi)
                
                if author_names is None:
                    st.error("Não foi possível recuperar os nomes dos autores a partir do DOI.")
                    return
                    
                st.success(f"Artigo encontrado: {article_title}")
                # Apenas indicar o número de autores, sem listá-los
                st.info(f"Foram encontrados {len(author_names)} autores na publicação.")
                
                # Busca de correspondências
                matched_results = fuzzy_name_match(input_names, author_names, threshold)
                
                mostrar_resultados(matched_results, input_names)
                
            except Exception as e:
                st.error(f"Ocorreu um erro: {e}")

# Função para mostrar os resultados de forma padronizada
def mostrar_resultados(matched_results, input_names):
    if matched_results:
        st.success(f"Encontrados {len(matched_results)} correspondências:")
        
        # Criar tabela com os resultados
        results_data = []
        for match in matched_results:
            results_data.append({
                "Nome inserido": match["nome_inserido"],
                "Nome encontrado": match["nome_encontrado"],
                "Similaridade (%)": round(match["similaridade"], 1),
                "Variação utilizada": match["variacao_usada"]
            })
        
        # Ordenar os resultados por similaridade (do maior para o menor)
        results_data.sort(key=lambda x: x["Similaridade (%)"], reverse=True)
        
        st.table(results_data)
        
        # Mostrar quais nomes não tiveram correspondência
        matched_input_names = set(match["nome_inserido"] for match in matched_results)
        unmatched_names = set(input_names) - matched_input_names
        
        if unmatched_names:
            st.warning("Nomes sem correspondência:")
            for name in unmatched_names:
                st.write(f"- {name}")
    else:
        st.warning("Nenhuma correspondência encontrada.")

if __name__ == "__main__":
    main()
