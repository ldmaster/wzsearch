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

- **`wzsearch-gui.exe`** — a **tela gráfica** (recomendado para o usuário final):
  duplo clique, arraste o export, escolha o nome/pasta e clique em *Gerar*.
- `wzsearch.exe` — a versão de linha de comando.
- `wzsearch.bat` — atalho: arraste o export em cima dele.
- `COMO-USAR.txt` — instruções em linguagem simples.

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

Duas abas (**Fotos** e **Buscar termo**) com a mesma base do CLI:

- **área de arrastar-e-soltar** o export (`.zip`/`.txt`) — ou clique para escolher;
- **nome do arquivo de saída** (sugerido a partir do export) e **pasta de destino**;
- botão **Gerar** com **barra de progresso** e mensagem de status;
- botão **Abrir pasta** ao terminar.

A geração roda numa thread separada, então a janela não congela. O arquivo é
gravado de forma incremental (reler o mesmo export não duplica linhas).

Rodar localmente:

```bash
uv pip install --python .venv/bin/python -e ".[gui]"
.venv/bin/python -m wzsearch.gui
```

> A GUI usa `tkinterdnd2` para o arrastar-e-soltar; o núcleo e o CLI seguem
> **somente com a biblioteca padrão**. Sem `tkinterdnd2` a tela ainda funciona
> (o clique para escolher o arquivo continua).


## Desenvolvimento

```bash
uv run --python .venv/bin/python ruff check .
uv run --python .venv/bin/python mypy
uv run --python .venv/bin/python pytest
```

## Não-objetivos

Ler conversa ao vivo, enviar mensagens, automatizar o WhatsApp Web, ou busca por
sentido/semântica.
