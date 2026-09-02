---
id: TOPIC-001
title: "Modelo interno do Git: objetos, snapshots e o .git"
status: root
content_status: materialized
content_version: 1
materialized_at: "2026-09-02T00:00:00Z"
difficulty: beginner
estimated_hours: 1.1
prerequisites: []
learning_outcomes:
  - id: LO-1
    statement: "Explicar o que o Git armazena internamente quando você faz um commit — blobs, trees e commits como snapshot — e por que um commit não é um diff."
    required_concepts:
      - "blob"
      - "tree"
      - "commit (snapshot)"
      - "hash SHA / conteúdo endereçável"
  - id: LO-2
    statement: "Usar comandos de inspeção (git cat-file, git ls-tree, git log) para examinar o conteúdo real armazenado pelo Git após um commit."
    required_concepts:
      - "git cat-file"
      - "git ls-tree"
      - "git log"
      - "pasta .git/objects"
  - id: LO-3
    statement: "Diferenciar working directory, staging area (índice) e repositório (.git), explicando o papel de cada um no caminho de um arquivo até um commit."
    required_concepts:
      - "working directory"
      - "staging area / index"
      - "repositório (.git)"
module: study/modules/TOPIC-001.md
assessment: study/assessments/TOPIC-001.yml
assessment_form: .github/ISSUE_TEMPLATE/assessment-topic-001.yml
---

# TOPIC-001 — Modelo interno do Git: objetos, snapshots e o .git

## O que você vai aprender

Você vai conseguir explicar o que o Git realmente guarda quando você faz um commit — os objetos *blob* (conteúdo de um arquivo), *tree* (uma pasta) e *commit* (um snapshot com metadados) — e inspecionar esses objetos de verdade dentro da pasta `.git`, em vez de confiar apenas no que `git log` mostra na superfície. Você também vai diferenciar working directory, staging area e repositório, explicando por que `git add` é uma etapa separada de `git commit`.

## Por que isso importa para você

Você disse que usa `git add`, `git commit`, `git push` e `git pull` no dia a dia, mas nunca entendeu de verdade como funciona por baixo dos panos. Este é o alicerce: sem entender que um commit é um snapshot completo (não um diff) e sem saber onde staging area, working directory e repositório se separam, branches, merge, rebase e conflitos continuam parecendo mágica. Esta etapa existe para tirar essa mágica do caminho antes de tudo o mais.

## O que você já precisa saber

- Nada além do que você já confirmou: uso confortável de `git add`, `git commit`, `git push` e `git pull` no dia a dia. Esta é a etapa raiz da trilha — não há pré-requisito interno.

## Seu plano para esta etapa

- [ ] Recuperar o que você já sabe sobre add/commit e registrar sua hipótese atual (10 min)
- [ ] Estudar o que são blobs, trees e commits, e por que commit é snapshot e não diff (20 min)
- [ ] Inspecionar objetos reais com `git cat-file` e `git ls-tree` no seu próprio terminal (20 min)
- [ ] Aplicar o conceito a um cenário novo e registrar a evidência escrita (16 min)

## Aula

A aula completa está pronta: [Modelo interno do Git: objetos, snapshots e o .git](../modules/TOPIC-001.md). Ela ensina a diferença entre snapshot e diff, o papel de blob/tree/commit, e como inspecionar objetos reais com comandos de terminal.

## Prática

A prática guiada e a prática independente ficam dentro da aula — não há laboratório externo separado para esta etapa. A aula te leva de um repositório de teste simples até produzir sua própria evidência de inspeção.

## O que você vai produzir

Uma explicação escrita curta (4 a 8 frases) sobre quais blobs foram reaproveitados e quais foram criados num terceiro commit de um repositório de teste, acompanhada da saída de terminal (`git cat-file`/`git ls-tree`) que comprova sua resposta.

## Como mostrar o que aprendeu

Envie o texto e a saída de terminal no formulário de avaliação. A saída de terminal colada como texto (ou um link para um gist) já é suficiente como evidência — não é necessário nenhum dado pessoal além disso.

## Para concluir esta etapa

- [ ] Explicar por que um commit é um snapshot e não um diff, sem depender das notas.
- [ ] Reconstruir o mapa visual do caminho working directory → staging area → commit.
- [ ] Inspecionar um commit real com `git cat-file`/`git ls-tree` e identificar blob, tree e commit.
- [ ] Reconhecer o equívoco mais comum ("commit guarda só a mudança") e corrigi-lo com suas palavras.
- [ ] Alcançar a pontuação mínima da avaliação sem um equívoco crítico.

> Marcar as atividades acima ajuda a acompanhar o avanço; a etapa é concluída depois da avaliação enviada e corrigida.

## Avaliação

Quando terminar a aula, abra a avaliação (link direto disponível dentro da aula) e, depois de enviar, escreva no chat:

`Terminei Modelo interno do Git: objetos, snapshots e o .git. Avalie minhas respostas.`

## Fontes principais

### Essenciais

- Chacon, S.; Straub, B. *Pro Git*, capítulo 10 "Git Internals — Plumbing and Porcelain" — https://git-scm.com/book/en/v2/Git-Internals-Plumbing-and-Porcelain

### Para aprofundar

- Documentação oficial `git-cat-file` — https://git-scm.com/docs/git-cat-file
- GitHub Docs, "About Git" — https://docs.github.com/en/get-started/using-git/about-git
- Learn Git Branching (visualização interativa) — https://learngitbranching.js.org/
