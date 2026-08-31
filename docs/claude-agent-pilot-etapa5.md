# Agent pilot: Etapa 5 — extensão para `generate` (`generate_proposal` + `generate_detailed`)

Status: **`generate_proposal` fechada** (1 dispatch real, hashes conferidos,
reviewer aprovou -- seção 6). **`generate_detailed` fechada como evidência
suficiente**, sem `approved` limpo (7 dispatches reais; mecanismo de
geração + bloqueio correto pelo reviewer isolado provados, mas a última
tentativa terminou `action_required` por um gap real do author -- seção
8). Ambas restritas ao escopo já decidido: `generate_detailed` sem slides
por padrão (`AGENT_PILOT_ENABLE_SLIDES`, seção 7).

## 1. Por que fatiar `generate` em duas suboperações

`instructions/manifest.yml`'s fase `generate` já se divide em duas
suboperações reais, com `completion_check_sets` distintos:

- `proposal` (`instructions/28-propose-path.md`): só `study/roadmap.md` --
  o grafo de tópicos, pré-requisitos, esforço. Nenhum conteúdo detalhado.
- `detailed_generation` (`instructions/30-generate-path.md`): materializa,
  por tópico, contrato, módulo completo (18 elementos obrigatórios),
  rubrica, GitHub Issue Form e **um deck de slides renderizado de verdade**
  (Mermaid → SVG → HTML → PDF via `scripts/render_study_slides.mjs`, que é
  Node.js, não Python).

Essa segunda parte tem uma dependência de infraestrutura que as fases
anteriores nunca precisaram (Node.js/npm no runner do Actions, renderização
de PDF) e um volume de conteúdo pedagógico real por tópico que não é
redutível a um motor determinístico como aconteceu com `publish`. Por isso
esta etapa cobre só `proposal` -- a fatia menor, comparável em tamanho a
`intake`, que usa só Opus para uma decisão estrutural sem tocar
infraestrutura nova.

## 2. Por que isso não é "reaproveitar um motor" como `publish`

Os scripts já existentes relacionados a currículo/conteúdo/slides
(`scripts/curriculum_state.py`, `scripts/course_content_review.py`,
`scripts/study_slides.py`, os `validate_*.py`, ~2170 linhas ao todo) são
**validadores**, não geradores -- eles checam se o que o modelo escreveu
está estruturalmente correto (schema, cobertura de outcome, ciclos no grafo
de pré-requisitos), mas não escrevem o roadmap nem a aula. Isso é trabalho
de julgamento pedagógico real, que só o modelo pode fazer.

Uma vantagem prática, porém: esses validadores **já rodam automaticamente
no CI existente do repositório**, independente do workflow deste piloto --
o mesmo CI que já valida currículo hoje para o fluxo manual (ChatGPT
Project) roda em qualquer push, inclusive nos branches que este harness cria.
Não foi necessário construir nenhuma verificação nova para esta etapa.

## 3. O que foi implementado

Como `generate_proposal` só escreve arquivos de repositório (nenhuma
integração com GitHub Issues, nenhum tool novo), a extensão foi puramente
de configuração -- o mesmo formato de `bootstrap_instance`/
`configure_intake`, não o de `intake`/`publish`:

- **Allowlist** (`agent_runtime.py`): `study/roadmap.md`,
  `.open-study-path/instance.yml` -- direto da seção "Outputs" de
  `instructions/28-propose-path.md`. Nenhum outro caminho (`study/topics/`,
  `study/modules/`, `study/slides/`, `study/assessments/`,
  `.github/ISSUE_TEMPLATE/assessment-topic-*.yml`) é aceito -- esses
  pertencem à suboperação `detailed_generation`, que não existe neste
  harness ainda.
- **Agente**: `curriculum_architect` (author) / `curriculum_reviewer`
  (reviewer), ambos já cadastrados em `AGENT_CATALOG` como tier `opus`
  (`claude-opus-4-8`). O campo `phase` de `AGENT_CATALOG` para esses ids é a
  string `"generate"` (igual ao `manifest.yml`, que não separa `proposal`/
  `detailed_generation` em ids distintos) -- isso é só descritivo;
  `resolve_effective_models()` busca por id de agente, nunca pela chave de
  fase do harness, então usar uma chave própria (`generate_proposal`)
  aqui não quebra a resolução de modelo.
