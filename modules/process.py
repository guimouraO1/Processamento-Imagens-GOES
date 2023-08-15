import os
import logging
import datetime
from osgeo import gdal  # Utilitario para a biblioteca GDAL
from osgeo import osr  # Utilitario para a biblioteca GDAL
import time
import matplotlib # Force matplotlib to not use any Xwindows backend.
matplotlib.use('Agg')
import matplotlib.pyplot as plt  # Plotagem de resultados, textos, logos, etc.
from matplotlib import cm  # Utilitario para paletas de cores
import numpy as np  # Suporte para arrays e matrizes multidimensionais, com diversas funções matemáticas para trabalhar com estas estruturas
import cartopy  # Inserir mapas, shapefiles, paralelos, meridianos, latitudes, longitudes, etc.
import cartopy.crs as ccrs  # Utilitario para sistemas de referência e coordenadas
import cartopy.io.shapereader as shpreader  # Utilitario para leitura de shapefiles
from utilities import load_cpt  # Funcao para ler as paletas de cores de arquivos CPT
from utilities import download_prod  # Funcao para download dos produtos do goes disponiveis na amazon
from multiprocessing import Process  # Utilitario para multiprocessamento
from shutil import copyfile  # Utilitario para copia de arquivos
from shapely.geometry import Point
import cartopy.feature as cfeature # features
from multiprocessing import Process  # Utilitario para multiprocessamento
from netCDF4 import Dataset  # Utilitario para a biblioteca NetCDF4
from Processamento import get_dirs

gdal.PushErrorHandler('CPLQuietErrorHandler')   # Ignore GDAL warnings

# ============================================# Diretórios ========================================= #
dirs = get_dirs()

# Acessando os diretórios usando as chaves do dicionário
dir_in = dirs['dir_in']
dir_main = dirs['dir_main']
dir_out = dirs['dir_out']
dir_libs = dirs['dir_libs']
dir_shapefiles = dirs['dir_shapefiles']
dir_colortables = dirs['dir_colortables']
dir_logos = dirs['dir_logos']
dir_temp = dirs['dir_temp']
arq_log = dirs['arq_log']
# ============================================# Diretórios ========================================= #

def process_band_cmi(file, ch, v_extent):
    global dir_shapefiles, dir_colortables, dir_logos, dir_out
    file_var = 'CMI'
    # Captura a hora para contagem do tempo de processamento da imagem
    processing_start_time = time.time()
    # Area de interesse para recorte
    if v_extent == 'br':
        # Brasil
        extent = [-90.0, -40.0, -20.0, 10.0]  # Min lon, Min lat, Max lon, Max lat
        # Choose the image resolution (the higher the number the faster the processing is)
        resolution = 4.0
    elif v_extent == 'sp':
        # São Paulo
        extent = [-53.25, -26.0, -44.0, -19.5]  # Min lon, Min lat, Max lon, Max lat
        # Choose the image resolution (the higher the number the faster the processing is)
        resolution = 1.0
    else:
        extent = [-115.98, -55.98, -25.01, 34.98]  # Min lon, Min lat, Max lon, Max lat
        resolution = 2.0

    # Reprojetando imagem CMI e recebendo data/hora da imagem, satelite e caminho absoluto do arquivo reprojetado
    dtime, satellite, reproject_band = reproject(file, file_var, v_extent, resolution)

    if 1 <= int(ch) <= 6:
        data = reproject_band.ReadAsArray()
    else:
        data = reproject_band.ReadAsArray() - 273.15
    reproject_band = None
    del reproject_band

    # Comprimentos de ondas do canais ABI
    wavelenghts = ['[]', '[0.47 μm]', '[0.64 μm]', '[0.865 μm]', '[1.378 μm]', '[1.61 μm]', '[2.25 μm]', '[3.90 μm]', '[6.19 μm]',
                   '[6.95 μm]', '[7.34 μm]', '[8.50 μm]', '[9.61 μm]', '[10.35 μm]', '[11.20 μm]', '[12.30 μm]', '[13.30 μm]']

    # Formatando data para plotar na imagem e salvar o arquivo
    date = (datetime.datetime.strptime(dtime, '%Y-%m-%dT%H:%M:%S.%fZ'))
    date_img = date.strftime('%d-%b-%Y %H:%M UTC')
    date_file = date.strftime('%Y%m%d_%H%M%S')

    # Definindo unidade de medida da imagem de acordo com o canal
    if 1 <= int(ch) <= 6:
        unit = "Albedo (%)"
    else:
        unit = "Brightness Temperature [°C]"
    # Formatando a descricao a ser plotada na imagem
    description = f" GOES-{satellite} ABI CMI Band {ch} {wavelenghts[int(ch)]} {unit} {date_img}"
    institution = "CEPAGRI - UNICAMP"

    # Definindo tamanho da imagem de saida
    d_p_i = 150
    fig = plt.figure(figsize=(2000 / float(d_p_i), 2000 / float(d_p_i)), frameon=True, dpi=d_p_i, edgecolor='black', facecolor='black')

    # Utilizando projecao geoestacionaria no cartopy
    ax = plt.axes(projection=ccrs.PlateCarree())

    if v_extent == 'br':
        # Adicionando o shapefile dos estados brasileiros
        # https://geoftp.ibge.gov.br/organizacao_do_territorio/malhas_territoriais/malhas_municipais/municipio_2020/Brasil/BR/BR_UF_2020.zip
        shapefile = list(shpreader.Reader(dir_shapefiles + 'brasil/BR_UF_2020').geometries())
        ax.add_geometries(shapefile, ccrs.PlateCarree(), edgecolor='cyan', facecolor='none', linewidth=0.7)
    elif v_extent == 'sp':
        # Adicionando o shapefile dos estados brasileiros e cidade de campinas
        # https://geoftp.ibge.gov.br/organizacao_do_territorio/malhas_territoriais/malhas_municipais/municipio_2020/Brasil/BR/BR_UF_2020.zip
        shapefile = list(shpreader.Reader(dir_shapefiles + 'brasil/BR_UF_2020').geometries())
        ax.add_geometries(shapefile, ccrs.PlateCarree(), edgecolor='cyan', facecolor='none', linewidth=0.7)
        shapefile = list(shpreader.Reader(dir_shapefiles + 'campinas/campinas').geometries())
        ax.add_geometries(shapefile, ccrs.PlateCarree(), edgecolor='yellow', facecolor='none', linewidth=1)

    # Adicionando  linhas dos litorais
    ax.coastlines(resolution='10m', color='cyan', linewidth=0.5)
    # Adicionando  linhas das fronteiras
    ax.add_feature(cartopy.feature.BORDERS, edgecolor='cyan', linewidth=0.5)
    # Adicionando  paralelos e meridianos
    gl = ax.gridlines(crs=ccrs.PlateCarree(), color='white', alpha=0.7, linestyle='--', linewidth=0.2, xlocs=np.arange(-180, 180, 5), ylocs=np.arange(-90, 90, 5))
    gl.top_labels = False
    gl.right_labels = False

    # Definindo a paleta de cores da imagem de acordo com o canal
    # Convertendo um arquivo CPT para ser usado em Python atraves da funcao loadCPT
    # CPT archive: http://soliton.vm.bytemark.co.uk/pub/cpt-city/
    if 1 <= int(ch) <= 6:
        cpt = load_cpt(dir_colortables + 'Square Root Visible Enhancement.cpt')
    elif int(ch) == 7:
        cpt = load_cpt(dir_colortables + 'SVGAIR2_TEMP.cpt')
    elif 8 <= int(ch) <= 10:
        cpt = load_cpt(dir_colortables + 'SVGAWVX_TEMP.cpt')
    else:
        cpt = load_cpt(dir_colortables + 'IR4AVHRR6.cpt')
    my_cmap = cm.colors.LinearSegmentedColormap('cpt', cpt)  # Criando uma paleta de cores personalizada

    # Formatando a extensao da imagem, modificando ordem de minimo e maximo longitude e latitude
    img_extent = [extent[0], extent[2], extent[1], extent[3]]  # Min lon, Max lon, Min lat, Max lat

    # Plotando a imagem
    # Definindo os valores maximos e minimos da imagem de acordo com o canal e paleta de cores utilizada
    if 1 <= int(ch) <= 6:
        img = ax.imshow(data, origin='upper', vmin=0, vmax=1, cmap=my_cmap, extent=img_extent)
    elif 7 <= int(ch) <= 10:
        img = ax.imshow(data, origin='upper', vmin=-112.15, vmax=56.85, cmap=my_cmap, extent=img_extent)
    else:
        img = ax.imshow(data, origin='upper', vmin=-103, vmax=84, cmap=my_cmap, extent=img_extent)

    # Adicionando barra da paleta de cores de acordo com o canal
    # Criando novos eixos de acordo com a posicao da imagem
    cax0 = fig.add_axes([ax.get_position().x0, ax.get_position().y0 - 0.01325, ax.get_position().width, 0.0125])
    if 1 <= int(ch) <= 6:
        cb = plt.colorbar(img, orientation="horizontal", cax=cax0, ticks=[0.2, 0.4, 0.6, 0.8])
        cb.ax.set_xticklabels(['0.2', '0.4', '0.6', '0.8'])
        cb.ax.tick_params(axis='x', colors='black', labelsize=8)  # Alterando cor e tamanho dos rotulos da barra da paleta de cores
    elif 7 <= int(ch) <= 10:
        cb = plt.colorbar(img, orientation="horizontal", cax=cax0)
        cb.ax.tick_params(axis='x', colors='black', labelsize=8)  # Alterando cor e tamanho dos rotulos da barra da paleta de cores
    else:
        cb = plt.colorbar(img, orientation="horizontal", cax=cax0)
        cb.ax.tick_params(axis='x', colors='gray', labelsize=8)  # Alterando cor e tamanho dos rotulos da barra da paleta de cores
    cb.outline.set_visible(False)  # Removendo contorno da barra da paleta de cores
    cb.ax.tick_params(width=0)  # Removendo ticks da barra da paleta de cores
    cb.ax.xaxis.set_tick_params(pad=-13)  # Colocando os rotulos dentro da barra da paleta de cores

    # Adicionando descricao da imagem
    # Criando novos eixos de acordo com a posicao da imagem
    cax1 = fig.add_axes([ax.get_position().x0 + 0.003, ax.get_position().y0 - 0.026, ax.get_position().width - 0.003, 0.0125])
    cax1.patch.set_color('black')  # Alterando a cor do novo eixo
    cax1.text(0, 0.13, description, color='white', size=10)  # Adicionando texto
    cax1.text(0.85, 0.13, institution, color='yellow', size=10)  # Adicionando texto
    cax1.xaxis.set_visible(False)  # Removendo rotulos do eixo X
    cax1.yaxis.set_visible(False)  # Removendo rotulos do eixo Y

    # Adicionando os logos
    logo_noaa = plt.imread(dir_logos + 'NOAA_Logo.png')  # Lendo o arquivo do logo
    logo_goes = plt.imread(dir_logos + 'GOES_Logo.png')  # Lendo o arquivo do logo
    logo_cepagri = plt.imread(dir_logos + 'CEPAGRI-Logo.png')  # Lendo o arquivo do logo
    fig.figimage(logo_noaa, 32, 233, zorder=3, alpha=0.6, origin='upper')  # Plotando logo
    fig.figimage(logo_goes, 10, 150, zorder=3, alpha=0.6, origin='upper')  # Plotando logo
    fig.figimage(logo_cepagri, 10, 70, zorder=3, alpha=0.8, origin='upper')  # Plotando logo

    # Salvando a imagem de saida
    plt.savefig(f'{dir_out}band{ch}/band{ch}_{date_file}_{v_extent}.png', bbox_inches='tight', pad_inches=0, dpi=d_p_i)
    # Fecha a janela para limpar a memoria
    plt.close()
    # Realiza o log do calculo do tempo de processamento da imagem
    logging.info(f'{file} - {v_extent} - {str(round(time.time() - processing_start_time, 4))} segundos')

