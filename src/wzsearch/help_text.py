"""The text shown in the Help window (kept out of the GUI code)."""

from __future__ import annotations

INTRO = (
    "O wzsearch lê uma conversa exportada do WhatsApp (.zip ou .txt) e mostra as "
    "fotos do chat — quem mandou, quando, a legenda — com estatísticas. Tudo roda "
    "no seu computador e fica guardado numa base local."
)

#: (tab, what it does)
SECTIONS: tuple[tuple[str, str], ...] = (
    (
        "Aba Fotos",
        "Onde tudo começa. Arraste o export do WhatsApp (.zip ou .txt) para a área "
        "da tela, ou clique em “Escolher arquivo…”, e depois em “Gerar”. As fotos "
        "são gravadas numa base local: ficam salvas entre sessões e reimportar o "
        "mesmo export não duplica nada.",
    ),
    (
        "Aba Buscar termo",
        "Consulta pontual, sem gravar na base. Informe um ou mais termos separados "
        "por vírgula e/ou uma expressão regular (regex) e clique em “Gerar”. O "
        "resultado aparece na hora; use “Salvar CSV…” para exportar.",
    ),
    (
        "Aba Resultados",
        "A lista das fotos. Filtre por remetente, período ou “só pendentes”. "
        "Selecione uma linha para ver a foto e todos os campos no painel da "
        "direita (duplo clique abre a foto em tamanho maior).\n\n"
        "• ☑ / ☐ (tecla Espaço): decide o que entra nas Análises.\n"
        "• Excluir (lixeira): tira da lista, mas pode ser restaurado.\n"
        "• Colunas…: escolhe quais colunas aparecem (há um preset “Enxuto”).\n"
        "• Salvar CSV…: exporta a lista que está na tela.",
    ),
    (
        "Aba Remetentes",
        "Dá um nome para quem aparece como número (ex.: “+55 11 9…” → “Ana”). O nome "
        "passa a valer na tabela de Resultados, nos filtros e nas Análises. O topo "
        "mostra quantos remetentes existem e quantos já têm nome.",
    ),
    (
        "Aba Lixeira",
        "O que você excluiu fica aqui. “Restaurar selecionados” devolve para a "
        "lista; “Excluir definitivamente” apaga de vez.",
    ),
    (
        "Aba Análises",
        "Estatísticas de quem postou: total, período, tabela por remetente, mapa de "
        "calor de dia da semana × hora, fotos por dia/mês/hora, palavras mais usadas "
        "nas legendas, tipos de arquivo e dias mais movimentados. O filtro no topo "
        "mostra o geral ou um remetente só. Só entram as fotos ativas e marcadas.",
    ),
    (
        "Aba Dados",
        "Backup de tudo (um .zip com o banco, os nomes e os avatares), restauração de "
        "um backup e “Apagar todos os dados”. O backup é a forma de levar os dados "
        "para outro computador.",
    ),
)

TIPS = (
    "Arrastar e soltar: funciona na área pontilhada das abas Fotos e Buscar termo.",
    "Atalhos: Espaço alterna ☑/☐; setas andam pela lista; duplo clique abre a foto.",
    "Nada é enviado para a internet e as fotos não são copiadas para fora do programa.",
    "“mídia pendente” quer dizer que aquela foto não estava incluída no export.",
)
