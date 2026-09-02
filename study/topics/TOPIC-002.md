---
id: TOPIC-002
title: "Branches e HEAD como ponteiros"
status: eligible_after_prerequisites
content_status: materialized
content_version: 1
materialized_at: "2026-09-02T00:00:00Z"
difficulty: beginner
estimated_hours: 0.8
prerequisites:
  - TOPIC-001
learning_outcomes:
  - id: LO-1
    statement: "Descrever tecnicamente o que é uma branch (uma referência leve que aponta para um commit) e o que é HEAD (onde você está agora)."
    required_concepts:
      - "branch como referência/ponteiro"
      - "HEAD"
      - "ref"
  - id: LO-2
    statement: "Prever o efeito de criar, trocar e apagar branches sobre os ponteiros e o histórico, incluindo fast-forward e detached HEAD."
    required_concepts:
      - "git branch"
      - "git switch / git checkout"
      - "fast-forward"
      - "detached HEAD"
  - id: LO-3
    statement: "Inspecionar para onde branches e HEAD apontam usando git log --oneline --graph e os arquivos em .git/refs."
    required_concepts:
      - ".git/refs"
      - "git log --oneline --graph"
module: study/modules/TOPIC-002.md
assessment: study/assessments/TOPIC-002.yml
assessment_form: .github/ISSUE_TEMPLATE/assessment-topic-002.yml
---

# TOPIC-002 — Branches e HEAD como ponteiros

## O que você vai aprender

Você vai conseguir descrever tecnicamente o que é uma branch (uma referência leve que aponta para um commit, não uma cópia dos arquivos) e o que é `HEAD` (o marcador de "onde você está agora"), e prever o que muda tecnicamente ao criar, trocar e apagar branches.

## Por que isso importa para você

Seu diagnóstico mostrou uma intuição correta — "branch é mais parecido com um ponteiro do que com uma cópia" — mas faltava a mecânica formal ligando branch, `HEAD` e commits. Sem essa mecânica, rebase (Aula 04) e conflitos (Aula 05) ficam confusos, porque os dois dependem de você entender exatamente o que se move quando uma branch avança.

## O que você já precisa saber

- **Aula 01 — Modelo interno do Git:** você precisa já conseguir explicar o que é um commit (um snapshot com hash) para entender o que uma branch aponta. Esta etapa não reensina blobs e trees; ela assume que você já sabe onde eles ficam.

## Seu plano para esta etapa

- [ ] Recuperar o que já sabe: revisar rapidamente o que é um commit (10 min)
- [ ] Estudar branch e HEAD como referências, não cópias (15 min)
- [ ] Inspecionar `.git/refs` e `git log --oneline --graph` no seu terminal (15 min)
- [ ] Prever e testar o efeito de criar/trocar/apagar uma branch (14 min)

## Aula

A aula completa está pronta: [Branches e HEAD como ponteiros](../modules/TOPIC-002.md). Ela ensina o que uma branch realmente é, o papel do `HEAD`, e como inspecionar essas referências diretamente.

## Prática

A prática guiada e a prática independente ficam dentro da aula — não há laboratório externo separado para esta etapa.

## O que você vai produzir

Uma previsão escrita (antes de rodar os comandos) do que vai acontecer com `HEAD` e com as branches em um cenário de criar/trocar/apagar branch, seguida da saída de terminal que confirma (ou corrige) essa previsão.

## Como mostrar o que aprendeu

Envie a previsão, a saída de terminal e uma frase final dizendo se sua previsão estava certa ou o que você errou. Isso é suficiente como evidência.

## Para concluir esta etapa

- [ ] Explicar o que é uma branch e o que é HEAD sem depender das notas.
- [ ] Reconstruir o mapa visual de branches apontando para commits.
- [ ] Prever corretamente o efeito de criar, trocar e apagar uma branch.
- [ ] Reconhecer o equívoco mais comum ("branch é uma cópia dos arquivos") e corrigi-lo.
- [ ] Alcançar a pontuação mínima da avaliação sem um equívoco crítico.

> Marcar as atividades acima ajuda a acompanhar o avanço; a etapa é concluída depois da avaliação enviada e corrigida.

## Avaliação

Quando terminar a aula, abra a avaliação (link direto disponível dentro da aula) e, depois de enviar, escreva no chat:

`Terminei Branches e HEAD como ponteiros. Avalie minhas respostas.`

## Fontes principais

### Essenciais

- Chacon, S.; Straub, B. *Pro Git*, capítulo 10.3 "Git Internals — Git References" — https://git-scm.com/book/en/v2/Git-Internals-Git-References

### Para aprofundar

- Documentação oficial `git-switch` — https://git-scm.com/docs/git-switch
- GitHub Docs, "About branches" — https://docs.github.com/en/repositories/configuring-branches-and-merges-in-your-repository/managing-branches-in-your-repository/about-branches
- Learn Git Branching (visualização interativa) — https://learngitbranching.js.org/