def process_gif(g_bands, g_br, g_sp):
    global dir_out
    # Cria lista vazia para controle do processamento paralelo
    gif_br = []
    # Cria lista vazia para controle do processamento paralelo
    gif_sp = []

    # Chamada de sistema para o software ffmpeg realizar a criacao do gif animado
    def create_gif_cmi(banda, roi):
        os.system(f'/usr/bin/ffmpeg -y -v warning -framerate 4 -pattern_type glob -i "{dir_out}band{banda}/band{banda}_*_*_{roi}.png" "{dir_out}band{banda}/band{banda}_{roi}.gif"')

    # Chamada de sistema para o software ffmpeg realizar a criacao do gif animado
    def create_gif(file_type, roi):
        os.system(f'/usr/bin/ffmpeg -y -v warning -framerate 4 -pattern_type glob -i "{dir_out}{file_type}/{file_type}_*_*_{roi}.png" "{dir_out}{file_type}/{file_type}_{roi}.gif"')

    # Se a variavel de controle de processamento do brasil for True, cria o gif
    if g_br:
        logging.info('')
        logging.info('CRIANDO GIF ANIMADO "BR"...')
        # Contador para gif nas 16 bandas
        for x in range(1, 17):
            # Transforma o inteiro contador em string e com 2 digitos
            b = str(x).zfill(2)
            # Se o dicionario de controle das bandas apontar True para essa banda, cria o gif
            if g_bands[b]:
                logging.info('Gif BR banda ' + b)
                # Cria o processo com a funcao gif
                process = Process(target=create_gif_cmi, args=(b, "br"))
                # Adiciona o processo na lista de controle do processamento paralelo
                gif_br.append(process)
                # Inicia o processo
                process.start()
        # Looping de controle que pausa o processamento principal ate que todos os processos da lista de controle do processamento paralelo sejam finalizados
        for process in gif_br:
            # Bloqueia a execução do processo principal ate que o processo cujo metodo de join() é chamado termine
            process.join()

    # Se a variavel de controle de processamento do estado de sao paulo for True, cria o gif
    if g_sp:
        logging.info('')
        logging.info('CRIANDO GIF ANIMADO "SP"...')
        # Contador para gif nas 16 bandas
        for x in range(1, 17):
            # Transforma o inteiro contador em string e com 2 digitos
            b = str(x).zfill(2)
            # Se o dicionario de controle das bandas apontar True para essa banda, cria o gif
            if g_bands[b]:
                logging.info('Gif SP banda ' + b)
                # Cria o processo com a funcao gif
                process = Process(target=create_gif_cmi, args=(b, "sp"))
                # Adiciona o processo na lista de controle do processamento paralelo
                gif_br.append(process)
                # Inicia o processo
                process.start()
        # Looping de controle que pausa o processamento principal ate que todos os processos da lista de controle do processamento paralelo sejam finalizados
        for process in gif_sp:
            # Bloqueia a execução do processo principal ate que o processo cujo metodo de join() é chamado termine
            process.join()

    if g_bands["17"]:
        if g_br:
            logging.info('')
            logging.info('CRIANDO GIF ANIMADO TRUECOLOR "BR"...')
            # Cria o processo com a funcao gif
            create_gif("truecolor", "br")
        if g_br:
            logging.info('')
            logging.info('CRIANDO GIF ANIMADO TRUECOLOR "SP"...')
            # Cria o processo com a funcao gif
            create_gif("truecolor", "sp")

    if g_bands["18"]:
        if g_br:
            logging.info('')
            logging.info('CRIANDO GIF ANIMADO RRQPEF "BR"...')
            # Cria o processo com a funcao gif
            create_gif("rrqpef", "br")
        if g_br:
            logging.info('')
            logging.info('CRIANDO GIF ANIMADO RRQPEF "SP"...')
            # Cria o processo com a funcao gif
            create_gif("rrqpef", "sp")

    if g_bands["19"]:
        if g_br:
            logging.info('')
            logging.info('CRIANDO GIF ANIMADO GLM "BR"...')
            # Cria o processo com a funcao gif
            create_gif("glm", "br")

    if g_bands["20"]:
        if g_br:
            logging.info('')
            logging.info('CRIANDO GIF ANIMADO NDVI "BR"...')
            # Cria o processo com a funcao gif
            create_gif("ndvi", "br")

    if g_bands["21"]:
        if g_br:
            logging.info('')
            logging.info('CRIANDO GIF ANIMADO FDCF "BR"...')
            # Cria o processo com a funcao gif
            create_gif("fdcf", "br")

def process_band_rgb(rgb_type, v_extent, ch01=None, ch02=None, ch03=None):
    global dir_shapefiles, dir_colortables, dir_logos, dir_out
    # Captura a hora para contagem do tempo de processamento da imagem
    processing_start_time = time.time()
    # Area de interesse para recorte
    if v_extent == 'br':
        # Brasil
        extent = [-90.0, -40.0, -20.0, 10.0]  # Min lon, Min lat, Max lon, Max lat
    elif v_extent == 'sp':
        # São Paulo
        extent = [-53.25, -26.0, -44.0, -19.5]  # Min lon, Min lat, Max lon, Max lat
    else:
        extent = [-115.98, -55.98, -25.01, 34.98]  # Min lon, Min lat, Max lon, Max lat

    if rgb_type == 'truecolor':
        # https://rammb.cira.colostate.edu/training/visit/quick_guides/
        # http://cimss.ssec.wisc.edu/goes/OCLOFactSheetPDFs/ABIQuickGuide_CIMSSRGB_v2.pdf
        # Lendo imagem CMI reprojetada
        reproject_ch01 = Dataset(ch01)
        reproject_ch02 = Dataset(ch02)
        reproject_ch03 = Dataset(ch03)

        # Coletando do nome da imagem o satelite e a data/hora
        satellite_ch01 = (ch01[ch01.find("M6C01_G") + 7:ch01.find("_s")])
        dtime_ch01 = ch01[ch01.find("M6C01_G16_s") + 11:ch01.find("_e") - 1]

        data_ch01 = reproject_ch01.variables['Band1'][:]
        data_ch02 = reproject_ch02.variables['Band1'][:]
        data_ch03 = reproject_ch03.variables['Band1'][:]
        reproject_ch01 = None
        del reproject_ch01
        reproject_ch02 = None
        del reproject_ch02
        reproject_ch03 = None
        del reproject_ch03

        # RGB Components
        R = data_ch02
        G = 0.45 * data_ch02 + 0.1 * data_ch03 + 0.45 * data_ch01
        B = data_ch01

        # Minimuns, Maximuns and Gamma
        Rmin = 0.0
        Rmax = 1.0
        Gmin = 0.0
        Gmax = 1.0
        Bmin = 0.0
        Bmax = 1.0

        R[R > Rmax] = Rmax
        R[R < Rmin] = Rmin
        G[G > Gmax] = Gmax
        G[G < Gmin] = Gmin
        B[B > Bmax] = Bmax
        B[B < Bmin] = Bmin

        gamma_R = 1
        gamma_G = 1
        gamma_B = 1

        # Normalize the data
        R = ((R - Rmin) / (Rmax - Rmin)) ** (1 / gamma_R)
        G = ((G - Gmin) / (Gmax - Gmin)) ** (1 / gamma_G)
        B = ((B - Bmin) / (Bmax - Bmin)) ** (1 / gamma_B)

        # Create the RGB
        RGB = np.stack([R, G, B], axis=2)

        # Eliminate values outside the globe
        mask = (RGB == [R[0, 0], G[0, 0], B[0, 0]]).all(axis=2)
        RGB[mask] = np.nan

    else:
        return False

    # Formatando data para plotar na imagem e salvar o arquivo
    date = (datetime.datetime.strptime(dtime_ch01, '%Y%j%H%M%S'))
    date_img = date.strftime('%d-%b-%Y %H:%M UTC')
    date_file = date.strftime('%Y%m%d_%H%M%S')

    # Formatando a descricao a ser plotada na imagem
    description = f' GOES-{satellite_ch01} Natural True Color {date_img}'
    institution = "CEPAGRI - UNICAMP"

    # Definindo tamanho da imagem de saida
    d_p_i = 150
    fig = plt.figure(figsize=(2000 / float(d_p_i), 2000 / float(d_p_i)), frameon=True, dpi=d_p_i, edgecolor='black', facecolor='black')

    # Utilizando projecao geoestacionaria no cartopy
    ax = plt.axes(projection=ccrs.PlateCarree())

    if v_extent == 'br':
        # Adicionando o shapefile dos estados brasileiros
        # https://geoftp.ibge.gov.br/organizacao_do_territorio/malhas_territoriais/malhas_municipais/municipio_2020/Brasil/BR/BR_UF_2020.zip
        shapefile = list(shpreader.Reader(dir_shapefiles + 'brasil/BR_UF_2020').geometries())
        ax.add_geometries(shapefile, ccrs.PlateCarree(), edgecolor='cyan', facecolor='none', linewidth=0.7)
    elif v_extent == 'sp':
        # Adicionando o shapefile dos estados brasileiros e cidade de campinas
        # https://geoftp.ibge.gov.br/organizacao_do_territorio/malhas_territoriais/malhas_municipais/municipio_2020/Brasil/BR/BR_UF_2020.zip
        shapefile = list(shpreader.Reader(dir_shapefiles + 'brasil/BR_UF_2020').geometries())
        ax.add_geometries(shapefile, ccrs.PlateCarree(), edgecolor='cyan', facecolor='none', linewidth=0.7)
        shapefile = list(shpreader.Reader(dir_shapefiles + 'campinas/campinas').geometries())
        ax.add_geometries(shapefile, ccrs.PlateCarree(), edgecolor='yellow', facecolor='none', linewidth=1)

    # Adicionando  linhas dos litorais
    ax.coastlines(resolution='10m', color='cyan', linewidth=0.5)
    # Adicionando  linhas das fronteiras
    ax.add_feature(cartopy.feature.BORDERS, edgecolor='cyan', linewidth=0.5)
    # Adicionando  paralelos e meridianos
    gl = ax.gridlines(crs=ccrs.PlateCarree(), color='white', alpha=0.7, linestyle='--', linewidth=0.2, xlocs=np.arange(-180, 180, 5), ylocs=np.arange(-90, 90, 5))
    gl.top_labels = False
    gl.right_labels = False

    # Formatando a extensao da imagem, modificando ordem de minimo e maximo longitude e latitude
    img_extent = [extent[0], extent[2], extent[1], extent[3]]  # Min lon, Max lon, Min lat, Max lat

    # Plotando a imagem
    ax.imshow(RGB, origin='upper', extent=img_extent)

    # Adicionando descricao da imagem
    # Criando novos eixos de acordo com a posicao da imagem
    cax0 = fig.add_axes([ax.get_position().x0 + 0.003, ax.get_position().y0 - 0.0135, ax.get_position().width - 0.003, 0.0125])
    cax0.patch.set_color('black')  # Alterando a cor do novo eixo
    cax0.text(0, 0.13, description, color='white', size=10)  # Adicionando texto
    cax0.text(0.85, 0.13, institution, color='yellow', size=10)  # Adicionando texto
    cax0.xaxis.set_visible(False)  # Removendo rotulos do eixo X
    cax0.yaxis.set_visible(False)  # Removendo rotulos do eixo Y

    # Adicionando os logos
    logo_noaa = plt.imread(dir_logos + 'NOAA_Logo.png')  # Lendo o arquivo do logo
    logo_goes = plt.imread(dir_logos + 'GOES_Logo.png')  # Lendo o arquivo do logo
    logo_cepagri = plt.imread(dir_logos + 'CEPAGRI-Logo.png')  # Lendo o arquivo do logo
    fig.figimage(logo_noaa, 32, 203, zorder=3, alpha=0.6, origin='upper')  # Plotando logo
    fig.figimage(logo_goes, 10, 120, zorder=3, alpha=0.6, origin='upper')  # Plotando logo
    fig.figimage(logo_cepagri, 10, 40, zorder=3, alpha=0.8, origin='upper')  # Plotando logo

    # Salvando a imagem de saida
    plt.savefig(f'{dir_out}{rgb_type}/{rgb_type}_{date_file}_{v_extent}.png', bbox_inches='tight', pad_inches=0, dpi=d_p_i)
    # Fecha a janela para limpar a memoria
    plt.close()
    # Realiza o log do calculo do tempo de processamento da imagem
    logging.info(f'{ch01[0:59].replace("M6C01", "M6C0*")} - {v_extent} - {str(round(time.time() - processing_start_time, 4))} segundos')