- **Review profile**: `curriculum` (`docs/review-framework.md`), com 7
  checks obrigatórios. Dois deles (`content_review_complete`,
  `assessment_alignment`) são sobre conteúdo materializado, que esta
  suboperação nunca cria -- o prompt do reviewer instrui explicitamente a
  marcá-los `passed` com uma nota de que não há conteúdo materializado no
  escopo desta operação, em vez de deixá-los `pending` (o que pareceria
  revisão incompleta) ou inventar achados que não se aplicam.
- **Nota de escopo no prompt do author**: como
  `instructions/30-generate-path.md` (a suboperação de materialização) está
  na mesma pasta `instructions/` e é facilmente alcançável por leitura, o
  prompt reforça explicitamente que só `study/roadmap.md` e
  `.open-study-path/instance.yml` podem ser escritos nesta execução -- o
  `write_file` recusa qualquer outro caminho independente do que o modelo
  tentar, mas a instrução deixa isso explícito também no prompt.

## 4. Testes offline

`scripts/test_agent_runtime.py` ganhou 2 casos novos (27 no total):
allowlist bate exatamente com a seção "Outputs" da instrução (incluindo a
confirmação de que os caminhos de `detailed_generation` são recusados), e a
fase não ganha nenhum tool de GitHub Issues (mesmo shape de tools que
`bootstrap_instance`/`configure_intake`).

## 5. O que falta para "validado"

Nenhum dispatch real ainda. Diferente de `intake`/`publish`, esta
suboperação não teve nenhuma dependência anterior faltando (não precisa de
fixture sintética -- `study.config.yml`/`state/intake-summary.json`/
`state/diagnostic-summary.json` já existem no repositório de teste de
rodadas anteriores, ou podem ser criados de forma mínima e realista antes
do dispatch). Fica pendente: rodar de verdade, conferir o roadmap gerado
contra os critérios de "Proposal quality" de `instructions/28-propose-
path.md`, e confirmar que o CI existente do repositório (não construído por
este piloto) valida a estrutura do currículo corretamente.

## 6. Validação real (dispatch único, fechada)

Status: **fechada.** Um dispatch real contra o repositório de teste
descartável.

### 6.1 Estado de entrada precisou ser reconstruído

Nenhuma PR anterior do repositório de teste tinha sido mergeada (todas
`bootstrap_instance`/`configure_intake`/`intake` ficaram como PR aberta,
por desenho -- o workflow nunca faz merge automático). `main` nunca teve
estado real. Além disso, **o `instance.yml` que essas PRs antigas
produziram não batia com o template canônico**
(`templates/instance.yml`): usavam `curriculum_status.diagnostic_status`
em vez de `status.diagnostic_complete`, sem os blocos `review_framework`/
`content_generation`/`study_slides` inteiros. Confirmado com
`scripts/curriculum_state.py`, que lê exatamente `status.curriculum_*` --
por isso o fixture desta validação foi reconstruído do template canônico
do zero, não copiado das PRs antigas. Como nenhuma delas foi mergeada,
não há inconsistência real em nenhum `main`, só nos branches de teste
descartados.

