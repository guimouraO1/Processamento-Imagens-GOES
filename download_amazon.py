#!/opt/miniconda3/envs/goes/bin/python3
# -*- coding: utf-8 -*-

from osgeo import gdal  # Utilitario para a biblioteca GDAL
from modules.utilities import download_prod  # Funcao para download dos produtos do goes disponiveis na amazon
from modules.utilities import download_cmi_joao
import datetime
from datetime import timedelta
import logging
import os
import time
from modules.dirs import get_dirs

dirs = get_dirs()

# Acessando os diretórios usando as chaves do dicionário
dir_in = dirs['dir_in']
dir_log = dirs['arq_log']

gdal.PushErrorHandler('CPLQuietErrorHandler')   # Ignore GDAL warnings 


#Inicia contador para o tempo gasto de processamento
start = time.time()

#Diretórios
arq_log = '/home/guimoura/download_amazon/logs/' + str(datetime.date.today()) + ".log"

# Configurando log
logging.basicConfig(filename=arq_log, level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s", datefmt="%d/%m/%Y %H:%M:%S")
# Capturando data/hora inicio
inicio = datetime.datetime.now().strftime("%d/%m/%Y-%H:%M:%S")
logging.info("")
logging.info("")
logging.info("==================================================================================================================")
logging.info("=                                  DOWNLOAD IMAGENS GOES AS " + inicio + "                                  =")
logging.info("==================================================================================================================")
logging.info("")


#Captura hora atual em UTC para download no site da Amazon
data_hora_atual = datetime.datetime.utcnow()

#Atrasa 10 min para entrar em conformidade com Amazon
data_10_min = datetime.datetime.strftime(data_hora_atual-timedelta(minutes=10),'%Y%m%d%H%M')

#Correção para poder fazer download em qualquer horário
data_hora_download_file = data_10_min[0:11]+ '0'

# Contador para download das 16 bandas
for x in range(1,17):
    # Transforma o inteiro contador em string e com 2 digitos
    b = str(x).zfill(2)
    # Download band
    logging.info("")
    logging.info(f'Tentando download Band{b}...')
    try:
        download_cmi_joao(data_hora_download_file, x, dir_in + f'band{b}', logging)
    except Exception as e:
        print(f'{e}')
        continue


# Função para renomear arquivos
def renomear_arquivos(diretorio):
    for nome_arquivo in os.listdir(diretorio):
        caminho_arquivo = os.path.join(diretorio, nome_arquivo)
        
        # Verifique se é um diretório
        if os.path.isdir(caminho_arquivo):
            # Se for um diretório, chame recursivamente a função
            renomear_arquivos(caminho_arquivo)
        else:
            # Verifique se o nome do arquivo contém "OR_"
            if "OR_" in nome_arquivo:
                # Construa o novo nome de arquivo substituindo "OR_" por "CG_"
                novo_nome = nome_arquivo.replace("OR_", "CG_")
                
                # Renomeie o arquivo
                os.rename(caminho_arquivo, os.path.join(diretorio, novo_nome))


# Percorra as subpastas "band01" até "band16"
for band_folder in range(1, 17):
    subdiretorio = os.path.join(dir_in, f"band{band_folder:02d}")
    
    if os.path.exists(subdiretorio):
        # Chame a função para renomear os arquivos na subpasta
        renomear_arquivos(subdiretorio)

print("Arquivos renomeados com sucesso!")

        
        
def finalize(s):
    # Capturando data/hora final
    fim = datetime.datetime.now().strftime("%d/%m/%Y-%H:%M:%S")
    # Realiza o log do calculo do tempo de execucao
    logging.info("")
    logging.info("Tempo gasto " + str(round(time.time() - s, 4)) + ' segundos')
    logging.info("")
    logging.info("==================================================================================================================")
    logging.info("=                             PROCESSAMENTO ENCERRADO GOES AS " + fim + "                                =")
    logging.info("==================================================================================================================")
    logging.info("")
    logging.info("")

finalize(start)