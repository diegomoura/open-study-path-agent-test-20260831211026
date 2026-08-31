---
version: 1
status: proposed
generated_at: null
source_of_truth: github
---

# Ferramentas que podem ajudar nesta trilha

Este plano mostra somente ferramentas com utilidade concreta para o curso e para a rotina escolhida. Tudo continua funcionando com os materiais do GitHub quando uma ferramenta opcional não é conectada.

## Visão rápida

| Para quê | Ferramenta | Por que pode ajudar | É necessária? | Alternativa |
| --- | --- | --- | --- | --- |
| Acompanhar as etapas | substituir | substituir | sim/não | GitHub Issues ou roadmap no repositório |
| Reservar horários fixos | substituir ou nenhuma | substituir | não | nenhum calendário |
| Receber lembretes flexíveis | substituir ou nenhum | substituir | não | acompanhamento no quadro |

Não mostre nesta tabela termos internos como `selected`, `optional_current_action`, `required_for_selected_publication`, `not_enabled`, `authority` ou `sync_status`.

## Preferência de conexão

Explique em linguagem simples se a pessoa aceita sugestões contextuais de conexão ou prefere permanecer sem outras contas.

Quando `integration_preferences.account_connections` for `no_external_accounts`, registre no bloco técnico:

`account_connections: no_external_accounts`

Nesse modo, não selecione nem recomende provedores que exigem outra conta. Use GitHub Issues ou Markdown do repositório, Mermaid, arquivos do GitHub, fontes primárias ou web e chat.

## Rotina de estudo

Registre a escolha de `integration_preferences.routine`:

- `fixed_calendar`: um calendário para blocos fixos;
- `flexible_reminders`: Todoist para lembretes recorrentes flexíveis;
- `none`: sem lembretes;
- `decide_later`: nenhuma ativação agora;
- `custom`: interpretar a descrição antes de escolher.

Não selecione calendário e Todoist para a mesma função. Uma rotina escolhida só pode ser ativada quando existirem detalhes suficientes:

- calendário: dias ou datas, horário inicial, duração, fuso e calendário selecionado;
- lembretes: recorrência ou gatilho e horário quando aplicável.

Quando faltar algum dado, o plano deve registrar somente a pergunta curta necessária. Não marque o provedor como configurado.

## Como cada ferramenta será usada

Crie uma seção somente para cada ferramenta selecionada ou recomendada com valor imediato.

### <Ferramenta> — <benefício principal>

- **Por que faz sentido para você:** use sinais concretos do objetivo, diagnóstico, rotina ou formato de aprendizagem.
- **Como será usada:** descreva a operação real nesta trilha.
- **Quando entra em cena:** diga em que momento a pessoa verá valor.
- **O que será compartilhado:** liste apenas os dados mínimos em linguagem simples.
- **Sem esta ferramenta:** explique a alternativa que já funciona.
- **Acesso:** informe se exige conta ou pode ter limitações.

Não crie uma seção para uma ferramenta apenas porque ela aparece em `already_uses`.

## E-mail sob demanda

Gmail e Outlook não são configurados durante a criação ou publicação da trilha. O e-mail é uma ação disponível somente quando a pessoa pedir para enviar ou preparar um resumo.

Não registre frequência, destinatário, filtro, rascunho ou política automática sem uma solicitação explícita. Até esse momento, a comunicação principal permanece no chat.

## Ferramentas que não foram escolhidas

Não crie uma lista extensa de recusas, reservas ou possibilidades futuras. Registre internamente somente decisões necessárias para idempotência ou segurança. A resposta ao aluno não deve conter um inventário equivalente a “O restante ficou assim”.

## Detalhes operacionais

<details>
<summary>Ver contrato técnico de integrações</summary>

Esta seção existe para o agente, revisão e auditoria. Ela não deve dominar a experiência de quem estuda.

Registre primeiro:

- account_connections: `ask_per_provider` ou `no_external_accounts`;
- routine mode e detalhes disponíveis;
- task fallback order: `trello`, `github_issues`, `markdown`, ajustado pela preferência da pessoa;
- integration constraints preservadas do intake.

Para cada capacidade realmente ativada, registre:

- provider;
- decision: `selected`, `recommended`, `declined` ou `unavailable`;
- preflight: `required_for_selected_publication`, `optional_current_action` ou `not_enabled`;
- authority boundary;
- provider-independent fallback;
- minimum data;
- connection-offer eligibility;
- return command when applicable;
- required configuration still missing;
- expected terminal disposition in `state/integrations.json`.

GitHub permanece responsável por currículo, conteúdo, avaliação e progresso verificado. Apenas um backend de tarefas mantém o estado de execução. Todoist pode ser principal ou lembrete auxiliar, nunca um segundo estado concorrente. Mermaid permanece a representação visual versionada. Airtable, quando usado, é uma projeção `github_to_airtable`.

Uma oferta de conexão exige clique explícito. Exibir o controle não comprova autorização e não permite escritas externas por si só. Provedores recusados, restringidos, irrelevantes, já conectados ou proibidos por `no_external_accounts` não devem ser sugeridos.

Para notificações por e-mail, não registre `selected` durante a publicação normal. Verifique o provedor somente dentro de uma solicitação explícita de envio ou rascunho.

</details>

## Regras por tipo de recurso

### Pesquisa e fontes

Use Consensus para apoiar pesquisas empíricas quando fizer sentido, mas registre sempre a fonte original no módulo. Para tecnologia, produtos, APIs e padrões, prefira documentação oficial e fontes primárias. Siga `docs/content-quality-and-sources.md`.

### Tarefas

Trello é adequado para trilhas com várias etapas, links e checklists. GitHub Issues é o primeiro fallback operacional. Todoist pode ser mais simples. Markdown do repositório é o último fallback interno. O cartão ou registro deve falar com a pessoa, não reproduzir estado técnico.

### Agenda e lembretes

Use Google ou Outlook Calendar para blocos fixos. Use Todoist para lembretes flexíveis. Nunca ative ambos para a mesma rotina. Nenhuma presença em calendário ou tarefa comprova aprendizagem.

### Resumos por e-mail

Gmail e Outlook podem enviar ou preparar um resumo somente sob demanda. Conexão disponível não significa configuração concluída. Sem solicitação atual, mantenha chat como canal principal e não mencione e-mail na resposta de publicação.

### Vídeos, cursos e outras formas de aprender

YouTube, aulas universitárias, Coursera, edX, Udemy, Khan Academy e outros catálogos podem complementar o módulo. Selecione a aula, seção, exercício ou timestamp exato, explique por que ajuda e ofereça alternativa gratuita quando houver custo potencial.

### Entregáveis e visualizações

Google Drive ou outro workspace pode guardar entregáveis quando for o local real de trabalho. Mermaid continua suficiente para compreender o conteúdo. Ferramentas externas não devem ser a única representação necessária.

## Estado e idempotência

Registre recursos externos com identificador seguro, URL, tópico, versão, limite de autoridade e estado de sincronização em `state/integrations.json`. Não armazene tokens, credenciais, submissões brutas ou detalhes OAuth.

Cada capacidade ativada deve ter `resolution_status: resolved` ou `action_required`. Não crie entradas learner-facing para capacidades inativas. O bloco superior `resolution` deve listar exatamente as capacidades que bloqueiam ou exigem uma decisão atual.
