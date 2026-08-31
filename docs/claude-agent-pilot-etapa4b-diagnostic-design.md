# Agent pilot: Etapa 4b — `diagnostic` (design fechado, harness implementado)

Status: **fechada.** Harness implementado e validado com uma sessão real
(4 turnos + 1 achado de infraestrutura contornado -- seção 6). Testado
offline (39 casos em `test_agent_runtime.py` + 2 em
`test_build_diagnostic_context.py`).

## 1. Por que `diagnostic` não cabe no harness atual

`instructions/20-diagnostic.md` é explícito: "Ask exactly one short
question or practical task at a time... Do not present the entire
questionnaire at once... Ask the next question directly when no
clarification is required." Isso é uma sessão real, com um humano
respondendo turno a turno -- não um "author isolado escreve arquivo,
reviewer confere diff" de disparo único.

O harness atual (`scripts/agent_runtime.py`, `run_agent()`) é fechado: uma
chamada de API, um conjunto de tool calls, termina em `finish_phase()`. Não
existe "aluno respondendo no meio do loop". Rodar isso sem humano
significaria o agente simulando as próprias respostas do aluno -- o que não
testa nem produz nada real.

## 2. Resolução: gatilho por `issue_comment`, não `workflow_dispatch`

As outras fases usam `workflow_dispatch`: um humano aperta "Run workflow",
o job roda do início ao fim sem interrupção. `diagnostic` precisa de um
gatilho que aconteça **a cada resposta do aluno**, não uma vez só. GitHub
Actions já tem esse gatilho: `issue_comment: [created]`.

Desenho:

1. Ao final de `intake`, uma issue é criada (ou reaproveitada) representando
   a sessão de diagnóstico, com uma label própria (`diagnostic:in-progress`).
2. O aluno responde a cada pergunta como **comentário** nessa issue -- não
   em chat, não em outro canal. A thread de comentários *é* a sessão.
3. Um novo comentário do aluno na issue dispara o workflow, filtrado pela
   label (`if: contains(github.event.issue.labels.*.name,
   'diagnostic:in-progress')`).
4. Cada disparo é uma chamada de author **isolada**, sem memória de sessão
   -- ela reconstrói o estado inteiro lendo a thread de comentários da
   issue (`list_issue_comments`), a mesma disciplina que já vale para
   `intake`/`publish`: contexto vem de artefatos, nunca de "lembrança".
   Isso é mais consistente com a filosofia do resto da proposta do que
   pareceria à primeira vista -- só muda o evento que dispara, não o
   princípio de isolamento de contexto.
5. A cada turno, o author decide, com base na thread reconstruída e no
   contrato de `instructions/20-diagnostic.md` (orçamento de perguntas,
   regra de parada):
   - evidência insuficiente → posta a próxima pergunta como comentário
     novo na issue (tool `post_issue_comment`, escopo restrito a essa
     issue e a essa label, mesmo princípio do `label_github_issue`
     restrito a uma única label em `intake`);
   - evidência suficiente → executa a operação de repositório de verdade
     (escreve `state/diagnostic-summary.json`, atualiza
     `.open-study-path/instance.yml`, abre PR) e posta a resposta de
     conclusão como comentário final.
6. O reviewer isolado (`diagnostic` profile, já existente em
   `scripts/review_framework.py`) roda **só no turno final** -- quando o
   author decide que a evidência é suficiente e abre PR -- não a cada
   pergunta. Isso evita custo de API a cada troca e mantém o padrão
   "reviewer nunca vê o raciocínio do author, só o resultado final".

## 3. Por que isso não é um ajuste incremental

Comparado a estender `intake`/`publish`, isso muda:

- o **evento de gatilho** (`issue_comment` em vez de `workflow_dispatch`) --
  workflow YAML novo, não uma opção a mais no existente;
- a necessidade de **tooling de comentário** (`list_issue_comments`,
  `post_issue_comment`), não coberto pelo tool set de GitHub Issues já
  existente (que só lê/rotula issues, nunca posta comentário);
- uma lógica de **orçamento de perguntas persistido entre turnos** (contar
  quantas perguntas já foram feitas, checar `owner_requested_comprehensive`,
  aplicar a regra de parada de `instructions/20-diagnostic.md`) que precisa
  ser reconstruída da thread a cada chamada -- não existe hoje um padrão no
  harness para "estado que persiste implicitamente numa conversa pública do
  GitHub" como este;
- validação real exigiria simular várias trocas de comentário reais
  (dispatches múltiplos por sessão de teste), não um único dispatch como
  bastou para `intake`/`publish`.

Isso é dimensionalmente parecido com o trabalho que intake+publish já
levaram juntos -- por isso fica registrado como sua própria etapa
("Etapa 4b"), não como algo que bloqueia ou precisa terminar antes da
Etapa 5.

## 4. Decisão registrada

- Formato: **turn-based via `issue_comment`**, não multi-turn dentro de uma
  única chamada de API, não `workflow_dispatch` de disparo único.
