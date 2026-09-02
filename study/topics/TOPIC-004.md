---
id: TOPIC-004
title: "Rebase: reescrevendo o histórico com segurança"
status: eligible_after_prerequisites
content_status: planned
content_version: 0
materialized_at: null
difficulty: beginner
estimated_hours: 1.4
prerequisites:
  - TOPIC-002
learning_outcomes:
  - id: LO-1
    statement: "Usar git rebase para reaplicar commits de uma branch de feature sobre outra base."
    required_concepts:
      - "git rebase"
      - "reescrever histórico"
  - id: LO-2
    statement: "Explicar por que o rebase gera novos commits/hashes e comparar o histórico antes/depois de um rebase."
    required_concepts:
      - "novos hashes após rebase"
      - "comparação de histórico antes/depois"
  - id: LO-3
    statement: "Aplicar a golden rule do rebase para decidir quando rebasear é seguro e quando é arriscado."
    required_concepts:
      - "golden rule do rebase"
      - "histórico já compartilhado"
module: study/modules/TOPIC-004.md
assessment: study/assessments/TOPIC-004.yml
assessment_form: .github/ISSUE_TEMPLATE/assessment-topic-004.yml
---

# TOPIC-004 — Rebase: reescrevendo o histórico com segurança

## O que você vai aprender

Você vai conseguir usar `git rebase` para reaplicar seus commits sobre outra base, entender por que isso reescreve o histórico (gerando novos commits e novos hashes), e saber quando usar e quando **não** usar rebase.

## Por que isso importa para você

Este é o ponto central do seu objetivo declarado: você nunca usou rebase de verdade e tem só um palpite conceitual, mas o time que você está entrando usa rebase no dia a dia. Esta etapa parte do zero prático, com laboratório guiado, apoiada no que você já sabe sobre branches e HEAD (Aula 02).

## O que você já precisa saber

- **Aula 02 — Branches e HEAD como ponteiros:** você precisa já conseguir explicar o que é uma branch e um commit para entender o que significa "reaplicar" commits sobre outra base.

## Seu plano para esta etapa

- [ ] Recuperar o que já sabe sobre branches divergentes (10 min)
- [ ] Estudar o que o rebase faz e por que ele gera novos hashes (20 min)
- [ ] Praticar um rebase guiado, comparando o histórico antes/depois (25 min)
- [ ] Estudar a golden rule do rebase e quando evitá-lo (15 min)
- [ ] Aplicar o conceito a um cenário novo e registrar a decisão tomada (14 min)

## Aula

Esta aula será preparada automaticamente quando você concluir os pré-requisitos desta etapa. Você não precisa pedir a geração manualmente.

## Prática

A prática guiada e a prática independente vão ficar dentro da aula, incluindo um laboratório de rebase de uma branch de feature sobre uma branch atualizada.

## O que você vai produzir

Um rebase real de uma branch de feature sobre uma base atualizada, com uma comparação escrita do histórico antes e depois, e uma justificativa de quando o rebase feito foi apropriado.

## Como mostrar o que aprendeu

A evidência esperada é a saída de `git log --oneline --graph` antes e depois do rebase, acompanhada da sua justificativa escrita.

## Para concluir esta etapa

- [ ] Explicar por que o rebase reescreve o histórico (novos hashes).
- [ ] Reconstruir o mapa visual de commits sendo reaplicados sobre outra base.
- [ ] Executar um rebase real em um repositório de teste.
- [ ] Aplicar a golden rule do rebase para decidir quando não rebasear.
- [ ] Alcançar a pontuação mínima da avaliação sem um equívoco crítico.

## Avaliação

Quando esta aula estiver pronta, o link direto da avaliação aparecerá aqui, e você poderá escrever:

`Terminei Rebase: reescrevendo o histórico com segurança. Avalie minhas respostas.`

## Fontes principais

### Essenciais

- Chacon, S.; Straub, B. *Pro Git*, capítulo 3.6 "Git Branching — Rebasing" — https://git-scm.com/book/en/v2/Git-Branching-Rebasing

### Para aprofundar

- Documentação oficial `git-rebase` — https://git-scm.com/docs/git-rebase
