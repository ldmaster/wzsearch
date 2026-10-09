# wzsearch

Busca termos e regex em uma conversa exportada do WhatsApp e gera um CSV com
**todas** as ocorrências: quem falou, quando, o trecho casado e dados associados.

- Entrada: export do app, com ou sem mídia (`.txt` ou `.zip`).
- Busca: palavra-chave e/ou regex informados por argumento. Sem LLM, sem rede.
- Saída: CSV de ocorrências + resumo no `stderr`.
- Stack: Python 3.12, **apenas biblioteca padrão**.

## Instalação

```bash
uv venv --python 3.12 .venv
uv pip install --python .venv/bin/python -e ".[dev]"
```

## Uso

```bash
wzsearch "WhatsApp Chat com Fulano.txt" \
  --term pix --term prazo \
  --regex "\d{3}\.\d{3}\.\d{3}-\d{2}" \
  --eu "Seu Nome" \
  --csv out.csv
```

Também aceita o `.zip` (com mídia) e vários arquivos de uma vez:

```bash
wzsearch export1.zip export2.zip --term pix --csv out.csv
```

Sem `--csv`, o resultado vai para a saída padrão.

### Opções

| Opção | Descrição |
| --- | --- |
| `inputs` | Um ou mais arquivos `.txt`/`.zip` exportados. |
| `--term TEXTO` | Palavra-chave literal (repetível). |
| `--regex EXPR` | Expressão regular (repetível). |
| `--csv CAMINHO` | Arquivo CSV de saída (padrão: `stdout`). |
| `--eu NOME` | Seu nome, para identificar de que lado você está na conversa. |
| `--chat NOME` | Sobrescreve o nome do chat derivado do arquivo. |
| `-i`, `--case-insensitive` | Ignora maiúsculas/minúsculas. |
| `--include-system` | Também busca em avisos de sistema (por padrão são ignorados). |
| `--photos` | Modo só-fotos: lista uma linha por mensagem com foto (não precisa de `--term`). |
| `--overwrite` | Reescreve o CSV do zero, em vez de acrescentar só as linhas novas. |

### Colunas do CSV

```
occurrence_id, termo, texto_casado, remetente, data, hora, timestamp,
chat, message_id, contexto, tem_midia, arquivo_midia, tem_foto,
foto_evidencia, foto_existe, telefone_remetente, numero_no_texto
```

- `occurrence_id`: índice sequencial de cada ocorrência.
- `termo`: o termo/regex que casou (`re:...` para regex).
- `texto_casado`: trecho exato encontrado.
- `remetente`: quem enviou (nome; normalizado por `--eu`).
- `telefone_remetente`: o número da pessoa, quando o rótulo é um telefone.
- `timestamp`: ISO `AAAA-MM-DD HH:MM:SS`; `data`/`hora` são os mesmos valores separados.
- `message_id`: índice da mensagem dentro do export (rastreio).
- `contexto`: trecho ao redor do casamento.
- `tem_midia`/`arquivo_midia`: se a mensagem tem placeholder de mídia e o nome do arquivo.
- `tem_foto`: `sim` quando a mídia é uma **foto** (jpg/jpeg/png/webp/heic/heif/gif),
  excluindo figurinhas (`STK-*.webp`).
- `foto_evidencia`: vínculo da foto como evidência, no formato `<arquivo do export>::<nome da foto>`
  (vazio quando o arquivo não está presente no export).
- `foto_existe`: `sim` quando o arquivo da foto está de fato dentro do export (`.zip`).
- `numero_no_texto`: números extraídos do texto, no formato `tipo:valor` (ver abaixo).

### Listar só as mensagens com foto

Com `--photos` o programa ignora a busca por termo e emite **uma linha por
mensagem que tenha foto**, com o remetente, o número, a data e a foto vinculada:

```bash
wzsearch "WhatsApp Chat com Ana.zip" --photos --csv fotos.csv
```

