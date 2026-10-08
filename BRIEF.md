# Brief — analisador de conversa do WhatsApp (busca por termo/regex)

Documento de handoff. Nada de código ainda: só o que foi decidido e o que falta.

## Objetivo

Ler uma conversa exportada do WhatsApp, procurar por palavras-chave e regex
informados pelo usuário, contar ocorrências e gerar um CSV com quem falou,
quantas vezes, quando, e os dados associados.

## Fonte de dados (DECIDIDO)

Export do próprio app, **incluindo mídia**. Consequência de formato:

- Sem mídia  -> `WhatsApp Chat com Fulano.txt`
- Com mídia  -> `WhatsApp Chat com Fulano.zip`, contendo `_chat.txt` + os arquivos

O programa deve aceitar **os dois**. No zip, o texto está em `_chat.txt` e as
mídias são arquivos irmãos; o vínculo é o placeholder no texto da mensagem
(ex.: `<anexo: 00000042-FOTO-2024-03-12-14-22-31.jpg>`), cujo formato varia por
plataforma e idioma. Conversas grandes podem vir em vários zips.

## Decisões já tomadas

- Busca: **palavra-chave e regex informados por argumento** (não semântica, sem LLM).
- Saída: **CSV** com todas as ocorrências.
- Nada de Playwright, nada de `msgstore.db`, nada de lib não-oficial.

## Saída: CSV de ocorrências

Colunas propostas:

    occurrence_id, termo, texto_casado, remetente, data, hora, timestamp,
    chat, message_id, contexto, tem_midia, arquivo_midia, numero_extraido

## PENDENTE (resolver antes de codar)

"numero_extraido" está ambíguo — escolher uma ou combinar:

- (a) telefone de quem enviou (só existe em export de **grupo**; em 1:1 o nome
      normalmente vem sozinho);
- (b) número **dentro** do texto (telefone, CPF, nº de pedido, valor em R$);
- (c) id sequencial da mensagem, só para rastrear a ocorrência.

Também pendente: em conversa 1:1 o remetente pode não ser marcado. Prever um
parâmetro `--eu "Seu Nome"` para identificar qual lado é o usuário.

## Sujeiras do formato a tratar (todas conhecidas)

- Mensagens **multilinha** (continuação não tem prefixo de data/remetente).
- **Mensagens de sistema**: "As mensagens e chamadas são protegidas…",
  "Você criou o grupo", "Fulano entrou", mudanças de número, etc.
- **Locale**: data é DD/MM/AA ou M/D/AA; hora 24h ou AM/PM; separadores variam.
  Detectar o formato nos primeiros registros válidos, não assumir.
- Placeholders de mídia (`<Mídia oculta>`, `<anexo: ...>`) e reações/editadas.
- Encoding/emoji e possíveis caracteres de controle.

## Privacidade

A conversa é pessoal e as mídias também. O programa **não** deve copiar, mover
nem enviar mídia para lugar nenhum por padrão: só referenciar (nome do arquivo,
tipo, se existe). Qualquer extração é sob pedido explícito.

## Stack e qualidade

- Python 3.12, **stdlib apenas** (zipfile, csv, re, datetime, argparse,
  unicodedata). Nenhuma dependência de rede, nenhum LLM.
- Testes com pytest sobre **fixtures sintéticas** de `_chat.txt` (não usar
  conversa real em teste). Foco nos casos sujos acima.
- Mesmo padrão do `py-harness`: type hints, docstrings, arquivos pequenos com
  responsabilidade única, e validação por ruff + mypy.
- CLI algo como:
  `wzsearch <export.zip|.txt> --term pix --term "prazo" --regex "\d{3}\.\d{3}\.\d{3}-\d{2}" --csv out.csv`

## Não-objetivos

- Ler conversa ao vivo, enviar mensagem, ou automatizar o WhatsApp Web.
- Busca por sentido ("assuntos sobre X") — se vier a ser pedido, aí entra o
  `py-harness`.
