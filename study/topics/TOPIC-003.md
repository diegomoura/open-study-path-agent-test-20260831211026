---
id: TOPIC-003
title: "Merge: unindo histórias de trabalho"
status: eligible_after_prerequisites
content_status: materialized
content_version: 1
materialized_at: "2026-09-02T23:18:53Z"
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
module: study/modules/merge-unindo-historias-de-trabalho.md
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

A aula completa está pronta: [Merge: unindo histórias de trabalho](../modules/merge-unindo-historias-de-trabalho.md). Ela ensina a diferença entre fast-forward e merge commit, o papel do ancestral comum, e como ler o histórico resultante de um merge.

## Prática

A prática guiada e a prática independente ficam dentro da aula — não há laboratório externo separado para esta etapa.

## O que você vai produzir

Dois cenários de merge que você mesmo cria (um fast-forward, um com merge commit), com a saída de `git log --oneline --graph --all` de cada um e uma explicação de por que cada um se comportou daquele jeito, a partir do ancestral comum.

## Como mostrar o que aprendeu

Envie os dois cenários, a saída de terminal de cada um e sua explicação no formulário de avaliação. A saída de terminal colada como texto (ou um link para um gist) já é suficiente como evidência.

## Para concluir esta etapa

- [ ] Explicar a diferença entre fast-forward merge e merge com commit de merge.
- [ ] Reconstruir o mapa visual de duas branches se unindo.
- [ ] Executar os dois tipos de merge em um repositório de teste.
- [ ] Reconhecer o papel do ancestral comum na decisão do Git.
- [ ] Alcançar a pontuação mínima da avaliação sem um equívoco crítico.

> Marcar as atividades acima ajuda a acompanhar o avanço; a etapa é concluída depois da avaliação enviada e corrigida.

## Avaliação

Quando terminar a aula, abra a avaliação (link direto disponível dentro da aula) e, depois de enviar, escreva no chat:

`Terminei Merge: unindo histórias de trabalho. Avalie minhas respostas.`

## Fontes principais

### Essenciais

- Chacon, S.; Straub, B. *Pro Git*, capítulo 3 "Git Branching — Basic Branching and Merging" — https://git-scm.com/book/en/v2/Git-Branching-Basic-Branching-and-Merging

### Para aprofundar

- Documentação oficial `git-merge` — https://git-scm.com/docs/git-merge
- GitHub Docs, "About pull request merges" — https://docs.github.com/en/pull-requests/collaborating-on-pull-requests/incorporating-changes-from-a-pull-request/about-pull-request-merges
- Learn Git Branching (visualização interativa) — https://learngitbranching.js.org/
