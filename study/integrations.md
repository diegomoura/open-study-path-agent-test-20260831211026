---
version: 1
status: proposed
generated_at: "2026-09-02T00:00:00Z"
source_of_truth: github
---

# Ferramentas que podem ajudar nesta trilha

Este plano mostra só o que tem utilidade concreta para a sua trilha de Git e GitHub. Tudo funciona direto pelos materiais do GitHub — nenhuma ferramenta opcional é obrigatória para estudar ou ser avaliado.

## Visão rápida

| Para quê | Ferramenta | Por que pode ajudar | É necessária? | Alternativa |
| --- | --- | --- | --- | --- |
| Acompanhar as etapas | GitHub Issues | Você já pediu uma experiência simples, sem ferramentas extras | sim | roadmap no repositório |
| Reservar horários fixos | nenhuma por enquanto | Você ainda não decidiu sobre rotina | não | nenhum calendário |
| Receber lembretes flexíveis | nenhuma por enquanto | Você ainda não decidiu sobre rotina | não | acompanhamento no quadro de tarefas |

## Preferência de conexão

Você optou por decisões contextuais por ferramenta (não pediu para evitar toda conta externa). Isso significa que, se uma ferramenta opcional puder ajudar em um momento concreto da trilha, o controle de conexão pode aparecer — mas nunca é ativado sem um clique seu.

## Rotina de estudo

Você marcou "decidir depois" (`decide_later`) sobre uso de calendário ou lembretes no intake. Por isso, nenhum lembrete ou bloco de calendário é criado agora. Se, mais adiante, você quiser lembretes recorrentes (Todoist) ou blocos fixos de estudo (Google Calendar), basta pedir e as informações que faltarem (dias, horário, duração, fuso) serão perguntadas antes de qualquer ativação.

## Como cada ferramenta será usada

### GitHub Issues — acompanhamento das etapas

- **Por que faz sentido para você:** no intake, você escolheu explicitamente "GitHub Issues, experiência simples" como preferência de organização.
- **Como será usada:** cada aula da trilha (Aula 01 a Aula 08) vira uma Issue própria, com o título `Aula NN · <título>`, os pré-requisitos diretos listados e os links de aula/avaliação. A Issue muda de estado conforme você avança.
- **Quando entra em cena:** na próxima etapa da trilha, quando as tarefas forem organizadas ("Organize minha trilha nas ferramentas que escolhemos").
- **O que será compartilhado:** só título, descrição, rótulos e estado da Issue — nenhum dado pessoal além do necessário para navegação.
- **Sem esta ferramenta:** o roadmap em `study/roadmap.md` e os contratos em `study/topics/` continuam sendo a fonte completa da trilha.
- **Acesso:** já disponível neste repositório GitHub; não exige conta nova.

### Consensus — apoio a pesquisas (opcional, sob demanda)

- **Por que faz sentido para você:** pode ajudar caso surja uma dúvida sobre alguma prática de mercado em fluxos de Git de times reais.
- **Como será usada:** apenas como apoio pontual de pesquisa; a fonte original (documentação oficial, Pro Git) continua sendo a referência registrada em cada aula.
- **Quando entra em cena:** somente se uma dúvida concreta durante o estudo justificar, nunca de forma automática.
- **O que será compartilhado:** nenhum dado além da pergunta de pesquisa pontual.
- **Sem esta ferramenta:** a trilha já cita fontes primárias e oficiais em cada aula.
- **Acesso:** opcional, ativado apenas sob demanda.

## E-mail sob demanda

Gmail e Outlook não são configurados agora. Se você quiser um resumo da sua trilha por e-mail em algum momento, é só pedir — a comunicação principal continua sendo este chat.

## Ferramentas que não foram escolhidas

Calendário, lembretes, controle de hábitos, workspace de artefatos, Airtable e visualização externa (Whimsical) não foram ativados porque a trilha ainda não tem sinal concreto de necessidade para eles e você pediu uma experiência simples. Nada disso bloqueia o estudo ou a avaliação.

## Detalhes operacionais

<details>
<summary>Ver contrato técnico de integrações</summary>

- account_connections: `ask_per_provider`
- routine mode: `decide_later` (nenhum detalhe de calendário/lembrete coletado ainda)
- task fallback order: `github_issues` (selecionado) → `markdown` (fallback interno do repositório)
- integration constraints preservadas do intake: `experience_preference: minimal`

Capacidades ativadas nesta fase de geração: nenhuma escrita externa foi realizada — apenas este plano e o roadmap. A publicação real das Issues acontece na próxima fase (`publish`), respeitando `state/integrations.json`.

Para cada capacidade realmente ativada na publicação, o registro em `state/integrations.json` seguirá: provider, decision (`selected`/`recommended`/`declined`/`unavailable`), preflight (`required_for_selected_publication`/`optional_current_action`/`not_enabled`), authority boundary, fallback, dados mínimos e status de sincronização.

GitHub permanece responsável por currículo, conteúdo, avaliação e progresso verificado. Apenas o GitHub Issues mantém o estado de execução nesta trilha. Mermaid permanece a representação visual versionada no roadmap e nos módulos.

</details>

## Estado e idempotência

Nenhum recurso externo foi criado durante a geração da trilha. `state/integrations.json` permanece com `resolution.status: not_started` até a próxima fase de publicação, que vai criar exatamente uma Issue por etapa aprovada do roadmap (incluindo aulas futuras, sem links quebrados) e registrar o fingerprint do roadmap aprovado.
