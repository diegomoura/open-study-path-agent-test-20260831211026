# Agent pilot: Etapa 6 — desenho para `evaluate`/`track`/`replan`

Status: **rascunho de desenho, nada implementado**. Nenhum workflow real foi
disparado. Este documento existe para ser revisado antes de qualquer código
ser escrito, seguindo o mesmo princípio das etapas anteriores (proposta,
seção 7, passo 6) -- exceto que aqui o mapeamento vem antes da implementação,
não depois.

## 1. Por que isso não é uma fatia só

A proposta original (seção 7, passo 6) trata "estender para
`evaluate`/`replan`" como um item. Olhando `instructions/manifest.yml`
real, são **três** fases (`evaluate`, `track`, `replan`), e `evaluate`
sozinho reaproveita por dentro praticamente todo o pipeline de
`generate_detailed` (materialização, `36-`/`37-review-*`, finalização de
bundle). Por isso esta etapa é sequenciada em quatro sub-entregas, mesmo
padrão que separou Etapa 5 de 5b:

- **6a** -- `track`
- **6b** -- `replan`
- **6c** -- `evaluate`, caminho "grading apenas" (sem materialização automática)
- **6d** -- `evaluate`, caminho completo com materialização encadeada

Cada uma é validada com dispatches reais antes da próxima começar, mesmo
processo das etapas 3-5b (rodar de verdade, conferir hash na mão antes de
considerar confiável -- ver `docs/claude-agent-pilot-etapa3.md` em diante).

## 2. Achado principal: a camada determinística já existe

