# Instagrab

**Instagrab** é um projeto para baixar posts públicos do Instagram em lote ou individualmente, armazenar metadados (legenda, hashtags, status) em um banco local SQLite e exibir os resultados em uma interface web estática moderna.

## Funcionalidades

* **Download de posts**

  * Baixa imagens e vídeos de posts, incluindo carrosséis
  * Salva legenda em arquivo `.txt` e mídias em pastas organizadas por perfil e shortcode
  * Suporte a operação em lote via arquivo de URLs
  * Delay configurável entre requisições para evitar bloqueios
  * Logs detalhados com opção `--debug`

* **Banco de dados SQLite**

  * Armazena registros em `instagrab.db`
  * Tabelas normalizadas: `posts`, `hashtags`, `post_hashtags`
  * Status do download: `salvo`, `falha`, `removido`
  * Extração automática de hashtags e vínculo com posts

* **Interface Web (HTML + Tailwind CSS + jQuery)**

  * Página estática (`index.html`) consumindo `data.json`
  * Busca e filtragem de registros
  * Paginação e seletor de número de entradas (em português)
  * Modo Claro/Escuro com toggle
  * Sidebar (menu hambúrguer) com opções **Sobre** e **Ajuda**
  * Ações por linha: **Acessar** (abre post) e **Copiar** URL
  * Exibição do total de posts baixados

## Estrutura do Projeto

```
├── instagrab.py         # Script principal de download
├── db.py                # Módulo de acesso e manipulação do SQLite
├── extract_saved.py     # (Opcional) Extrai URLs dos posts salvos via Instaloader
├── export_json.py       # Exporta registros SQLite para data.json
├── data.json            # Dados exportados (gerado em tempo de execução)
├── index.html           # Interface web estática
├── README.md            # Documentação do projeto
└── requirements.txt     # Dependências Python
```

## Instalação

1. Clone este repositório:

   ```bash
   git clone https://github.com/hugoleonardoitz/instagrab.git
   cd instagrab
   ```

2. Crie um ambiente virtual e instale as dependências:

   ```bash
   python -m venv venv_instagrab
   source venv_instagrab/bin/activate   # Linux/macOS
   venv_instagrab\Scripts\activate    # Windows
   pip install --upgrade pip
   pip install -r requirements.txt
   ```

3. (Opcional) Gere sessão autenticada para `extract_saved.py`:

   ```bash
   instaloader --login SEU_USUARIO
   ```

## Uso

* **Download único**:

  ```bash
  python instagrab.py https://www.instagram.com/p/SHORTCODE/
  ```

* **Download em lote** (arquivo `urls.txt` com URLs por linha ou vírgula):

  ```bash
  python instagrab.py -i urls.txt --delay 2.5 --output-dir downloads
  ```

* **Exportar para JSON** (para interface web):

  ```bash
  python export_json.py --db instagrab.db --output data.json
  ```

* **Visualizar interface**:

  ```bash
  python -m http.server 8000
  # Acesse http://localhost:8000/index.html
  ```

## Configurações

* `--delay`: tempo de espera entre downloads (padrão: 1.0s)
* `--debug`: exibe logs detalhados no console
* **Tema**: alterne claro/escuro na interface
* **Paginação**: selecione quantas entradas exibir por página

## Contribuição

1. Fork este repositório
2. Crie uma branch de feature (`git checkout -b feature/nome`)
3. Faça commit das suas alterações (`git commit -m 'Add nova feature'`)
4. Push para a branch (`git push origin feature/nome`)
5. Abra um Pull Request

## Licença

Este projeto está licenciado sob a [MIT License](LICENSE).
