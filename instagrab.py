#!/usr/bin/env python
# instagrab.py
"""
Baixa legenda e mídias (imagens e vídeos) de posts públicos do Instagram,
incluindo carrosséis. Suporta download único ou em lote via arquivo de links.
Salva em SQLite (instagrab.db) registrando posts e hashtags.
"""

import argparse
import logging
import os
import re
import sys
import time
from typing import List, Optional, Tuple
from urllib.parse import urlparse

import instaloader
import requests
from instaloader import Post

from db import DB

# Regex para extrair hashtags (sem #)
HASHTAG_REGEX = re.compile(r"#(\w+)")
# Obter o logger global
logger = logging.getLogger()


def setup_logging(debug: bool, log_file: str = "instagrab.log") -> None:
    """
    Configura o sistema de logs.
    - Sempre grava DEBUG e acima em arquivo (encoding utf-8).
    - Se debug=True, também exibe DEBUG no console.
    """
    logger.setLevel(logging.DEBUG)
    fmt = "%(asctime)s - %(levelname)s - %(message)s"
    formatter = logging.Formatter(fmt)

    # Handler para arquivo
    fh = logging.FileHandler(log_file, encoding="utf-8")
    fh.setLevel(logging.DEBUG)
    fh.setFormatter(formatter)
    logger.addHandler(fh)

    # Handler para console (se debug)
    if debug:
        ch = logging.StreamHandler(sys.stdout)
        ch.setLevel(logging.DEBUG)
        ch.setFormatter(formatter)
        logger.addHandler(ch)
    else:
        # Se não for debug, limita o log do console a INFO e acima
        ch = logging.StreamHandler(sys.stdout)
        ch.setLevel(logging.INFO)
        ch.setFormatter(formatter)
        logger.addHandler(ch)

def parse_args() -> argparse.Namespace:
    """Analisa argumentos da linha de comando."""
    parser = argparse.ArgumentParser(
        description="Baixa legenda, mídias e registra posts no SQLite (com hashtags)."
    )
    parser.add_argument("url", nargs="?", help="URL pública do post (p/, reel/ ou tv/).")
    parser.add_argument(
        "-i", "--input-file",
        help="Arquivo txt ou csv com lista de URLs do Instagram."
    )
    parser.add_argument(
        "--output-dir",
        default="downloads",
        help="Diretório base onde as mídias serão salvas."
    )
    parser.add_argument(
        "--delay",
        type=float,
        default=1.0,
        help="Delay (em segundos) entre cada requisição de mídia."
    )
    parser.add_argument(
        "--debug",
        action="store_true",
        help="Exibe logs de debug no console além de gravar em arquivo."
    )
    args = parser.parse_args()
    if not args.url and not args.input_file:
        parser.error("Você deve fornecer uma URL ou um arquivo de entrada (--input-file).")
    return args


def extract_shortcode(url: str) -> str:
    """Extrai o shortcode do post a partir da URL."""
    p = urlparse(url)
    parts = p.path.strip("/").split("/")
    if len(parts) >= 2 and parts[0] in ("p", "tv", "reel"):
        return parts[1]
    raise ValueError(f"URL inválida de post do Instagram: {url}")


def get_post_details(shortcode: str) -> Tuple[Post, List[str]]:
    """Busca metadados e URLs de mídia de um post."""
    loader = instaloader.Instaloader(
        download_comments=False, save_metadata=False, quiet=True
    )
    post = instaloader.Post.from_shortcode(loader.context, shortcode)
    
    urls = []
    if post.typename == 'GraphSidecar':  # Carrossel
        for node in post.get_sidecar_nodes():
            urls.append(node.video_url if node.is_video else node.display_url)
    else:  # Imagem ou vídeo único
        urls.append(post.video_url if post.is_video else post.url)
        
    return post, urls