def reproject(reproj_file, reproj_var, reproj_extent, reproj_resolution):
    global dir_in
    def get_geot(ex, nlines, ncols):
        # Compute resolution based on data dimension
        resx = (ex[2] - ex[0]) / ncols
        resy = (ex[3] - ex[1]) / nlines
        return [ex[0], resx, 0, ex[3], 0, -resy]

    if reproj_extent == 'br':
        # Brasil
        r_extent = [-90.0, -40.0, -20.0, 10.0]  # Min lon, Min lat, Max lon, Max lat
    elif reproj_extent == 'sp':
        # São Paulo
        r_extent = [-53.25, -26.0, -44.0, -19.5]  # Min lon, Min lat, Max lon, Max lat
    else:
        r_extent = [-90.0, -40.0, -20.0, 10.0]  # Min lon, Min lat, Max lon, Max lat

    # GOES-16 Spatial Reference System
    source_prj = osr.SpatialReference()
    source_prj.ImportFromProj4('+proj=geos +h=35786023.0 +a=6378137.0 +b=6356752.31414 +f=0.00335281068119356027 +lat_0=0.0 +lon_0=-75 +sweep=x +no_defs')
    # Lat/lon WSG84 Spatial Reference System
    target_prj = osr.SpatialReference()
    target_prj.ImportFromProj4('+proj=longlat +ellps=WGS84 +datum=WGS84 +no_defs')

    # Abrindo imagem com a biblioteca GDAL
    raw = gdal.Open(f'NETCDF:{reproj_file}:' + reproj_var, gdal.GA_ReadOnly)

    # Lendo os metadados do cabecalho
    if reproj_var == 'BCM':  ### O arquivo Clear Sky não possui sacale e offset é um arquivo binário
        metadata = raw.GetMetadata()
        scale = 1
        offset = 0
        undef = float(metadata.get(reproj_var + '#_FillValue'))
        file_dtime = metadata.get('NC_GLOBAL#time_coverage_start')
        file_satellite = metadata.get('NC_GLOBAL#platform_ID')[1:3]

    else:  # Alteração João 26/08/2022
        metadata = raw.GetMetadata()
        scale = float(metadata.get(reproj_var + '#scale_factor'))
        offset = float(metadata.get(reproj_var + '#add_offset'))
        undef = float(metadata.get(reproj_var + '#_FillValue'))
        file_dtime = metadata.get('NC_GLOBAL#time_coverage_start')
        file_satellite = metadata.get('NC_GLOBAL#platform_ID')[1:3]

    # Setup projection and geo-transformation
    raw.SetProjection(source_prj.ExportToWkt())
    # raw.SetGeoTransform(raw.GetGeoTransform())
    GOES16_EXTENT = [-5434894.885056, -5434894.885056, 5434894.885056, 5434894.885056]
    raw.SetGeoTransform(get_geot(GOES16_EXTENT, raw.RasterYSize, raw.RasterXSize))

    # Compute grid dimension
    KM_PER_DEGREE = 111.32
    sizex = int(((r_extent[2] - r_extent[0]) * KM_PER_DEGREE) / reproj_resolution)
    sizey = int(((r_extent[3] - r_extent[1]) * KM_PER_DEGREE) / reproj_resolution)

    # Get memory driver
    driver = gdal.GetDriverByName('MEM')

    # Create grid
    grid = driver.Create('grid', sizex, sizey, 1, gdal.GDT_Float32)

    # Setup projection and geo-transformation
    grid.SetProjection(target_prj.ExportToWkt())
    grid.SetGeoTransform(get_geot(r_extent, grid.RasterYSize, grid.RasterXSize))

    # Perform the projection/resampling
    gdal.ReprojectImage(raw, grid, source_prj.ExportToWkt(), target_prj.ExportToWkt(), gdal.GRA_NearestNeighbour, options=['NUM_THREADS=ALL_CPUS'])

    # Close file
    raw = None
    del raw

    # Read grid data
    array = grid.ReadAsArray()

    # Mask fill values (i.e. invalid values)
    np.ma.masked_where(array, array == -1, False)

    # Aplicando scale, offset
    array = array * scale + offset

    grid.GetRasterBand(1).SetNoDataValue(-1)
    grid.GetRasterBand(1).WriteArray(array)

    # Define the parameters of the output file
    kwargs = {'format': 'netCDF',
              'dstSRS': target_prj,
              'outputBounds': (r_extent[0], r_extent[3], r_extent[2], r_extent[1]),
              'outputBoundsSRS': target_prj,
              'outputType': gdal.GDT_Float32,
              'srcNodata': undef,
              'dstNodata': 'nan',
              'resampleAlg': gdal.GRA_NearestNeighbour}

    reproj_file = reproj_file.split('/')
    reproj_file.reverse()
    r_file = reproj_file[0].replace('.nc', f'_reproj_{reproj_extent}.nc')
    gdal.Warp(f'{dir_in}{reproj_file[1]}/{r_file}', grid, **kwargs)

    return file_dtime, file_satellite, grid

def process_rrqpef(rrqpef, ch13, v_extent):
    global dir_in, dir_shapefiles, dir_colortables, dir_logos, dir_out
    file_var = 'RRQPE'
    # Captura a hora para contagem do tempo de processamento da imagem
    processing_start_time = time.time()
    # Area de interesse para recorte
    if v_extent == 'br':
        # Brasil
        extent = [-90.0, -40.0, -20.0, 10.0]  # Min lon, Min lat, Max lon, Max lat
        # Choose the image resolution (the higher the number the faster the processing is)
        resolution = 4.0
    elif v_extent == 'sp':
        # São Paulo
        extent = [-53.25, -26.0, -44.0, -19.5]  # Min lon, Min lat, Max lon, Max lat
        # Choose the image resolution (the higher the number the faster the processing is)
        resolution = 1.0
    else:
        extent = [-115.98, -55.98, -25.01, 34.98]  # Min lon, Min lat, Max lon, Max lat
        resolution = 2.0

    # Reprojetando imagem CMI e recebendo data/hora da imagem, satelite e caminho absoluto do arquivo reprojetado
    dtime, satellite, reproject_rrqpef = reproject(rrqpef, file_var, v_extent, resolution)
    data = reproject_rrqpef.ReadAsArray()
    reproject_rrqpef = None
    del reproject_rrqpef
    # Convert from int16 to uint16
    data = data.astype(np.float64)
    data[data == max(data[0])] = np.nan
    data[data == min(data[0])] = np.nan

    reproject_ch13 = Dataset(ch13)
    data_ch13 = reproject_ch13.variables['Band1'][:]

    # Formatando data para plotar na imagem e salvar o arquivo
    date = (datetime.datetime.strptime(dtime, '%Y-%m-%dT%H:%M:%S.%fZ'))
    date_img = date.strftime('%d-%b-%Y %H:%M UTC')
    date_file = date.strftime('%Y%m%d_%H%M%S')

    # Formatando a descricao a ser plotada na imagem
    description = f' GOES-{satellite} Rainfall Rate (Quantitative Precipitation Estimate) mm/h {date_img}'
    institution = "CEPAGRI - UNICAMP"

    # Definindo tamanho da imagem de saida
    d_p_i = 150
    fig = plt.figure(figsize=(2000 / float(d_p_i), 2000 / float(d_p_i)), frameon=True, dpi=d_p_i, edgecolor='black', facecolor='black')

    # Utilizando projecao geoestacionaria no cartopy
    ax = plt.axes(projection=ccrs.PlateCarree())

    ax.set_extent([extent[0], extent[2], extent[1], extent[3]], ccrs.PlateCarree())

    if v_extent == 'br':
        # Adicionando o shapefile dos estados brasileiros
        # https://geoftp.ibge.gov.br/organizacao_do_territorio/malhas_territoriais/malhas_municipais/municipio_2020/Brasil/BR/BR_UF_2020.zip
        shapefile = list(shpreader.Reader(dir_shapefiles + 'brasil/BR_UF_2020').geometries())
        ax.add_geometries(shapefile, ccrs.PlateCarree(), edgecolor='cyan', facecolor='none', linewidth=0.7)
    elif v_extent == 'sp':
        # Adicionando o shapefile dos estados brasileiros e cidade de campinas
        # https://geoftp.ibge.gov.br/organizacao_do_territorio/malhas_territoriais/malhas_municipais/municipio_2020/Brasil/BR/BR_UF_2020.zip
        shapefile = list(shpreader.Reader(dir_shapefiles + 'brasil/BR_UF_2020').geometries())
        ax.add_geometries(shapefile, ccrs.PlateCarree(), edgecolor='cyan', facecolor='none', linewidth=0.7)
        shapefile = list(shpreader.Reader(dir_shapefiles + 'campinas/campinas').geometries())
        ax.add_geometries(shapefile, ccrs.PlateCarree(), edgecolor='yellow', facecolor='none', linewidth=1)

    # Adicionando  linhas dos litorais
    ax.coastlines(resolution='10m', color='cyan', linewidth=0.5)
    # Adicionando  linhas das fronteiras
    ax.add_feature(cartopy.feature.BORDERS, edgecolor='cyan', linewidth=0.5)
    # Adicionando  paralelos e meridianos
    gl = ax.gridlines(crs=ccrs.PlateCarree(), color='white', alpha=0.7, linestyle='--', linewidth=0.2, xlocs=np.arange(-180, 180, 5), ylocs=np.arange(-90, 90, 5))
    gl.top_labels = False
    gl.right_labels = False

    # Formatando a extensao da imagem, modificando ordem de minimo e maximo longitude e latitude
    img_extent = [extent[0], extent[2], extent[1], extent[3]]  # Min lon, Max lon, Min lat, Max lat

    # Plotando base
    ax.imshow(data_ch13, origin='upper', cmap='gray_r', extent=img_extent)

    # Plotando a imagem
    img = ax.imshow(data, vmin=0, vmax=150, cmap='jet', origin='upper', extent=img_extent)

    # Criando novos eixos de acordo com a posicao da imagem
    cax0 = fig.add_axes([ax.get_position().x0 + 0.0025, ax.get_position().y0 - 0.01325, ax.get_position().width - 0.0025, 0.0125])
    cb = plt.colorbar(img, orientation="horizontal", cax=cax0)
    cb.ax.tick_params(axis='x', colors='white', labelsize=8)  # Alterando cor e tamanho dos rotulos da barra da paleta de cores
    cb.outline.set_visible(False)  # Removendo contorno da barra da paleta de cores
    cb.ax.tick_params(width=0)  # Removendo ticks da barra da paleta de cores
    cb.ax.xaxis.set_tick_params(pad=-13)  # Colocando os rotulos dentro da barra da paleta de cores

    # Adicionando descricao da imagem
    # Criando novos eixos de acordo com a posicao da imagem
    cax1 = fig.add_axes([ax.get_position().x0 + 0.003, ax.get_position().y0 - 0.026, ax.get_position().width - 0.003, 0.0125])
    cax1.patch.set_color('black')  # Alterando a cor do novo eixo
    cax1.text(0, 0.13, description, color='white', size=10)  # Adicionando texto
    cax1.text(0.85, 0.13, institution, color='yellow', size=10)  # Adicionando texto
    cax1.xaxis.set_visible(False)  # Removendo rotulos do eixo X
    cax1.yaxis.set_visible(False)  # Removendo rotulos do eixo Y

    # Adicionando os logos
    logo_noaa = plt.imread(dir_logos + 'NOAA_Logo.png')  # Lendo o arquivo do logo
    logo_goes = plt.imread(dir_logos + 'GOES_Logo.png')  # Lendo o arquivo do logo
    logo_cepagri = plt.imread(dir_logos + 'CEPAGRI-Logo.png')  # Lendo o arquivo do logo
    fig.figimage(logo_noaa, 32, 223, zorder=3, alpha=0.6, origin='upper')  # Plotando logo
    fig.figimage(logo_goes, 10, 140, zorder=3, alpha=0.6, origin='upper')  # Plotando logo
    fig.figimage(logo_cepagri, 10, 60, zorder=3, alpha=0.8, origin='upper')  # Plotando logo

    # Salvando a imagem de saida
    plt.savefig(f'{dir_out}rrqpef/rrqpef_{date_file}_{v_extent}.png', bbox_inches='tight', pad_inches=0, dpi=d_p_i)
    # Fecha a janela para limpar a memoria
    plt.close()
    # Realiza o log do calculo do tempo de processamento da imagem
    logging.info(f'{rrqpef} - {v_extent} - {str(round(time.time() - processing_start_time, 4))} segundos')

