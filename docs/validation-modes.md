# Validation modes

The validation workflow is copied into repositories created from this template, so it must support both repository modes.

Repository mode is determined from marker files, not repository metadata such as reported size, search indexing or an incomplete checkout.

## Template mode

Template mode applies while `.open-study-path/instance.yml` is absent. The validator checks reusable contracts and rejects learner-specific instance artifacts.

## Instance mode

Instance mode applies when `.open-study-path/instance.yml` exists. The validator requires the bootstrap artifacts, confirms that the instance repository is not the canonical template, checks the source-template identity and validates both `study.config.example.yml` and `study.config.yml` against the JSON Schema.

The inherited `.open-study-path/template.yml` must remain present in instances because it identifies the canonical source and reusable assets. The instance marker takes precedence when determining validation mode; it does not replace the template marker. Deleting either required marker is an invalid repository transformation.