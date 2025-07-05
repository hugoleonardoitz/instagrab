#!/usr/bin/env python
# db.py
"""
Módulo de acesso ao SQLite para controle de posts e hashtags.

- Banco local: instagrab.db
- Tabelas: posts, hashtags, post_hashtags

Fornece métodos para criar esquema, inserir/atualizar posts, inserir hashtags,
vincular posts a hashtags e consultar por filtros e hashtag.
"""
import sqlite3
from sqlite3 import Connection, Row
from typing import List, Dict, Optional, Any

DB_FILE = "instagrab.db"

# SQL de criação das três tabelas
CREATE_POSTS = '''
CREATE TABLE IF NOT EXISTS posts (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    perfil TEXT NOT NULL,
    shortcode TEXT NOT NULL,
    url_completa TEXT NOT NULL,
    descricao TEXT,
    status TEXT NOT NULL CHECK(status IN ('salvo','falha','removido')),
    criado_em TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    atualizado_em TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(perfil, shortcode)
);
'''
CREATE_HASHTAGS = '''
CREATE TABLE IF NOT EXISTS hashtags (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    tag TEXT NOT NULL UNIQUE
);
'''
CREATE_LINK = '''
CREATE TABLE IF NOT EXISTS post_hashtags (
    post_id INTEGER NOT NULL,
    hashtag_id INTEGER NOT NULL,
    PRIMARY KEY (post_id, hashtag_id),
    FOREIGN KEY(post_id) REFERENCES posts(id) ON DELETE CASCADE,
    FOREIGN KEY(hashtag_id) REFERENCES hashtags(id) ON DELETE CASCADE
);
'''

class DB:
    """Classe para gerenciar a conexão e operações com o banco de dados SQLite."""
    def __init__(self, db_file: str = DB_FILE) -> None:
        """
        Inicializa a conexão com o banco de dados e cria as tabelas se não existirem.
        """
        self.conn: Connection = sqlite3.connect(db_file)
        self.conn.row_factory = sqlite3.Row
        self.init_db()

    def init_db(self) -> None:
        """Cria as tabelas posts, hashtags e post_hashtags se não existirem."""
        cur = self.conn.cursor()
        cur.execute(CREATE_POSTS)
        cur.execute(CREATE_HASHTAGS)
        cur.execute(CREATE_LINK)
        self.conn.commit()

    def upsert_post(
        self,
        perfil: str,
        shortcode: str,
        url_completa: str,
        descricao: Optional[str],
        status: str
    ) -> int:
        """
        Insere um post ou atualiza descrição/status se já existir.
        Retorna o post_id.
        NOTA: A cláusula RETURNING requer SQLite versão 3.35.0+
        """
        cur = self.conn.cursor()
        cur.execute(
            '''
            INSERT INTO posts(perfil, shortcode, url_completa, descricao, status)
            VALUES(?,?,?,?,?)
            ON CONFLICT(perfil, shortcode) DO UPDATE SET
                descricao = excluded.descricao,
                status = excluded.status,
                atualizado_em = CURRENT_TIMESTAMP
            RETURNING id;
            ''',
            (perfil, shortcode, url_completa, descricao, status)
        )
        # A cláusula RETURNING evita uma segunda consulta para buscar o ID.
        row = cur.fetchone()
        self.conn.commit()
        if not row:
            # Fallback para versões mais antigas do SQLite, caso RETURNING não funcione
            cur.execute('SELECT id FROM posts WHERE perfil=? AND shortcode=?', (perfil, shortcode))
            row = cur.fetchone()

        return row['id'] if row else -1

    def insert_hashtag(self, tag: str) -> int:
        """
        Insere uma hashtag única (lowercase, sem #) e retorna seu id.
        """
        cur = self.conn.cursor()
        cur.execute('INSERT OR IGNORE INTO hashtags(tag) VALUES(?)', (tag.lower(),))
        self.conn.commit()
        cur.execute('SELECT id FROM hashtags WHERE tag=?', (tag.lower(),))
        row = cur.fetchone()
        return row['id'] if row else -1

    def link_post_hashtag(self, post_id: int, hashtag_id: int) -> None:
        """
        Cria vínculo entre post e hashtag.
        """
        cur = self.conn.cursor()
        cur.execute(
            'INSERT OR IGNORE INTO post_hashtags(post_id, hashtag_id) VALUES(?,?)',
            (post_id, hashtag_id)
        )
        self.conn.commit()

    def get_posts(
        self,
        perfil: Optional[str] = None,
        status: Optional[str] = None,
        descricao_like: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """
        Retorna posts filtrados opcionalmente por perfil, status ou parte da descrição.
        """
        cur = self.conn.cursor()
        sql = 'SELECT * FROM posts'
        clauses, params = [], []
        if perfil:
            clauses.append('perfil = ?')
            params.append(perfil)
        if status:
            clauses.append('status = ?')
            params.append(status)
        if descricao_like:
            clauses.append('descricao LIKE ?')
            params.append(f'%{descricao_like}%')

        if clauses:
            sql += ' WHERE ' + ' AND '.join(clauses)

        sql += ' ORDER BY criado_em DESC'
        cur.execute(sql, params)
        return [dict(r) for r in cur.fetchall()]

    def get_posts_by_hashtag(self, tag: str) -> List[Dict[str, Any]]:
        """
        Retorna posts associados a uma hashtag específica.
        """
        cur = self.conn.cursor()
        cur.execute(
            '''
            SELECT p.* FROM posts p
            JOIN post_hashtags ph ON p.id = ph.post_id
            JOIN hashtags h ON h.id = ph.hashtag_id
            WHERE h.tag = ?
            ORDER BY p.criado_em DESC
            ''',
            (tag.lower(),)
        )
        return [dict(r) for r in cur.fetchall()]

    def close(self) -> None:
        """Fecha a conexão com o banco de dados."""
        self.conn.close()
