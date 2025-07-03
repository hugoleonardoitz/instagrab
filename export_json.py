#!/usr/bin/env python
# export_json.py
"""
Exporta registros do SQLite (instagrab.db) para JSON estático.
Inclui posts e suas hashtags associadas.

Como usar:
    python export_json.py --db instagrab.db --output data.json

O JSON gerado terá formato:
[
  {
    "id": 1,
    "perfil": "usuario",
    "shortcode": "ABC123",
    "url_completa": "https://www.instagram.com/p/ABC123/",
    "descricao": "Texto sem hashtags",
    "status": "salvo",
    "criado_em": "2025-06-28 12:00:00",
    "atualizado_em": "2025-06-28 12:05:00",
    "hashtags": ["tag1","tag2",...]
  },
  ...
]
"""
import argparse
import json
import sqlite3
import sys


def parse_args():
    parser = argparse.ArgumentParser(description="Exporta registros do SQLite para JSON estático.")
    parser.add_argument(
        "--db", default="instagrab.db",
        help="Caminho para o arquivo SQLite (instagrab.db)"
    )
    parser.add_argument(
        "--output", default="data.json",
        help="Arquivo de saída JSON"
    )
    return parser.parse_args()


def export_to_json(db_file: str, output_file: str):
    conn = sqlite3.connect(db_file)
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()
    # Consulta posts com hashtags agrupadas
    cur.execute('''
        SELECT
            p.id,
            p.perfil,
            p.shortcode,
            p.url_completa,
            p.descricao,
            p.status,
            p.criado_em,
            p.atualizado_em,
            GROUP_CONCAT(h.tag) AS hashtags
        FROM posts p
        LEFT JOIN post_hashtags ph ON p.id = ph.post_id
        LEFT JOIN hashtags h ON h.id = ph.hashtag_id
        GROUP BY p.id
        ORDER BY p.criado_em DESC;
    ''')
    rows = cur.fetchall()
    data = []
    for row in rows:
        tags = row['hashtags'].split(',') if row['hashtags'] else []
        item = {
            'id': row['id'],
            'perfil': row['perfil'],
            'shortcode': row['shortcode'],
            'url_completa': row['url_completa'],
            'descricao': row['descricao'],
            'status': row['status'],
            'criado_em': row['criado_em'],
            'atualizado_em': row['atualizado_em'],
            'hashtags': tags
        }
        data.append(item)
    # Grava JSON
    try:
        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        print(f"Exportação concluída: {len(data)} registros em '{output_file}'")
    except Exception as e:
        print(f"Erro ao gravar JSON: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == '__main__':
    args = parse_args()
    export_to_json(args.db, args.output)
