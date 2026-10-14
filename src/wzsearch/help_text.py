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
            "Para a exportação sair com todas as mídias possíveis, veja o tópico "
            "“Exportar com as mídias” — ele explica os passos e o que o WhatsApp não "
            "entrega.",
        ),
        tip="Conversas grandes podem vir em vários .zip — importe todos, um por vez.",
    ),
    Topic(
        title="Exportar com as mídias",
        summary="Como exportar para as fotos virem junto — e o que o WhatsApp deixa de fora.",
        bullets=(
            "Android: abra a conversa → ⋮ (três pontinhos) → Mais → Exportar conversa → "
            "marque “Incluir mídia” → escolha para onde mandar (Arquivos, e-mail, Drive…).",
            "iPhone: abra a conversa → toque no nome do contato/grupo no topo → role até "
            "“Exportar conversa” → escolha “Anexar mídia” → salve em Arquivos.",
            "O resultado é um .zip com o texto da conversa e as fotos. É esse .zip que o "
            "wzsearch lê. Sem marcar a mídia vem só o texto — e aí toda foto aparece como "
            "“sem o arquivo no export”.",
            "Conversa grande: o WhatsApp quebra a exportação em vários .zip (…, …(1), "
            "…(2)). Importe todos, um por vez: o app não duplica e só acrescenta o que "
            "falta.",
            "Se você importou só o texto e depois importa o .zip com a mídia, as fotos que "
            "estavam “sem o arquivo no export” são completadas — não viram linhas "
            "repetidas. O rodapé avisa quantas foram completadas.",
            "Reexportar a mesma conversa não duplica nada, mesmo que o arquivo do export "
            "tenha outro nome (o WhatsApp chama o segundo de “… (1).zip”).",
            "Mesmo com “Incluir mídia” marcado, o WhatsApp costuma limitar o tamanho da "
            "exportação e pode deixar arquivos antigos de fora.",
            "O que nunca vem: mídia que expirou, que foi vista uma única vez, que foi "
            "apagada, ou que aparece como “Mídia oculta” (nesse caso o export não diz nem "
            "se era foto, vídeo ou documento). Essas linhas continuam na lista, com a "
            "legenda, marcadas como “sem o arquivo no export”.",
            "Nome e metadados: o WhatsApp renomeia todo arquivo para IMG-AAAAMMDD-WA#### "
            "(a data é a que ele usou) e apaga o EXIF — data de captura, câmera e GPS "
            "normalmente não existem no arquivo que chega. Por isso a auditoria mostra o "
            "que existe de verdade: nome, tamanho, dimensões e a comparação entre a data "
            "do nome e a data da mensagem.",
            "O app não baixa, não copia e não extrai nada para o disco: ele lê a mídia de "
            "dentro do .zip, direto para a memória.",
        ),
        tip="Se quase tudo aparecer “sem o arquivo no export”, quase sempre é exportação "
        "feita sem mídia ou conversa grande demais — refaça a exportação em partes.",
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
            "A coluna Pontos mostra “− 2 +”: clique na metade da esquerda para tirar "
            "um ponto e na da direita para somar.",
            "Clique no título de uma coluna para ordenar a lista por ela; clique de novo "
            "para inverter (a coluna em uso mostra ▲ ou ▼).",
            "Passe o mouse sobre o título de uma coluna, sobre um filtro ou sobre um "
            "botão: aparece uma dica explicando o que aquilo faz.",
            "“Excluir” tira a linha da lista e manda para a lixeira.",
            "“Colunas…” escolhe o que a tabela mostra; “Salvar CSV…” exporta o que está na tela.",
        ),
        tab="Explorar",
        tip="O botão “Colunas…” tem um preset “Enxuto” para quando quiser mais velocidade.",
    ),
    Topic(
        title="Pontuação",
        summary="Cada foto vale de 1 ponto para cima; foto de exercício vale 2.",
        bullets=(
            "Toda foto entra valendo 1 ponto. Quando a legenda (ou a mensagem seguinte "
            "da mesma pessoa) fala de exercício — treino, academia, corrida, bike, "
            "caminhada e afins — a foto já entra valendo 2.",
            "As fotos que já estavam na base também são avaliadas sozinhas: ao abrir o "
            "app, as que a legenda marca viram 2 pontos sem você clicar em nada.",
            "Para ajustar, clique no “−” ou no “+” da coluna Pontos, na própria linha: "
            "o ponto sai ou entra na hora e a Análises se atualiza.",
            "Com várias linhas selecionadas, use o menu “Pontos ▾” da barra de cima "
            "(ou as teclas + e −).",
            "O mínimo é 1 ponto: o “−” nunca deixa a foto abaixo disso. Não há máximo, "
            "então dá para usar a pontuação como peso, se você quiser.",
            "As fotos que a legenda marcou como exercício ficam com uma cor diferente na "
            "lista, e o filtro “só sugestões automáticas” mostra essas para você conferir.",
            "Ajustou na mão? O app não mexe mais nessa linha. O “Reavaliar pelas legendas” "
            "(no menu Pontos ▾) só recalcula as que você não tocou.",
            "Para conferir tudo com calma, há a Auditoria da pontuação em ⚙ Ajustes "
            "(tópico próprio nesta ajuda).",
        ),
        tab="Explorar",
        tip="A leitura da legenda é feita no seu computador, offline — nada é enviado "
        "para a internet.",
    ),
    Topic(
        title="Análises",
        summary="Estatísticas de quem postou o quê.",
        bullets=(
            "Tabela por remetente: fotos, %, com arquivo, pendentes, pontos, fotos de "
            "exercício, dias ativos e primeira/última foto.",
            "Mapa de calor de dia da semana × hora; fotos por dia, mês, hora e dia da semana.",
            "Palavras mais usadas nas legendas, tipos de arquivo e dias mais movimentados.",
            "Pontuação total, média de pontos por foto, fotos de exercício (2 pts) e "
            "quantas sugestões automáticas faltam revisar.",
            "“Sem o arquivo no export” são as fotos cujo arquivo não veio na exportação: "
            "sobra a legenda, sem imagem nem metadados (veja Ajuda → Exportar com as "
            "mídias).",
            "Gráfico de pontos por remetente.",
            "Clique no título de uma coluna da tabela para ordenar; clique de novo para "
            "inverter (▲/▼ mostra a coluna em uso).",
            "Passe o mouse por cima de qualquer número do resumo, de um gráfico ou de um "
            "título de coluna: aparece a explicação daquele campo.",
            "O filtro no topo mostra o geral ou um remetente só.",
            "A roda do mouse rola a página com o ponteiro em qualquer ponto dela. A "
            "exceção é a tabela “Por remetente”: ela tem altura fixa e barra de rolagem "
            "própria, então rola por dentro — assim a lista pode crescer sem empurrar a "
            "página inteira.",
        ),
        tab="Análises",
        tip="Só entram as fotos ativas e marcadas com ☑ na aba Explorar.",
    ),
    Topic(
        title="Auditoria da pontuação",
        summary="Conferir, uma por uma, por que cada foto recebeu os pontos que recebeu.",
        bullets=(
            "Abra em ⚙ Ajustes → Auditoria de pontuação…",
            "O topo mostra o resumo: quantas fotos, quantos pontos, quantas sugestões "
            "ainda para revisar e quantas ficaram fora do padrão (3 pontos ou mais).",
            "“Mostrar:” filtra por situação — sugestões a revisar, confirmadas, ajustadas "
            "por você, fora do padrão ou todas. Dá para combinar com um remetente só.",
            "A coluna “Motivo da pontuação” diz qual palavra casou e onde: na legenda ou "
            "na mensagem seguinte da mesma pessoa. Selecionando a linha, o painel da "
            "direita mostra a foto, a legenda e o contexto completos.",
            "No painel da direita também aparece o que o arquivo diz: nome (com a data "
            "que o WhatsApp usou), tamanho, dimensões, se é retrato/paisagem e, quando o "
            "EXIF sobreviveu, data de captura e câmera. Dá para comparar a data do nome "
            "com a data da mensagem — foto encaminhada costuma não bater.",
            "Antes de confirmar ou ajustar, escreva o motivo no campo “Motivo do ajuste”: "
            "ele fica gravado na foto (coluna “Seu motivo”), aparece na lista e vai no CSV.",
            "“Confirmar sugestão” aceita o valor como está e tira a linha da lista de "
            "pendências; “+1 ponto” e “−1 ponto” corrigem o valor (e o app não mexe mais "
            "nessa linha).",
            "Clique no título de uma coluna para ordenar (clique de novo para inverter).",
            "Duplo clique na linha abre a foto em tamanho maior; passe o mouse pelas "
            "colunas para ver o que cada uma significa.",
        ),
        tip="É aqui que você confia na pontuação: as sugestões da legenda ficam separadas "
        "do que você já revisou.",
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
            "**Duplicatas** procura registros com o mesmo conteúdo de mensagem (data/hora, "
            "remetente, arquivo e legenda) que vieram de importações diferentes — a mesma "
            "foto gravada mais de uma vez — e mantém uma de cada, mandando as cópias para "
            "a lixeira. A que fica herda a foto e a pontuação que você já tinha ajustado.",
        ),
        tip="O backup é a forma de levar o histórico para outra máquina.",
    ),
    Topic(
        title="Privacidade",
        summary="O que acontece com os seus dados.",
        bullets=(
            "Nada é enviado para a internet: o programa roda offline.",
            "As fotos ficam numa base local (um arquivo .db) na pasta de dados do usuário.",
            "O programa não copia mídia para fora dele; só referencia e mostra.",
        ),
    ),
)


def topic_by_tab(tab: str) -> Topic | None:
    """Return the topic that documents a given tab (used by the Help menu)."""
    return next((topic for topic in TOPICS if topic.tab == tab), None)
