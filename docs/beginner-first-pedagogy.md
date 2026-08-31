# Pedagogia progressiva para pessoas iniciantes

Uma trilha pode ser tecnicamente correta e ainda começar acima do ponto em que a pessoa está. Este contrato protege a entrada conceitual, especialmente quando alguém é experiente em uma área adjacente, mas iniciante no assunto do curso.

## Nível é multidimensional

O nível declarado e o diagnóstico valem para o assunto da trilha. Experiência transferível deve acelerar exemplos, exercícios e aplicações, não eliminar fundamentos que a pessoa disse não dominar.

Exemplo: uma pessoa sênior em backend pode trabalhar cedo com APIs, observabilidade e testes, mas ainda precisa aprender desde o início o que são IA generativa, modelo, modelo de linguagem, treinamento, inferência, embeddings ou RAG quando essas lacunas foram registradas.

Nunca interprete uma lista de assuntos desejados como conhecimento prévio. “Quero aprender agentes e RAG” define escopo, não domínio.

## Progressão conceitual

Antes de explicar o mecanismo interno ou pedir aplicação profissional:

1. diga em linguagem comum o que é o objeto estudado;
2. expanda siglas na primeira ocorrência visível;
3. defina os termos indispensáveis antes de usá-los para definir outros termos;
4. diferencie conceitos vizinhos que costumam ser confundidos;
5. mostre por que o conceito existe e onde aparece;
6. construa uma intuição;
7. só então apresente detalhes técnicos, limites e implementação.

Para uma aula iniciante, a sequência normalmente inclui:

- `## Começando do zero`;
- `### Vocabulário desta aula`;
- `## Intuição antes dos detalhes`;
- conteúdo técnico progressivo;
- exemplos trabalhados e prática.

A seção de vocabulário não é um glossário decorativo. Ela deve explicar os termos que a pessoa precisa para compreender a aula atual.

## Escrita que ensina

Prefira:

- uma ideia principal por parágrafo;
- primeiro a frase simples, depois o nome técnico;
- frases de transição que mostrem como uma ideia leva à seguinte;
- explicação de “por quê” antes de listas de propriedades;
- termos consistentes, sem alternar sinônimos técnicos sem necessidade;
- exemplos imediatamente após conceitos abstratos;
- retomadas curtas quando um conceito anterior é indispensável.

Evite empilhar termos novos em uma mesma frase. Quando uma frase contém vários conceitos ainda não definidos, divida a explicação e introduza cada um progressivamente.

## Analogias com limites explícitos

Use analogias quando elas reduzirem a carga cognitiva. Uma analogia deve conter:

- `**Analogia:**` — a comparação;
- `**Onde a analogia ajuda:**` — a relação útil;
- `**Onde a analogia deixa de funcionar:**` — o limite que evita uma compreensão errada.

Não force analogias em conceitos simples ou quando a comparação distorcer o mecanismo. Nesse caso, use `**Exemplo concreto:**` com uma situação reconhecível e explique diretamente o processo.

Analogia não é evidência e não substitui definição técnica, exemplo resolvido ou fonte.

## Exemplos concretos e situações do mundo real

Sempre que o tema permitir, inclua:

- ao menos um exemplo cotidiano ou uma situação reconhecível para construir intuição;
- ao menos um exemplo ligado ao objetivo ou à experiência da pessoa;
- um caso com erro, ambiguidade ou limite.

Estruture exemplos como:

1. situação;
2. mecanismo ou decisão;
3. consequência;
4. forma de verificar;
5. limite ou alternativa.

Diferencie:

- **cenário realista criado para ensino** — plausível, mas não apresentado como evento ocorrido;
- **caso real documentado** — precisa de fonte verificável;
- **analogia** — comparação parcial, com limite declarado.

Nunca invente um caso histórico, incidente, empresa, resultado ou estatística para fazer a aula parecer concreta.

## Roadmap compreensível

No primeiro ponto em que um conceito aparece no roadmap, combine o termo técnico com uma descrição curta em linguagem comum.

Exemplos:

- **Embeddings — representar conteúdos como vetores para comparar proximidade de significado**;
- **RAG — buscar informações externas antes de gerar a resposta**;
- **Evals — testar respostas com casos e critérios repetíveis**.

O roadmap pode conservar os nomes técnicos, mas não deve exigir que uma pessoa iniciante já conheça o vocabulário do curso para entender o que aprenderá.

## Revisão obrigatória

Rejeite ou corrija uma aula quando:

- uma sigla do título não é explicada antes do conteúdo técnico;
- a primeira definição usa outros termos ainda não definidos;
- experiência em uma área adjacente foi tratada como domínio do assunto;
- o texto começa pelo mecanismo sem explicar o objeto;
- conceitos abstratos não têm analogia útil nem exemplo concreto, embora isso ajudasse;
- uma analogia não declara seu limite;
- um cenário pedagógico é apresentado como caso real;
- a aula é densa o suficiente para um especialista, mas não progressiva para o nível configurado.
