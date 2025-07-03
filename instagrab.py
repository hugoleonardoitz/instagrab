#!/usr/bin/env python
# instagrab.py
"""
Baixa legenda e mídias (imagens e vídeos) de posts públicos do Instagram,
incluindo carrosséis. Suporta download único ou em lote via arquivo de links.
Salva em SQLite (instagrab.db) registrando posts e hashtags.

Como usar:
  Download único:
    python instagrab.py URL_DO_POST [--output-dir DIRETORIO] [--delay SEGUNDOS] [--debug]
  Download em lote:
    python instagrab.py --input-file links.txt [--output-dir DIRETORIO] [--delay SEGUNDOS] [--debug]

Requisitos:
  - Python 3.7+
  - instaloader, requests
"""

import argparse
import logging
import os
import re
import sys
import time
from urllib.parse import urlparse

import requests
import instaloader
from db import DB

# Regex para extrair hashtags (sem #)
HASHTAG_REGEX = re.compile(r"#(\w+)")

def setup_logging(debug: bool, log_file: str = "instagrab.log"):
    """
    Configura o sistema de logs.
    - Sempre grava DEBUG e acima em arquivo (encoding utf-8).
    - Se debug=True, também exibe DEBUG no console.
    """
    logger = logging.getLogger()
    logger.setLevel(logging.DEBUG if debug else logging.INFO)
    fmt = "%(asctime)s - %(levelname)s - %(message)s"

    fh = logging.FileHandler(log_file, encoding="utf-8")
    fh.setLevel(logging.DEBUG)
    fh.setFormatter(logging.Formatter(fmt))
    logger.addHandler(fh)

    if debug:
        ch = logging.StreamHandler(sys.stdout)
        ch.setLevel(logging.DEBUG)
        ch.setFormatter(logging.Formatter(fmt))
        logger.addHandler(ch)


def parse_args():
    """
    Analisa argumentos da linha de comando.
    Retorna objeto com atributos url, input_file, output_dir, delay, debug.
    """
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
    """
    Extrai o shortcode do post a partir da URL.
    Lança ValueError se não for válida.
    """
    p = urlparse(url)
    parts = p.path.strip("/").split("/")
    if len(parts) >= 2 and parts[0] in ("p", "tv", "reel"):
        return parts[1]
    raise ValueError(f"URL inválida de post do Instagram: {url}")


def print_summary(username: str, shortcode: str, caption: str, media_urls: list, post_dir: str, delay: float):
    """
    Exibe em tela resumo do download.
    """
    print("Resumo do Download:")
    print(f" Perfil: {username}")
    print(f" Shortcode: {shortcode}")
    print(f" Legenda ({len(caption)} chars): {caption[:60]}{'...' if len(caption)>60 else ''}\n")
    print(f" Total de mídias: {len(media_urls)}")
    for idx, m in enumerate(media_urls, 1):
        t = "Vídeo" if ".mp4" in m else "Imagem"
        print(f"  {idx:02d}. {t}: {m}")
    print(f" Diretório: {post_dir}")
    print(f" Delay: {delay}s\n")


def download_post(url: str, output_dir: str, delay: float, db: DB):
    """
    Processa um único post:
    - Extrai shortcode e username
    - Gera pasta, salva legenda como {shortcode}.txt
    - Faz download de mídias
    - Registra no SQLite: post + hashtags
    """
    logger = logging.getLogger()
    shortcode = extract_shortcode(url)
    logger.debug(f"Processando {url} (shortcode={shortcode})")

    loader = instaloader.Instaloader(
        download_comments=False, save_metadata=False, quiet=True
    )
    post = instaloader.Post.from_shortcode(loader.context, shortcode)
    username = post.owner_username
    caption = post.caption or ""
    # Cria diretórios de saída
    post_dir = os.path.join(output_dir, username, shortcode)
    os.makedirs(post_dir, exist_ok=True)
    # Salva legenda
    cap_file = os.path.join(post_dir, f"{shortcode}.txt")
    try:
        with open(cap_file, 'w', encoding='utf-8') as cf:
            cf.write(caption)
        logger.info(f"Legenda salva: {cap_file}")
    except Exception as e:
        logger.error(f"Falha ao salvar legenda: {e}")
    # Coleta mídias
    urls = []
    try:
        if post.typename == 'GraphSidecar':
            for node in post.get_sidecar_nodes():
                urls.append(node.video_url if node.is_video else node.display_url)
        else:
            urls.append(post.video_url if post.is_video else post.url)
    except Exception as e:
        logger.error(f"Erro ao coletar URLs: {e}")
        urls = []
    print_summary(username, shortcode, caption, urls, post_dir, delay)
    # Download mídias
    downloaded = []
    for i, murl in enumerate(urls, 1):
        ext = '.mp4' if '.mp4' in murl else '.jpg'
        path = os.path.join(post_dir, f"{shortcode}_{i:02d}{ext}")
        try:
            resp = requests.get(murl, stream=True, headers={'User-Agent':'Mozilla/5.0'})
            resp.raise_for_status()
            with open(path, 'wb') as f:
                for chunk in resp.iter_content(8192): f.write(chunk)
            downloaded.append(path)
            logger.info(f"Salvo: {path}")
        except Exception as e:
            logger.error(f"Falha download {murl}: {e}")
        time.sleep(delay)
    # Determina status
    status = 'salvo' if len(downloaded)==len(urls) and urls else 'falha'
    # Insere no DB e obtém post_id
    post_id = db.upsert_post(username, shortcode, url, caption, status)
    # Processa hashtags
    tags = HASHTAG_REGEX.findall(caption)
    for tag in set(tags):
        hid = db.insert_hashtag(tag)
        db.link_post_hashtag(post_id, hid)
    return downloaded


def main():
    args = parse_args()
    setup_logging(args.debug)
    db = DB()
    # Monta lista de URLs
    urls = []
    if args.input_file:
        try:
            with open(args.input_file, 'r', encoding='utf-8') as f:
                for line in f:
                    for u in line.strip().split(','):
                        if u: urls.append(u.strip())
        except Exception as e:
            logging.error(f"Erro leitura {args.input_file}: {e}")
            sys.exit(1)
    if args.url:
        urls.append(args.url)
    # Processa cada URL
    for u in urls:
        try:
            files = download_post(u, args.output_dir, args.delay, db)
            logging.info(f"Concluído {u}: {files}")
        except Exception as e:
            logging.error(f"Erro em {u}: {e}")

if __name__ == '__main__':
    main()
