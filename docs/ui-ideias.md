# wzsearch — 3 ideias de refatoração de UI

Objetivo: **menos botões, menos abas, mais clareza**. O app cresceu por dentro
(lista, banco, avatares, lixeira, análises, backup) e a interface ficou com 7 abas
e 4 botões fixos na tela principal. Abaixo, três caminhos — do mais conservador ao
mais ambicioso — com o que muda, o ganho, o custo e um esboço.

---

## Ideia 1 — "Uma lista só" (unificar Fotos + Buscar termo + Resultados)

**Hoje:** três abas para a mesma coisa (ver/consultar as fotos). A aba *Fotos* e a
*Buscar termo* são quase idênticas: uma área de arrastar e um botão.

**Proposta:** uma única tela **Explorar**, com:

```
┌─ Explorar ─────────────────────────────────────────────────────────┐
│  [ arraste o export aqui ]   ou   [ Escolher arquivo… ]            │
│                                                                   │
│  Buscar: [ pix, prazo          ▼]  [ ] regex   Remetente: [todos ▼]│
│  Período: [____] até [____]   [ ] só pendentes        N de M linhas│
├───────────────────────────────────────────────────────────────────┤
│  ☑ │ Remetente │ Data │ Contexto │ Legenda │ Arquivo │ …           │
│  ...                                                              │
└───────────────────────────────────────────────────────────────────┘
```

**O que muda**
- A busca por termo/regex deixa de ser uma aba e vira **um filtro da lista**
  (campo de busca no topo, com um modo "regex").
- Importar é uma ação dessa tela (arrastar/botão), não uma tela própria.
- Os chamados "Resultados" *são* a lista.
- **Onde fica a lixeira?** Na gaveta **⚙ Ajustes**, junto com Remetentes e Dados —
  é aqui que a Ideia 1 se apoia na Ideia 2. A lista mostra só o que está ativo;
  excluir tira a linha da lista e manda para a lixeira, com **desfazer** imediato
  (e o contador da gaveta sobe).

**Ganho:** sai de 3 abas para 1; o conceito "buscar" e "listar" viram o mesmo.
**Custo:** a busca hoje não grava no banco; passaria a filtrar ao vivo (ou a gravar
as ocorrências também). É a mudança que mais mexe no código.

---

## Ideia 2 — "Configuração em gaveta" (Remetentes + Lixeira + Dados fora das abas)

**Hoje:** três abas de manutenção (Remetentes, Lixeira, Dados) competindo com o uso
diário (ver as fotos e as análises).

**Proposta:** manter **duas** abas de trabalho — *Explorar* e *Análises* — e mover o
resto para uma **gaveta** lateral, aberta por um botão de engrenagem:

```
  [ Explorar ] [ Análises ]                              ⚙ Ajustes ▸
                                                    ┌───────────────────┐
                                                    │ Remetentes  (20)  │
                                                    │ Lixeira     (3)   │
                                                    │ Dados / backup    │
                                                    └───────────────────┘
```

**Ganho:** as ações do dia a dia ficam sozinhas; as de manutenção ficam agrupadas e
com contagem (útil: "tem 3 na lixeira").
**Custo:** um clique a mais para chegar a essas funções — compensado pelas contagens
nos rótulos.

---

## Ideia 3 — "Ações no contexto" (a barra muda com a seleção + clique direito)

**Hoje:** na aba principal há 4 botões fixos (Incluir/Excluir, Excluir, Salvar CSV,
Colunas) que só fazem sentido em certos momentos.

**Proposta:** uma barra de ações **sensível ao contexto** + menu de clique direito:

| Estado | Ações visíveis |
| --- | --- |
| nada selecionado | Salvar CSV… · Colunas… |
| 1 linha | Ver foto (duplo clique) · Incluir/Excluir · Avatar do contato · Excluir |
| várias linhas | Incluir/Excluir (N) · Excluir (N) |

Os filtros viram **chips** que aparecem só quando ativos (ex.: `período: 01/03–31/03 ✕`),
e o resto fica atrás de um "Filtrar ▾".

**Ganho:** a tela fica limpa; a ação certa aparece na hora certa.
**Custo:** ação escondida pode passar despercebida → mitigar com uma dica
("clique direito para mais ações") e manter a tecla Espaço para incluir/excluir.

---

## Ganhos rápidos (independentes das ideias acima)

1. **Lembrar preferências**: colunas escolhidas, último filtro e último remetente
   selecionado voltam na próxima abertura (hoje tudo reseta).
2. **Modo escuro**: seguir o tema claro/escuro do sistema em vez de cores fixas.
3. **Paleta de comandos** (⌘K/Ctrl+K) para as ações raras (backup, apagar, importar).
4. **Barra de status fixa** com "X ativos · Y fora da análise · Z na lixeira"
   (hoje essa contagem fica no rodapé e some atrás do resumo).

## Comparação

| Ideia | Abas/botões a menos | Esforço | Risco |
| --- | --- | --- | --- |
| 1 — Uma lista só | 2 abas + 1 botão | alto | médio |
| 2 — Gaveta de ajustes | 3 abas | baixo | baixo |
| 3 — Ações no contexto | 3–4 botões | médio | baixo |

Sugestão de ordem: **2 → 3 → 1** (barato e seguro primeiro, depois o contexto, e por
último a unificação das telas, que é a que mais mexe no comportamento).
