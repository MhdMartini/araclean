---
title: AraClean Offset Map
emoji: 🧭
colorFrom: green
colorTo: indigo
sdk: gradio
sdk_version: 6.26.0
python_version: 3.12
app_file: app.py
pinned: false
license: mit
suggested_hardware: cpu-basic
short_description: Project normalized Arabic spans back to their original text.
tags:
  - arabic
  - nlp
  - arabic-nlp
  - text-normalization
  - offset-mapping
---

# AraClean offset-preserving normalization

Arabic normalization improves retrieval and model input, but it can remove or replace characters.
That usually makes a normalized hit difficult to locate in the raw document. This demo makes
[AraClean's offset map](https://mhdmartini.github.io/araclean/latest/guides/offset-preserving/)
visible:

1. Paste Arabic text and choose a reproducible profile.
2. Select a span in the normalized text to highlight its source in the original.
3. Select a span in the original to highlight what a model sees after normalization.

The first direction demonstrates **RAG citation grounding**: search normalized text, then cite the
untouched source. The reverse direction demonstrates **NER/span annotation**: project an annotation
or model result between raw and normalized text.

The demo runs entirely on CPU and downloads no model or dataset. Learn more in the
[AraClean repository](https://github.com/MhdMartini/araclean) and
[documentation](https://mhdmartini.github.io/araclean/).

## Run locally

From an AraClean checkout, run the committed app against the local package source:

```bash
uv run --with gradio==6.26.0 python spaces/araclean_offset_demo/app.py
```

Open the local URL printed by Gradio (normally `http://127.0.0.1:7860`). To reproduce the exact
standalone Space environment instead, change into this directory, create a virtual environment,
install `requirements.txt`, and run `python app.py`.

## Deploy this folder to a Space

Authenticate the Hugging Face CLI, create a Gradio Space, then upload this directory at the root:

```bash
uvx --from huggingface_hub hf auth login
uvx --from huggingface_hub hf repos create YOUR_USERNAME/araclean-offset-map \
  --repo-type space --sdk gradio --exist-ok
uvx --from huggingface_hub hf upload YOUR_USERNAME/araclean-offset-map \
  spaces/araclean_offset_demo . --repo-type space \
  --commit-message "Deploy AraClean offset-map demo"
```

Hugging Face reads the YAML above, installs `requirements.txt`, and starts `app.py`. Watch the
Space's **Build logs** until its status changes to **Running**.
