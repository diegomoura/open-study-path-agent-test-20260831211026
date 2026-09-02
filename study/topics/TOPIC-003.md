---
id: TOPIC-003
title: "Merge: unindo histórias de trabalho"
status: eligible_after_prerequisites
content_status: planned
content_version: 0
materialized_at: null
difficulty: beginner
estimated_hours: 1.1
prerequisites:
  - TOPIC-002
learning_outcomes:
  - id: LO-1
    statement: "Executar um merge e distinguir fast-forward de merge com commit de merge."
    required_concepts:
      - "merge"
      - "merge commit"
      - "fast-forward merge"
  - id: LO-2
    statement: "Ler o histórico resultante de um merge (via git log --graph) e explicar por que ele tomou aquela forma, incluindo o papel do ancestral comum."
    required_concepts:
      - "ancestral comum (merge base)"
      - "git log --graph"
module: study/modules/TOPIC-003.md
assessment: study/assessments/TOPIC-003.yml
assessment_form: .github/ISSUE_TEMPLATE/assessment-topic-003.yml
---

# TOPIC-003 — Merge: unindo histórias de trabalho

## O que você vai aprender

Você vai conseguir executar um merge, distinguir um *fast-forward merge* (quando o Git só anda o ponteiro para frente) de um merge que cria um *merge commit* (quando as duas linhas de trabalho realmente divergiram), e ler o histórico resultante para entender por que ele tomou aquela forma.

## Por que isso importa para você

Merge é a base do trabalho em equipe e o primeiro passo para entender conflitos (Aula 05) e o fluxo de feature branch com pull requests (Aula 06). Seu diagnóstico mostrou uma intuição correta — "merge cria um commit de merge" — mas ainda sem prática guiada real. Aqui essa intuição vira prática segura, apoiada no que você já sabe sobre branches e HEAD (Aula 02).

## O que você já precisa saber

- **Aula 02 — Branches e HEAD como ponteiros:** você precisa já conseguir explicar o que uma branch aponta e o que é fast-forward, porque merge é a primeira operação em que esse conceito é aplicado de verdade.

## Seu plano para esta etapa

- [ ] Recuperar o que já sabe sobre branches e fast-forward (10 min)
- [ ] Estudar merge commit, fast-forward merge e ancestral comum (20 min)
- [ ] Praticar um merge fast-forward e um merge com commit de merge (25 min)
- [ ] Ler o histórico resultante com git log --graph e explicar o porquê (15 min)

## Aula

Esta aula será preparada automaticamente quando você concluir os pré-requisitos desta etapa. Você não precisa pedir a geração manualmente.

## Prática

A prática guiada e a prática independente vão ficar dentro da aula, cobrindo cenários de merge fast-forward e merge com commit de merge, sem necessidade de laboratório externo.

## O que você vai produzir

Um cenário de merge (fast-forward e não fast-forward) que você mesmo cria, com uma explicação de por que cada um se comportou daquele jeito a partir do grafo de commits.

## Como mostrar o que aprendeu

A evidência esperada é a saída de `git log --graph` de cada cenário, acompanhada da sua explicação escrita.

## Para concluir esta etapa

- [ ] Explicar a diferença entre fast-forward merge e merge com commit de merge.
- [ ] Reconstruir o mapa visual de duas branches se unindo.
- [ ] Executar os dois tipos de merge em um repositório de teste.
- [ ] Reconhecer o papel do ancestral comum na decisão do Git.
- [ ] Alcançar a pontuação mínima da avaliação sem um equívoco crítico.

## Avaliação

Quando esta aula estiver pronta, o link direto da avaliação aparecerá aqui, e você poderá escrever:

`Terminei Merge: unindo histórias de trabalho. Avalie minhas respostas.`

## Fontes principais

### Essenciais

- Chacon, S.; Straub, B. *Pro Git*, capítulo 3 "Git Branching — Basic Branching and Merging" — https://git-scm.com/book/en/v2/Git-Branching-Basic-Branching-and-Merging

### Para aprofundar

- Documentação oficial `git-merge` — https://git-scm.com/docs/git-merge