def process_glm(ch13, glm_list, v_extent):
    global dir_in, dir_shapefiles, dir_colortables, dir_logos, dir_out
    # Captura a hora para contagem do tempo de processamento da imagem
    processing_start_time = time.time()
    # Area de interesse para recorte
    if v_extent == 'br':
        # Brasil
        extent = [-90.0, -40.0, -20.0, 10.0]  # Min lon, Min lat, Max lon, Max lat
    elif v_extent == 'sp':
        # São Paulo
        extent = [-53.25, -26.0, -44.0, -19.5]  # Min lon, Min lat, Max lon, Max lat
    else:
        extent = [-115.98, -55.98, -25.01, 34.98]  # Min lon, Min lat, Max lon, Max lat

    # Lendo imagem CMI reprojetada
    reproject_ch13 = Dataset(ch13)
    data_ch13 = reproject_ch13.variables['Band1'][:]

    # Coletando do nome da imagem o satelite e a data/hora
    satellite = (glm_list[0][glm_list[0].find("GLM-L2-LCFA_G") + 13:glm_list[0].find("_s")])
    dtime = (glm_list[0][glm_list[0].find("GLM-L2-LCFA_G16_s") + 17:glm_list[0].find("_e") - 1])

    # Initialize arrays for latitude, longitude, and event energy
    lats = np.array([])
    lons = np.array([])
    energies = np.array([])

    for g in glm_list:
        # Lendo imagem CMI reprojetada
        glm = Dataset(f'{dir_in}glm/{g}')
        # Append lats / longs / event energies
        lats = np.append(lats, glm.variables['event_lat'][:])
        lons = np.append(lons, glm.variables['event_lon'][:])
        energies = np.append(energies, glm.variables['event_energy'][:])

    # Stack and transpose the lat lons
    values = np.vstack((lats, lons)).T
    # Get the counts
    points, counts = np.unique(values, axis=0, return_counts=True)
    # Get the counts indices
    idx = counts.argsort()

    # Formatando data para plotar na imagem e salvar o arquivo
    date = (datetime.datetime.strptime(dtime, '%Y%j%H%M%S'))
    date_img = date.strftime('%d-%b-%Y %H:%M UTC')
    date_file = date.strftime('%Y%m%d_%H%M%S')

    # Formatando a descricao a ser plotada na imagem
    description = f' GOES-{satellite} GLM Density {date_img}'
    institution = "CEPAGRI - UNICAMP"

    # Choose the plot size (width x height, in inches)
    d_p_i = 150
    fig = plt.figure(figsize=(2000 / float(d_p_i), 2000 / float(d_p_i)), frameon=True, dpi=d_p_i, edgecolor='black', facecolor='black')

    # Use the Geostationary projection in cartopy
    ax = plt.axes(projection=ccrs.PlateCarree())

    # Define the image extent
    ax.set_extent([extent[0], extent[2], extent[1], extent[3]], ccrs.PlateCarree())

    if v_extent == 'br':
        # Adicionando o shapefile dos estados brasileiros
        # https://geoftp.ibge.gov.br/organizacao_do_territorio/malhas_territoriais/malhas_municipais/municipio_2020/Brasil/BR/BR_UF_2020.zip
        shapefile = list(shpreader.Reader(dir_shapefiles + 'brasil/BR_UF_2020').geometries())
        ax.add_geometries(shapefile, ccrs.PlateCarree(), edgecolor='cyan', facecolor='none', linewidth=0.7)
    elif v_extent == 'sp':
        # Adicionando o shapefile dos estados brasileiros e cidade de campinas
        # https://geoftp.ibge.gov.br/organizacao_do_territorio/malhas_territoriais/malhas_municipais/municipio_2020/Brasil/BR/BR_UF_2020.zip
        shapefile = list(shpreader.Reader(dir_shapefiles + 'brasil/BR_UF_2020').geometries())
        ax.add_geometries(shapefile, ccrs.PlateCarree(), edgecolor='cyan', facecolor='none', linewidth=0.7)
        shapefile = list(shpreader.Reader(dir_shapefiles + 'campinas/campinas').geometries())
        ax.add_geometries(shapefile, ccrs.PlateCarree(), edgecolor='yellow', facecolor='none', linewidth=1)

    # Adicionando  linhas dos litorais
    ax.coastlines(resolution='10m', color='cyan', linewidth=0.5)
    # Adicionando  linhas das fronteiras
    ax.add_feature(cartopy.feature.BORDERS, edgecolor='cyan', linewidth=0.5)
    # Adicionando  paralelos e meridianos
    gl = ax.gridlines(crs=ccrs.PlateCarree(), color='white', alpha=0.7, linestyle='--', linewidth=0.2, xlocs=np.arange(-180, 180, 5), ylocs=np.arange(-90, 90, 5))
    gl.top_labels = False
    gl.right_labels = False

    # Formatando a extensao da imagem, modificando ordem de minimo e maximo longitude e latitude
    img_extent = [extent[0], extent[2], extent[1], extent[3]]  # Min lon, Max lon, Min lat, Max lat

    # Plotando base
    ax.imshow(data_ch13, origin='upper', cmap='gray_r', extent=img_extent)

    # Plot the GLM Data
    glm = plt.scatter(points[idx, 1], points[idx, 0], vmin=0, vmax=1000, s=counts[idx] * 0.1, c=counts[idx], cmap="jet", zorder=2)

    cax0 = fig.add_axes([ax.get_position().x0, ax.get_position().y0 - 0.01325, ax.get_position().width, 0.0125])
    cb = plt.colorbar(glm, orientation="horizontal", cax=cax0, ticks=[200, 400, 600, 800])
    cb.ax.set_xticklabels(['200', '400', '600', '800'])
    cb.ax.tick_params(axis='x', colors='black', labelsize=8)  # Alterando cor e tamanho dos rotulos da barra da paleta de cores
    cb.outline.set_visible(False)  # Removendo contorno da barra da paleta de cores
    cb.ax.tick_params(width=0)  # Removendo ticks da barra da paleta de cores
    cb.ax.xaxis.set_tick_params(pad=-13)  # Colocando os rotulos dentro da barra da paleta de cores

    # Adicionando descricao da imagem
    # Criando novos eixos de acordo com a posicao da imagem
    cax1 = fig.add_axes([ax.get_position().x0 + 0.003, ax.get_position().y0 - 0.026, ax.get_position().width - 0.003, 0.0125])
    cax1.patch.set_color('black')  # Alterando a cor do novo eixo
    cax1.text(0, 0.13, description, color='white', size=10)  # Adicionando texto
    cax1.text(0.85, 0.13, institution, color='yellow', size=10)  # Adicionando texto
    cax1.xaxis.set_visible(False)  # Removendo rotulos do eixo X
    cax1.yaxis.set_visible(False)  # Removendo rotulos do eixo Y

    # Adicionando os logos
    logo_noaa = plt.imread(dir_logos + 'NOAA_Logo.png')  # Lendo o arquivo do logo
    logo_goes = plt.imread(dir_logos + 'GOES_Logo.png')  # Lendo o arquivo do logo
    logo_cepagri = plt.imread(dir_logos + 'CEPAGRI-Logo.png')  # Lendo o arquivo do logo
    fig.figimage(logo_noaa, 32, 233, zorder=3, alpha=0.6, origin='upper')  # Plotando logo
    fig.figimage(logo_goes, 10, 150, zorder=3, alpha=0.6, origin='upper')  # Plotando logo
    fig.figimage(logo_cepagri, 10, 70, zorder=3, alpha=0.8, origin='upper')  # Plotando logo

    # Salvando a imagem de saida
    plt.savefig(f'{dir_out}glm/glm_{date_file}_{v_extent}.png', bbox_inches='tight', pad_inches=0, dpi=d_p_i)
    # Fecha a janela para limpar a memoria
    plt.close()
    # Realiza o log do calculo do tempo de processamento da imagem
    logging.info(f'{dir_in}glm/{glm_list[0][0:31]}*.nc - {v_extent} - {str(round(time.time() - processing_start_time, 4))} segundos')

