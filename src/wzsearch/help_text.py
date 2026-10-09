"""The help content, as structured topics (rendered by :mod:`wzsearch.gui_help`)."""

from __future__ import annotations

from dataclasses import dataclass

INTRO = (
    "O wzsearch lê uma conversa exportada do WhatsApp e mostra as fotos do chat — "
    "quem mandou, quando e a legenda — com estatísticas. Tudo roda no seu computador."
)


@dataclass(frozen=True, slots=True)
class Topic:
    """One help topic shown in the list on the left."""

    title: str
    summary: str
    bullets: tuple[str, ...]
    tab: str | None = None
    tip: str | None = None


TOPICS: tuple[Topic, ...] = (
    Topic(
        title="Começando",
        summary="Importar a conversa leva dois passos.",
        bullets=(
            "No WhatsApp: abra a conversa, menu (três pontinhos) → Mais → "
            "Exportar conversa → “Incluir mídia”.",
            "No wzsearch: arraste o arquivo .zip/.txt para a área da tela ou clique "
            "em “Escolher arquivo…”, e depois em “Gerar”.",
            "As fotos ficam numa base local: na próxima vez já estarão lá e "
            "reimportar o mesmo export não duplica nada.",
        ),
        tip="Conversas grandes podem vir em vários .zip — importe todos, um por vez.",
    ),
    Topic(
        title="Explorar (a lista)",
        summary="A tela principal: filtrar, ver a foto e decidir o que entra nas análises.",
        bullets=(
            "Filtre por remetente, por período, por “só pendentes” ou digitando um "
            "termo (marque “regex” para usar uma expressão regular).",
            "Clique numa linha para ver a foto e todos os campos no painel da direita; "
            "duplo clique abre a foto em tamanho maior.",
            "Clique no ☑/☐ da primeira coluna (ou use a tecla Espaço com a linha "
            "selecionada) para decidir o que entra nas Análises.",
            "“Excluir” tira a linha da lista e manda para a lixeira.",
            "“Colunas…” escolhe o que a tabela mostra; “Salvar CSV…” exporta o que está na tela.",
        ),
        tab="Explorar",
        tip="O botão “Colunas…” tem um preset “Enxuto” para quando quiser mais velocidade.",
    ),
    Topic(
        title="Análises",
        summary="Estatísticas de quem postou o quê.",
        bullets=(
            "Tabela por remetente: fotos, %, com arquivo, pendentes, dias ativos e "
            "primeira/última foto.",
            "Mapa de calor de dia da semana × hora; fotos por dia, mês, hora e dia da semana.",
            "Palavras mais usadas nas legendas, tipos de arquivo e dias mais movimentados.",
            "O filtro no topo mostra o geral ou um remetente só.",
        ),
        tab="Análises",
        tip="Só entram as fotos ativas e marcadas com ☑ na aba Explorar.",
    ),
    Topic(
        title="Remetentes",
        summary="Dar nome a quem aparece como número.",
        bullets=(
            "Escolha um remetente na lista, digite o nome e clique em “Salvar nome”.",
            "O nome passa a valer na lista, nos filtros e nas Análises.",
            "O topo mostra quantos remetentes existem e quantos já têm nome.",
        ),
        tip="Serve para trocar “+55 11 91234-5678” por “Ana” em todo o app.",
    ),
    Topic(
        title="Lixeira",
        summary="O que você excluiu fica guardado aqui.",
        bullets=(
            "“Restaurar selecionados” devolve as linhas para a lista.",
            "“Excluir definitivamente” apaga de vez (não dá para desfazer).",
        ),
    ),
    Topic(
        title="Dados e backup",
        summary="Levar tudo para outro computador ou começar de novo.",
        bullets=(
            "“Fazer backup de todos os dados…” gera um único .zip com a base (fotos "
            "incluídas), os nomes e os avatares.",
            "“Restaurar backup…” substitui os dados atuais pelos do arquivo.",
            "“Apagar todos os dados” limpa tudo — é irreversível.",
        ),
        tip="O backup é a forma de levar o histórico para outra máquina.",
    ),
    Topic(
        title="Atualizações",
        summary="Como o app avisa que existe versão nova.",
        bullets=(
            "Ao abrir, ele pergunta ao GitHub qual é a última versão; havendo novidade, "
            "aparece uma faixa no topo da janela.",
            "No Windows, “Atualizar agora” baixa o pacote, confere a assinatura digital e "
            "troca o programa: o app fecha e volta já na versão nova.",
            "Nada é instalado sem assinatura válida — se a verificação falhar, ele não troca.",
            "Para desligar (ou checar na hora): ⚙ Ajustes → Atualizações…",
        ),
        tip="Essa consulta é a única conexão que o wzsearch faz com a internet.",
    ),
    Topic(
        title="Privacidade",
        summary="O que acontece com os seus dados.",
        bullets=(
            "O conteúdo das conversas nunca é enviado: a única conexão é a consulta de "
            "versão (desligável em Ajustes → Atualizações).",
            "As fotos ficam numa base local (um arquivo .db) na pasta de dados do usuário.",
            "O programa não copia mídia para fora dele; só referencia e mostra.",
        ),
    ),
)


def topic_by_tab(tab: str) -> Topic | None:
    """Return the topic that documents a given tab (used by the Help menu)."""
    return next((topic for topic in TOPICS if topic.tab == tab), None)
