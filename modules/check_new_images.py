import os  # Importa a biblioteca os para operações de sistema.
import re  # Importa a biblioteca re para expressões regulares.
import json  # Importa a biblioteca json para manipulação de arquivos JSON.
import logging  # Importa a biblioteca logging para registrar informações.
import shutil

# Função para remover todos os arquivos de uma pasta, exceto um específico.
def removerTodosExceto(nome_arquivo, pasta):
    for arquivo in os.listdir(pasta):
        caminho_arquivo = os.path.join(pasta, arquivo)
        # Verifica se o arquivo é um arquivo e se não é o arquivo especificado.
        if os.path.isfile(caminho_arquivo) and arquivo != nome_arquivo and len(arquivo) > 1:
            os.remove(caminho_arquivo)

# Função para abrir o arquivo "oldBands.json" e retornar a lista de "oldImagesName".
def openOld():
    with open('oldBands.json', 'r') as jsonOld:
        oldImages = json.load(jsonOld)['oldImagesName']
        return oldImages

# Função para modificar um valor em um arquivo JSON.
def modificarKeyOldBands(caminho_arquivo, chave, novo_valor):
    with open(caminho_arquivo, 'r') as arquivo_json:
        dados = json.load(arquivo_json)
    dados['oldImagesName'][chave] = novo_valor
    with open(caminho_arquivo, 'w') as arquivo_json:
        json.dump(dados, arquivo_json, indent=4)

# Função para verificar a existência de novas imagens.
def checarImagens(bands, dir_in):
    logging.info("VERIFICANDO NOVAS IMAGENS")
    # Chegagem imagens ABI 1-16
    for x in range(1, 17): 
        b = str(x).zfill(2) # Formata o número para ter dois dígitos (01, 02, ..., 16).
        # Obtém uma lista de imagens que correspondem a um padrão específico na pasta.
        imagens = [f for f in os.listdir(f'{dir_in}band{b}') if os.path.isfile(os.path.join(f'{dir_in}band{b}', f)) and re.match('^CG_ABI-L2-CMIPF-M[0-9]C[0-1][0-9]_G16_s.+_e.+_c.+.nc$', f)]
        if imagens: # Se houver imagens na lista:
            # Encontra a imagem mais recente na lista.
            latestBand = max(imagens)
            old_bands = openOld() # Obtém as imagens antigas.
            # Se houver uma imagem mais recente e ela for diferente das antigas:
            if latestBand and latestBand != old_bands[b]: 
                logging.info(f'Novas imagens para o dia band{b}')  # Registra informações sobre as novas imagens.
                if len(imagens) > 1:  # Se houver mais de uma imagem na pasta:
                    removerTodosExceto(latestBand, f'{dir_in}band{b}/')  # Remove todas as imagens, exceto a mais recente.                
                modificarKeyOldBands('oldBands.json', b, latestBand)  # Modifica o arquivo JSON com a imagem mais recente.
                bands[b] = True  # Atualiza o dicionário "bands" com a imagem mais recente.
            else:
                logging.info(f'Sem imagens para o dia band{b}')  # Registra se não houver novas imagens.
                bands[b] = False  # Define a banda como False.
        else:
            logging.info(f'Sem imagens para o dia band{b}')  # Registra se não houver imagens na pasta.
            bands[b] = False  # Define a banda como False.
    
    
    # Checagem de novas imagens truecolor (Band 17) if bands 1,2,3
    if all(bands[str(x).zfill(2)] for x in range(1, 4)):
        # Se Todas as três bandas são True
        bands['17'] = True
        logging.info(f'Novas imagens TRUECOLOR')
    else:
        bands["17"] = False
        logging.info(f'Sem novas imagens TRUECOLOR')
            
    return bands  # Retorna o dicionário "bands".