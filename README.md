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

O nome do arquivo do export **não** entra nessa identidade: o WhatsApp chama a
segunda exportação da mesma conversa de `… (1).zip`, e comparar o nome faria o
CSV repetir tudo o que já estava lá.

## Exportar a conversa com as mídias

O app lê o que o WhatsApp entrega — então vale exportar direito:

- **Android**: abra a conversa → **⋮** (três pontinhos) → **Mais** → **Exportar conversa**
  → marque **“Incluir mídia”** → escolha para onde mandar (Arquivos, e-mail, Drive…).
- **iPhone**: abra a conversa → toque no **nome do contato/grupo** no topo → role até
  **Exportar conversa** → escolha **“Anexar mídia”** → salve em Arquivos.
- O resultado é um **`.zip`** com o texto da conversa **e** as fotos. É esse `.zip` que o
  wzsearch lê (o `.txt` sozinho funciona, mas só com o texto).

Limitações (do WhatsApp, não do app):

- **Sem marcar a mídia** vem só o texto — e toda foto aparece como **“sem o arquivo no
  export”** na tela (a linha existe, com a legenda, mas sem imagem nem metadados).
- **Conversa grande**: o WhatsApp quebra a exportação em vários `.zip` (…, …(1), …(2)).
  Importe todos, um por vez — nada é duplicado e só o que falta é acrescentado.
- **Limite de tamanho**: mesmo com “Incluir mídia” marcado, o WhatsApp costuma deixar
  arquivos antigos de fora.
- **O que nunca vem**: mídia que expirou, que foi vista uma única vez, que foi apagada ou
  que aparece como “Mídia oculta” (o export não diz nem se era foto, vídeo ou documento).
- **Nomes e metadados**: todo arquivo chega renomeado como `IMG-AAAAMMDD-WA####` (a data é
  a que o WhatsApp usou) e **sem EXIF** — data de captura, câmera e GPS normalmente não
  existem. É por isso que a auditoria mostra o que existe de verdade: nome, tamanho,
  dimensões e a comparação entre a data do nome e a data da mensagem.
- **Nada é baixado nem copiado**: o app lê a mídia de dentro do `.zip`, direto para a
  memória, e nada sai da máquina.

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

## Baixar o app (sem instalar Python)

Os binários ficam nas **Releases** do repositório — baixáveis por qualquer pessoa,
**sem login no GitHub**:

- https://github.com/ldmaster/wzsearch/releases

Cada Release traz um zip por sistema, com **só o app de interface** dentro:

| Sistema | Arquivo | O que tem dentro |
| --- | --- | --- |
| Windows | `wzsearch-windows.zip` | `wzsearch.exe` (duplo clique) |
| macOS Apple Silicon (M1–M4) | `wzsearch-macos-arm64.zip` | `wzsearch.app` (arraste para *Aplicativos*) |
| macOS Intel | `wzsearch-macos-intel.zip` | `wzsearch.app` |
| Linux | `wzsearch-linux.zip` | `wzsearch` (`chmod +x` e execute) |

Para saber qual é o seu Mac: menu Apple → *Sobre este Mac* (ou `uname -m` no Terminal:
`arm64` = Apple Silicon, `x86_64` = Intel).

As instruções de uso estão na própria janela, no menu **Ajuda → Como usar…**. O antigo
`wzsearch.bat` e o arquivo de instruções foram descontinuados, e o zip não traz mais o
CLI: quem quiser a linha de comando instala o pacote com `pip`/`uv`.

Para gerar uma nova release, crie e envie uma tag:

```bash
git tag v0.10.0
git push origin v0.10.0
```

O workflow compila os **três** apps (Windows, macOS e Linux) e anexa os zips ao Release.
Dá para testar a compilação sem publicar nada: em *Actions → build → Run workflow*.

### Observações dos binários

- **macOS**: cada zip traz um `.app` da sua arquitetura (o CI compila em um Mac Apple
  Silicon e em um Intel — as bibliotecas de imagem não são universais). Baixado da
  internet, ele leva a marca de quarentena do Gatekeeper; se o sistema reclamar, rode
  `xattr -dr com.apple.quarantine /Applications/wzsearch.app`.