Fixture final commitado direto em `main` do repo de teste: `instance.yml`
no formato canônico, `study.config.yml`/`state/intake-summary.json`
reaproveitados do conteúdo real já validado na Etapa 4 (PR #8),
`state/diagnostic-summary.json` sintético, validado contra
`schemas/diagnostic-summary.schema.json`, claramente rotulado como
fixture no próprio campo `learner_context.notes` (diagnostic nunca foi
implementado neste harness).

### 6.2 Achado real: bug na tabela de preços, corrigido nesta mesma etapa

`state/agent-pilot-usage.jsonl` voltou com `estimated_cost_usd: null` para
author e reviewer. Causa raiz: `MODEL_PRICING_USD_PER_MTOK` em
`agent_runtime.py` tinha a chave `"claude-opus-5"`, mas
`agent_model_resolution.MODEL_CATALOG` resolve o tier `opus` para
`"claude-opus-4-8"` -- um mismatch silencioso de string que fazia todo
run em tier Opus reportar custo `null` em vez de errar alto. Verifiquei a
tarifa real (`$5/$25/$6.25/$0.50` por MTok, já confirmada por múltiplas
fontes independentes de pricing de Opus 4.8) -- os *valores* já estavam
certos, só a *chave* estava errada. Corrigido, e um teste de regressão
novo (`test_pricing_table_covers_every_resolvable_model`) garante que
todo modelo resolvível em `MODEL_CATALOG` tem entrada correspondente na
tabela de preço -- esse bug não pode mais passar despercebido para um
tier novo no futuro.

Custo real recomputado com a tabela corrigida: **$1.9829** (author
$1.6462 + reviewer $0.3367), 689.423 tokens combinados. Consideravelmente
mais caro que qualquer fase em Haiku, como esperado para Opus.

### 6.3 Resultado da geração

Roadmap real gerado para "Aprender Go do zero" (7 aulas, grafo com dois
ramos paralelos -- concorrência e testes -- convergindo no serviço HTTP
final), personalizado de forma consistente com o fixture de diagnóstico
(trata experiência em Python/JS como acelerador de sintaxe, mas tipagem
estática/concorrência como genuinamente novas, batendo exatamente com
`material_caveats`/`knowledge_gaps` do fixture). Vocabulário técnico
explicado na primeira ocorrência, sem terminologia interna vazando pro
texto do aluno, esforço total honesto (~8-9h) sem prazo forçado.

`instance.yml` atualizado corretamente: `curriculum_proposed: true`,
`curriculum_approved: true`, `curriculum_generated: false`, todo o resto
do estado preservado.

Reviewer isolado: `status: approved`, todos os 7 checks do profile
`curriculum` `passed` -- incluindo os dois sobre conteúdo materializado
(`content_review_complete`, `assessment_alignment`), corretamente
marcados `passed` com nota de escopo em vez de `pending`, exatamente como
o prompt instruiu. Os 2 hashes registrados no artefato de revisão
conferidos na mão, batem exatamente.

Nenhum achado negativo desta vez -- diferente de `intake`/`publish`, este
dispatch não revelou nenhum comportamento incorreto do harness, só o bug
pré-existente da tabela de preços (não relacionado à lógica de
`generate_proposal` em si).

## 7. Extensão para `generate_detailed` (Etapa 5b, sem slides por padrão)

Status: **design implementado, testado offline, aguardando validação
real.** Segunda fatia da Etapa 5 -- a suboperação `detailed_generation`
de `instructions/30-generate-path.md` (contratos de tópico, módulos de
aula completos, rubricas, GitHub Issue Forms), restrita a **sem geração
de slides** por decisão explícita do dono da instância.

### 7.1 Por que slides ficaram de fora por padrão

`scripts/render_study_slides.mjs` é Node.js, não Python -- renderiza
Mermaid → SVG → HTML → PDF via Puppeteer. Nenhuma fase anterior deste
harness precisou de infraestrutura fora de Python/pip no runner do
Actions. Construir isso corretamente (deck de 12-24 slides, revisão
independente via `instructions/37-review-study-slides.md`, renderização
real de PDF, os 14 checks de `REQUIRED_REVIEW_CHECKS` em
`scripts/study_slides.py`) é um pedaço de trabalho comparável em tamanho
ao resto de `generate_detailed` -- por isso fica atrás de um toggle,
não implementado nesta etapa.

### 7.2 Achado de infraestrutura resolvido antes do harness: `study_slides.py` não suportava "desligado"

Antes de sequer desenhar o toggle do harness, descobri que
`scripts/validate_study_slides.py` roda **sem condição** em todo push
(`.github/workflows/validate-template.yml`, step "Validate study-slide
contract", sem `if:` -- diferente dos steps de renderização Node.js, que
só rodam se `contract_version == 3`). E `slides_enabled()` tratava
`study_slides.enabled: false` deliberado exatamente como qualquer outra
misconfiguração -- sempre erro, sem um modo "desligado" real. Corrigido
em PR #87 (mergeado, `22cf902`): nova função `slides_deliberately_disabled()`
que só retorna `True` quando `enabled` é exatamente `False` (ausência de
config continua sendo tratada como esquecimento, não opt-out), e
`validate_repository()` passa sem erros nesse caso, mesmo com tópicos
`content_status: materialized` presentes.

### 7.3 O toggle (`AGENT_PILOT_ENABLE_SLIDES`)

- Env var, default `false`/não setada -- nunca exposta como input de
  `workflow_dispatch` (ficaria fácil demais de ligar sem querer); só
  editável direto no YAML do workflow, fricção intencional ("trancada").
- `slides_toggle_enabled()` em `agent_runtime.py` lê a env var.
- Se alguém setar `true`, `main()` recusa **antes de qualquer chamada de
  API**, com uma mensagem clara ("não implementado ainda, ver
  docs/claude-agent-pilot-etapa5.md seção 7") -- confirmado na linha de
  comando, `exit code 1`, sem custo.
- O allowlist de `generate_detailed` nunca inclui `study/slides/` nem
  `state/slide-reviews/`, independente do valor da env var -- a proteção
  real está no `write_file`, não só na checagem de `main()`.

### 7.4 O que muda no harness

- **Allowlist**: `study/topics/`, `study/modules/`, `study/assessments/`,
  `state/content-reviews/`, `.github/ISSUE_TEMPLATE/assessment-*` (prefixo
  restrito o bastante pra não sombrear `create-study-path.yml`, o form de
  intake), mais `study/roadmap.md`/`.open-study-path/instance.yml`/
  `study/integrations.md` (podem ser atualizados de novo nesta fase).
- **Agente**: `content_author`/`content_reviewer`, tier `sonnet`.
- **Review profile**: `curriculum` (mesmo de `generate_proposal`) -- mas
  desta vez `content_review_complete`/`assessment_alignment` se aplicam
  de verdade, já que existe conteúdo materializado.
- **Nota de escopo do author**: lista exatamente quais dos 18 elementos
  do "Complete-content contract" se aplicam (17, sem o link de PDF),
  quais passos de outcome traceability não se aplicam (7 e 8, sobre
  slides), e reforça materializar só a janela de lookahead configurada
  em `instance.yml`'s `content_generation`, não o roadmap inteiro.
- **Nota de escopo do reviewer**: não cobrar `study/slides/`/`slides_review`
  como achado -- mas cobrar se o módulo/rubrica/Issue Form **prometer**
  um deck de slides que não existe nesta execução.

### 7.5 Testes offline

`scripts/test_agent_runtime.py` ganhou 2 casos novos (30 no total):
allowlist exclui slides mesmo com prefixos testados exaustivamente
(incluindo confirmar que `.github/ISSUE_TEMPLATE/assessment-*` não
sombreia o form de intake), e `slides_toggle_enabled()` lê a env var
corretamente em ambas as direções.

### 7.6 O que falta para "validado"

Nenhum dispatch real ainda. Diferente de `generate_proposal`, esta
suboperação precisa de um `study/roadmap.md` real como input (já existe
no repositório de teste, gerado no dispatch real da seção 6) -- não
precisa de fixture adicional além do que já foi commitado. Pendente:
rodar de verdade, conferir um tópico materializado contra os 17
elementos aplicáveis do contrato de conteúdo completo, confirmar que o
reviewer isolado aplica `instructions/36-review-course-content.md`
corretamente, e confirmar que `scripts/validate_study_slides.py` (CI do
próprio repositório) passa de verdade com `study_slides.enabled: false`
e tópicos materializados sem slides.

## 8. Validação real (7 dispatches; mecanismo provado, sem `approved` limpo)

Status: **fechada como evidência suficiente**, decisão explícita com você
de não gastar mais um dispatch para forçar um `approved` limpo agora. O
mecanismo central -- geração pedagógica real + bloqueio correto de um gap
real pelo reviewer isolado -- está provado.

### 8.1 Cronologia dos 7 dispatches

`generate_detailed` foi, de longe, a fase mais difícil de fazer rodar até o
fim neste piloto -- diferente de `intake`/`publish`/`generate_proposal`,
que funcionaram no primeiro ou segundo dispatch real.

1. **Tentativa 1**: `AgentBudgetExceeded` -- orçamento padrão de 20
   iterações (dimensionado para fases menores) insuficiente para ler ~4
   arquivos de input e escrever ~6-7 saídas. Corrigido: `PHASE_MAX_TOOL_
   ITERATIONS`, override por fase (não elevação global), `generate_
   detailed` ganha 40.
2. **Tentativa 2**: estourou de novo, mesmo com 40. Sem visibilidade
   nenhuma do que o modelo estava fazendo -- só "did not call its finish
   tool". Corrigido: `AgentBudgetExceeded` ganha `tool_call_names`, log
   completo impresso no stderr antes de falhar.
3. **Tentativa 3** (diagnóstico): revelou um modo de falha *diferente* --
   o modelo parou de produzir tool calls sem esgotar o orçamento
   (`run.finished=False` sem exceção). Corrigido: transcript passa a
   guardar `stop_reason` de cada resposta; `main()` imprime isso e o texto
   final do modelo antes de falhar.
4. **Tentativa 4**: o **author terminou com sucesso** -- materializou
   TOPIC-001 completo (contrato, módulo, rubrica, Issue Form), contratos
   corretos para todo o roadmap (`content_status: planned` nos demais),
   `study/integrations.md` coerente (preview `status: proposed`, nem
   previsto por mim ao montar a allowlist, mas correto). O **reviewer**
   estourou `stop_reason: max_tokens` (4096, default) escrevendo o
   artefato de revisão completo contra conteúdo real. Corrigido:
   `PHASE_MAX_TOKENS`, override por fase, `generate_detailed` ganha 8192.
5. **Tentativa 5**: desta vez foi o **author** que estourou `max_tokens`
   a 8192 -- um único `write_file` com um módulo de aula completo pode
   sozinho consumir a maior parte do orçamento de um turno. Antes de
   subir mais às cegas, confirmei via busca real: Sonnet 5 aceita até
   **128.000 tokens de saída** na API síncrona padrão, sem beta header, e
   `max_tokens` **não afeta custo real nem rate limit** -- é só um teto de
   resposta. Elevado para 16384.
6. **Tentativa 6**: falhou **antes de qualquer chamada de API** --
   `"Your credit balance is too low to access the Anthropic API"`. Não é
   bug de código; é o limite de gasto real da conta batendo, depois de
   todos os dispatches desta sessão (Etapas 3, 4, 5 completas). Resolvido
   por você no Console da Anthropic.
7. **Tentativa 7**: **sucesso completo**. Author e reviewer terminaram,
   PR real aberto (#16 no repo de teste). Ver seção 8.2.

### 8.2 Resultado da tentativa 7

Author materializou TOPIC-001 (mesmo conteúdo de qualidade da tentativa
4: outcomes bem mapeados, pedagogia beginner-first correta considerando o
perfil real do aluno em `state/diagnostic-summary.json`, fontes
plausíveis com locators precisos) mas **não criou
`state/content-reviews/TOPIC-001.yml`** -- a revisão independente de
conteúdo exigida por `instructions/32-generation-execution.md` como parte
da mesma operação, não um passo posterior.

O **reviewer isolado pegou isso corretamente**: `status: action_required`,
citando a instrução exata (`instructions/32-generation-execution.md`,
`instructions/36-review-course-content.md`, `instance.yml`'s
`content_review.required_for_materialized_topics: true`), e notou que o
próprio resumo do author reconhecia a omissão sem corrigi-la --
"Acknowledging the omission... is not a substitute for doing it." Deu
feedback positivo específico também (outcome markers bem posicionados,
rubrica cobrindo todos os outcomes, pedagogia executada corretamente).

3 hashes conferidos na mão (módulo, contrato de tópico, Issue Form) --
todos batem. Custo real: **$1.5870** (author $0.9754 + reviewer $0.6116,
Sonnet, 2.028.781 tokens combinados).

### 8.3 Achado de prompt, corrigido nesta mesma etapa (sem revalidar)

`AUTHOR_DETAILED_NOTE` mencionava rodar `instructions/36-review-course-
content.md` como parte do trabalho, mas não deixava claro o suficiente que
`state/content-reviews/<TOPIC-ID>.yml` é um **entregável obrigatório desta
mesma operação**, não um passo posterior opcional. Corrigido: o prompt
agora afirma isso explicitamente, citando o achado real da tentativa 7
como o que não deve se repetir. **Não revalidado com um oitavo dispatch**
-- decisão explícita de tratar a evidência já coletada (mecanismo provado,
bloqueio correto do reviewer) como suficiente por ora.

### 8.4 Custo total da validação de `generate_detailed`

Só a tentativa 7 (a única que completou e registrou uso) tem custo exato
registrado: $1.5870. As tentativas 1-5 consumiram API real sem registrar
uso (o log de custo só é escrito ao final de uma execução bem-sucedida) --
gap de visibilidade conhecido, não corrigido nesta etapa. A tentativa 6
não custou nada (falhou antes de qualquer chamada). Custo total real da
fase é maior que $1.59, mas não é possível recuperar o valor exato das
tentativas que falharam.
