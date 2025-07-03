# extract_saved.py
"""
Extrai URLs dos posts salvos do seu Instagram e grava em arquivo de texto.
Utiliza Instaloader com sessão autenticada.

Como usar:
 1) Gere a sessão (uma vez apenas):
    instaloader --login SEU_USUARIO

 2) Execute este script:
    python extract_saved.py --user SEU_USUARIO --session-file session-SEU_USUARIO --output lista_urls.txt

O arquivo de saída conterá uma URL por linha:
  https://www.instagram.com/p/SHORTCODE1/
  https://www.instagram.com/p/SHORTCODE2/
etc.
"""

import argparse
import logging
import sys
from instaloader import Instaloader, Profile


def parse_args():
    parser = argparse.ArgumentParser(
        description="Extrai links de posts salvos no Instagram (coleção padrão)")
    parser.add_argument("--user", required=True,
                        help="Seu nome de usuário Instagram (login)")
    parser.add_argument("--session-file", required=True,
                        help="Arquivo de sessão gerado por instaloader --login")
    parser.add_argument("--output", default="lista_urls.txt",
                        help="Arquivo de saída para gravar as URLs")
    parser.add_argument("--debug", action="store_true",
                        help="Exibe logs de debug no console")
    return parser.parse_args()


def setup_logging(debug: bool):
    logger = logging.getLogger()
    logger.setLevel(logging.DEBUG if debug else logging.INFO)
    ch = logging.StreamHandler(sys.stdout)
    ch.setLevel(logging.DEBUG if debug else logging.INFO)
    fmt = "%(asctime)s - %(levelname)s - %(message)s"
    ch.setFormatter(logging.Formatter(fmt))
    logger.addHandler(ch)


def main():
    args = parse_args()
    setup_logging(args.debug)
    logger = logging.getLogger()

    L = Instaloader()
    try:
        L.load_session_from_file(args.user, args.session_file)
    except Exception as e:
        logger.error(f"Falha ao carregar sessão: {e}")
        sys.exit(1)

    profile = Profile.from_username(L.context, args.user)
    logger.info(f"Carregando posts salvos de @{args.user}...")

    try:
        saved_posts = profile.get_saved_posts()
    except Exception as e:
        logger.error(f"Erro ao obter salvos: {e}")
        sys.exit(1)

    count = 0
    with open(args.output, "w", encoding="utf-8") as f:
        for post in saved_posts:
            url = f"https://www.instagram.com/p/{post.shortcode}/"
            f.write(url + "\n")
            count += 1
    logger.info(f"Concluído: {count} URLs gravadas em {args.output}")


if __name__ == "__main__":
    main()