Colunas desse CSV (sem `numero_no_texto`):

```
foto_id, remetente, telefone_remetente, data, hora, timestamp, chat,
message_id, contexto, legenda, contexto_provavel, foto_arquivo, foto_evidencia,
foto_existe, midia_pendente
```

- `legenda`: a mensagem sem o placeholder da mídia (a legenda da foto).
- `contexto_provavel`: a **próxima mensagem do mesmo remetente** (pulando as de
  outras pessoas), como pista do que a foto é.
- `midia_pendente`: `sim` quando o arquivo **não** está no export.

Quando a foto **não existe** (arquivo fora do export, ou `<Mídia oculta>`), a
linha ainda entra, só com a `legenda` e `midia_pendente=sim` — sem `foto_arquivo`
nem `foto_evidencia`. Isso inclui as `<Mídia oculta>` (tipo desconhecido: pode
ser foto, vídeo ou documento). `foto_evidencia` aponta para o arquivo dentro do
export (`WhatsApp Chat com Ana.zip::comprovante.jpg`) e `foto_existe` diz se ele
está de fato presente (`.zip`). A imagem não é copiada nem extraída.

## Rodar de novo no mesmo export (incremental)

Se o `--csv` já existe com as mesmas colunas, o programa **lê o que já está lá e
só acrescenta as linhas novas** (continua a numeração de `occurrence_id`/`foto_id`).
Assim você pode reler a mesma fonte quantas vezes quiser sem duplicar:

```bash
wzsearch "WhatsApp Chat com Ana.zip" --photos --csv fotos.csv   # 1ª vez: cria
wzsearch "WhatsApp Chat com Ana.zip" --photos --csv fotos.csv   # 2ª vez: "0 foto(s) (N já existiam, ignoradas)"
```

A identidade de cada linha é o conteúdo dela sem o id sequencial. Se a fonte
crescer, só as mensagens novas entram. Para forçar um arquivo novo, use
`--overwrite`. Se o CSV existente tiver outro cabeçalho (ex.: de outro modo), o
programa avisa e para, em vez de misturar formatos.

## Decisões de projeto

- **`numero_extraido` virou colunas separadas**: `telefone_remetente` (telefone de
  quem enviou, opção *a*), `numero_no_texto` (números dentro do texto, opção *b*)
  e `message_id` (índice da mensagem, opção *c*).
- **`numero_no_texto`** usa regex embutidos para o Brasil: `cnpj`, `cpf`, `valor`
  (`R$ ...`), `telefone` e `pedido` (códigos rotulados / `#...`). Padrões de
  maior prioridade "reservam" seu trecho, então um número não aparece duas vezes.
- **Conversa 1:1 sem remetente marcado**: mensagens sem prefixo são atribuídas ao
  contato (o outro lado); `--eu NOME` normaliza `Você`/`You` para o seu nome.

## Sujeiras de formato tratadas

