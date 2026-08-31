# Configuração de modelo por agente

Esta é a fatia 1 de uma proposta maior de migração para agentes reais executados via API
(ver a proposta de trabalho compartilhada fora do repositório). Aqui existe apenas a
**lógica de resolução de modelo** — qual modelo Claude cada papel de agente deve usar — e
sua validação. Nenhuma chamada de API acontece a partir destes arquivos ainda; isso é
trabalho de uma etapa futura, quando as fases do `instructions/manifest.yml` passarem a
rodar como workflows do GitHub Actions em vez de uma conversa manual.

## Arquivos envolvidos

- `templates/agent-models.yml` — configuração padrão, com todo `model_overrides` em `null`
  (tier recomendado). `instructions/00-bootstrap.md` copia este arquivo para
  `.open-study-path/models.yml` durante o bootstrap de uma instância, quando esse arquivo
  ainda não existir — nunca sobrescrevendo uma instância já configurada.
- `.open-study-path/models.yml` — configuração real de uma instância. Opcional: na ausência
  dele (por exemplo, uma instância criada antes desta automação existir), todo agente usa o
  tier recomendado.
- `schemas/agent-model-config.schema.json` — schema JSON validado em CI.
- `scripts/agent_model_resolution.py` — lógica pura (sem I/O) que resolve o modelo efetivo
  de cada agente a partir do dial global e dos overrides. Já é consumida diretamente por
  `scripts/agent_runtime.py` para escolher o modelo real de cada chamada de API de um
  dispatch do harness (`.github/workflows/agent-pilot-setup.yml`).
- `scripts/validate_model_config.py` — CLI que valida o schema e imprime a resolução efetiva.
- `scripts/model_config_review_note.py` — roda no job revisor de um dispatch real
  (`.github/workflows/agent-pilot-setup.yml`) e persiste os avisos estruturais, se houver
  algum, em `state/reviews/model-config-warnings.md`; o conteúdo também é anexado ao corpo
  do pull request via `scripts/format_pr_body.py`. Sem aviso nenhum, nenhum arquivo é escrito
  (e um arquivo obsoleto de um dispatch anterior é removido).

## O dial (`reasoning_tier`)

Um ajuste global de três posições:

- `economy` — um degrau abaixo do recomendado em cada agente (nunca abaixo de `haiku`).
- `recommended` — usa exatamente o tier recomendado da tabela abaixo. Padrão.
- `maximum` — um degrau acima do recomendado em cada agente (nunca acima de `opus`).

## Overrides por agente (`model_overrides`)

Cada entrada aceita `null` (herda do dial) ou um tier explícito (`haiku`, `sonnet`, `opus`),
sobrescrevendo o dial só para aquele agente.

## Tabela de agentes e tier recomendado

| Agente | Fase | Papel | Tier recomendado | Estrutural? |
|---|---|---|---|---|
| `bootstrap` | bootstrap_instance | autor | haiku | não |
| `configure_intake` | configure_intake | autor | haiku | não |
| `intake_resolution` | intake | autor | haiku | não |
| `diagnostic` | diagnostic | autor | sonnet | não |
| `curriculum_architect` | generate | autor | opus | **sim** |
| `curriculum_reviewer` | generate | revisor | opus | **sim** |
| `content_author` | generate / evaluate | autor | sonnet | **sim** |
| `content_reviewer` | generate / evaluate | revisor | sonnet | **sim** |
| `publish` | publish | autor | haiku | não |
| `integration_preflight` | publish | revisor | haiku | não |
| `evaluate` | evaluate | autor | sonnet | **sim** |
| `track` | track | autor | haiku | não |
| `replan` | replan | autor | sonnet | não |

"Estrutural" marca agentes cuja decisão é difícil de corrigir depois ou define diretamente a
densidade pedagógica do que é gerado/revisado. Configurar um desses abaixo do tier
recomendado (via dial ou override) gera um **aviso não-bloqueante** — o CI não falha, mas o
aviso fica visível em `scripts/validate_model_config.py`. É uma escolha legítima de
custo/qualidade da pessoa dona da instância, só não deve ser silenciosa.

Os três itens que este documento listava aqui como "fora do escopo" (cópia automática do
template no bootstrap, persistência do aviso estrutural em `state/reviews/` e consumo real
de `agent_model_resolution.py` pelos workflows) estão todos implementados — ver a lista de
arquivos acima.