- Escopo de implementação: **fora desta sessão de trabalho**. Fica
  documentado como próximo passo elegível a qualquer momento, sem bloquear
  `generate` (Etapa 5, proposta seção 7 passo 5).
- `docs/claude-agent-pilot.md` §Scope aponta para este documento em vez de
  descrever `diagnostic` como "pendente de decisão" -- a decisão já foi
  tomada.

## 5. O que foi implementado

Implementação real do desenho acima, sem desvios de arquitetura.

### 5.1 Harness (`agent_runtime.py`)

- Allowlist: `.open-study-path/instance.yml`, `state/diagnostic-summary.json`
  -- direto de `instructions/20-diagnostic.md`'s "Diagnostic pull-request
  policy", cross-checado contra `scripts/review_framework.py`'s próprio
  `_allowed_domain_path` para o profile `diagnostic` (batem exatamente).
- Agente `diagnostic` (author, `sonnet` -- já cadastrado em `AGENT_CATALOG`).
- Dois tools novos, exclusivos do author (o reviewer não ganha nenhum):
  `list_issue_comments(number)` (lê a thread inteira) e
  `post_issue_comment(number, body)` (posta pergunta ou resposta de
  conclusão).
- `diagnostic` entra em `PHASES_WITH_GITHUB_ISSUES` (para ganhar
  `github_request`/`repository`), mas é explicitamente excluído do bloco
  genérico que dá tools de leitura de issue ao *reviewer* -- a instrução
  exige que o reviewer reconstrua a conclusão só a partir do resumo
  persistido, nunca da transcrição bruta.
- Guard estrutural real em `finish_phase`: recusa terminar um turno de
  `diagnostic` sem que `post_issue_comment` tenha sido chamado antes. Isso é
  deliberadamente mais fraco que os guards de `intake`/`publish` (que travam
  em cima de um resultado determinístico de classificação) -- aqui não
  existe sinal determinístico de "evidência suficiente", a decisão é
  julgamento do modelo. O guard garante só que nenhum turno termina em
  silêncio, não que o julgamento em si estava certo.

### 5.2 `scripts/build_diagnostic_context.py`

Novo. Busca o corpo da issue + todos os comentários via API do GitHub e
monta um texto único (`render_transcript()`) que vira o `extra_context` do
author -- é o mecanismo completo de "memória" entre turnos, já que cada
invocação é um processo novo sem estado nenhum. Testado offline (2 casos).

### 5.3 `build_agent_prompt.py`

- `--extra-context-file` novo na CLI: le o contexto de um arquivo em vez de
  um argumento de shell -- necessário porque uma transcrição de várias
  perguntas/respostas pode ter aspas e quebras de linha, inseguro como
  argumento único de shell (mesmo raciocínio que já levou `EXTRA_CONTEXT` a
  ser passado via `env:` no workflow original, agora um passo além).
- `instructions/20-diagnostic.md` + `21-diagnostic-completion-recovery.md`
  como contrato; review profile `diagnostic` (5 checks:
  `evidence_basis`, `bounded_questioning`, `adjacent_experience_separation`,
  `placement_consistency`, `privacy_and_minimization`).
- Nota de escopo do author: passo a passo explícito do turno (ler a thread
  primeiro sempre, decidir suficiência, postar pergunta OU concluir),
  adaptando o contrato -- escrito assumindo um chat ao vivo -- para o
  formato real "um processo novo por resposta do aluno".
- Nota de escopo do reviewer: reforça que não há tools de issue disponíveis
  de propósito, e que evidência fraca no resumo já é, por si, um achado
  (`placement_consistency`), não motivo para tentar investigar a conversa
  original.

### 5.4 Workflow novo (`.github/workflows/agent-pilot-diagnostic.yml`)

Não é uma opção a mais no workflow existente -- é um arquivo próprio,
porque o modelo de gatilho e a semântica de sucesso/falha são
fundamentalmente diferentes:

- Gatilho `issue_comment: [created]`, não `workflow_dispatch`.
- Guardas: só roda se (a) o comentário foi numa *issue*, não numa PR
  (`issue_comment` dispara para os dois no modelo do GitHub); (b) a issue
  tem a label `diagnostic:in-progress`; (c) quem comentou não foi o próprio
  bot -- sem isso, a pergunta/resposta que o author posta re-dispararia o
  workflow nele mesmo, um loop infinito real.
- `TARGET_REPO` é sempre `github.repository` (nunca de input) -- mesma
  fronteira de segurança de todas as outras fases.
- **Diff vazio não é falha aqui** -- é o resultado normal da maioria dos
  turnos (o author só postou a próxima pergunta). Um novo step "Check
  whether this turn completed the diagnostic" define
  `completed=true/false` como output do job; o job do reviewer só roda
  quando `completed=true` (`needs.author.outputs.completed == 'true'`).
- Ao completar (turno terminal), a label `diagnostic:in-progress` é
  removida **antes** do commit -- fecha a janela onde uma resposta
  tardia/duplicada do aluno poderia disparar um segundo turno contra uma
  sessão já resolvida.