- **Linux**: o binário precisa de um ambiente gráfico (X11/Wayland) com Tk. O `wzsearch`
  é de uma arquitetura só (a do runner, x86_64) — em ARM, instale o pacote com `pip`.
- **Windows**: o executável carrega a versão nas Propriedades (recurso PE).

## Tela gráfica (GUI)

Duas abas de trabalho + menus:

- **Explorar** — a tela principal. Arraste o export (`.zip`/`.txt`) e clique em
  **Gerar**: as fotos vão para uma **base local** e ficam salvas entre sessões.
  Reimportar **nunca duplica**: a identidade de cada foto é a mensagem em si (chat,
  data/hora, remetente, arquivo e legenda), não o nome do arquivo do export — então
  exportar a conversa de novo (o WhatsApp chama a segunda de `… (1).zip`) e apontar para
  ela só acrescenta o que é novo. E se você importou **só o texto** antes, importar o
  `.zip` depois **completa** aquelas fotos que estavam “sem o arquivo no export” em vez
  de criar linhas repetidas — o status do rodapé diz quantas foram completadas.
  A lista tem **busca por termo ou regex**,
  filtros (remetente, período, só sem arquivo, só sugestões automáticas),
  **☑ incluir/excluir da análise** (botão ou tecla Espaço), **Pontos** (ver abaixo),
  **ordenação clicando no título da coluna** (clique de novo para inverter; ▲/▼ marca a
  coluna em uso), **dicas ao passar o mouse** sobre títulos, filtros e botões,
  **Excluir** (manda para a lixeira), **prévia da foto**,
  **visualizador** (duplo clique), **Colunas…** e **Salvar CSV…**.
- **Análises** — frequência de postagem: total/mídias **sem o arquivo no export**, período, **tabela por
  remetente** (fotos, %, com arquivo, sem arquivo, pontos, fotos de exercício, dias ativos,
  1ª e última foto — ordenável clicando no título da coluna), **pontuação total e média**,
  **mapa de calor dia da semana × hora**
  ("quando postam"), picos (hora/dia/mês mais ativos), **palavras mais usadas nas
  legendas**, **tipos de arquivo**, **pontos por remetente**, fotos por
  dia/mês/hora/dia da semana, dias mais movimentados, concentração (top 3),
  mais/menos ativa, média e mediana por dia ativo, intervalo médio/mediano entre
  fotos e maior sequência de dias seguidos. Só entram as fotos **ativas e marcadas**, e
  um **filtro no topo** mostra o **geral** ou **por remetente**. Cada número, gráfico e
  coluna tem uma **dica** explicando o que é — passe o mouse por cima. A roda rola a
  página com o ponteiro em qualquer ponto dela; a tabela **Por remetente** é a exceção
  (altura fixa, rola por dentro com barra própria), para a lista poder crescer.
- **⚙ Ajustes** (canto superior direito) — **Remetentes** (dar nome a quem aparece como
  número; o nome vale na lista, nos filtros e nas Análises), **Lixeira** (restaurar ou
  excluir de vez), **Auditoria de pontuação** (ver abaixo) e **Dados e backup**
  (backup num `.zip`, restaurar, apagar tudo).
- **Menu Ajuda** — *Como usar…* abre uma janela com **tópicos** à esquerda (Começando,
  Exportar com as mídias, Explorar, Pontuação, Análises, Auditoria da pontuação,
  Remetentes, Lixeira, Dados, Privacidade), conteúdo formatado à direita
  e um botão que leva direto para a aba. *Sobre o wzsearch* mostra versão e autor.

Ideias de evolução da interface estão em [`docs/ui-ideias.md`](docs/ui-ideias.md) e os
protótipos clicáveis em [`docs/ui-prototipos.html`](docs/ui-prototipos.html).

### Pontuação por foto

Cada foto vale **no mínimo 1 ponto**, e vale **2 quando é foto de exercício**. O ajuste
é no próprio registro, na coluna **Pontos** da lista:

```
│ ☑ │ Pontos │ Remetente │ Data       │ Legenda            │
│ ☑ │ − 2 +  │ Ana       │ 2024-03-01 │ treino de hoje 💪  │
```

- Clique na **metade da esquerda** da célula (`−`) para tirar um ponto e na **metade da
  direita** (`+`) para somar. Também vale selecionar várias linhas e usar o menu
  **Pontos ▾** da barra de cima, ou as teclas `+` e `−`.