def process_ndvi(ndvi_diario, ch02, ch03, v_extent):
    global dir_shapefiles, dir_colortables, dir_logos, dir_in, dir_out
    # Captura a hora para contagem do tempo de processamento da imagem
    processing_start_time = time.time()
    # Area de interesse para recorte
    if v_extent == 'br':
        # Brasil
        extent = [-90.0, -40.0, -20.0, 10.0]  # Min lon, Min lat, Max lon, Max lat
    elif v_extent == 'sp':
        # São Paulo
        extent = [-53.25, -26.0, -44.0, -19.5]  # Min lon, Min lat, Max lon, Max lat
    else:
        extent = [-115.98, -55.98, -25.01, 34.98]  # Min lon, Min lat, Max lon, Max lat

    # Lendo imagem CMI reprojetada
    reproject_ch02 = Dataset(ch02)
    reproject_ch03 = Dataset(ch03)

    # Coletando do nome da imagem a data/hora
    dtime_ch02 = ch02[ch02.find("M6C02_G16_s") + 11:ch02.find("_e") - 1]

    #//Hora para fazer o download Mask
    dtime_mask = ch02[ch02.find("M6C02_G16_s") + 11:ch02.find("_e") - 3]

    ## Transforma de data Juliana para data normal
    year = datetime.datetime.strptime(dtime_mask, '%Y%j%H%M').strftime('%Y')
    day_of_year = datetime.datetime.strptime(dtime_mask, '%Y%j%H%M').strftime('%d')
    month = datetime.datetime.strptime(dtime_mask, '%Y%j%H%M').strftime('%m')
    hora = datetime.datetime.strptime(dtime_mask, '%Y%j%H%M').strftime('%H')
    min = datetime.datetime.strptime(dtime_mask, '%Y%j%H%M').strftime('%M')

    yyyymmddhhmn = year+month+day_of_year+hora+min

    #//Download arquivo mascara de nuvens
    print("Download File Mask NDVI")
    file_mask = download_prod(yyyymmddhhmn,'ABI-L2-ACMF',f'{dir_in}clsm/')


    # // Reprojetando o arquivo de nuvens
    reproject(f'{dir_in}clsm/{file_mask}.nc','BCM',v_extent,4)

    # //Capturando o nome do arquivo reprojetado
    r_file = file_mask + f'_reproj_{v_extent}.nc'
    
    # // Abrindo o Dataset do arquivo da mascara
    reproject_mask = Dataset(f'{dir_in}clsm/{r_file}')


    data_ch02 = reproject_ch02.variables['Band1'][:]
    data_ch03 = reproject_ch03.variables['Band1'][:]

    ## //
    data_mask = reproject_mask.variables['Band1'][:]

    reproject_ch02 = None
    del reproject_ch02
    reproject_ch03 = None
    del reproject_ch03

    ## //
    reproject_mask = None
    del reproject_mask


    # NDVI Components
    NDVI = (data_ch03 - data_ch02) / (data_ch03 + data_ch02)

    # // Capturando somente os valores máximos de NDVI
    NDVI_fmax = np.zeros(np.shape(NDVI))
    NDVI_fmax[NDVI_fmax == 0 ] = np.nan

    NDVI_fmax = np.fmax(NDVI_fmax,NDVI)

    # // Retirando as nuvens do arquivo NDVI
    NDVI_fmax = np.where(data_mask==0,NDVI,data_mask)
    NDVI_fmax[NDVI_fmax == 1]= np.nan

    # Formatando data para plotar na imagem e salvar o arquivo
    date = (datetime.datetime.strptime(dtime_ch02, '%Y%j%H%M%S'))
    date_file = date.strftime('%Y%m%d_%H%M%S')

    # Salvando array NDVI
    print('Salvando - NDVI')
    NDVI_fmax.dump(f'{dir_in}ndvi/ndvi_{date_file}_{v_extent}.npy')

    # // Removendo os arquivos Clear Sky Mask baixados e reprojetado de nuvens
    print('Removendo arquivo filemask do diretório')
    os.remove(f'{dir_in}clsm/{r_file}')
    os.remove(f'{dir_in}clsm/{file_mask}.nc')


    if ndvi_diario and datetime.datetime.now().isoweekday() == 6:
        # Captura a data atual e calculando data inicial e final
        date_now = datetime.datetime.now()
        date_ini = datetime.datetime(date_now.year, date_now.month, date_now.day, int(13), int(00))
        date_end = datetime.datetime(date_now.year, date_now.month, date_now.day, int(18), int(00))

        # Cria uma lista com os itens no diretorio temp que sao arquivos e se encaixa na expressao regular "^ndvi_.+_.+_br.npy$"
        ndvi_list = [name for name in os.listdir(f'{dir_in}ndvi') if os.path.isfile(os.path.join(f'{dir_in}ndvi', name)) and re.match('^ndvi_.+_.+_br.npy$', name)]
        # Ordena de forma alfabetica a lista, ficando assim os arquivos mais antigos no comeco
        ndvi_list.sort()
        teste = np.load(f'{dir_in}ndvi/{ndvi_list[0]}', allow_pickle=True)
        NDVI_fmax = np.zeros(teste.shape)
        ## // Seta os valores para nan para não haver problema entre fazer o máximo entre um valor negativo e zero 
        ## // max(i,v) = v se i#0 e v >i / v £ R, se i=0 e v<0 max(i,v) = i então se i = nan max(i,v)=v para v £ R
        NDVI_fmax[NDVI_fmax == 0] = np.nan
        del teste

        # Looping para ler e comparar os arquivos NDVI salvos do sabado
        for f in ndvi_list:
            # Captura a data do arquivo
            date = f[f.find("ndvi_") + 5:f.find("ndvi_") + 13]
            # Captura a hora do arquivo
            hour = f[f.find("ndvi_") + 14:f.find("ndvi_") + 20]
            # Monta a data/hora do arquivo
            date_file = (datetime.datetime.strptime(date + hour, '%Y%m%d%H%M%S'))
            # Se a data/hora do arquivo estiver dentro do limite de datas
            if date_ini <= date_file <= date_end + datetime.timedelta(minutes=1):
                # print(f, date_file)
                # Le o arquivo NDVI
                NDVI_file = np.load(f'{dir_in}ndvi/{f}', allow_pickle=True)
                NDVI_file[NDVI_file > 0.999] = np.nan
                NDVI_file[NDVI_file < -0.999] = np.nan
                # Compara os arrays NDVI e retorna um novo array com os maiores valores de cada elemento
                NDVI_fmax = np.fmax(NDVI_fmax, NDVI_file)
                
            else:
                continue
                
        NDVI_fmax.dump(f'{dir_in}ndvi/ndvi_{date_ini.strftime("%Y%m%d")}_{date_end.strftime("%Y%m%d")}_br_fmax.npy')
        

        # Captura a data atual e calculando data inicial e final do acumulado da semana
        date_ini = datetime.datetime(date_now.year, date_now.month, date_now.day, int(23), int(59)) - datetime.timedelta(days=6, hours=23, minutes=59)
        date_end = datetime.datetime(date_now.year, date_now.month, date_now.day, int(23), int(59))

        # Cria uma lista com os itens no diretorio temp que sao arquivos e se encaixa na expressao regular "^ndvi_.+_.+_br.npy$"
        ndvi_list_fmax = [name for name in os.listdir(f'{dir_in}ndvi') if os.path.isfile(os.path.join(f'{dir_in}ndvi', name)) and re.match('^ndvi_.+_.+_br_fmax.npy$', name)]
        
        # Ordena de forma alfabetica a lista, ficando assim os arquivos mais antigos no comeco
        ndvi_list_fmax.sort()
        teste = np.load(f'{dir_in}ndvi/{ndvi_list_fmax[0]}', allow_pickle=True)
        NDVI_fmax = np.zeros(teste.shape)
        NDVI_fmax[NDVI_fmax == 0] = np.nan
        del teste

        # Looping para ler e comparar os arquivos NDVI salvos da semana
        for f in range(0, len(ndvi_list_fmax)):
            # Captura a data do arquivo
            date_i = ndvi_list_fmax[f][ndvi_list_fmax[f].find("ndvi_") + 5:ndvi_list_fmax[f].find("ndvi_") + 13]
            date_e = ndvi_list_fmax[f][ndvi_list_fmax[f].find("ndvi_") + 14:ndvi_list_fmax[f].find("ndvi_") + 22]
            # Monta a data/hora do arquivo
            date_file_i = (datetime.datetime.strptime(date_i, '%Y%m%d'))
            date_file_e = (datetime.datetime.strptime(date_e, '%Y%m%d'))
            # Se a data/hora do arquivo estiver dentro do limite de datas
            if date_file_i == date_file_e and date_ini <= date_file_i <= date_end:
                # Le o arquivo NDVI
                NDVI_file_fmax = np.load(f'{dir_in}ndvi/{ndvi_list_fmax[f]}', allow_pickle=True)

                # Compara os arrays NDVI e retorna um novo array com os maiores valores de cada elemento
                NDVI_fmax = np.fmax(NDVI_fmax, NDVI_file_fmax)

            else:
                continue

        NDVI_fmax.dump(f'{dir_in}ndvi/ndvi_{date_ini.strftime("%Y%m%d")}_{date_end.strftime("%Y%m%d")}_br.npy')

        # Formatando a descricao a ser plotada na imagem
        description = f' GOES-16 COMPOSIÇÃO MÁXIMA DE VALOR NDVI NO PERÍODO {date_ini.strftime("%d-%b-%Y")}  -  {date_end.strftime("%d-%b-%Y")}'
        institution = "CEPAGRI - UNICAMP"

        # Choose the plot size (width x height, in inches)
        d_p_i = 150
        fig = plt.figure(figsize=(2000 / float(d_p_i), 2000 / float(d_p_i)), frameon=True, dpi=d_p_i, edgecolor='black', facecolor='black')

        # Use the Geostationary projection in cartopy
        ax = plt.axes(projection=ccrs.PlateCarree())

        # Adicionando o shapefile dos estados brasileiros
        # https://geoftp.ibge.gov.br/organizacao_do_territorio/malhas_territoriais/malhas_municipais/municipio_2020/Brasil/BR/BR_UF_2020.zip
        shapefile = list(shpreader.Reader(dir_shapefiles + 'brasil/BR_UF_2020').geometries())
        ax.add_geometries(shapefile, ccrs.PlateCarree(), edgecolor='black', facecolor='none', linewidth=0.7)

        # Adicionando  linhas dos litorais
        ax.coastlines(resolution='10m', color='black', linewidth=0.5)
        # Adicionando  linhas das fronteiras
        ax.add_feature(cartopy.feature.BORDERS, edgecolor='black', linewidth=0.5)
        # Adicionando  paralelos e meridianos
        gl = ax.gridlines(crs=ccrs.PlateCarree(), color='white', alpha=0.7, linestyle='--', linewidth=0.2, xlocs=np.arange(-180, 180, 5), ylocs=np.arange(-90, 90, 5))
        gl.top_labels = False
        gl.right_labels = False

        # # Add an ocean mask
        ax.add_feature(cfeature.OCEAN, facecolor='cornflowerblue', zorder=3)
        
        # Formatando a extensao da imagem, modificando ordem de minimo e maximo longitude e latitude
        img_extent = [extent[0], extent[2], extent[1], extent[3]]  # Min lon, Max lon, Min lat, Max lat

        colors = ["#0000FF", "#0030FF", "#0060FF", "#0090FF", "#00C0FF", "#003000", "#164A16", "#00C000", "#FFFF00", "#FF8000", "#FF0000"]
        my_cmap = cm.colors.LinearSegmentedColormap.from_list("", colors)  # Create a custom linear colormap

        # Plotando a imagem
        array_NDVI = np.load(f'{dir_in}ndvi/ndvi_{date_ini.strftime("%Y%m%d")}_{date_end.strftime("%Y%m%d")}_br.npy', allow_pickle=True)
        img = ax.imshow(array_NDVI, origin='upper', vmin=-1, vmax=1, cmap=my_cmap, extent=img_extent)

        cax0 = fig.add_axes([ax.get_position().x0, ax.get_position().y0 - 0.01325, ax.get_position().width, 0.0125])
        cb = plt.colorbar(img, orientation="horizontal", cax=cax0, ticks=[-0.66, -0.33, 0, 0.33, 0.66])
        cb.ax.set_xticklabels(['-0.66', '-0.33', '0', '0.33', '0.66'])
        cb.ax.tick_params(axis='x', colors='black', labelsize=8)  # Alterando cor e tamanho dos rotulos da barra da paleta de cores
        cb.outline.set_visible(False)  # Removendo contorno da barra da paleta de cores
        cb.ax.tick_params(width=0)  # Removendo ticks da barra da paleta de cores
        cb.ax.xaxis.set_tick_params(pad=-13)  # Colocando os rotulos dentro da barra da paleta de cores

        # Adicionando descricao da imagem
        # Criando novos eixos de acordo com a posicao da imagem
        cax1 = fig.add_axes([ax.get_position().x0 + 0.003, ax.get_position().y0 - 0.026, ax.get_position().width - 0.003, 0.0125])
        cax1.patch.set_color('black')  # Alterando a cor do novo eixo
        cax1.text(0, 0.13, description, color='white', size=10)  # Adicionando texto
        cax1.text(0.85, 0.13, institution, color='yellow', size=10)  # Adicionando texto
        cax1.xaxis.set_visible(False)  # Removendo rotulos do eixo X
        cax1.yaxis.set_visible(False)  # Removendo rotulos do eixo Y

        # Adicionando os logos
        logo_noaa = plt.imread(dir_logos + 'NOAA_Logo.png')  # Lendo o arquivo do logo
        logo_goes = plt.imread(dir_logos + 'GOES_Logo.png')  # Lendo o arquivo do logo
        logo_cepagri = plt.imread(dir_logos + 'CEPAGRI-Logo.png')  # Lendo o arquivo do logo
        fig.figimage(logo_noaa, 32, 233, zorder=3, alpha=0.6, origin='upper')  # Plotando logo
        fig.figimage(logo_goes, 10, 150, zorder=3, alpha=0.6, origin='upper')  # Plotando logo
        fig.figimage(logo_cepagri, 10, 70, zorder=3, alpha=0.8, origin='upper')  # Plotando logo

        # Salvando a imagem de saida
        # plt.savefig(f'{dir_out}ndvi/ndvi_{date_end.strftime("%Y%m%d_%H%M%S")}_br.png', bbox_inches='tight', pad_inches=0, dpi=d_p_i)
        plt.savefig(f'{dir_out}ndvi/ndvi_{date_end.strftime("%Y%m%d_%H%M%S")}_br.png', bbox_inches='tight', pad_inches=0, dpi=d_p_i)
        # Fecha a janela para limpar a memoria
        plt.close()

    elif ndvi_diario:
        # Captura a data atual e calculando data inicial e final
        date_now = datetime.datetime.now()
        date_ini = datetime.datetime(date_now.year, date_now.month, date_now.day, int(13), int(00))
        date_end = datetime.datetime(date_now.year, date_now.month, date_now.day, int(18), int(00))

        # Cria uma lista com os itens no diretorio temp que sao arquivos e se encaixa na expressao regular "^ndvi_.+_.+_br.npy$"
        ndvi_list = [name for name in os.listdir(f'{dir_in}ndvi') if os.path.isfile(os.path.join(f'{dir_in}ndvi', name)) and re.match('^ndvi_.+_.+_br.npy$', name)]
        # Ordena de forma alfabetica a lista, ficando assim os arquivos mais antigos no comeco
        ndvi_list.sort()
        teste = np.load(f'{dir_in}ndvi/{ndvi_list[0]}', allow_pickle=True)
        NDVI_fmax = np.zeros(teste.shape)
        ## // Seta os valores para nan para não haver problema entre fazer o máximo entre um valor negativo e zero 
        ## // max(i,v) = v se i#0 e v >i / v £ R, se i=0 e v<0 max(i,v) = i então se i = nan max(i,v)=v para v £ R
        NDVI_fmax[NDVI_fmax == 0] = np.nan
        del teste

        # Looping para ler e comparar os arquivos NDVI salvos do dia
        for f in ndvi_list:
            # Captura a data do arquivo
            date = f[f.find("ndvi_") + 5:f.find("ndvi_") + 13]
            # Captura a hora do arquivo
            hour = f[f.find("ndvi_") + 14:f.find("ndvi_") + 20]
            # Monta a data/hora do arquivo
            date_file = (datetime.datetime.strptime(date + hour, '%Y%m%d%H%M%S'))
            # Se a data/hora do arquivo estiver dentro do limite de datas
            if date_ini <= date_file <= date_end + datetime.timedelta(minutes=1):
                # print(f, date_file)
                # Le o arquivo NDVI
                NDVI_file = np.load(f'{dir_in}ndvi/{f}', allow_pickle=True)
                NDVI_file[NDVI_file > 0.999] = np.nan
                NDVI_file[NDVI_file < -0.999] = np.nan
                # Compara os arrays NDVI e retorna um novo array com os maiores valores de cada elemento
                NDVI_fmax = np.fmax(NDVI_fmax, NDVI_file)
                # Remove o arquivo NDVI
                # os.remove(f'{dir_in}ndvi/{f}')
            else:
                continue
        ## // Acho desnecessário essa passagem pois nas linhas 308 e 309 tem o mesmo efeito
        # for i in range(0, NDVI_fmax.shape[0]):
        #     for j in range(0, NDVI_fmax.shape[1]):
        #         if not -1 < NDVI_fmax[i][j] < 1:
        #             NDVI_fmax[i][j] = np.nan
                

        NDVI_fmax.dump(f'{dir_in}ndvi/ndvi_{date_ini.strftime("%Y%m%d")}_{date_end.strftime("%Y%m%d")}_br_fmax.npy')

    # Realiza o log do calculo do tempo de processamento da imagem
    logging.info(f'{ch02[0:59].replace("M6C02", "M6C0*")} - {v_extent} - {str(round(time.time() - processing_start_time, 4))} segundos')