- **Limitação conhecida, mesma categoria já documentada para
  `intake`/`publish`**: a resposta de conclusão é postada como comentário
  pelo *author*, antes do reviewer isolado confirmar. Se o reviewer
  bloquear (`action_required`), o aluno já viu a mensagem de conclusão
  mesmo assim -- efeito colateral imediato, independente do PR ser
  mergeado.

### 5.5 O que falta para "validado"

Diferente de todas as fases anteriores, validar isso de verdade exige
simular idas e vindas reais de comentário (não um único
`workflow_dispatch`): criar uma issue de sessão com a label
`diagnostic:in-progress`, postar uma resposta, conferir que o workflow
dispara e posta a próxima pergunta, repetir até a conclusão, e então
aplicar o mesmo critério de sempre (hash na mão, custo real, revisão
isolada).

## 6. Validação real (4 turnos + 1 achado de infraestrutura; fechada)

Status: **fechada.** Sessão real de diagnóstico simulada issue #17 do
repositório de teste, aluno com perfil real (Python/JS profissional,
TypeScript/tsc no dia a dia, zero experiência em Go).

### 6.1 Turnos 1-3 -- funcionaram perfeitamente

- **Turno 1** (comentário inicial "pronto para começar"): author declarou o
  orçamento (até 5 perguntas), fez a pergunta 1. Diff vazio, job do
  reviewer corretamente pulado (`needs.author.outputs.completed != 'true'`).
- **Turno 2**: reconstruiu a thread inteira sozinho, fez a pergunta 2
  coerente com a resposta anterior. Diff vazio de novo, reviewer pulado.
- **Turno 3**: idem, pergunta 3 bem direcionada (buscando o sinal prático
  que faltava).

Em nenhum desses 3 turnos o author teve acesso a nada além do
`list_issue_comments` -- confirma que a reconstrução de estado a partir da
própria thread funciona exatamente como desenhado.

### 6.2 Turno 4 -- author concluiu certo, achado real de `max_tokens` (mesma classe do `generate_detailed`)

Com só 3 perguntas (dentro do orçamento `target_min`), o author decidiu
evidência suficiente, escreveu `state/diagnostic-summary.json`, removeu a
label `diagnostic:in-progress` **antes** do commit (exatamente como
desenhado), abriu branch. O **reviewer** estourou `stop_reason: max_tokens`
-- `diagnostic` nunca tinha sido adicionado a `PHASE_MAX_TOKENS` (mesmo bug
de omissão que `generate_detailed` teve, não corrigido por analogia na
hora). Corrigido: `diagnostic` também ganha 16384.

### 6.3 Achado de infraestrutura: `rerun-failed-jobs` não preserva `needs.*.outputs`

Tentativa de aplicar o fix diretamente no branch já criado pelo author e
re-rodar só o job do reviewer via API (`rerun-failed-jobs`) falhou duas
vezes sem gerar log nenhum (`BlobNotFound`) -- o job parece falhar antes
mesmo do checkout, sugerindo que `needs.author.outputs.branch/base_sha`
não sobrevive a um rerun parcial que exclui o job que os produziu. Não é
bug deste harness; é uma limitação real do próprio recurso do GitHub
Actions. Contornado com um turno inteiramente novo (label reaplicada,
mais um comentário) em vez de insistir no rerun parcial.

### 6.4 Resultado final -- aprovado, hash conferido

Turno de retry: author reconheceu a mesma evidência (3 perguntas já
respondidas na thread) como suficiente, re-escreveu
`state/diagnostic-summary.json` com o conteúdo real da sessão -- e
corretamente **não** re-escreveu `.open-study-path/instance.yml`, porque
`status.diagnostic_complete: true` já estava lá desde o fixture sintético
construído para a Etapa 5 (o reviewer notou isso explicitamente como nota
de escopo, não como falha).

Reviewer isolado: `status: approved`, 5/5 checks `passed`, achados
substantivos e específicos (citou as 3 perguntas reais, confirmou que
experiência adjacente em Python/JS/TypeScript não foi confundida com
domínio de Go, notou a experiência superficial em Java corretamente
registrada como lacuna e não como competência). Achado extra: o reviewer
avaliou com nuance a própria narrativa do retry (mencionada no resumo do
author) como "não verificável só pelos artefatos, mas consistente" --
nem ignorou, nem superreagiu.

Hash de `state/diagnostic-summary.json` conferido na mão -- bate. Custo
real do turno que fechou: **$0.3580** (author $0.1326 + reviewer $0.2254,
Sonnet, 249.748 tokens combinados).

### 6.5 Fechamento

`diagnostic` está validado de ponta a ponta: reconstrução de estado sem
memória entre turnos, orçamento de perguntas respeitado, guard de
`finish_phase` nunca testado a ponto de disparar (todos os turnos postaram
comentário corretamente), diff vazio tratado como sucesso normal, label
removida no momento certo, revisão isolada substantiva e correta.
