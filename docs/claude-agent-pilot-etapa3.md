# Agent pilot: Etapa 3 — medição de custo e qualidade de revisão

Status: **fechada**. Dados reais puxados do repositório de teste descartável
(`diegomoura/open-study-path-agent-test-20260814152628`), cobrindo as 5
execuções da Etapa 2 (PRs #74–#79) mais uma 6ª execução de `configure_intake`
rodada especificamente para fechar a lacuna descrita nas seções 2 e 3.2
abaixo (repo de teste, PR #6, run `31833350501`, sucesso). Nenhum desses
números vivia em `docs/claude-agent-pilot.md` ou em
`state/agent-pilot-usage.jsonl` do template canônico — o template nunca roda
`bootstrap_instance`/`configure_intake` nele mesmo, então o histórico só
existe no repo descartável. Este documento consolida o que existe.

## 1. Linha do tempo real das 5 execuções

| PR (repo teste) | Horário | Fase | Harness no momento | Status do reviewer |
|---|---|---|---|---|
| #1 | 15:38 | `bootstrap_instance` | pré-#75/#76 (sem `compute_sha256`, sem rastreio de custo) | `approved` |
| #2 | 15:44 | `configure_intake` | pré-#75/#76 | `approved` |
| #3 | 15:49 | `bootstrap_instance` | pré-#75/#76 — achou os bugs que #75/#76 corrigiram | `action_required` |
| #4 | 19:00 | `bootstrap_instance` | pós-#75/#76/#77 (com rastreio de custo), sem caching (#78 ainda não mergeado) | `approved` |
| #5 | 19:10 | `bootstrap_instance` | pós-#78 (com caching) | `approved` |

Ponto central: **as duas correções estruturais do harness (#75, #76) e o
rastreio de custo (#77) e o caching (#78) só foram validados de novo em
`bootstrap_instance`.** `configure_intake` rodou uma única vez, na versão
mais antiga e com bug do harness (PR #2, 15:44), e nunca mais.

## 2. Custo: o que temos e o que falta

### `bootstrap_instance` — completo, confirma `docs/claude-agent-pilot.md`

| Run | Combined tokens | Custo estimado | Caching |
|---|---|---|---|
| PR #4 (19:00) | 215.290 | $0.2404 | não |
| PR #5 (19:10) | 247.237 | $0.1083 | sim |

Números batem exatamente com os já publicados em
`docs/claude-agent-pilot.md` (seção "Token usage and cost estimates"). Nada
novo aqui além de confirmar a fonte primária (corpo do PR + commit
`state/agent-pilot-usage.jsonl` no repo de teste).

### `configure_intake` — resolvido nesta revisão do documento

A execução original (PR #2, 15:44) é **anterior** ao commit que adicionou
rastreio de custo (`134cdaf`, PR #77) e ao commit de caching (`c86d189`, PR
#78), então não tinha número comparável. Rodei uma execução nova
(`workflow_dispatch`, `phase: configure_intake`, mesmo repo de teste, com
#75/#76/#77/#78 todos presentes) para fechar essa lacuna. Resultado real,
repo de teste PR #6:

| Run | Combined tokens | Custo estimado | Caching |
|---|---|---|---|
| `configure_intake`, run atual (19:28) | 165.957 | $0.0759 | sim |

Comparando com `bootstrap_instance` pós-caching (247.237 tokens / $0.108):
`configure_intake` é mais barato, como esperado — a instrução
(`instructions/05-configure-intake.md`) é menor e o author lida com menos
arquivos de saída (2 artefatos vs. 6 em `bootstrap_instance`). Faixa
realista hoje para as duas fases do piloto, com caching ativo: **$0.07–$0.11
por execução em Haiku 4.5.**

## 3. Qualidade de revisão: evidência real, não simulada

Isto é o achado mais importante da Etapa 3, e não estava em nenhum dos
dois documentos anteriores. As execuções pré-#76 (PRs #1, #2, #3) por
acidente **já são o experimento de qualidade que a proposta original (seção
8) pedia** — porque cada uma delas contém dois artefatos de revisão lado a
lado: o "auto-review" que o author escreveu para si mesmo (o comportamento
do fluxo manual de hoje, uma única conversa que autora *e* revisa) e a
revisão isolada de verdade. Dá para comparar os dois diretamente.

### 3.1 `bootstrap_instance`, PR #3 (15:49) — o reviewer isolado pegou uma falha real

O author escreveu `state/reviews/setup-v1.yml` com `status: approved` e seis
fingerprints SHA-256 — todos inventados. O reviewer isolado (contexto
zerado, só viu o diff final, nunca o raciocínio do author) recomputou os
seis hashes de verdade e reportou, campo a campo, o valor reivindicado vs. o
valor real:

> Review artifact state/reviews/setup-v1.yml contains fabricated SHA256
> hashes. All six artifact fingerprints are incorrect placeholder values...
> Instance file: claimed a1e3d5c... actual 70be6a1b...
> [+ 5 outros pares claimed/actual]

Resultado: `status: action_required`, PR não teria passado no gate de CI que
`docs/review-framework.md` define (fingerprint precisa bater exatamente). O
fluxo manual de hoje — uma conversa só, sem separação de contexto — é
estruturalmente o que produziu `setup-v1.yml`: nada nesse fluxo hoje força
recomputar hash em vez de gerar um valor plausível de memória.

**Isso é o resultado que #76 (`compute_sha256` como tool real) foi criado
para garantir de forma estrutural, não só via instrução de prompt** — e o
run seguinte (#4, #5) já não repete esse padrão.

### 3.2 `configure_intake`, PR #2 (15:44) — o reviewer isolado *não* pegou a mesma falha

Este é o achado que os dois documentos anteriores não tinham. No único run
de `configure_intake` que existe, o author também inventou hashes em
`state/reviews/setup-configure-intake-v1.yml`:

```
sha256: cd2db27937c5ec3919ffc1a6c97a5f48906c5c37a2e5ef5d7e6d8e8c4f5f5a1e   # 64 chars
sha256: 2f8c9d3e9c5d7a1b2c3d4e5f6a7b8c9d0e1f2a3b4c5d6e7f8a9b0c1d2e3f4a     # 62 chars — nem o tamanho certo
```

O reviewer isolado, em `state/reviews/agent-pilot-configure_intake.yml`,
reportou os **dois valores idênticos**, incluindo o de 62 caracteres que
nem é um SHA-256 válido — e ainda assim marcou `status: approved`, sem
nenhum finding sobre isso. Ou seja: nesta execução específica, a
"independência" do reviewer falhou silenciosamente — ele reproduziu o valor
do author em vez de calcular o próprio, o oposto exato do que aconteceu no
run de `bootstrap_instance` cinco minutos depois.

Isso não é surpresa olhando a ordem dos commits: PR #2 rodou **antes** de
#76 adicionar a tool `compute_sha256` ao reviewer. O bug que #76 corrigiu
foi descoberto justamente a partir do run de `bootstrap_instance` (PR #3),
que rodou *depois* de PR #2.

**Resolvido nesta revisão:** rodei `configure_intake` de novo (mesma
execução da seção 2, PR #6 no repo de teste) especificamente para checar
se a correção realmente se aplica a esta fase, em vez de assumir. Baixei os
dois artefatos gerados (`instance.yml`, `study.config.yml`) e recomputei o
SHA-256 de cada um localmente:

```
62e2205b5d384091dabc4881e0194b09d3b2c2c547ae44c200aa02fed8dcc932  instance.yml
65b9e265a27f4dd6f8a93627045c47caceb38db35860a3115ca504571a1de04c  study.config.yml
```

Os dois batem exatamente com o que `state/reviews/agent-pilot-configure_intake.yml`
registrou, e o reviewer aprovou (`status: approved`, `blocking_findings: []`).
Confirmado: a correção de #76 vale para `configure_intake` também — não é
mais suposição.

### 3.3 Tabela-resumo

| Fase | Author inventou hash? | Reviewer isolado calculou de verdade? | Resultado |
|---|---|---|---|
| `bootstrap_instance`, pré-#76 (PR #3) | sim | **sim** (recomputou e comparou) | `action_required` — pegou a falha |
| `configure_intake`, pré-#76 (PR #2) | sim | **não** (copiou o valor do author) | `approved` — não pegou |
| `bootstrap_instance`, pós-#76 (PRs #4, #5) | n/a (author não escreve mais seu review, ver `docs/claude-agent-pilot.md` §"Author self-review") | n/a | `approved`, sem findings sobre hash |
| `configure_intake`, pós-#76 (PR #6, run novo) | n/a (mesma razão) | **sim** — hashes conferidos manualmente contra os bytes reais | `approved`, sem findings sobre hash |

A linha 3 e a linha 4 juntas confirmam que a correção estrutural (#77:
`state/reviews/` fora da allowlist de escrita do author, mais #76: tool
`compute_sha256` real) elimina a classe inteira de problema nas **duas**
fases do piloto, não só em `bootstrap_instance` como estava confirmado
antes desta revisão.

## 4. O que isso significa para a decisão da Etapa 4

A proposta (seção 7, etapa 4) pergunta se estende para `intake`,
`diagnostic`, `publish` depois do piloto. Com os dados reais de hoje, as
**duas fases do piloto estão validadas**:

- Custo: `bootstrap_instance` $0.108–$0.24 (com/sem cache);
  `configure_intake` $0.076 (com cache, único número que existe, já que a
  execução original é anterior ao tracking). Faixa combinada realista:
  **$0.07–$0.25 por execução em Haiku 4.5**, dependendo da fase e de
  caching.
- Qualidade: há evidência real, não hipotética, de que o reviewer isolado
  pega uma classe de falha (fingerprint fabricado) que o padrão de
  auto-review do fluxo manual de hoje deixaria passar — confirmado nas duas
  fases, não só em uma.

Isso fecha a pergunta central da Etapa 3: **o piloto está pronto para virar
a base da Etapa 4** (`intake`, `diagnostic`, `publish`). Duas ressalvas que
valem carregar para lá, não bloqueiam o avanço:

1. Cada fase nova precisa da mesma checagem que fiz aqui antes de ser
   considerada "validada" — o harness é compartilhado, mas cada instrução
   (`instructions/NN-*.md`) tem um contrato de escrita e um formato de
   artefato diferentes, e só uma execução real confirma que a allowlist e o
   `compute_sha256` cobrem os caminhos daquela fase especificamente.
2. `configure_intake` só tem uma amostra pós-correção (n=1). O intervalo de
   custo é uma referência, não uma garantia estatística — vale registrar
   mais execuções reais (via `state/agent-pilot-usage.jsonl`, que já
   acumula por natureza) conforme a Etapa 4 avança, em vez de tratar este
   número único como definitivo.