Diferente de `generate` (Etapa 5, seção 2 -- "isso não é reaproveitar um
motor"), a camada determinística para estas três fases **já está pronta e
testada**, de antes deste trabalho de agentes começar:

- `scripts/review_framework.py` já define os profiles `assessment`,
  `progress` e `replan` (checks e `reviewer_role` completos) e
  `phase_allows_artifact()` já restringe exatamente o diff permitido de
  cada uma.
- `scripts/task_projection_engine.py` já tem `apply_assessment_result()`
  (marca tópico `completed`/`review_required`) e
  `ensure_focused_review_resource()` (cria o recurso de recuperação
  focada) prontos para uso.
- `scripts/test_review_framework.py` já cobre os três profiles.

O trabalho desta etapa é só a camada do harness (`agent_runtime.py` +
`build_agent_prompt.py` + workflow YAML) que ainda não existe para essas
três fases -- não construir validação nova.

## 3. `track` (Etapa 6a)

### 3.1 Lacuna real: `track` não existe no sistema de configuração de modelo

Confirmado por inspeção direta: `track` **não aparece** em
`AGENT_CATALOG` (`scripts/agent_model_resolution.py`), nem em
`templates/agent-models.yml`, nem em
`schemas/agent-model-config.schema.json` (que usa
`additionalProperties: false` -- um `model_overrides.track` hoje seria
rejeitado pelo schema), nem na lista de agentes "estruturais" do
`AGENTS.md`. Isso não é uma lacuna só do harness -- é uma lacuna do
próprio desenho de configuração de modelo (proposta, seção 3/4), que
nunca cobriu esta fase.

**Decisão proposta:** dar a `track` seu próprio id de agente, tier
**Haiku**, **não** classificado como decisão estrutural. Justificativa:
no escopo restrito do pilot (só backend `github_issues`, sem
Trello/Todoist/Habitify/Reclaim reais), a fase é sincronização de estado
com regras de transição bem definidas (`50-track-progress.md`: mastery só
vem de avaliação verificada, atividade externa nunca é suficiente
sozinha) -- mesma classe de `publish`/`integration_preflight`, não de
`curriculum_architect`/`evaluate`.

Isso exige tocar (sem nenhuma chamada de API):
- `scripts/agent_model_resolution.py` -- nova linha em `AGENT_CATALOG`.
- `schemas/agent-model-config.schema.json` -- nova propriedade `track`.
- `templates/agent-models.yml` -- nova entrada `track: null`.
- `AGENTS.md` -- documentar a decisão de tier.

### 3.2 Allowlist e prompt

- Allowlist direto de `phase_allows_artifact("progress")`:
  `state/progress.json`, `state/integrations.json`. Sem prefixos.
- Nenhuma ferramenta nova: leitura de repositório + leitura do backend
  GitHub Issues (mesmo padrão de `intake`/`publish`, via
  `PHASES_WITH_GITHUB_ISSUES`) já cobre o que `50-track-progress.md`
  pede. Não precisa de `run_publish_projection` -- é leitura de estado,
  não projeção de tarefas novas.
- `PHASE_INSTRUCTION_FILES["track"] = ["instructions/50-track-progress.md"]`,
  review profile `progress`.

## 4. `replan` (Etapa 6b)

- Já tem linha em `AGENT_CATALOG` (Sonnet) e no template -- nenhuma
  lacuna de configuração aqui.
- Allowlist direto de `phase_allows_artifact("replan")`:
  `.open-study-path/instance.yml`, `study.config.yml`,
  `state/progress.json`, prefixo `study/`, mais
  `.github/ISSUE_TEMPLATE/assessment-topic-*.yml` -- praticamente a união
  de `PROPOSAL_ALLOWED_*` com um pedaço de `GENERATE_DETAILED_ALLOWED_*`.
- **Fora do escopo desta etapa:** a seção "Migration boundary" de
  `60-replan.md` pode disparar uma operação `migration` separada
  (profile `migration`, que existe em `review_framework.py` mas não
  corresponde a nenhuma fase do `manifest.yml` hoje). Se o agente de
  replan tentar sugerir uma migração, o comportamento correto nesta etapa
  é reportar isso via `finish_phase` e recusar prosseguir -- mesmo
  padrão de "recusar alto e cedo" já usado para o toggle de slides em
  `generate_detailed`.

## 5. `evaluate` (Etapas 6c e 6d)

### 5.1 Peça nova: resolvedor de issue de avaliação

Não existe hoje nenhum script equivalente a `intake_resolution.py` para a
seção "Resolve the assessment issue" de `55-evaluate-topic.md` (labels
`assessment`/`assessment:submitted`, marcador oculto
`open-study-path:assessment topic_id=TOPIC-000`, não já registrada em
`state/assessments/TOPIC-000/`, não `assessment:graded`, criada depois da
última tentativa quando existir uma anterior; estados
`unique`/`none`/`ambiguous`, nunca heurística de "issue mais nova").

Precisa de `scripts/assessment_resolution.py` novo, no mesmo espírito de
`resolve_intake_candidates`: o motor determinístico decide o estado, o
modelo nunca escolhe a issue por conta própria. Exposto no harness como
`resolve_assessment_candidates(topic_id)`, mesmo padrão de
`resolve_intake_candidates`.

### 5.2 Gatilho

`evaluate` não é multiturn como `diagnostic` -- é uma correção de uma
submissão já completa, mais parecido com `publish`/`intake` (um
`workflow_dispatch` = uma operação completa). **Decisão:** `workflow_dispatch`
com `issue_number` opcional (mesmo padrão de `55-evaluate-topic.md`, que já
trata o número da issue como fallback explícito, não obrigatório). Gatilho
por evento (`issues: labeled: assessment:submitted`) fica para depois do
pilot manual estar validado, mesmo raciocínio que adiou isso para
`intake`/`publish`.

### 5.3 Etapa 6c -- grading apenas

Escopo: resolver a issue, ler contrato/módulo/rubrica, corrigir
resposta-por-resposta, persistir `state/assessments/TOPIC-000/attempt-NNN.json`,
preparar a transição de `state/progress.json`, revisão independente com
profile `assessment`, publicar comentário e labels. **Sem** o passo
"quando dominado, materializar automaticamente a próxima janela"
(`57-materialize-next-content.md`) -- se o tópico for dominado, a fase
termina reportando que a materialização automática ainda não está
habilitada neste harness, em vez de tentar rodá-la.

Allowlist (subconjunto de `phase_allows_artifact("assessment")` que não
depende de materialização): `state/assessments/` (prefixo),
`state/progress.json`, `state/integrations.json`.

Ferramentas novas: `resolve_assessment_candidates` (5.1),
`apply_assessment_result`/`ensure_focused_review_resource` expostas como
tool wrapping o `task_projection_engine.py` (mesmo padrão de
`run_publish_projection` para `publish`), `label_github_issue` estendido
para aceitar `assessment:graded`/`assessment:recovery-required`/remover
`assessment:submitted`, `post_issue_comment` reaproveitado de
`PHASES_WITH_ISSUE_COMMENTS` (leitura/escrita de issue, não o padrão
multiturn do `diagnostic`).

### 5.4 Etapa 6d -- materialização encadeada

Só depois de 6c validado com dispatches reais. Liga
`57-materialize-next-content.md` de dentro do agente de avaliação quando
o tópico é dominado, reaproveitando o mesmo pipeline de conteúdo de
`generate_detailed` (autoria, `36-review-course-content.md`,
`38-finalize-generated-bundle.md`) -- **com slides desligados por
padrão**, mesma restrição de `AGENT_PILOT_ENABLE_SLIDES` já usada em
`generate_detailed`. Confirmado com você: slides ficam fora também aqui.

Orçamento: `evaluate` com materialização é um superconjunto de
`generate_detailed`, que já precisou de override
(`PHASE_MAX_TOKENS=16384`, `PHASE_MAX_TOOL_ITERATIONS=40`) e mesmo assim
bateu no teto real durante a Etapa 5b. Proposta: começar 6d com um teto
ainda maior (ex. `PHASE_MAX_TOOL_ITERATIONS=60`) em vez de reaproveitar o
valor de `generate_detailed` sem medir primeiro -- ajustar com base no
primeiro dispatch real, mesmo processo que gerou a tabela atual.

## 6. O que fica fora desta etapa

- Slides em qualquer parte do fluxo de `evaluate` (5.4) -- confirmado.
- Backends de tarefa além de `github_issues` (mesma restrição de
  `publish` desde a Etapa 4).
- Operação `migration` disparada por `replan` (4).
- Gatilho por evento (`issues: labeled`) para `evaluate` -- fica
  `workflow_dispatch` só, mesmo raciocínio de risco baixo já usado.

## 7. Próximo passo

Nenhum código foi escrito ainda além deste documento. Pendente sua
confirmação para começar a implementação da Etapa 6a (`track`) --
allowlist, entrada em `AGENT_CATALOG`/schema/template, `AGENTS.md`, sem
nenhuma chamada de API real até um dispatch de validação ser
explicitamente decidido com você, no repositório de teste descartável de
sempre.