- Mensagens **multilinha** (linhas de continuação sem timestamp são unidas).
- **Avisos de sistema** ("As mensagens e chamadas são protegidas…", "Você criou o
  grupo…", "Fulano entrou", "This message was deleted", …).
- **Locale detectado nos dados**: `DD/MM` vs `M/D`, 24h vs AM/PM, e linhas
  Android (`... - Fulano:`) vs iOS (`[...] Fulano:`).
- Placeholders de **mídia** (`<anexo: ...>`, `<Mídia oculta>`, `<attached: ...>`).
- **Encoding**: BOM UTF-8/UTF-16, UTF-8 e fallback `cp1252`; normalização de CRLF
  e remoção de marcas invisíveis.

## Privacidade

O programa **não** copia, move nem envia mídia. Apenas referencia o nome do
arquivo, o tipo e se ele existe no export. Testes usam fixtures sintéticas —
nenhuma conversa real.

Nada é enviado para a internet: o programa **roda offline**. Nenhuma informação
sobre as conversas — mensagens, fotos, nomes, números — sai da máquina.

## Baixar o executável (sem instalar Python)

Os binários ficam nas **Releases** do repositório — baixáveis por qualquer pessoa,
**sem login no GitHub**:

- https://github.com/ldmaster/wzsearch/releases

Baixe `wzsearch-windows.zip` e descompacte: dentro dele há **só o `wzsearch.exe`**
(duplo clique para abrir) — as instruções de uso estão na própria janela, no menu
**Ajuda → Como usar…**. O antigo `wzsearch.bat` e o arquivo de instruções foram
descontinuados. O CLI continua disponível para quem instala o pacote com `pip`/`uv`.

Para gerar uma nova release, crie e envie uma tag:

```bash
git tag v0.9.0
git push origin v0.9.0
```

O workflow compila **o executável do Windows** e anexa o zip ao Release. O app do
macOS é construído **apenas localmente** (`./scripts/build_macos.sh`) e não vai para
o Release.

## Tela gráfica (GUI)

Duas abas de trabalho + menus:

- **Explorar** — a tela principal. Arraste o export (`.zip`/`.txt`) e clique em
  **Gerar**: as fotos vão para uma **base local** e ficam salvas entre sessões
  (reimportar o mesmo export não duplica). A lista tem **busca por termo ou regex**,
  filtros (remetente, período, só pendentes), **☑ incluir/excluir da análise**
  (botão ou tecla Espaço), **Excluir** (manda para a lixeira), **prévia da foto**,
  **visualizador** (duplo clique), **Colunas…** e **Salvar CSV…**.
- **Análises** — frequência de postagem: total/mídias pendentes, período, **tabela por
  remetente** (fotos, %, com arquivo, pendentes, dias ativos, 1ª e última foto),
  **mapa de calor dia da semana × hora** ("quando postam"), picos (hora/dia/mês mais
  ativos), **palavras mais usadas nas legendas**, **tipos de arquivo**, fotos por
  dia/mês/hora/dia da semana, dias mais movimentados, concentração (top 3),
  mais/menos ativa, média e mediana por dia ativo, intervalo médio/mediano entre
  fotos e maior sequência de dias seguidos. Só entram as fotos **ativas e marcadas**, e
  um **filtro no topo** mostra o **geral** ou **por remetente**.
- **⚙ Ajustes** (canto superior direito) — **Remetentes** (dar nome a quem aparece como
  número; o nome vale na lista, nos filtros e nas Análises), **Lixeira** (restaurar ou
  excluir de vez) e **Dados e backup** (backup num `.zip`, restaurar, apagar tudo).
- **Menu Ajuda** — *Como usar…* abre uma janela com **tópicos** à esquerda (Começando,
  Explorar, Análises, Remetentes, Lixeira, Dados, Privacidade), conteúdo formatado à
  direita e um botão que leva direto para a aba. *Sobre o wzsearch* mostra versão e autor.

Ideias de evolução da interface estão em [`docs/ui-ideias.md`](docs/ui-ideias.md) e os
protótipos clicáveis em [`docs/ui-prototipos.html`](docs/ui-prototipos.html).

### Onde ficam os dados

Um único arquivo SQLite com as fotos embutidas, na pasta de dados oculta do sistema
(sobreponível com `WZSEARCH_HOME`):

- macOS: `~/Library/Application Support/wzsearch/wzsearch.db`
- Windows: `%APPDATA%\wzsearch\wzsearch.db`
- Linux: `~/.local/share/wzsearch/wzsearch.db`

A pasta guarda também os avatares, os nomes de remetentes e o `wzsearch.log`. O banco é
dado pessoal local — nada sai da máquina; use a aba **Dados** para **backup** (um `.zip`
com tudo), **restaurar** ou **apagar todos os dados**. O CLI também importa para a base:
`wzsearch export.zip --photos --db base.db`.

As fotos são lidas **do zip direto para a memória** (nada é extraído para o disco).
Formatos de imagem: `jpg`, `png`, `webp`, `gif` e **`heic`/`heif`** (fotos de iPhone,
via `pillow-heif`, já incluído no executável).

### Avatares (foto do remetente)

O export do WhatsApp **não** traz a foto de perfil dos contatos, e as rotas que
teriam isso (automação do WhatsApp Web, `msgstore.db`) são não-oficiais e estão
fora do escopo do projeto. Então o app oferece:

- **avatar de iniciais** gerado (bolinha colorida com as iniciais), sempre; e
- **foto real que você anexa** em *Definir foto do contato…*, guardada em
  `~/.wzsearch/avatars.json` (dá para mudar a pasta com a variável `WZSEARCH_HOME`).

Rodar localmente:

```bash
uv pip install --python .venv/bin/python -e ".[gui]"
.venv/bin/python -m wzsearch.gui
```

> A GUI usa `tkinterdnd2` para o arrastar-e-soltar; o núcleo e o CLI seguem
> **somente com a biblioteca padrão**. Sem `tkinterdnd2` a tela ainda funciona
> (o clique para escolher o arquivo continua).

## Build local (macOS)

O Python do Homebrew **não** inclui Tkinter (a GUI precisa dele), então o build
local usa um Python gerenciado pelo `uv`, que já traz Tkinter:

```bash
cd /Users/lucasdavi/IA/wzsearch
./scripts/build_macos.sh
```

Isso gera:

- `dist/wzsearch.app` — o app. Abra com: `open dist/wzsearch.app`
- `dist/wzsearch-cli` — a linha de comando. Ex.:
  `./dist/wzsearch-cli --photos --csv fotos.csv "/caminho/export.zip"`

No macOS os dois não podem ter o mesmo nome (o `.app` usa `wzsearch`, então o CLI
local fica `wzsearch-cli`); no zip do Windows o executável é `wzsearch.exe`.

O script é equivalente a (caso queira rodar à mão):

```bash
cd /Users/lucasdavi/IA/wzsearch
uv python install 3.12
uv venv --python-preference only-managed --python 3.12 .venv-mac
uv pip install --python .venv-mac/bin/python -e ".[gui]" "pyinstaller>=6.6,<7"
.venv-mac/bin/pyinstaller --onefile --name wzsearch-cli --paths src packaging/wzsearch_entry.py
.venv-mac/bin/pyinstaller --windowed --name wzsearch --paths src \
    --collect-all tkinterdnd2 packaging/wzsearch_gui_entry.py
open dist/wzsearch.app
```

Sem build, direto do código (testar mais rápido):

```bash
.venv-mac/bin/python -m wzsearch.gui
```

Observações:

- Os binários gerados rodam só na **arquitetura desta máquina** (arm64). Para
  Apple Intel, gere num Mac Intel.
- Binários copiados/baixados levam a marca de quarentena do Gatekeeper; se
  reclamar, rode `xattr -d com.apple.quarantine dist/wzsearch.app`.
- Alternativa ao `uv`: `brew install python-tk@3.12` instala o Tkinter no Python
  do Homebrew e o `.venv` normal passa a rodar a GUI.
- Para gerar o `.exe` no Windows, rode antes
  `python scripts/make_version_info.py` (ele escreve `packaging/version_info.txt`,
  que não vai para o repositório) e use `--version-file packaging/version_info.txt`:
  é essa versão que aparece nas Propriedades do executável.



## Desenvolvimento

```bash
uv run --python .venv/bin/python ruff check .
uv run --python .venv/bin/python mypy
uv run --python .venv/bin/python pytest
```

## Não-objetivos

Ler conversa ao vivo, enviar mensagens, automatizar o WhatsApp Web, ou busca por
sentido/semântica.

## Licença

MIT — veja [`LICENSE`](LICENSE). Pode usar, modificar e redistribuir, inclusive
comercialmente; o programa vem sem garantia e o conteúdo das conversas não sai da
máquina de quem usa.