def process_fdcf(fdcf, ch01, ch02, ch03, v_extent, fdcf_diario):
    global dir_shapefiles, dir_colortables, dir_logos, dir_in, dir_out

    def degrees(file_id):
        proj_info = file_id.variables['goes_imager_projection']
        lon_origin = proj_info.longitude_of_projection_origin
        H = proj_info.perspective_point_height + proj_info.semi_major_axis
        r_eq = proj_info.semi_major_axis
        r_pol = proj_info.semi_minor_axis

        # Data info
        lat_rad_1d = file_id.variables['x'][:]
        lon_rad_1d = file_id.variables['y'][:]

        # Create meshgrid filled with radian angles
        lat_rad, lon_rad = np.meshgrid(lat_rad_1d, lon_rad_1d)

        # lat/lon calculus routine from satellite radian angle vectors
        lambda_0 = (lon_origin * np.pi) / 180.0

        a_var = np.power(np.sin(lat_rad), 2.0) + (np.power(np.cos(lat_rad), 2.0) * (
                np.power(np.cos(lon_rad), 2.0) + (((r_eq * r_eq) / (r_pol * r_pol)) * np.power(np.sin(lon_rad), 2.0))))
        b_var = -2.0 * H * np.cos(lat_rad) * np.cos(lon_rad)
        c_var = (H ** 2.0) - (r_eq ** 2.0)

        r_s = (-1.0 * b_var - np.sqrt((b_var ** 2) - (4.0 * a_var * c_var))) / (2.0 * a_var)

        s_x = r_s * np.cos(lat_rad) * np.cos(lon_rad)
        s_y = - r_s * np.sin(lat_rad)
        s_z = r_s * np.cos(lat_rad) * np.sin(lon_rad)

        lat = (180.0 / np.pi) * (np.arctan(((r_eq * r_eq) / (r_pol * r_pol)) * (s_z / np.sqrt(((H - s_x) * (H - s_x)) + (s_y * s_y)))))
        lon = (lambda_0 - np.arctan(s_y / (H - s_x))) * (180.0 / np.pi)

        return lat, lon

    def save_txt(array, nome_arquivo_txt):
        # Checa se a matriz é vazia
        if len(array) == 0:
            print(f'{nome_arquivo_txt} vazia')
            pass
        else:
            # Criando nome do arquivo e diretório -- Mudar as barras para Linux
            with open(f"{dir_out}fdcf/{nome_arquivo_txt}.txt", 'w') as file:  # tomar cuidado se não ele fica criando diretorio
                for valor in array:
                    valor = f"{valor[0]},{valor[1]}\n"
                    file.write(valor)

    def save_log_erro(array_errors, nome_arquivo_txt):
        # Checa se a matriz é vazia
        if len(array_errors) == 0:
            pass
        else:
            # Criando nome do arquivo e diretório -- Mudar as barras para Linux
            with open(f"{dir_out}fdcf/{nome_arquivo_txt}.txt", 'w') as file:
                for valor in array_errors:
                    erro = f"{valor}\n"
                    file.write(erro)

    file_var = 'FDCF'
    # Captura a hora para contagem do tempo de processamento da imagem
    processing_start_time = time.time()
    # Area de interesse para recorte
    if v_extent == 'br':
        # Brasil
        extent = [-90.0, -40.0, -20.0, 10.0]  # Min lon, Min lat, Max lon, Max lat
        # Choose the image resolution (the higher the number the faster the processing is)
        resolution = 4.0
    elif v_extent == 'sp':
        # São Paulo
        extent = [-53.25, -26.0, -44.0, -19.5]  # Min lon, Min lat, Max lon, Max lat
        # Choose the image resolution (the higher the number the faster the processing is)
        resolution = 1.0
    else:
        extent = [-115.98, -55.98, -25.01, 34.98]  # Min lon, Min lat, Max lon, Max lat
        resolution = 2.0

    # Lendo imagem FDCF
    fire_mask = Dataset(fdcf)

    # Coletando do nome da imagem a data/hora
    dtime_fdcf = fdcf[fdcf.find("ABI-L2-FDCF-M6_G16_s") + 20:fdcf.find("_e") - 1]
    # Formatando data para plotar na imagem e salvar o arquivo
    date = (datetime.datetime.strptime(dtime_fdcf, '%Y%j%H%M%S'))
    date_img = date.strftime('%d-%b-%Y')
    date_file = date.strftime('%Y%m%d_%H%M%S')

    matriz_pixels_fogo = []
    fire_mask_values = fire_mask.variables['Mask'][:, :]
    selected_fires = (fire_mask_values == 10) | (fire_mask_values == 11) | (fire_mask_values == 13) | (
            fire_mask_values == 30) | (fire_mask_values == 33)
    lat, lon = degrees(fire_mask)
    # separando Latitudes e Longitudes dos pontos
    p_lat = lat[selected_fires]
    p_lon = lon[selected_fires]
    brasil = list(shpreader.Reader(dir_shapefiles + "divisao_estados/gadm36_BRA_0").geometries())
    for i in range(len(p_lat)):
        if brasil[0].covers(Point(p_lon[i], p_lat[i])):
            p = (p_lat[i], p_lon[i])
            matriz_pixels_fogo.append(p)

    save_txt(matriz_pixels_fogo, f'fdcf_{date.strftime("%Y%m%d_%H%M%S")}_br')

    # Le o arquivo de controle de quantidade de pontos
    try:
        with open(f'{dir_temp}band21_control.txt', 'r') as fo:
            control = fo.readline()
            print("tamanho control withopen: ", int(control))
    except:
        control = 0
        print("tamanho control except: ", int(control))

    # Verifica se as ocorrencias de pontos é maior que as anteriores, se sim, armazena a quantidade e as imagens para gerar fundo
    print("Len matriz_pixels_fogo: ", len(matriz_pixels_fogo), " int control: ", int(control))
    date_ini = datetime.datetime(date.year, date.month, date.day, int(13), int(00))
    date_end = datetime.datetime(date.year, date.month, date.day, int(18), int(1))
    if len(matriz_pixels_fogo) > int(control) and date_ini <= date <= date_end:
        copyfile(ch01, f'{dir_in}fdcf/ch01.nc')
        copyfile(ch02, f'{dir_in}fdcf/ch02.nc')
        copyfile(ch03, f'{dir_in}fdcf/ch03.nc')
        with open(f'{dir_temp}band21_control.txt', 'w') as fo:
            fo.write(str(len(matriz_pixels_fogo)))

    print("fdcf_diario: ", fdcf_diario)
    if fdcf_diario:
        # Reiniciar contagem para verificar imagem com maior quantidade de pontos no dia
        with open(f'{dir_temp}band21_control.txt', 'w') as fo:
            fo.write(str(0))

        # Lendo imagem CMI reprojetada
        reproject_ch01 = Dataset(f'{dir_in}fdcf/ch01.nc')
        reproject_ch02 = Dataset(f'{dir_in}fdcf/ch02.nc')
        reproject_ch03 = Dataset(f'{dir_in}fdcf/ch03.nc')
        data_ch01 = reproject_ch01.variables['Band1'][:]
        data_ch02 = reproject_ch02.variables['Band1'][:]
        data_ch03 = reproject_ch03.variables['Band1'][:]
        reproject_ch01 = None
        del reproject_ch01
        reproject_ch02 = None
        del reproject_ch02
        reproject_ch03 = None
        del reproject_ch03
        # RGB Components
        R = data_ch02
        G = 0.45 * data_ch02 + 0.1 * data_ch03 + 0.45 * data_ch01
        B = data_ch01
        # Minimuns, Maximuns and Gamma
        Rmin = 0.0
        Rmax = 1.0
        Gmin = 0.0
        Gmax = 1.0
        Bmin = 0.0
        Bmax = 1.0
        R[R > Rmax] = Rmax
        R[R < Rmin] = Rmin
        G[G > Gmax] = Gmax
        G[G < Gmin] = Gmin
        B[B > Bmax] = Bmax
        B[B < Bmin] = Bmin
        gamma_R = 1
        gamma_G = 1
        gamma_B = 1
        # Normalize the data
        R = ((R - Rmin) / (Rmax - Rmin)) ** (1 / gamma_R)
        G = ((G - Gmin) / (Gmax - Gmin)) ** (1 / gamma_G)
        B = ((B - Bmin) / (Bmax - Bmin)) ** (1 / gamma_B)
        # Create the RGB
        RGB = np.stack([R, G, B], axis=2)
        # Eliminate values outside the globe
        mask = (RGB == [R[0, 0], G[0, 0], B[0, 0]]).all(axis=2)
        RGB[mask] = np.nan

        # Definindo tamanho da imagem de saida.
        d_p_i = 150
        fig = plt.figure(figsize=(2000 / float(d_p_i), 2000 / float(d_p_i)), frameon=True, dpi=d_p_i, edgecolor='black', facecolor='black')
        img_extent = [extent[0], extent[2], extent[1], extent[3]]
        ax = plt.axes(projection=ccrs.PlateCarree(), extent=img_extent)
        ax.set_extent([extent[0], extent[2], extent[1], extent[3]], ccrs.PlateCarree())

        # Estados, coastline e shape Brasil.
        estados = shpreader.Reader(dir_shapefiles + 'brasil/BR_UF_2020').geometries()
        ax.add_geometries(estados, ccrs.PlateCarree(), edgecolor='orange', facecolor='none', linewidth=0.65, zorder=4)
        ax.coastlines(resolution='10m', color='orange', linewidth=0.4, zorder=4)
        ax.add_feature(cartopy.feature.BORDERS, edgecolor='orange', linewidth=0.4, zorder=4)
        gl = ax.gridlines(color='white', linestyle='--', linewidth=0.25, alpha=0.4, xlocs=np.arange(-180, 180, 5), ylocs=np.arange(-90, 90, 5), zorder=5)

        # Adicionando descricao da imagem.
        cruz = '+'
        description = f"GOES-16 Natural True Color,     Fire Hot Spot em {date_img}"  # Esse espaço é necessário para adicionar o caractere na imagem
        institution = f'CEPAGRI - UNICAMP'

        # Plotando a imagem RGB
        ax.imshow(RGB, origin='upper', extent=img_extent)

        # Criando novos eixos conforme a posicao da imagem.
        cax0 = fig.add_axes([ax.get_position().x0 + 0.02, ax.get_position().y0 - 0.0135, ax.get_position().width - 0.02, 0.0090])
        cax0.patch.set_color('black')  # Alterando a cor do novo eixo
        cax0.text(-0.02, 0.13, description, color='white', size=10)  # Adicionando descrição
        cax0.text(0.178, 0.13, cruz, color='red', size=12)  # Adicionando simbolo "+"
        cax0.text(0.85, 0.13, institution, color='yellow', size=10)  # Adicionando Instituicao
        cax0.xaxis.set_visible(False)  # Removendo

        # Adicionando os logos.
        logo_noaa = plt.imread(dir_logos + 'NOAA_Logo.png')  # Lendo o arquivo do logo
        logo_goes = plt.imread(dir_logos + 'GOES_Logo.png')  # Lendo o arquivo do logo
        logo_cepagri = plt.imread(dir_logos + 'CEPAGRI-Logo.png')  # Lendo o arquivo do logo
        fig.figimage(logo_noaa, 26, 203, zorder=3, alpha=0.6, origin='upper')  # Plotando logo
        fig.figimage(logo_goes, 10, 120, zorder=3, alpha=0.6, origin='upper')  # Plotando logo
        fig.figimage(logo_cepagri, 10, 40, zorder=3, alpha=0.8, origin='upper')  # Plotando logo

        # Cria uma lista com os itens no diretorio temp que sao arquivos e se encaixa na expressao regular "^fdcf_.+_.+_br.txt$"
        fdcf_list = [name for name in os.listdir(f'{dir_out}fdcf') if os.path.isfile(os.path.join(f'{dir_out}fdcf', name)) and re.match(f'^fdcf_{date.strftime("%Y%m%d")}_.+_br.txt$', name)]

        # Cria matriz diária de pontos e log. de erros e faz o ‘loop’ nos arquivos do diretório.
        matriz_diaria = []

        ## Captura a lista com os "contornos" dos estados para separar o total de pontos individual
        geometry_estados = list(shpreader.Reader(dir_shapefiles + "divisao_estados/gadm40_BRA_1.shp").geometries())

        ## Os 26 estados estão em ordem alfabética no arquivo shapefile e o indice 27 armazena o total diário
        lista_totalpixels_uf = [0 for i in range(28)]
        log_erro = []
        for name in fdcf_list:
            try:
                with open(f'{dir_out}fdcf/{name}', 'r') as file:
                    for linha in file.readlines():
                        linha = linha.split(',')
                        p = [float(linha[0]), float(linha[1])]  # Ponto em lat,lon
                        ## Checkagem para evitar contagem de pontos duplicados
                        if not (p in matriz_diaria):   
                            ax.plot(float(linha[1]), float(linha[0]), 'r+', ms=2.5, transform=ccrs.PlateCarree())  # plotando em lon,lat
                            matriz_diaria.append(p)
                            ## Contagem do total por estado
                            for j in range(27):
                                estado = geometry_estados[j]
                                if estado.covers(Point(float(linha[1]),float(linha[0]))):
                                    lista_totalpixels_uf[j]+=1
                                    break
                        else:
                            continue
            except Exception as erro:
                print(f'Erro no processamento da matriz diária: {erro}')
                log_erro.append(f'{name} - Error: {erro}')
                pass

        # Calcula a soma do total de focos incendios diário
        lista_totalpixels_uf[27]+= np.sum(lista_totalpixels_uf)

        ### Manipulação dos dados para tabela
        lista_siglas_UF = ['AC','AL','AP','AM','BA','CE','DF','ES','GO','MA','MT','MS','MG','PA','PB','PR','PE','PI','RJ','RN',
                   'RS','RO','RR','SC','SP','SE','TO','Total']
        columns = ('UF', 'Hot Spot')
        data = []
        for i in range(28):
            table_value = (lista_siglas_UF[i],lista_totalpixels_uf[i])
            data.append(table_value)
        
        ## Cria a tabela com os dados separados anteriormente
        tabela= matplotlib.table.table(ax =ax,cellText=data,colLabels=columns,cellLoc ='center',loc='lower right',rowLoc='center',
                               colLoc='center')
        tabela.auto_set_column_width(col=list(range(len(data))))

        # Cria os nomes dos arquivos diários e salva no "directory".

        print("save_txt: matriz_diaria")
        save_txt(matriz_diaria, f'fdcf_{date.strftime("%Y%m%d")}_br')
        save_log_erro(log_erro, f'fdcf_{date.strftime("%Y%m%d")}_errors')

        plt.savefig(f'{dir_out}fdcf/fdcf_{date_file}_br.png', bbox_inches='tight', pad_inches=0, dpi=d_p_i)
        # Fecha a janela para limpar a memoria
        plt.close()

        # Remove arquivos separados do dia
        print('Removendo os arquivos fdcf do dia do diretório')
        for name in fdcf_list:
            os.remove(f'{dir_out}fdcf/{name}')

    # Realiza o log do calculo do tempo de processamento da imagem
    logging.info(f'{fdcf} - {v_extent} - {str(round(time.time() - processing_start_time, 4))} segundos')