def download_media(media_urls: List[str], post_dir: str, shortcode: str, delay: float) -> List[str]:
    """Baixa os arquivos de mídia (imagens/vídeos) de um post."""
    downloaded_files = []
    for i, murl in enumerate(media_urls, 1):
        ext = '.mp4' if '.mp4' in murl else '.jpg'
        path = os.path.join(post_dir, f"{shortcode}_{i:02d}{ext}")
        try:
            resp = requests.get(murl, stream=True, headers={'User-Agent': 'Mozilla/5.0'})
            resp.raise_for_status()
            with open(path, 'wb') as f:
                for chunk in resp.iter_content(8192):
                    f.write(chunk)
            downloaded_files.append(path)
            logger.info(f"Mídia salva: {path}")
        except requests.RequestException as e:
            logger.error(f"Falha no download de {murl}: {e}")
        time.sleep(delay)
    return downloaded_files


def save_caption_and_update_db(db: DB, post: Post, url: str, status: str) -> None:
    """Salva a legenda em arquivo e atualiza o banco de dados com o post e hashtags."""
    caption = post.caption or ""
    
    # Insere/Atualiza o post no banco de dados e obtém o ID
    post_id = db.upsert_post(
        perfil=post.owner_username,
        shortcode=post.shortcode,
        url_completa=url,
        descricao=caption,
        status=status
    )
    if post_id == -1:
        logger.error(f"Não foi possível obter o post_id para o shortcode {post.shortcode}")
        return

    # Processa e vincula as hashtags
    tags = HASHTAG_REGEX.findall(caption)
    for tag in set(tags):  # Usa set para evitar duplicatas
        hashtag_id = db.insert_hashtag(tag)
        if hashtag_id != -1:
            db.link_post_hashtag(post_id, hashtag_id)
    logger.info(f"Post {post.shortcode} e hashtags salvos no banco de dados.")


def process_post(url: str, output_dir: str, delay: float, db: DB) -> None:
    """
    Orquestra o processo completo de download e registro de um único post.
    """
    try:
        shortcode = extract_shortcode(url)
        logger.debug(f"Processando {url} (shortcode={shortcode})")

        post, media_urls = get_post_details(shortcode)
        username = post.owner_username
        caption = post.caption or ""

        post_dir = os.path.join(output_dir, username, shortcode)
        os.makedirs(post_dir, exist_ok=True)

        # Salva a legenda em arquivo
        cap_file = os.path.join(post_dir, f"{shortcode}.txt")
        with open(cap_file, 'w', encoding='utf-8') as cf:
            cf.write(caption)
        logger.info(f"Legenda salva: {cap_file}")

        # Baixa as mídias
        downloaded_files = download_media(media_urls, post_dir, shortcode, delay)
        
        # Determina o status final do download
        status = 'salvo' if media_urls and len(downloaded_files) == len(media_urls) else 'falha'
        
        # Salva no banco de dados
        save_caption_and_update_db(db, post, url, status)

        logger.info(f"Processamento de {url} concluído. Status: {status}. Mídias salvas: {len(downloaded_files)}")

    except instaloader.exceptions.InstaloaderException as e:
        logger.error(f"Erro do Instaloader ao processar {url}: {e}")
    except Exception as e:
        logger.error(f"Erro inesperado ao processar {url}: {e}", exc_info=True)


def main() -> None:
    """Função principal que executa o script."""
    args = parse_args()
    setup_logging(args.debug)
    db = DB()
    
    urls_to_process = []
    if args.input_file:
        try:
            with open(args.input_file, 'r', encoding='utf-8') as f:
                for line in f:
                    # Suporta URLs separadas por vírgula ou em linhas diferentes
                    cleaned_line = line.strip()
                    if cleaned_line:
                        urls_to_process.extend(u.strip() for u in cleaned_line.split(','))
        except FileNotFoundError:
            logger.error(f"Arquivo de entrada não encontrado: {args.input_file}")
            sys.exit(1)
        except Exception as e:
            logger.error(f"Erro ao ler o arquivo {args.input_file}: {e}")
            sys.exit(1)
            
    if args.url:
        urls_to_process.append(args.url)
    
    # Processa cada URL da lista
    if not urls_to_process:
        logger.warning("Nenhuma URL para processar.")
        return

    logger.info(f"Iniciando processamento de {len(urls_to_process)} URL(s).")
    for u in urls_to_process:
        if u: # Garante que a URL não está vazia
            process_post(u, args.output_dir, args.delay, db)
    
    db.close()
    logger.info("Processamento finalizado.")


if __name__ == '__main__':
    main()
