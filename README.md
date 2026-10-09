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

## Baixar o executável (sem instalar Python)

Os binários ficam nas **Releases** do repositório — baixáveis por qualquer pessoa,
**sem login no GitHub**:

- https://github.com/ldmaster/wzsearch/releases

Baixe `wzsearch-windows.zip` e descompacte. Dentro dele:

- **`wzsearch-gui.exe`** — o app: duplo clique, arraste o export, escolha o
  nome/pasta e clique em *Gerar*.
- `COMO-USAR.txt` — instruções em linguagem simples.

O pacote do Windows traz **só o executável da tela**. O antigo `wzsearch.bat`
(que rodava a versão de linha de comando por arrastar-e-soltar) foi descontinuado.
O CLI continua disponível para quem instala o pacote com `pip`/`uv`.

Para gerar uma nova release, crie e envie uma tag:

```bash
git tag v0.1.1
git push origin v0.1.1
```

O workflow compila os binários, empacota e anexa os zips ao Release. O binário do
macOS é *best-effort*: os runners arm64 do GitHub são limitados por capacidade e o
job pode nem iniciar (sem quebrar a release). No macOS, o binário não é assinado —
se o Gatekeeper reclamar, use `xattr -d com.apple.quarantine wzsearch`.

## Tela gráfica (GUI)

Seis abas + menu de ajuda:

- **Fotos** — arraste o export (`.zip`/`.txt`) e clique em **Gerar**: as fotos vão para
  uma **base local** e ficam salvas entre sessões (reimportar o mesmo export não duplica).
- **Buscar termo** — termos/regex; o resultado aparece na hora (não vai para a base).
- **Resultados** — as fotos numa tabela (com **barra de rolagem**), filtros (remetente,
  período, só pendentes), **☑ incluir/excluir da análise** (botão ou tecla Espaço),
  **Excluir** (manda para a lixeira), **prévia da foto**, **visualizador** (duplo clique),
  **avatares** e **Salvar CSV…** (exporta a visão atual). Quando a base já tem registros,
  o app **abre nesta aba**.
- **Remetentes** — dá um **nome** para quem aparece como número (ex.: `+55 11 9…` →
  "Ana"). O nome passa a valer na tabela de Resultados, no filtro e nas Análises.
- **Lixeira** — o que foi excluído, com **Restaurar** e **Excluir definitivamente**.
- **Análises** — frequência de postagem: total/mídias pendentes, período, **tabela por
  remetente** (fotos, %, com arquivo, pendentes, dias ativos, 1ª e última foto),
  **mapa de calor dia da semana × hora** ("quando postam"), picos (hora/dia/mês mais
  ativos), **palavras mais usadas nas legendas**, **tipos de arquivo**, fotos por
  dia/mês/hora/dia da semana, dias mais movimentados, concentração (top 3),
  mais/menos ativa, média e mediana por dia ativo, intervalo médio/mediano entre
  fotos e maior sequência de dias seguidos. Só entram as fotos **ativas e marcadas**, e
  um **filtro no topo** mostra o **geral** ou **por remetente**.
- **Dados** — **Fazer backup de todos os dados…** (um `.zip` com o banco, os nomes e os
  avatares), **Restaurar backup…** e **Apagar todos os dados** (irreversível).
- **Menu Ajuda** — *Como usar cada aba* (uma janela com o guia de cada tela e dicas) e
  *Sobre o wzsearch* (versão e autor).

Ideias de evolução da interface estão em [`docs/ui-ideias.md`](docs/ui-ideias.md).

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

- `dist/wzsearch-gui.app` — a tela. Abra com: `open dist/wzsearch-gui.app`
- `dist/wzsearch` — a CLI. Ex.:
  `./dist/wzsearch --photos --csv fotos.csv "/caminho/export.zip"`

O script é equivalente a (caso queira rodar à mão):

```bash
cd /Users/lucasdavi/IA/wzsearch
uv python install 3.12
uv venv --python-preference only-managed --python 3.12 .venv-mac
uv pip install --python .venv-mac/bin/python -e ".[gui]" "pyinstaller>=6.6,<7"
.venv-mac/bin/pyinstaller --onefile --name wzsearch --paths src packaging/wzsearch_entry.py
.venv-mac/bin/pyinstaller --windowed --name wzsearch-gui --paths src \
    --collect-all tkinterdnd2 packaging/wzsearch_gui_entry.py
open dist/wzsearch-gui.app
```

Sem build, direto do código (testar mais rápido):

```bash
.venv-mac/bin/python -m wzsearch.gui
```

Observações:

- Os binários gerados rodam só na **arquitetura desta máquina** (arm64). Para
  Apple Intel, gere num Mac Intel (ou via CI com `macos-13`).
- Binários copiados/baixados levam a marca de quarentena do Gatekeeper; se
  reclamar, rode `xattr -d com.apple.quarantine dist/wzsearch-gui.app`.
- Alternativa ao `uv`: `brew install python-tk@3.12` instala o Tkinter no Python
  do Homebrew e o `.venv` normal passa a rodar a GUI.



## Desenvolvimento

```bash
uv run --python .venv/bin/python ruff check .
uv run --python .venv/bin/python mypy
uv run --python .venv/bin/python pytest
```

## Não-objetivos

Ler conversa ao vivo, enviar mensagens, automatizar o WhatsApp Web, ou busca por
sentido/semântica.