def read_process_file(banda):
    # Le o arquivo de processamento e retorna a lista
    with open(f'{dir_temp}{banda}_process.txt', 'r') as fo:
        return fo.readlines()

def processing(p_bands, p_br, p_sp, dir_in, dir_temp):

    # Cria lista vazia para controle do processamento paralelo
    process_br = []
    # Cria lista vazia para controle processamento paralelo
    process_sp = []
    # Variavel de processamento diario do NDVI
    ndvi_diario = False
    # Perguntar ao joão
    ultima_diario = []

# ============================================# bands 1-16 BR ============================================== #

    # Processando arquivos das bandas do ABI
    # Se a variavel de controle de processamento do brasil for True, realiza o processamento
    if p_br:
        logging.info("")
        logging.info('PROCESSANDO IMAGENS "BR"...')
        # Contador para processamento nas 16 bandas
        for x in range(1, 17):
            # Transforma o inteiro contador em string e com 2 digitos
            b = str(x).zfill(2)
            # Se o dicionario de controle das bandas apontar True para essa banda, realiza o processamento
            if p_bands[b]:
                # Le o arquivo de processamento da banda
                img = read_process_file(f'band{b}')
                # Para cada imagem no arquivo, cria um processo chamando a funcao de processamento
                for i in img:
                    # Remove possiveis espacos vazios no inicio ou final da string
                    i = i.strip()
                    # Tenta realizar o processamento da imagem
                    try:
                        # Cria o processo com a funcao de processamento
                        process = Process(target=process_band_cmi, args=(f'{dir_in}band{b}/{i}', b, "br"))
                        # Adiciona o processo na lista de controle do processamento paralelo
                        process_br.append(process)
                        # Inicia o processo
                        process.start()
                    # Caso seja retornado algum erro do processamento, realiza o log e remove a imagem com erro de processamento
                    except OSError as ose:
                        # Realiza o log do erro
                        logging.info(f'Erro Arquivo - OSError - {i}')
                        logging.info(str(ose))
                        # Remove a imagem com erro de processamento
                        os.remove(f'{dir_in}band{b}/{i}')
                    except AttributeError as ae:
                        # Realiza o log do erro
                        logging.info(f'Erro Arquivo - AttributeError - {i}')
                        logging.info(str(ae))
                        # Remove a imagem com erro de processamento
                        os.remove(f'{dir_in}band{b}/{i}')
            # Se o dicionario de controle das bandas apontar False para essa banda, nao realiza o processamento e continua a tentativa nas outras bandas
            else:
                continue
        # Looping de controle que pausa o processamento principal ate que todos os processos da lista de controle do processamento paralelo sejam finalizados
        for process in process_br:
            # Bloqueia a execução do processo principal ate que o processo cujo metodo de join() é chamado termine
            process.join()
        # Limpa lista vazia para controle do processamento paralelo
        process_br = []

# ============================================# bands 1-16 BR ============================================== #


# ============================================# bands 1-16 SP ============================================== #

    # Se a variavel de controle de processamento do estado de sao paulo for True, realiza o processamento
    if p_sp:
        logging.info("")
        logging.info('PROCESSANDO IMAGENS "SP"...')
        # Contador para processamento nas 16 bandas
        for x in range(1, 17):
            # Transforma o inteiro contador em string e com 2 digitos
            b = str(x).zfill(2)
            # Se o dicionario de controle das bandas apontar True para essa banda, realiza o processamento
            if p_bands[b]:
                # Le o arquivo de processamento da banda
                img = read_process_file(f'band{b}')
                # Para cada imagem no arquivo, cria um processo chamando a funcao de processamento
                for i in img:
                    # Remove possiveis espacos vazios no inicio ou final da string
                    i = i.strip()
                    # Tenta realizar o processamento da imagem
                    try:
                        # Cria o processo com a funcao de processamento
                        process = Process(target=process_band_cmi, args=(f'{dir_in}band{b}/{i}', b, "sp"))
                        # Adiciona o processo na lista de controle do processamento paralelo
                        process_sp.append(process)
                        # Inicia o processo
                        process.start()
                    # Caso seja retornado algum erro do processamento, realiza o log e remove a imagem com erro de processamento
                    except OSError as ose:
                        # Realiza o log do erro
                        logging.info("Erro Arquivo - OSError")
                        logging.info(str(ose))
                        # Remove a imagem com erro de processamento
                        os.remove(f'{dir_in}band{b}/{i}')
                    except AttributeError as ae:
                        # Realiza o log do erro
                        logging.info(f'Erro Arquivo - AttributeError - {i}')
                        logging.info(str(ae))
                        # Remove a imagem com erro de processamento
                        os.remove(f'{dir_in}band{b}/{i}')
            # Se o dicionario de controle das bandas apontar False para essa banda, nao realiza o processamento e continua a tentativa nas outras bandas
            else:
                continue
        # Looping de controle que pausa o processamento principal ate que todos os processos da lista de controle do processamento paralelo sejam finalizados
        for process in process_sp:
            # Bloqueia a execução do processo principal ate que o processo cujo metodo de join() é chamado termine
            process.join()
        # Limpa lista vazia para controle do processamento paralelo
        process_sp = []

# ============================================# bands 1-16 BR ============================================== #


# ============================================# TrueColor BR ============================================== #

    # Checagem se e possivel gerar imagem TrueColor
    if p_bands["17"]:
        # Se a variavel de controle de processamento do brasil for True, realiza o processamento
        if p_br:
            logging.info("")
            logging.info('PROCESSANDO IMAGENS TRUECOLOR "BR"...')
            band17 = read_process_file('band17')
            # Para cada imagem no arquivo, cria um processo chamando a funcao de processamento
            for i in band17:
                # Remove possiveis espacos vazios no inicio ou final da string e separa cada termo como um elemento
                i = i.strip().split(';')
                # Montando dicionario de argumentos
                kwargs = {'ch01': f'{dir_in}band01/{i[0].replace(".nc", "_reproj_br.nc")}', 'ch02': f'{dir_in}band02/{i[1].replace(".nc", "_reproj_br.nc")}',
                          'ch03': f'{dir_in}band03/{i[2].replace(".nc", "_reproj_br.nc")}'}
                # Tenta realizar o processamento da imagem
                try:
                    # Cria o processo com a funcao de processamento
                    process = Process(target=process_band_rgb, args=("truecolor", "br"), kwargs=kwargs)
                    # Adiciona o processo na lista de controle do processamento paralelo
                    process_br.append(process)
                    # Inicia o processo
                    process.start()
                # Caso seja retornado algum erro do processamento, realiza o log e remove a imagem com erro de processamento
                except OSError as ose:
                    # Realiza o log do erro
                    logging.info("Erro Arquivo - OSError")
                    logging.info(str(ose))
                    # Remove a imagem com erro de processamento
                    os.remove(f'{dir_in}band01/{i[0].replace(".nc", "_reproj_br.nc")}')
                    os.remove(f'{dir_in}band02/{i[1].replace(".nc", "_reproj_br.nc")}')
                    os.remove(f'{dir_in}band03/{i[2].replace(".nc", "_reproj_br.nc")}')
                except AttributeError as ae:
                    # Realiza o log do erro
                    logging.info(f'Erro Arquivo - AttributeError - {i}')
                    logging.info(str(ae))
                    # Remove a imagem com erro de processamento
                    os.remove(f'{dir_in}band01/{i[0].replace(".nc", "_reproj_br.nc")}')
                    os.remove(f'{dir_in}band02/{i[1].replace(".nc", "_reproj_br.nc")}')
                    os.remove(f'{dir_in}band03/{i[2].replace(".nc", "_reproj_br.nc")}')
            # Looping de controle que pausa o processamento principal ate que todos os processos da lista de controle do processamento paralelo sejam finalizados
            for process in process_br:
                # Bloqueia a execução do processo principal ate que o processo cujo metodo de join() é chamado termine
                process.join()
            # Limpa lista vazia para controle do processamento paralelo
            process_br = []
# ============================================# TrueColor BR ============================================== #


# ============================================# TrueColor SP ============================================== #
        # Se a variavel de controle de processamento do estado de sao paulo for True, realiza o processamento
        if p_sp:
            logging.info("")
            logging.info('PROCESSANDO IMAGENS TRUECOLOR "SP"...')
            band17 = read_process_file('band17')
            # Para cada imagem no arquivo, cria um processo chamando a funcao de processamento
            for i in band17:
                # Remove possiveis espacos vazios no inicio ou final da string e separa cada termo como um elemento
                i = i.strip().split(';')
                # Montando dicionario de argumentos
                kwargs = {'ch01': f'{dir_in}band01/{i[0].replace(".nc", "_reproj_sp.nc")}', 'ch02': f'{dir_in}band02/{i[1].replace(".nc", "_reproj_sp.nc")}',
                          'ch03': f'{dir_in}band03/{i[2].replace(".nc", "_reproj_sp.nc")}'}
                # Tenta realizar o processamento da imagem
                try:
                    # Cria o processo com a funcao de processamento
                    process = Process(target=process_band_rgb, args=("truecolor", "sp"), kwargs=kwargs)
                    # Adiciona o processo na lista de controle do processamento paralelo
                    process_sp.append(process)
                    # Inicia o processo
                    process.start()
                # Caso seja retornado algum erro do processamento, realiza o log e remove a imagem com erro de processamento
                except OSError as ose:
                    # Realiza o log do erro
                    logging.info("Erro Arquivo - OSError")
                    logging.info(str(ose))
                    # Remove a imagem com erro de processamento
                    os.remove(f'{dir_in}band01/{i[0].replace(".nc", "_reproj_sp.nc")}')
                    os.remove(f'{dir_in}band02/{i[1].replace(".nc", "_reproj_sp.nc")}')
                    os.remove(f'{dir_in}band03/{i[2].replace(".nc", "_reproj_sp.nc")}')
                except AttributeError as ae:
                    # Realiza o log do erro
                    logging.info(f'Erro Arquivo - AttributeError - {i}')
                    logging.info(str(ae))
                    # Remove a imagem com erro de processamento
                    os.remove(f'{dir_in}band01/{i[0].replace(".nc", "_reproj_sp.nc")}')
                    os.remove(f'{dir_in}band02/{i[1].replace(".nc", "_reproj_sp.nc")}')
                    os.remove(f'{dir_in}band03/{i[2].replace(".nc", "_reproj_sp.nc")}')
            # Looping de controle que pausa o processamento principal ate que todos os processos da lista de controle do processamento paralelo sejam finalizados
            for process in process_sp:
                # Bloqueia a execução do processo principal ate que o processo cujo metodo de join() é chamado termine
                process.join()
            # Limpa lista vazia para controle do processamento paralelo
            process_sp = []
# ============================================# TrueColor SP ============================================== #


# ============================================# RRQPEF BR ============================================== #
    # Checagem se e possivel gerar imagem RRQPEF
    if p_bands["18"]:
        # Se a variavel de controle de processamento do brasil for True, realiza o processamento
        if p_br:
            logging.info("")
            logging.info('PROCESSANDO IMAGENS RRQPEF "BR"...')
            band18 = read_process_file('band18')
            # Para cada imagem no arquivo, cria um processo chamando a funcao de processamento
            for i in band18:
                # Remove possiveis espacos vazios no inicio ou final da string e separa cada termo como um elemento
                i = i.strip().split(';')
                # Tenta realizar o processamento da imagem
                try:
                    # Cria o processo com a funcao de processamento
                    process = Process(target=process_rrqpef, args=(f'{dir_in}rrqpef/{i[0]}', f'{dir_in}band13/{i[1].replace(".nc", "_reproj_br.nc")}', "br"))
                    # Adiciona o processo na lista de controle do processamento paralelo
                    process_br.append(process)
                    # Inicia o processo
                    process.start()
                # Caso seja retornado algum erro do processamento, realiza o log e remove a imagem com erro de processamento
                except OSError as ose:
                    # Realiza o log do erro
                    logging.info("Erro Arquivo - OSError")
                    logging.info(str(ose))
                    # Remove a imagem com erro de processamento
                    os.remove(f'{dir_in}rrqpef/{i[0]}')
                    os.remove(f'{dir_in}band13/{i[1].replace(".nc", "_reproj_br.nc")}')
                except AttributeError as ae:
                    # Realiza o log do erro
                    logging.info(f'Erro Arquivo - AttributeError - {i}')
                    logging.info(str(ae))
                    # Remove a imagem com erro de processamento
                    os.remove(f'{dir_in}rrqpef/{i[0]}')
                    os.remove(f'{dir_in}band13/{i[1].replace(".nc", "_reproj_br.nc")}')
            # Looping de controle que pausa o processamento principal ate que todos os processos da lista de controle do processamento paralelo sejam finalizados
            for process in process_br:
                # Bloqueia a execução do processo principal ate que o processo cujo metodo de join() é chamado termine
                process.join()
            # Limpa lista vazia para controle do processamento paralelo
            process_br = []