- O mínimo é **1**: o `−` nunca deixa a foto abaixo disso. Não há máximo — a pontuação
  também serve como peso, se você quiser dar 3 ou mais para uma foto.
- Foto de exercício já entra valendo 2 sozinha: o app procura na **legenda** e na
  **mensagem seguinte da mesma pessoa** palavras como *treino, academia, corrida, bike,
  caminhada, natação, futebol, crossfit* (a lista fica em `src/wzsearch/score.py`, fácil
  de aumentar). Essa leitura é feita **offline**, sem modelo e sem rede.
- A base que **já existia** é avaliada sozinha: ao abrir o app, as fotos que a legenda
  marca viram 2 pontos sem nenhum clique (e as que ficam em 1 ponto continuam em 1).
  Ao importar um export novo, a avaliação já acontece na entrada das fotos.
- O que veio da legenda é uma **sugestão**: essas linhas ficam com a cor da pontuação na
  lista, o filtro **só sugestões automáticas** mostra só elas, e as Análises dizem quantas
  faltam revisar. Assim que você **ajusta** ou **confirma** uma delas na auditoria, o app
  não mexe mais nessa linha — o **Reavaliar pelas legendas** recalcula apenas as que você
  não decidiu.
- Na aba **Análises** entram **pontuação total**, **média de pontos por foto**, **fotos de
  exercício (2 pts)**, **sugestões a revisar**, as colunas **Pontos** e **2 pts** na tabela
  por remetente e um gráfico de **pontos por remetente**. O filtro de remetente do topo
  vale para tudo isso.
- No **Salvar CSV…**, as colunas `pontos`, `pontos_origem` e `pontos_motivo` vão no fim do
  arquivo. O CSV
  do CLI (`--photos`) **não** muda, para não quebrar a regra de acrescentar só as linhas
  novas em arquivos que já existem.
- Ajustou ou confirmou uma sugestão? Escreva o **motivo** na auditoria: ele fica gravado na
  foto (coluna “Seu motivo”) e no CSV, para você lembrar depois por que aquela foto saiu
  do padrão.

Nada disso sai da máquina: a pontuação mora no mesmo banco local das fotos.

### Auditoria de pontuação

Em **⚙ Ajustes → Auditoria de pontuação…** há uma janela só para conferir a pontuação —
é onde dá para confiar no que a legenda sugeriu:

- O topo resume: `N foto(s) · X ponto(s) · Y sugestão(ões) a revisar · Z ajuste(s) seu(s)`,
  mais quantas ficaram **fora do padrão** (3 pontos ou mais).
- O filtro **Mostrar:** separa as situações — *Sugestões a revisar*, *Sugestões
  confirmadas*, *Ajustadas por você*, *3+ pontos*, *Já decididas* e *Todas as fotos* — e
  pode ser combinado com um remetente.
- A coluna **Sugerido por** diz qual palavra casou e onde ela apareceu (na legenda ou na
  mensagem seguinte da mesma pessoa) — sem a legenda, a própria coluna “Legenda” da
  tabela ajuda a bater o olho.
- O painel da direita mostra **a foto** da linha selecionada (leitura direta do banco;
  duplo clique abre grande) e, embaixo, o que **o arquivo diz**: nome, tamanho, dimensões,
  orientação e, quando o EXIF sobreviveu, data de captura e câmera — junto da comparação
  entre a data do nome e a data da mensagem (é o que pega foto encaminhada).
- **Motivo do ajuste**: escreva por que você está mexendo na pontuação (ex. “era o café,
  a legenda seguinte falava de outra pessoa”) antes de confirmar/ajustar. O texto fica
  gravado na foto — coluna **“Seu motivo”** na lista e na auditoria, e no CSV — e é
  aplicado às linhas selecionadas de uma vez.
- **Confirmar sugestão** aceita o valor como está e tira a linha das pendências;
  **+1 ponto** / **−1 ponto** corrigem (e a linha passa a ser sua, fora do alcance do
  “Reavaliar”); **Reavaliar pelas legendas** refaz a leitura de tudo que você não decidiu.
- As colunas ordenam clicando no título, como nas outras tabelas.

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
