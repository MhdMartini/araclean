# Reproducible preprocessing

Preprocessing is part of your method. If a paper, a teammate, or your future self cannot rerun
*exactly* the normalization a dataset went through, results stop being comparable — and Arabic
preprocessing is where that silently goes wrong most often. araclean treats the preprocessing
configuration as a first-class, serializable artifact.

## Name the profile, pin the version

The cheapest reproducibility statement is a profile name plus the araclean version:

```pycon
>>> import araclean
>>> isinstance(araclean.__version__, str)
True

```

> *"Text was normalized with araclean X.Y.Z, profile `search`."*

Profiles are versioned with the library and never change silently: behavior changes arrive as
version bumps with changelog entries (the version itself is derived from Conventional Commits).
Published docs are versioned too — the version selector on this site pins the docs to the release
you installed.

## Serialize the exact pipeline

A `Pipeline` round-trips through a plain, JSON-friendly dict — every step name and its full
configuration:

```pycon
>>> import json
>>> from araclean import Pipeline
>>> pipe = Pipeline.from_profile("search").drop("MapDigits")
>>> payload = json.dumps(pipe.to_dict(), ensure_ascii=False)  # ship this with your dataset
>>> restored = Pipeline.from_dict(json.loads(payload))
>>> restored("اَلسّلامُ عليكم") == pipe("اَلسّلامُ عليكم")
True

```

This captures *adapted* pipelines too — the `drop` above is in the payload, not a footnote.
[Custom steps](custom-steps.md) join the round-trip once they implement `to_dict` and register a
factory.

Data that can drift is pinned inside the serialized form. `RemoveStopwords`, for example, embeds
the bundled stopword-list version, and refuses to rehydrate against a release whose list differs:

```pycon
>>> from araclean import RemoveStopwords
>>> RemoveStopwords().to_dict()
{'name': 'RemoveStopwords', 'config': {'version': '2.0.0'}}

```

## Serialize a configured call

If you stayed at the `normalize` level, the same applies to its configuration: `NormalizeConfig`
is a frozen pydantic model, so a tuned call serializes to a few bytes of JSON and validates on the
way back in:

```pycon
>>> from araclean import NormalizeConfig, normalize
>>> config = NormalizeConfig(profile="ml", map_digits=True)
>>> config.model_dump_json(exclude_defaults=True)
'{"profile":"ml","map_digits":true}'
>>> normalize("٢٠٢٤", config=NormalizeConfig.model_validate_json('{"profile":"ml","map_digits":true}'))
'2024'

```

Because the model is `extra="forbid"` with closed enums, a stale or typo'd config from disk fails
loudly instead of running something subtly different. There is a published JSON Schema for it, so
non-Python tooling can validate configs too:

```pycon
>>> schema = NormalizeConfig.model_json_schema()
>>> schema["title"], schema["additionalProperties"]
('NormalizeConfig', False)

```

## State what was lost

A methods section should say not just *what ran* but *what it discarded*. The audit gives you that
sentence from the pipeline itself:

```pycon
>>> report = Pipeline.from_profile("ml").audit()
>>> report.lossless
False
>>> report.lossy_steps
('RemoveTashkeel', 'ReduceElongation')

```

See [the safety contract](../concepts/safety.md) for the classes the report buckets steps into.

## The full recipe

For a dataset card or appendix, ship three things:

1. the araclean version (`araclean.__version__`),
2. the serialized pipeline (`pipe.to_dict()`) or config (`config.model_dump_json()`),
3. the audit summary (`pipe.audit()`).

Anyone with `pip install araclean==X.Y.Z` and the payload reproduces your preprocessing exactly —
no notebook archaeology required.