# ============================================# RRQPEF BR ============================================== #


# ============================================# RRQPEF SP ============================================== #
        # Se a variavel de controle de processamento do estado de sao paulo for True, realiza o processamento
        if p_sp:
            logging.info("")
            logging.info('PROCESSANDO IMAGENS RRQPEF "SP"...')
            band18 = read_process_file('band18')
            # Para cada imagem no arquivo, cria um processo chamando a funcao de processamento
            for i in band18:
                # Remove possiveis espacos vazios no inicio ou final da string e separa cada termo como um elemento
                i = i.strip().split(';')
                # Tenta realizar o processamento da imagem
                try:
                    # Cria o processo com a funcao de processamento
                    process = Process(target=process_rrqpef, args=(f'{dir_in}rrqpef/{i[0]}', f'{dir_in}band13/{i[1].replace(".nc", "_reproj_sp.nc")}', "sp"))
                    # Adiciona o processo na lista de controle do processamento paralelo
                    process_sp.append(process)
                    # Inicia o processo
                    process.start()
                # Caso seja retornado algum erro do processamento, realiza o log e remove a imagem com erro de processamento
                except OSError as ose:
                    # Realiza o log do erro
                    logging.info("Erro Arquivo - OSError")
                    logging.info(str(ose))
                    # Remove a imagem com erro de processamento
                    os.remove(f'{dir_in}rrqpef/{i[0]}')
                    os.remove(f'{dir_in}band13/{i[1].replace(".nc", "_reproj_sp.nc")}')
                except AttributeError as ae:
                    # Realiza o log do erro
                    logging.info(f'Erro Arquivo - AttributeError - {i}')
                    logging.info(str(ae))
                    # Remove a imagem com erro de processamento
                    os.remove(f'{dir_in}rrqpef/{i[0]}')
                    os.remove(f'{dir_in}band13/{i[1].replace(".nc", "_reproj_sp.nc")}')
            # Looping de controle que pausa o processamento principal ate que todos os processos da lista de controle do processamento paralelo sejam finalizados
            for process in process_sp:
                # Bloqueia a execução do processo principal ate que o processo cujo metodo de join() é chamado termine
                process.join()
            # Limpa lista vazia para controle do processamento paralelo
            process_sp = []

# ============================================# RRQPEF SP ============================================== #


# ============================================# GLM BR ============================================== #

    # Checagem se e possivel gerar imagem GLM
    if p_bands["19"]:
        # Se a variavel de controle de processamento do brasil for True, realiza o processamento
        if p_br:
            logging.info("")
            logging.info('PROCESSANDO IMAGENS GLM "BR"...')
            band19 = read_process_file('band19')
            # Para cada imagem no arquivo, cria um processo chamando a funcao de processamento
            for i in band19:
                # Remove possiveis espacos vazios no inicio ou final da string e separa cada termo como um elemento
                i = i.strip().split(';')
                # Coletando lista de GLM no indice 1
                j = i[1].replace("'", "").strip('][').split(', ')
                # Tenta realizar o processamento da imagem
                try:
                    # Cria o processo com a funcao de processamento
                    process = Process(target=process_glm, args=(f'{dir_in}band13/{i[0].replace(".nc", "_reproj_br.nc")}', j, "br"))
                    # Adiciona o processo na lista de controle do processamento paralelo
                    process_br.append(process)
                    # Inicia o processo
                    process.start()
                # Caso seja retornado algum erro do processamento, realiza o log e remove a imagem com erro de processamento
                except OSError as ose:
                    # Realiza o log do erro
                    logging.info("Erro Arquivo - OSError")
                    logging.info(str(ose))
                    # Remove a imagem com erro de processamento
                    os.remove(f'{dir_in}band13/{i[0].replace(".nc", "_reproj_br.nc")}')
                    for f in j:
                        os.remove(f'{dir_in}glm/{f}')
                except AttributeError as ae:
                    # Realiza o log do erro
                    logging.info(f'Erro Arquivo - AttributeError - {i}')
                    logging.info(str(ae))
                    # Remove a imagem com erro de processamento
                    os.remove(f'{dir_in}band13/{i[0].replace(".nc", "_reproj_br.nc")}')
                    for f in j:
                        os.remove(f'{dir_in}glm/{f}')
            # Looping de controle que pausa o processamento principal ate que todos os processos da lista de controle do processamento paralelo sejam finalizados
            for process in process_br:
                # Bloqueia a execução do processo principal ate que o processo cujo metodo de join() é chamado termine
                process.join()
            # Limpa lista vazia para controle do processamento paralelo
            process_br = []

# ============================================# GLM BR ============================================== #


# ============================================# NDVI BR ============================================== #

    # Checagem se e possivel gerar imagem NDVI
    if p_bands["20"]:
        # Se a variavel de controle de processamento do brasil for True, realiza o processamento
        if p_br:
            logging.info("")
            logging.info('PROCESSANDO IMAGENS NDVI "BR"...')
            band20 = read_process_file('band20')
            # Para cada imagem no arquivo, cria um processo chamando a funcao de processamento
            for i in band20:
                # Remove possiveis espacos vazios no inicio ou final da string e separa cada termo como um elemento
                i = i.strip().split(';')
                # Captura a data do arquivo
                date_file = (datetime.datetime.strptime(i[0][i[0].find("M6C02_G16_s") + 11:i[0].find("_e") - 1], '%Y%j%H%M%S'))
                # Captura a data atual
                date_now = datetime.datetime.now()
                # Aponta o horario 18h para a data atual
                date = datetime.datetime(date_now.year, date_now.month, date_now.day, int(18), int(00))
                # Se a data do arquivo for maior ou igual as 18h da data atual e o dia da semana atual for sabado (6)
                if date_file >= date:
                    # Adiciona true para a variavel de processamento semanal
                    ndvi_diario = True
                    # Guarda a ultima imagem semanal
                    ultima_diario = i
                    # Pula o processamento dessa ultima imagem
                    continue
                # Tenta realizar o processamento da imagem
                try:
                    # Cria o processo com a funcao de processamento
                    process = Process(target=process_ndvi,
                                      args=(ndvi_diario, f'{dir_in}band02/{i[0].replace(".nc", "_reproj_br.nc")}', f'{dir_in}band03/{i[1].replace(".nc", "_reproj_br.nc")}', "br"))
                    # Adiciona o processo na lista de controle do processamento paralelo
                    process_br.append(process)
                    # Inicia o processo
                    process.start()
                # Caso seja retornado algum erro do processamento, realiza o log e remove a imagem com erro de processamento
                except OSError as ose:
                    # Realiza o log do erro
                    logging.info("Erro Arquivo - OSError")
                    logging.info(str(ose))
                    # Remove a imagem com erro de processamento
                    os.remove(f'{dir_in}band02/{i[0].replace(".nc", "_reproj_br.nc")}')
                    os.remove(f'{dir_in}band03/{i[1].replace(".nc", "_reproj_br.nc")}')
                except AttributeError as ae:
                    # Realiza o log do erro
                    logging.info(f'Erro Arquivo - AttributeError - {i}')
                    logging.info(str(ae))
                    # Remove a imagem com erro de processamento
                    os.remove(f'{dir_in}band02/{i[0].replace(".nc", "_reproj_br.nc")}')
                    os.remove(f'{dir_in}band03/{i[1].replace(".nc", "_reproj_br.nc")}')
            # Looping de controle que pausa o processamento principal ate que todos os processos da lista de controle do processamento paralelo sejam finalizados
            for process in process_br:
                # Bloqueia a execução do processo principal ate que o processo cujo metodo de join() é chamado termine
                process.join()

            if ndvi_diario:
                # Tenta realizar o processamento da ultima imagem
                try:
                    # Cria o processo com a funcao de processamento
                    process_ndvi(ndvi_diario, f'{dir_in}band02/{ultima_diario[0].replace(".nc", "_reproj_br.nc")}', f'{dir_in}band03/{ultima_diario[1].replace(".nc", "_reproj_br.nc")}', "br")
                # Caso seja retornado algum erro do processamento, realiza o log e remove a imagem com erro de processamento
                except OSError as ose:
                    # Realiza o log do erro
                    logging.info("Erro Arquivo - OSError")
                    logging.info(str(ose))
                    # Remove a imagem com erro de processamento
                    os.remove(f'{dir_in}band02/{ultima_diario[0].replace(".nc", "_reproj_br.nc")}')
                    os.remove(f'{dir_in}band03/{ultima_diario[1].replace(".nc", "_reproj_br.nc")}')
                except AttributeError as ae:
                    # Realiza o log do erro
                    logging.info(f'Erro Arquivo - AttributeError - {ultima_diario}')
                    logging.info(str(ae))
                    # Remove a imagem com erro de processamento
                    os.remove(f'{dir_in}band02/{ultima_diario[0].replace(".nc", "_reproj_br.nc")}')
                    os.remove(f'{dir_in}band03/{ultima_diario[1].replace(".nc", "_reproj_br.nc")}')

            # Limpa lista vazia para controle do processamento paralelo
            process_br = []

        # Verifica se deve ser gerado a imagem ndvi, se sim, a banda continua True, caso nao, a banda volta para False
        if ndvi_diario and datetime.datetime.now().isoweekday() == 6:
            p_bands["20"] = True
        else:
            p_bands["20"] = False
            # Remove o arquivo de processamento ndvi
            os.remove(f'{dir_temp}band20_process.txt')

    # Checagem se e possivel gerar imagem FDCF
    if p_bands["21"]:
        fdcf_diario = False
        # Se a variavel de controle de processamento do brasil for True, realiza o processamento
        if p_br:
            logging.info("")
            logging.info('PROCESSANDO IMAGENS FDCF "BR"...')
            band21 = read_process_file('band21')
            # Para cada imagem no arquivo, cria um processo chamando a funcao de processamento
            for i in band21:
                # Remove possiveis espacos vazios no inicio ou final da string e separa cada termo como um elemento
                i = i.strip().split(';')
                # Captura a data do arquivo
                date_file = (datetime.datetime.strptime(i[0][i[0].find("ABI-L2-FDCF-M6_G16_s") + 20:i[0].find("_e") - 1], '%Y%j%H%M%S'))
                # Captura a data atual
                # date_now = datetime.datetime.now() - datetime.timedelta(days=1)
                date_now = datetime.datetime.now()
                # Aponta o horario 23h50 para o dia anterior
                date = datetime.datetime(date_now.year, date_now.month, date_now.day, int(23), int(50))
                # Se a data do arquivo for maior ou igual as 23h50 da do dia anterior
                print("date_file: ", type(date_file), date_file)
                print("date: ", type(date), date)
                print("date_file: ", date_file.year, date_file.month, date_file.day, "date: ", date.year, date.month, date.day)
                #Checagem para ver se é 23:50 para processamento do acumulado diário
                if date_file.year == date.year and date_file.month == date.month and date_file.day == date.day and date_file >= date:
                    # Adiciona true para a variavel de processamento semanal
                    fdcf_diario = True
                    print("fdcf_diario: ", fdcf_diario)
                else:
                    # Adiciona false para a variavel de processamento semanal
                    fdcf_diario = False
                print("fdcf_diario: ", fdcf_diario)
                # Tenta realizar o processamento da imagem
                try:
                    # Cria o processo com a funcao de processamento
                    process = Process(target=process_fdcf, args=(f'{i[0]}', f'{i[1]}', f'{i[2]}', f'{i[3]}', "br", fdcf_diario))
                    # Adiciona o processo na lista de controle do processamento paralelo
                    process_br.append(process)
                    # Inicia o processo
                    process.start()
                # Caso seja retornado algum erro do processamento, realiza o log e remove a imagem com erro de processamento
                except OSError as ose:
                    # Realiza o log do erro
                    logging.info("Erro Arquivo - OSError")
                    logging.info(str(ose))
                    # Remove a imagem com erro de processamento
                    os.remove(f'{i[0]}')
                    os.remove(f'{i[1]}')
                    os.remove(f'{i[2]}')
                    os.remove(f'{i[3]}')
                except AttributeError as ae:
                    # Realiza o log do erro
                    logging.info(f'Erro Arquivo - AttributeError - {i}')
                    logging.info(str(ae))
                    # Remove a imagem com erro de processamento
                    os.remove(f'{i[0]}')
                    os.remove(f'{i[1]}')
                    os.remove(f'{i[2]}')
                    os.remove(f'{i[3]}')
            # Looping de controle que pausa o processamento principal ate que todos os processos da lista de controle do processamento paralelo sejam finalizados
            for process in process_br:
                # Bloqueia a execução do processo principal ate que o processo cujo metodo de join() é chamado termine
                process.join()
            # Limpa lista vazia para controle do processamento paralelo
            process_br = []

    # Realiza log do encerramento do processamento
    logging.info("")
    logging.info("PROCESSAMENTO ENCERRADO")


# ============================================# NDVI BR ============================================== #


    # Retorna o dicionario de controle das bandas
    return p_bands