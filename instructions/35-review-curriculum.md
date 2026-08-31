# Internal curriculum review checklist

Run this checklist automatically inside initial generation and later materialization. Do not ask the owner for a separate generic review command.

This pass reviews **curriculum architecture**: scope, dependency graph, topic contracts, effort and the consistency of the planned learning journey. It does not replace the independent review of **materialized teaching content**. After this checklist, run `instructions/36-review-course-content.md` for every materialized topic before approval.

A valid graph can still contain a lesson that teaches the wrong subject, omits a promised concept or assesses something else. Curriculum review and course-content review are both required when the content-review contract is enabled.

Review against approved intake, diagnostic evidence, generation instructions, source-quality guidance, learner-language guidance, visual-learning guidance, integration contracts and verified assessment evidence. Read `docs/beginner-first-pedagogy.md` for beginner or vocabulary-gap paths.

## Review checklist

Confirm that:

1. the roadmap contains the complete approved dependency graph and a real Mermaid view;
2. prerequisites exist, the graph is acyclic and each topic is coherent and independently assessable;
3. topics use three to seven focused actions, normally 10–25 minutes each;
4. effort is proportionate and large separable topics are split;
5. every topic has a valid internal content status;
6. learner-facing prose says “aula pronta” or “aula futura” rather than exposing `materialized`, `planned`, rolling-window or topological terminology;
7. every ready topic has a complete module, rubric and direct Issue Form;
8. future topics do not contain broken links or pretend that detailed content exists;
9. topic headings and copy use the configured language consistently;
10. the reason each topic matters is personalized from approved evidence rather than generic motivation text;
11. every ready module teaches the content instead of merely listing activities or external readings;
12. modules contain orientation, study session, prerequisite retrieval, explanations, worked examples, misconceptions, guided practice, independent practice and active recall;
13. every module contains the configured number of useful Mermaid diagrams, introduced and explained;
14. diagrams match the subject and are not decorative;
15. each assessment has five substantial prompts and a 100-point rubric with passing score, critical misconceptions and focused recovery;
16. assessment copy is human and does not explain predictable title or issue-resolution mechanics;
17. each module links the exact instance Issue Form URL;
18. when flashcards are useful, the module links Markdown first, TSV second and an external set only when recorded;
19. local flashcard decks contain useful matching material;
20. visible completion commands use the topic title while technical topic-ID aliases remain accepted internally;
21. roadmap, topic, module, form, integration-plan and task copy follow `docs/learner-facing-language.md`;
22. successful phase responses do not require PR, CI, hash, branch or changed-file details;
23. the initial ready set follows configured thresholds and dependency order internally without exposing implementation language to the learner;
24. later materialization preserves approved objectives, prerequisites, deliverables, effort and completion criteria;
25. assessment-informed adaptation changes examples, emphasis, sources, formats and practice without silently rewriting the curriculum structure;
26. total effort remains consistent with availability without turning weekly capacity into fixed course structure;
27. scope is explicitly introductory when it cannot satisfy the full long-term goal.

Before handing materialized topics to the content reviewer, also confirm that each topic contract defines stable learning outcome IDs, required concepts and direct prerequisites. Topic numbering is an identifier and display aid; it is not evidence that the numerically previous topic is a prerequisite.

## Beginner progression and writing review

For every beginner roadmap and ready lesson, confirm that:

28. the declared subject level remains authoritative even when the learner has senior experience in another field;
29. desired subjects are treated as scope, not proof of prior knowledge;
30. new roadmap terms receive a short plain-language explanation;
31. `## Começando do zero`, `### Vocabulário desta aula` and `## Intuição antes dos detalhes` appear before technical content;
32. every title acronym is expanded and defined;
33. definitions do not depend on several terms that have not yet been introduced;
34. the text explains the object before its mechanism;
35. paragraphs avoid stacking multiple undefined concepts;
36. every lesson has a bounded analogy or labeled concrete example;
37. an analogy states where it helps and where it stops working;
38. difficult topics normally combine a recognizable example and a domain-relevant example;
39. a realistic teaching scenario is labeled as pedagogical;
40. a documented real case has a verified source;
41. flashcards contain foundational definitions and contrasts;
42. assessment verifies the central definition before advanced application.

Reject a lesson when it is technically accurate for a specialist but not progressive for the declared subject level.

## Source and content review

For every ready module, confirm that:

43. `## Como este conteúdo foi construído` explains provenance and agent-created adaptations;
44. `## Outras formas de aprender` exists and contains only useful alternatives or a brief explanation that the core practice is more appropriate;
45. `## Fontes e caminhos para aprofundar` contains normally three to seven reviewed sources;
46. at least one primary or official source exists when available;
47. at least one reliable explanatory source supports definitions, evidence or limits;
48. a video, open lecture, podcast, interactive resource or precise course lesson is included when it adds real value and is accessible;
49. every online source has a direct verified link and a precise locator such as chapter, section, page, DOI, version, lesson, exercise or timestamp;
50. the module explains how each source was used;
51. current or unstable claims were verified against current authoritative sources;
52. plugin outputs are not cited instead of original sources;
53. potentially paid resources have a free or official alternative;
54. videos specify purpose, duration or timestamp, language/legends when relevant and an active learning task;
55. papers, articles, TCCs and dissertations are represented with an accurate evidence role and limits;
56. copyright-sensitive sources are paraphrased and not reproduced extensively;
57. external resources enrich but do not replace the self-contained lesson;
58. analogies and invented examples are identified as pedagogical adaptations.

## Integration and task review

Confirm that:

59. `study/integrations.md` opens with a human summary and keeps operational classifications in a collapsed technical section;
60. only capabilities supported by course or learner signals are recommended;
61. one task backend is primary;
62. Quizlet and other formative tools do not affect completion and always have a durable local alternative;
63. calendar, habit, analytics and reminder tools do not create competing learning state;
64. Airtable remains `github_to_airtable`;
65. external courses and media identify exact useful sections, access, effort and evidence;
66. providers in `avoid` or prohibited by account preferences are not selected;
67. optional providers cannot block core generation or study;
68. no external resource is created during curriculum generation or review;
69. Trello card text uses human titles, “Você pode começar por aqui”, clear next action and “Esta aula será preparada automaticamente...” for future content;
70. Trello does not repeat internal authority, materialization or workflow language in every card.

Reject a lesson when it could be replaced by a short checklist without losing teaching content, when major claims are not traceable to inspected sources, when references are a link dump, when media was added only to make the lesson look richer, or when a difficult concept lacks a bridge from intuition to technical detail.

Reject learner-facing copy when it leads with PR/CI success, exposes internal classifications, mixes languages unnecessarily, makes the learner command repository mechanics or repeats system disclaimers in every artifact.

## Course-content handoff

For every materialized topic, hand the final authoring output to `instructions/36-review-course-content.md`. The independent pass must compare topic outcomes, required concepts, prerequisite graph, module, practice, assessment and task projection. It creates or refreshes `state/content-reviews/TOPIC-000.yml` for the exact content version. A missing, stale or blocked review prevents merge.

## Allowed diffs and merge

Initial generation and later materialization must stay within the configured curriculum scope. Correct resolvable problems directly on the proposal branch, run required checks, self-review the final diff and merge under `agent_review_then_merge` when no genuine pedagogical, privacy, cost or integration-policy decision remains.

Record technical review status in GitHub. In chat, report the learner outcome and next step. Link a PR only when a concrete unresolved decision requires the owner.
