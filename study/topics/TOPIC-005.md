---
id: TOPIC-005
title: "Conflitos de merge: do simples ao multi-arquivo"
status: eligible_after_prerequisites
content_status: planned
content_version: 0
materialized_at: null
difficulty: intermediate
estimated_hours: 1.4
prerequisites:
  - TOPIC-003
  - TOPIC-004
learning_outcomes:
  - id: LO-1
    statement: "Ler marcadores de conflito (<<<<<<< ======= >>>>>>>) e identificar qual lado é 'ours' e qual é 'theirs' em merge e em rebase."
    required_concepts:
      - "marcadores de conflito"
      - "ours vs theirs"
  - id: LO-2
    statement: "Resolver conflitos em múltiplos arquivos simultaneamente, verificando o resultado antes de finalizar."
    required_concepts:
      - "resolução multi-arquivo"
      - "verificação antes de finalizar"
  - id: LO-3
    statement: "Decidir entre abortar (--abort) e continuar (--continue) uma operação com conflito, com um procedimento pessoal para não entrar em pânico."
    required_concepts:
      - "git merge --abort / git rebase --abort"
      - "git merge --continue / git rebase --continue"
module: study/modules/TOPIC-005.md
assessment: study/assessments/TOPIC-005.yml
assessment_form: .github/ISSUE_TEMPLATE/assessment-topic-005.yml
---

# TOPIC-005 — Conflitos de merge: do simples ao multi-arquivo

## O que você vai aprender

Você vai conseguir resolver conflitos com método — ler os marcadores `<<<<<<< ======= >>>>>>>`, entender qual lado é qual, resolver conflitos em múltiplos arquivos ao mesmo tempo (tanto em merge quanto em rebase) e verificar o resultado antes de finalizar.

## Por que isso importa para você

É o medo que você declarou explicitamente no intake. Você já resolveu um conflito simples (um arquivo), e aqui você sobe de degrau, de forma guiada, até o conflito complexo que quer resolver "sem entrar em pânico" — usando o que você já sabe sobre merge (Aula 03) e rebase (Aula 04).

## O que você já precisa saber

- **Aula 03 — Merge:** você precisa já conseguir executar um merge e entender o que é um merge commit, porque conflitos aparecem exatamente nesse processo.
- **Aula 04 — Rebase:** você precisa já conseguir executar um rebase, porque conflitos também aparecem durante a reaplicação de commits.

## Seu plano para esta etapa

- [ ] Recuperar o que já sabe sobre merge e rebase (10 min)
- [ ] Estudar os marcadores de conflito e ours vs theirs (15 min)
- [ ] Praticar a resolução de um conflito multi-arquivo em merge (25 min)
- [ ] Praticar a resolução de um conflito multi-arquivo em rebase (25 min)
- [ ] Escrever seu procedimento pessoal para não entrar em pânico (10 min)

## Aula

Esta aula será preparada automaticamente quando você concluir os pré-requisitos desta etapa (Aula 03 e Aula 04). Você não precisa pedir a geração manualmente.

## Prática

A prática guiada e a prática independente vão ficar dentro da aula, incluindo um laboratório com conflito multi-arquivo em merge e em rebase.

## O que você vai produzir

Um laboratório com conflito multi-arquivo (em merge e em rebase) que você resolve e verifica, mais uma descrição do seu procedimento pessoal para lidar com conflitos sem pânico.

## Como mostrar o que aprendeu

A evidência esperada é o histórico e o conteúdo final dos arquivos após a resolução, acompanhados da sua explicação de cada decisão tomada.

## Para concluir esta etapa

- [ ] Ler e interpretar corretamente marcadores de conflito em um cenário novo.
- [ ] Resolver um conflito em múltiplos arquivos simultaneamente.
- [ ] Decidir corretamente entre abortar e continuar uma operação com conflito.
- [ ] Descrever um procedimento pessoal para lidar com conflitos sem pânico.
- [ ] Alcançar a pontuação mínima da avaliação sem um equívoco crítico.

## Avaliação

Quando esta aula estiver pronta, o link direto da avaliação aparecerá aqui, e você poderá escrever:

`Terminei Conflitos de merge: do simples ao multi-arquivo. Avalie minhas respostas.`

## Fontes principais

### Essenciais

- GitHub Docs, "Resolving a merge conflict using the command line" — https://docs.github.com/en/pull-requests/collaborating-on-pull-requests-with-code-quality-features/addressing-merge-conflicts/resolving-a-merge-conflict-using-the-command-line

### Para aprofundar

- Documentação oficial `git-rebase` (seção sobre conflitos) — https://git-scm.com/docs/git-rebase
