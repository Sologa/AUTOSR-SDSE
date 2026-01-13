# Discrete Audio Tokens: More Than a Survey! — workspace 報告（API vs Codex CLI）

## 0. 範圍與說明

本報告覆蓋兩個 workspace 的完整產物：
- workspaces/discrete_audio_tokens_more_than_a_survey-api（原始 API 路徑）
- workspaces/discrete_audio_tokens_more_than_a_survey（後續 Codex CLI 路徑）

重點：
- 報告包含 seed → filter-seed → keywords → harvest → criteria → review → snowball 的實際產物（若存在）。
- 受限於檔案體積，超大型輸出不在本文內嵌全文，但提供完整的檔案校驗資訊、統計摘要與路徑。
- `--cutoff-by-similar-title false` 受到明確禁止，本報告只描述現行強制啟用的 cutoff 行為，不會提出關閉建議。

## 1. 事實檢查與外部來源

### 1.1 本地證據來源

以下路徑均已讀取並納入分析：

- workspaces/discrete_audio_tokens_more_than_a_survey-api/**

- workspaces/discrete_audio_tokens_more_than_a_survey/**

- resources/LLM/prompts/**

- src/pipelines/topic_pipeline.py（僅用於確認流程規則；未改動）

### 1.2 外部查核（arXiv API）

查核動機：確認與兩條 seed 搜尋 query 對應的 arXiv 結果是否與 workspace 內記錄一致。
查核來源：arXiv API（export.arxiv.org）。

查核時間（UTC）：2026-01-13T16:46:42.356608+00:00


```json
{
  "checked_at": "2026-01-13T16:46:42.356608+00:00",
  "queries": {
    "codex_workspace_query": {
      "query": "(all:\"discrete audio tokens\" OR all:\"discrete audio tokenization\" OR all:\"discrete acoustic tokens\") AND (all:\"survey\" OR all:\"review\" OR all:\"overview\" OR all:\"systematic review\" OR all:\"systematic literature review\" OR all:\"scoping review\" OR all:\"mapping study\" OR all:\"tutorial\")",
      "url": "https://export.arxiv.org/api/query?search_query=%28all%3A%22discrete+audio+tokens%22+OR+all%3A%22discrete+audio+tokenization%22+OR+all%3A%22discrete+acoustic+tokens%22%29+AND+%28all%3A%22survey%22+OR+all%3A%22review%22+OR+all%3A%22overview%22+OR+all%3A%22systematic+review%22+OR+all%3A%22systematic+literature+review%22+OR+all%3A%22scoping+review%22+OR+all%3A%22mapping+study%22+OR+all%3A%22tutorial%22%29&start=0&max_results=20",
      "count": 1,
      "titles": [
        "Discrete Audio Tokens: More Than a Survey!"
      ],
      "ids": [
        "http://arxiv.org/abs/2506.10274v3"
      ]
    },
    "api_workspace_query": {
      "query": "(all:\"discrete audio tokens\" OR all:\"discrete speech tokens\" OR all:\"audio tokenization discrete tokens\") AND (all:\"survey\" OR all:\"review\" OR all:\"overview\" OR all:\"systematic review\" OR all:\"systematic literature review\" OR all:\"scoping review\" OR all:\"mapping study\" OR all:\"tutorial\")",
      "url": "https://export.arxiv.org/api/query?search_query=%28all%3A%22discrete+audio+tokens%22+OR+all%3A%22discrete+speech+tokens%22+OR+all%3A%22audio+tokenization+discrete+tokens%22%29+AND+%28all%3A%22survey%22+OR+all%3A%22review%22+OR+all%3A%22overview%22+OR+all%3A%22systematic+review%22+OR+all%3A%22systematic+literature+review%22+OR+all%3A%22scoping+review%22+OR+all%3A%22mapping+study%22+OR+all%3A%22tutorial%22%29&start=0&max_results=20",
      "count": 4,
      "titles": [
        "Recent Advances in Discrete Speech Tokens: A Review",
        "Discrete Audio Tokens: More Than a Survey!",
        "Objective Evaluation of Prosody and Intelligibility in Speech Synthesis via Conditional Prediction of Discrete Tokens",
        "EMORL-TTS: Reinforcement Learning for Fine-Grained Emotion Control in LLM-based TTS"
      ],
      "ids": [
        "http://arxiv.org/abs/2502.06490v4",
        "http://arxiv.org/abs/2506.10274v3",
        "http://arxiv.org/abs/2509.20485v1",
        "http://arxiv.org/abs/2510.05758v1"
      ]
    }
  }
}
```

## 2. workspace 總覽

| workspace | topic | updated_at |
| --- | --- | --- |

| workspaces/discrete_audio_tokens_more_than_a_survey-api | Discrete Audio Tokens: More Than a Survey! | 2026-01-07T18:15:18.194560+00:00 |

| workspaces/discrete_audio_tokens_more_than_a_survey | Discrete Audio Tokens: More Than a Survey! | 2026-01-13T14:58:11.466036+00:00 |


## 3. workspace: workspaces/discrete_audio_tokens_more_than_a_survey-api（API）

### 3.1 重要摘要

- seed 階段：rewrite 成功擴大 query，下載 1 篇 seed PDF（2502.06490）。
- filter-seed：LLM 判定該 seed 為 yes。
- keywords/harvest/criteria/review/snowball 均有產物。
- 多處產物出現指向非 -api workspace 的路徑（見 6.2 數據一致性說明）。

### 3.2 主要小型產物（全文內嵌）

#### workspaces/discrete_audio_tokens_more_than_a_survey-api/config.json

```json
{
  "topic": "Discrete Audio Tokens: More Than a Survey!",
  "updated_at": "2026-01-07T18:15:18.194560+00:00"
}
```

#### workspaces/discrete_audio_tokens_more_than_a_survey-api/cutoff/cutoff.json

```json
{
  "topic_title": "Discrete Audio Tokens: More Than a Survey!",
  "topic_title_normalized": "discrete audio tokens more than a survey",
  "target_paper": {
    "source": "arxiv",
    "id": "2506.10274",
    "title": "Discrete Audio Tokens: More Than a Survey!",
    "published_date": "2025-06-12",
    "published_raw": "2025-06-12"
  },
  "cutoff_date": "2025-06-12",
  "policy": {
    "exclude_same_title": true,
    "exclude_on_or_after_cutoff_date": true
  },
  "derived_from": "seed_selection",
  "generated_at": "2026-01-07T09:55:53.644292+00:00"
}
```

#### workspaces/discrete_audio_tokens_more_than_a_survey-api/seed/queries/arxiv.json

```json
[
  {
    "id": "http://arxiv.org/abs/2502.06490v4",
    "title": "Recent Advances in Discrete Speech Tokens: A Review",
    "summary": "The rapid advancement of speech generation technologies in the era of large language models (LLMs) has established discrete speech tokens as a foundational paradigm for speech representation. These tokens, characterized by their discrete, compact, and concise nature, are not only advantageous for efficient transmission and storage, but also inherently compatible with the language modeling framework, enabling seamless integration of speech into text-dominated LLM architectures. Current research categorizes discrete speech tokens into two principal classes: acoustic tokens and semantic tokens, each of which has evolved into a rich research domain characterized by unique design philosophies and methodological approaches. This survey systematically synthesizes the existing taxonomy and recent innovations in discrete speech tokenization, conducts a critical examination of the strengths and limitations of each paradigm, and presents systematic experimental comparisons across token types. Furthermore, we identify persistent challenges in the field and propose potential research directions, aiming to offer actionable insights to inspire future advancements in the development and application of discrete speech tokens.",
    "published": "2025-02-10T14:08:25Z"
  },
  {
    "id": "http://arxiv.org/abs/2506.10274v3",
    "title": "Discrete Audio Tokens: More Than a Survey!",
    "summary": "Discrete audio tokens are compact representations that aim to preserve perceptual quality, phonetic content, and speaker characteristics while enabling efficient storage and inference, as well as competitive performance across diverse downstream tasks. They provide a practical alternative to continuous features, enabling the integration of speech and audio into modern large language models (LLMs). As interest in token-based audio processing grows, various tokenization methods have emerged, and several surveys have reviewed the latest progress in the field. However, existing studies often focus on specific domains or tasks and lack a unified comparison across various benchmarks. This paper presents a systematic review and benchmark of discrete audio tokenizers, covering three domains: speech, music, and general audio. We propose a taxonomy of tokenization approaches based on encoder-decoder, quantization techniques, training paradigm, streamability, and application domains. We evaluate tokenizers on multiple benchmarks for reconstruction, downstream performance, and acoustic language modeling, and analyze trade-offs through controlled ablation studies. Our findings highlight key limitations, practical considerations, and open challenges, providing insight and guidance for future research in this rapidly evolving area. For more information, including our main results and tokenizer database, please refer to our website: https://poonehmousavi.github.io/dates-website/.",
    "published": "2025-06-12T01:35:43Z"
  },
  {
    "id": "http://arxiv.org/abs/2509.20485v1",
    "title": "Objective Evaluation of Prosody and Intelligibility in Speech Synthesis via Conditional Prediction of Discrete Tokens",
    "summary": "Objective evaluation of synthesized speech is critical for advancing speech generation systems, yet existing metrics for intelligibility and prosody remain limited in scope and weakly correlated with human perception. Word Error Rate (WER) provides only a coarse text-based measure of intelligibility, while F0-RMSE and related pitch-based metrics offer a narrow, reference-dependent view of prosody. To address these limitations, we propose TTScore, a targeted and reference-free evaluation framework based on conditional prediction of discrete speech tokens. TTScore employs two sequence-to-sequence predictors conditioned on input text: TTScore-int, which measures intelligibility through content tokens, and TTScore-pro, which evaluates prosody through prosody tokens. For each synthesized utterance, the predictors compute the likelihood of the corresponding token sequences, yielding interpretable scores that capture alignment with intended linguistic content and prosodic structure. Experiments on the SOMOS, VoiceMOS, and TTSArena benchmarks demonstrate that TTScore-int and TTScore-pro provide reliable, aspect-specific evaluation and achieve stronger correlations with human judgments of overall quality than existing intelligibility and prosody-focused metrics.",
    "published": "2025-09-24T18:55:18Z"
  },
  {
    "id": "http://arxiv.org/abs/2510.05758v1",
    "title": "EMORL-TTS: Reinforcement Learning for Fine-Grained Emotion Control in LLM-based TTS",
    "summary": "Recent LLM-based TTS systems achieve strong quality and zero-shot ability, but lack fine-grained emotional control due to their reliance on discrete speech tokens. Existing approaches either limit emotions to categorical labels or cannot generalize to LLM-based architectures. We propose EMORL-TTS (Fine-grained Emotion-controllable TTS with Reinforcement Learning), a framework that unifies global intensity control in the VAD space with local emphasis regulation. Our method combines supervised fine-tuning with reinforcement learning guided by task-specific rewards for emotion category, intensity, and emphasis. Moreover, we further investigate how emphasis placement modulates fine-grained emotion intensity. Experiments show that EMORL-TTS improves emotion accuracy, intensity differentiation, and emphasis clarity, while preserving synthesis quality comparable to strong LLM-based baselines.",
    "published": "2025-10-07T10:24:12Z"
  }
]
```

#### workspaces/discrete_audio_tokens_more_than_a_survey-api/seed/queries/seed_selection.json

```json
{
  "topic": "Discrete Audio Tokens: More Than a Survey!",
  "topic_variants": [
    "Discrete Audio Tokens: More Than a Survey!",
    "discrete audio tokens: more than a survey",
    "Discrete Audio Tokens",
    "discrete audio tokens: more than a surveys"
  ],
  "cutoff_by_similar_title": true,
  "similarity_threshold": 0.8,
  "title_filter_applied": true,
  "title_filter_keywords": [
    "survey",
    "review",
    "overview"
  ],
  "cutoff_reason": "exact_title_match",
  "cutoff_candidate": {
    "arxiv_id": "2506.10274",
    "title": "Discrete Audio Tokens: More Than a Survey!",
    "published": "2025-06-12T01:35:43Z",
    "published_date": "2025-06-12",
    "similarity": {
      "best_variant": "Discrete Audio Tokens: More Than a Survey!",
      "sequence_ratio": 1.0,
      "token_containment": 1.0,
      "topic": "Discrete Audio Tokens: More Than a Survey!",
      "title": "Discrete Audio Tokens: More Than a Survey!",
      "score": 1.0
    }
  },
  "cutoff_date": "2025-06-12",
  "topic_title_normalized": "discrete audio tokens more than a survey",
  "records_total": 4,
  "records_after_title_filter": 2,
  "records_after_filter": 1,
  "download_top_k": 5,
  "download_selected": [
    {
      "arxiv_id": "2502.06490",
      "title": "Recent Advances in Discrete Speech Tokens: A Review",
      "published": "2025-02-10T14:08:25Z"
    }
  ],
  "candidates": [
    {
      "arxiv_id": "2502.06490",
      "title": "Recent Advances in Discrete Speech Tokens: A Review",
      "published": "2025-02-10T14:08:25Z",
      "published_date": "2025-02-10",
      "similarity": {
        "best_variant": "Discrete Audio Tokens: More Than a Survey!",
        "sequence_ratio": 0.4782608695652174,
        "token_containment": 0.5,
        "topic": "Discrete Audio Tokens: More Than a Survey!",
        "title": "Recent Advances in Discrete Speech Tokens: A Review",
        "score": 0.5
      }
    },
    {
      "arxiv_id": "2506.10274",
      "title": "Discrete Audio Tokens: More Than a Survey!",
      "published": "2025-06-12T01:35:43Z",
      "published_date": "2025-06-12",
      "similarity": {
        "best_variant": "Discrete Audio Tokens: More Than a Survey!",
        "sequence_ratio": 1.0,
        "token_containment": 1.0,
        "topic": "Discrete Audio Tokens: More Than a Survey!",
        "title": "Discrete Audio Tokens: More Than a Survey!",
        "score": 1.0
      }
    }
  ],
  "anchor_mode": "phrase",
  "search_query": "(all:\"discrete audio tokens\" OR all:\"discrete speech tokens\" OR all:\"audio tokenization discrete tokens\") AND (all:\"survey\" OR all:\"review\" OR all:\"overview\" OR all:\"systematic review\" OR all:\"systematic literature review\" OR all:\"scoping review\" OR all:\"mapping study\" OR all:\"tutorial\")",
  "scope": "all",
  "boolean_operator": "AND",
  "raw_query": null
}
```

#### workspaces/discrete_audio_tokens_more_than_a_survey-api/seed/queries/seed_rewrite.json

```json
{
  "topic": "Discrete Audio Tokens: More Than a Survey!",
  "trigger_reason": "cutoff_removed_all_candidates",
  "attempts": [
    {
      "attempt": 1,
      "model": "gpt-5.2",
      "provider": "openai",
      "raw_output": "discrete audio tokens  \ndiscrete audio tokenization  \nquantized audio tokens",
      "parsed_phrases": [
        "discrete audio tokens",
        "discrete audio tokenization",
        "quantized audio tokens"
      ],
      "parsed_phrase": "discrete audio tokens",
      "status": "ok",
      "error": null
    },
    {
      "attempt": 2,
      "model": "gpt-5.2",
      "provider": "openai",
      "raw_output": "discrete audio tokens  \ndiscrete speech tokens  \naudio tokenization discrete tokens",
      "parsed_phrases": [
        "discrete audio tokens",
        "discrete speech tokens",
        "audio tokenization discrete tokens"
      ],
      "parsed_phrase": "discrete audio tokens",
      "status": "ok",
      "error": null
    }
  ],
  "selected_queries": [
    "discrete audio tokens",
    "discrete speech tokens",
    "audio tokenization discrete tokens"
  ],
  "original_seed_query": "(all:\"Discrete Audio Tokens: More Than a Survey!\" OR all:\"discrete audio tokens: more than a survey\" OR all:\"Discrete Audio Tokens\" OR all:\"discrete audio tokens: more than a surveys\") AND (all:\"survey\" OR all:\"review\" OR all:\"overview\" OR all:\"systematic review\" OR all:\"systematic literature review\" OR all:\"scoping review\" OR all:\"mapping study\" OR all:\"tutorial\")",
  "cutoff_reason": "cutoff_removed_all_candidates",
  "cutoff_candidate_title": "Discrete Audio Tokens: More Than a Survey!",
  "generated_at": "2026-01-07T09:56:02.311663+00:00",
  "preview_only": false
}
```

#### workspaces/discrete_audio_tokens_more_than_a_survey-api/seed/downloads/download_results.json

```json
{
  "topic": "Discrete Audio Tokens: More Than a Survey!",
  "anchors": [
    "discrete audio tokens",
    "discrete speech tokens",
    "audio tokenization discrete tokens"
  ],
  "survey_terms": [
    "survey",
    "review",
    "overview",
    "systematic review",
    "systematic literature review",
    "scoping review",
    "mapping study",
    "tutorial"
  ],
  "anchor_mode": "phrase",
  "search_query": "(all:\"discrete audio tokens\" OR all:\"discrete speech tokens\" OR all:\"audio tokenization discrete tokens\") AND (all:\"survey\" OR all:\"review\" OR all:\"overview\" OR all:\"systematic review\" OR all:\"systematic literature review\" OR all:\"scoping review\" OR all:\"mapping study\" OR all:\"tutorial\")",
  "raw_query": null,
  "max_results": 25,
  "download_top_k": 5,
  "downloaded_at": "2026-01-07T09:56:02.309828+00:00",
  "downloads": {
    "arxiv": [
      {
        "source": "arxiv",
        "identifier": "2502.06490",
        "metadata": {
          "arxiv_id": "2502.06490",
          "title": "Recent Advances in Discrete Speech Tokens: A Review",
          "summary": "The rapid advancement of speech generation technologies in the era of large language models (LLMs) has established discrete speech tokens as a foundational paradigm for speech representation. These tokens, characterized by their discrete, compact, and concise nature, are not only advantageous for efficient transmission and storage, but also inherently compatible with the language modeling framework, enabling seamless integration of speech into text-dominated LLM architectures. Current research categorizes discrete speech tokens into two principal classes: acoustic tokens and semantic tokens, each of which has evolved into a rich research domain characterized by unique design philosophies and methodological approaches. This survey systematically synthesizes the existing taxonomy and recent innovations in discrete speech tokenization, conducts a critical examination of the strengths and limitations of each paradigm, and presents systematic experimental comparisons across token types. Furthermore, we identify persistent challenges in the field and propose potential research directions, aiming to offer actionable insights to inspire future advancements in the development and application of discrete speech tokens.",
          "authors": [
            "Yiwei Guo",
            "Zhihan Li",
            "Hankun Wang",
            "Bohan Li",
            "Chongtian Shao",
            "Hanglei Zhang",
            "Chenpeng Du",
            "Xie Chen",
            "Shujie Liu",
            "Kai Yu"
          ],
          "published": "2025-02-10T14:08:25Z",
          "updated": "2025-12-12T05:18:11Z",
          "categories": [
            "eess.AS",
            "cs.AI",
            "cs.MM",
            "cs.SD",
            "eess.SP"
          ],
          "pdf_url": "https://arxiv.org/pdf/2502.06490v4",
          "landing_url": "https://arxiv.org/abs/2502.06490v4",
          "doi": "https://doi.org/10.48550/arXiv.2502.06490"
        },
        "pdf_path": "workspaces/discrete_audio_tokens_more_than_a_survey/seed/downloads/arxiv/2502.06490.pdf",
        "bibtex_path": null,
        "issues": [
          {
            "asset": "bibtex",
            "reason": "missing",
            "url": "https://arxiv.org/bibtex/2502.06490"
          }
        ]
      }
    ],
    "semantic_scholar": [],
    "dblp": []
  },
  "rewrite_attempts": 2,
  "rewrite_query": "discrete audio tokens",
  "rewrite_queries": [
    "discrete audio tokens",
    "discrete speech tokens",
    "audio tokenization discrete tokens"
  ]
}
```

#### workspaces/discrete_audio_tokens_more_than_a_survey-api/seed/filters/llm_screening.json

```json
{
  "topic": "Discrete Audio Tokens: More Than a Survey!",
  "model": "gpt-5-mini",
  "generated_at": "2026-01-07T09:56:06.397055+00:00",
  "papers": [
    {
      "arxiv_id": "2502.06490",
      "title": "Recent Advances in Discrete Speech Tokens: A Review",
      "abstract": "The rapid advancement of speech generation technologies in the era of large language models (LLMs) has established discrete speech tokens as a foundational paradigm for speech representation. These tokens, characterized by their discrete, compact, and concise nature, are not only advantageous for efficient transmission and storage, but also inherently compatible with the language modeling framework, enabling seamless integration of speech into text-dominated LLM architectures. Current research categorizes discrete speech tokens into two principal classes: acoustic tokens and semantic tokens, each of which has evolved into a rich research domain characterized by unique design philosophies and methodological approaches. This survey systematically synthesizes the existing taxonomy and recent innovations in discrete speech tokenization, conducts a critical examination of the strengths and limitations of each paradigm, and presents systematic experimental comparisons across token types. Furthermore, we identify persistent challenges in the field and propose potential research directions, aiming to offer actionable insights to inspire future advancements in the development and application of discrete speech tokens.",
      "decision": "yes",
      "reason": "文章標題與摘要明確表明這是一篇系統性的綜述，且主題直接聚焦於離散語音/音訊標記的研究進展。",
      "confidence": 0.92
    }
  ],
  "fallback": {
    "enabled": true,
    "triggered": false,
    "min_selected": 2,
    "selected_before": 1,
    "selected_after": 1,
    "added": [],
    "prompt_path": null
  }
}
```

#### workspaces/discrete_audio_tokens_more_than_a_survey-api/seed/filters/selected_ids.json

```json
{
  "selected": [
    "2502.06490"
  ],
  "rejected": [],
  "fallback_added": []
}
```

#### workspaces/discrete_audio_tokens_more_than_a_survey-api/keywords/keywords.json

```json
{
  "topic": "Discrete Audio Tokens: More Than a Survey!",
  "anchor_terms": [
    "discrete speech tokens",
    "speech tokenization",
    "acoustic tokens",
    "semantic tokens"
  ],
  "search_terms": {
    "quantization_methods": [
      "offline clustering",
      "k-means",
      "vector quantization",
      "gumbel vq",
      "finite scalar quantization",
      "residual vq",
      "straight through estimator",
      "grouped vq"
    ],
    "acoustic_token_models": [
      "acoustic tokens",
      "semantic distillation",
      "neural codec",
      "vq-gan",
      "vq-vae",
      "diffusion",
      "transformer",
      "disentanglement",
      "single codebook"
    ],
    "semantic_token_models": [
      "semantic tokens",
      "self supervised learning",
      "hubert",
      "wav2vec",
      "wavlm",
      "vq-wav2vec",
      "supervised tokenizer",
      "internal quantization",
      "external quantization"
    ],
    "length_reduction": [
      "deduplication",
      "acoustic bpe",
      "variable frame rate",
      "length reduction",
      "byte pair encoding",
      "unit discovery",
      "frame rate",
      "variable bitrate"
    ],
    "evaluation_benchmarks": [
      "reconstruction metrics",
      "pesq",
      "stoi",
      "word error rate",
      "gross pitch error",
      "codebook utilization",
      "codec-superb",
      "dasb"
    ],
    "downstream_applications": [
      "discrete speech tokens",
      "speech tokenization",
      "speech token vocoder",
      "voice conversion",
      "speech generation",
      "text to speech",
      "spoken language modeling",
      "spoken language understanding",
      "speech translation",
      "decoder-only transformers"
    ]
  },
  "papers": [
    {
      "id": "guo_discrete_speech_tokens_2025",
      "source_id": "arXiv:2502.06490",
      "title": "Recent Advances in Discrete Speech Tokens: A Review",
      "abstract": "The rapid advancement of speech generation technologies in the era of large language models (LLMs) has established discrete speech tokens as a foundational paradigm for speech representation. These tokens, characterized by their discrete, compact, and concise nature, are not only advantageous for efficient transmission and storage, but also inherently compatible with the language modeling framework, enabling seamless integration of speech into text-dominated LLM architectures. Current research categorizes discrete speech tokens into two principal classes: acoustic tokens and semantic tokens, each of which has evolved into a rich research domain characterized by unique design philosophies and methodological approaches. This survey systematically synthesizes the existing taxonomy and recent innovations in discrete speech tokenization, conducts a critical examination of the strengths and limitations of each paradigm, and presents systematic experimental comparisons across token types. Furthermore, we identify persistent challenges in the field and propose potential research directions, aiming to offer actionable insights to inspire future advancements in the development and application of discrete speech tokens.",
      "year": "2025",
      "source_url": "https://arxiv.org/abs/2502.06490v4",
      "pdf_path": "workspaces/discrete_audio_tokens_more_than_a_survey/seed/downloads/arxiv/2502.06490.pdf",
      "detected_keywords": [
        {
          "term": "discrete speech tokens",
          "category": "downstream_applications",
          "evidence": {
            "quote": "has established discrete speech tokens as a foundational paradigm for speech representation.",
            "page": "1"
          },
          "confidence": 0.65
        },
        {
          "term": "speech tokenization",
          "category": "downstream_applications",
          "evidence": {
            "quote": "a necessary step before applying speech data to LLM is the tokenization of speech",
            "page": "1"
          },
          "confidence": 0.62
        },
        {
          "term": "acoustic tokens",
          "category": "acoustic_token_models",
          "evidence": {
            "quote": "two types of speech tokens: acoustic tokens and semantic tokens.",
            "page": "1"
          },
          "confidence": 0.62
        },
        {
          "term": "semantic tokens",
          "category": "semantic_token_models",
          "evidence": {
            "quote": "two types of speech tokens: acoustic tokens and semantic tokens.",
            "page": "1"
          },
          "confidence": 0.62
        },
        {
          "term": "offline clustering",
          "category": "quantization_methods",
          "evidence": {
            "quote": "A. Offline Clustering",
            "page": "2"
          },
          "confidence": 0.48
        },
        {
          "term": "k-means",
          "category": "quantization_methods",
          "evidence": {
            "quote": "The most frequently used clustering method for discrete speech tokens is k-means clustering",
            "page": "2"
          },
          "confidence": 0.52
        },
        {
          "term": "vector quantization",
          "category": "quantization_methods",
          "evidence": {
            "quote": "vector quantization (VQ) [44] enables a learnable network module",
            "page": "2"
          },
          "confidence": 0.55
        },
        {
          "term": "Gumbel VQ",
          "category": "quantization_methods",
          "evidence": {
            "quote": "2) Gumbel VQ:",
            "page": "3"
          },
          "confidence": 0.42
        },
        {
          "term": "finite scalar quantization",
          "category": "quantization_methods",
          "evidence": {
            "quote": "3) Finite Scalar Quantization (FSQ):",
            "page": "3"
          },
          "confidence": 0.46
        },
        {
          "term": "residual VQ",
          "category": "quantization_methods",
          "evidence": {
            "quote": "2) Residual VQ (RVQ), also known as multi-stage quantization",
            "page": "4"
          },
          "confidence": 0.5
        },
        {
          "term": "semantic distillation",
          "category": "acoustic_token_models",
          "evidence": {
            "quote": "The process of introducing semantic information into acoustic tokens is termed semantic distillation",
            "page": "7"
          },
          "confidence": 0.5
        },
        {
          "term": "speech token vocoder",
          "category": "downstream_applications",
          "evidence": {
            "quote": "a speech token vocoder\n(also known as speech resynthesis model) becomes necessary.",
            "page": "10"
          },
          "confidence": 0.48
        },
        {
          "term": "deduplication",
          "category": "length_reduction",
          "evidence": {
            "quote": "A common approach to reduce token sequence lengths is deduplication",
            "page": "11"
          },
          "confidence": 0.5
        },
        {
          "term": "acoustic BPE",
          "category": "length_reduction",
          "evidence": {
            "quote": "Another popular approach is acoustic byte-pair encoding\n(BPE)",
            "page": "11"
          },
          "confidence": 0.5
        },
        {
          "term": "variable frame rate",
          "category": "length_reduction",
          "evidence": {
            "quote": "This kind of discrete speech tokens is referred to as variable frame rate (VFR) tokens in this review.",
            "page": "11"
          },
          "confidence": 0.5
        },
        {
          "term": "voice conversion",
          "category": "downstream_applications",
          "evidence": {
            "quote": "we conduct voice\nconversion (VC) experiments",
            "page": "14"
          },
          "confidence": 0.45
        }
      ]
    }
  ]
}
```

#### workspaces/discrete_audio_tokens_more_than_a_survey-api/keywords/keyword_extractor_usage_20260107_101539Z.json

```json
{
  "timestamp": "2026-01-07T10:18:45.048675+00:00",
  "records": [
    {
      "provider": "openai",
      "model": "gpt-5.2",
      "mode": "pdf",
      "input_tokens": 54364,
      "output_tokens": 3607,
      "cost": 0.145635,
      "metadata": {
        "mode": "per_pdf",
        "topic": "Discrete Audio Tokens: More Than a Survey!",
        "pdf_path": "workspaces/discrete_audio_tokens_more_than_a_survey/seed/downloads/arxiv/2502.06490.pdf"
      }
    },
    {
      "provider": "openai",
      "model": "gpt-5.2",
      "mode": "sync",
      "input_tokens": 2421,
      "output_tokens": 7059,
      "cost": 0.103063,
      "metadata": {
        "mode": "aggregation",
        "topic": "Discrete Audio Tokens: More Than a Survey!"
      }
    }
  ],
  "total": {
    "input_tokens": 56785,
    "output_tokens": 10666,
    "cost": 0.24869799999999997
  }
}
```

#### workspaces/discrete_audio_tokens_more_than_a_survey-api/harvest/query_plan.json

```json
{
  "topic": "Discrete Audio Tokens: More Than a Survey!",
  "generated_at": "2026-01-07T10:51:54.648784+00:00",
  "anchors": [
    "discrete speech tokens",
    "speech tokenization",
    "acoustic tokens",
    "semantic tokens"
  ],
  "search_terms": [
    "offline clustering",
    "k-means",
    "vector quantization",
    "acoustic tokens",
    "semantic distillation",
    "neural codec",
    "semantic tokens",
    "self supervised learning",
    "hubert",
    "deduplication",
    "acoustic bpe",
    "variable frame rate",
    "reconstruction metrics",
    "pesq",
    "stoi",
    "discrete speech tokens",
    "speech tokenization",
    "speech token vocoder"
  ],
  "scope": "all",
  "boolean_operator": "OR",
  "top_k_per_query": 100,
  "start_date": "2022-06-12",
  "end_date": "2025-06-11",
  "cutoff_date": "2025-06-12",
  "queries_run": 72,
  "queries": [
    {
      "anchor": "discrete speech tokens",
      "search_term": "offline clustering",
      "search_query": "(all:\"discrete speech tokens\") OR (all:\"offline clustering\")",
      "records_returned": 58,
      "records_added": 33,
      "error": null
    },
    {
      "anchor": "discrete speech tokens",
      "search_term": "k-means",
      "search_query": "(all:\"discrete speech tokens\") OR (all:\"k-means\")",
      "records_returned": 100,
      "records_added": 15,
      "error": null
    },
    {
      "anchor": "discrete speech tokens",
      "search_term": "vector quantization",
      "search_query": "(all:\"discrete speech tokens\") OR (all:\"vector quantization\")",
      "records_returned": 100,
      "records_added": 45,
      "error": null
    },
    {
      "anchor": "discrete speech tokens",
      "search_term": "acoustic tokens",
      "search_query": "(all:\"discrete speech tokens\") OR (all:\"acoustic tokens\")",
      "records_returned": 98,
      "records_added": 38,
      "error": null
    },
    {
      "anchor": "discrete speech tokens",
      "search_term": "semantic distillation",
      "search_query": "(all:\"discrete speech tokens\") OR (all:\"semantic distillation\")",
      "records_returned": 72,
      "records_added": 17,
      "error": null
    },
    {
      "anchor": "discrete speech tokens",
      "search_term": "neural codec",
      "search_query": "(all:\"discrete speech tokens\") OR (all:\"neural codec\")",
      "records_returned": 100,
      "records_added": 43,
      "error": null
    },
    {
      "anchor": "discrete speech tokens",
      "search_term": "semantic tokens",
      "search_query": "(all:\"discrete speech tokens\") OR (all:\"semantic tokens\")",
      "records_returned": 100,
      "records_added": 34,
      "error": null
    },
    {
      "anchor": "discrete speech tokens",
      "search_term": "self supervised learning",
      "search_query": "(all:\"discrete speech tokens\") OR (all:\"self supervised learning\")",
      "records_returned": 100,
      "records_added": 47,
      "error": null
    },
    {
      "anchor": "discrete speech tokens",
      "search_term": "hubert",
      "search_query": "(all:\"discrete speech tokens\") OR (all:\"hubert\")",
      "records_returned": 100,
      "records_added": 38,
      "error": null
    },
    {
      "anchor": "discrete speech tokens",
      "search_term": "deduplication",
      "search_query": "(all:\"discrete speech tokens\") OR (all:\"deduplication\")",
      "records_returned": 100,
      "records_added": 30,
      "error": null
    },
    {
      "anchor": "discrete speech tokens",
      "search_term": "acoustic bpe",
      "search_query": "(all:\"discrete speech tokens\") OR (all:\"acoustic bpe\")",
      "records_returned": 37,
      "records_added": 2,
      "error": null
    },
    {
      "anchor": "discrete speech tokens",
      "search_term": "variable frame rate",
      "search_query": "(all:\"discrete speech tokens\") OR (all:\"variable frame rate\")",
      "records_returned": 53,
      "records_added": 10,
      "error": null
    },
    {
      "anchor": "discrete speech tokens",
      "search_term": "reconstruction metrics",
      "search_query": "(all:\"discrete speech tokens\") OR (all:\"reconstruction metrics\")",
      "records_returned": 100,
      "records_added": 29,
      "error": null
    },
    {
      "anchor": "discrete speech tokens",
      "search_term": "pesq",
      "search_query": "(all:\"discrete speech tokens\") OR (all:\"pesq\")",
      "records_returned": 100,
      "records_added": 23,
      "error": null
    },
    {
      "anchor": "discrete speech tokens",
      "search_term": "stoi",
      "search_query": "(all:\"discrete speech tokens\") OR (all:\"stoi\")",
      "records_returned": 100,
      "records_added": 18,
      "error": null
    },
    {
      "anchor": "discrete speech tokens",
      "search_term": "discrete speech tokens",
      "search_query": "(all:\"discrete speech tokens\") OR (all:\"discrete speech tokens\")",
      "records_returned": 35,
      "records_added": 0,
      "error": null
    },
    {
      "anchor": "discrete speech tokens",
      "search_term": "speech tokenization",
      "search_query": "(all:\"discrete speech tokens\") OR (all:\"speech tokenization\")",
      "records_returned": 100,
      "records_added": 31,
      "error": null
    },
    {
      "anchor": "discrete speech tokens",
      "search_term": "speech token vocoder",
      "search_query": "(all:\"discrete speech tokens\") OR (all:\"speech token vocoder\")",
      "records_returned": 36,
      "records_added": 1,
      "error": null
    },
    {
      "anchor": "speech tokenization",
      "search_term": "offline clustering",
      "search_query": "(all:\"speech tokenization\") OR (all:\"offline clustering\")",
      "records_returned": 100,
      "records_added": 0,
      "error": null
    },
    {
      "anchor": "speech tokenization",
      "search_term": "k-means",
      "search_query": "(all:\"speech tokenization\") OR (all:\"k-means\")",
      "records_returned": 100,
      "records_added": 0,
      "error": null
    },
    {
      "anchor": "speech tokenization",
      "search_term": "vector quantization",
      "search_query": "(all:\"speech tokenization\") OR (all:\"vector quantization\")",
      "records_returned": 100,
      "records_added": 0,
      "error": null
    },
    {
      "anchor": "speech tokenization",
      "search_term": "acoustic tokens",
      "search_query": "(all:\"speech tokenization\") OR (all:\"acoustic tokens\")",
      "records_returned": 100,
      "records_added": 0,
      "error": null
    },
    {
      "anchor": "speech tokenization",
      "search_term": "semantic distillation",
      "search_query": "(all:\"speech tokenization\") OR (all:\"semantic distillation\")",
      "records_returned": 100,
      "records_added": 0,
      "error": null
    },
    {
      "anchor": "speech tokenization",
      "search_term": "neural codec",
      "search_query": "(all:\"speech tokenization\") OR (all:\"neural codec\")",
      "records_returned": 100,
      "records_added": 0,
      "error": null
    },
    {
      "anchor": "speech tokenization",
      "search_term": "semantic tokens",
      "search_query": "(all:\"speech tokenization\") OR (all:\"semantic tokens\")",
      "records_returned": 100,
      "records_added": 1,
      "error": null
    },
    {
      "anchor": "speech tokenization",
      "search_term": "self supervised learning",
      "search_query": "(all:\"speech tokenization\") OR (all:\"self supervised learning\")",
      "records_returned": 100,
      "records_added": 0,
      "error": null
    },
    {
      "anchor": "speech tokenization",
      "search_term": "hubert",
      "search_query": "(all:\"speech tokenization\") OR (all:\"hubert\")",
      "records_returned": 100,
      "records_added": 0,
      "error": null
    },
    {
      "anchor": "speech tokenization",
      "search_term": "deduplication",
      "search_query": "(all:\"speech tokenization\") OR (all:\"deduplication\")",
      "records_returned": 100,
      "records_added": 0,
      "error": null
    },
    {
      "anchor": "speech tokenization",
      "search_term": "acoustic bpe",
      "search_query": "(all:\"speech tokenization\") OR (all:\"acoustic bpe\")",
      "records_returned": 100,
      "records_added": 2,
      "error": null
    },
    {
      "anchor": "speech tokenization",
      "search_term": "variable frame rate",
      "search_query": "(all:\"speech tokenization\") OR (all:\"variable frame rate\")",
      "records_returned": 100,
      "records_added": 0,
      "error": null
    },
    {
      "anchor": "speech tokenization",
      "search_term": "reconstruction metrics",
      "search_query": "(all:\"speech tokenization\") OR (all:\"reconstruction metrics\")",
      "records_returned": 100,
      "records_added": 0,
      "error": null
    },
    {
      "anchor": "speech tokenization",
      "search_term": "pesq",
      "search_query": "(all:\"speech tokenization\") OR (all:\"pesq\")",
      "records_returned": 100,
      "records_added": 0,
      "error": null
    },
    {
      "anchor": "speech tokenization",
      "search_term": "stoi",
      "search_query": "(all:\"speech tokenization\") OR (all:\"stoi\")",
      "records_returned": 100,
      "records_added": 0,
      "error": null
    },
    {
      "anchor": "speech tokenization",
      "search_term": "discrete speech tokens",
      "search_query": "(all:\"speech tokenization\") OR (all:\"discrete speech tokens\")",
      "records_returned": 100,
      "records_added": 1,
      "error": null
    },
    {
      "anchor": "speech tokenization",
      "search_term": "speech tokenization",
      "search_query": "(all:\"speech tokenization\") OR (all:\"speech tokenization\")",
      "records_returned": 100,
      "records_added": 2,
      "error": null
    },
    {
      "anchor": "speech tokenization",
      "search_term": "speech token vocoder",
      "search_query": "(all:\"speech tokenization\") OR (all:\"speech token vocoder\")",
      "records_returned": 100,
      "records_added": 0,
      "error": null
    },
    {
      "anchor": "acoustic tokens",
      "search_term": "offline clustering",
      "search_query": "(all:\"acoustic tokens\") OR (all:\"offline clustering\")",
      "records_returned": 89,
      "records_added": 1,
      "error": null
    },
    {
      "anchor": "acoustic tokens",
      "search_term": "k-means",
      "search_query": "(all:\"acoustic tokens\") OR (all:\"k-means\")",
      "records_returned": 100,
      "records_added": 0,
      "error": null
    },
    {
      "anchor": "acoustic tokens",
      "search_term": "vector quantization",
      "search_query": "(all:\"acoustic tokens\") OR (all:\"vector quantization\")",
      "records_returned": 100,
      "records_added": 1,
      "error": null
    },
    {
      "anchor": "acoustic tokens",
      "search_term": "acoustic tokens",
      "search_query": "(all:\"acoustic tokens\") OR (all:\"acoustic tokens\")",
      "records_returned": 66,
      "records_added": 0,
      "error": null
    },
    {
      "anchor": "acoustic tokens",
      "search_term": "semantic distillation",
      "search_query": "(all:\"acoustic tokens\") OR (all:\"semantic distillation\")",
      "records_returned": 100,
      "records_added": 0,
      "error": null
    },
    {
      "anchor": "acoustic tokens",
      "search_term": "neural codec",
      "search_query": "(all:\"acoustic tokens\") OR (all:\"neural codec\")",
      "records_returned": 100,
      "records_added": 3,
      "error": null
    },
    {
      "anchor": "acoustic tokens",
      "search_term": "semantic tokens",
      "search_query": "(all:\"acoustic tokens\") OR (all:\"semantic tokens\")",
      "records_returned": 100,
      "records_added": 0,
      "error": null
    },
    {
      "anchor": "acoustic tokens",
      "search_term": "self supervised learning",
      "search_query": "(all:\"acoustic tokens\") OR (all:\"self supervised learning\")",
      "records_returned": 100,
      "records_added": 0,
      "error": null
    },
    {
      "anchor": "acoustic tokens",
      "search_term": "hubert",
      "search_query": "(all:\"acoustic tokens\") OR (all:\"hubert\")",
      "records_returned": 100,
      "records_added": 2,
      "error": null
    },
    {
      "anchor": "acoustic tokens",
      "search_term": "deduplication",
      "search_query": "(all:\"acoustic tokens\") OR (all:\"deduplication\")",
      "records_returned": 100,
      "records_added": 4,
      "error": null
    },
    {
      "anchor": "acoustic tokens",
      "search_term": "acoustic bpe",
      "search_query": "(all:\"acoustic tokens\") OR (all:\"acoustic bpe\")",
      "records_returned": 68,
      "records_added": 0,
      "error": null
    },
    {
      "anchor": "acoustic tokens",
      "search_term": "variable frame rate",
      "search_query": "(all:\"acoustic tokens\") OR (all:\"variable frame rate\")",
      "records_returned": 84,
      "records_added": 0,
      "error": null
    },
    {
      "anchor": "acoustic tokens",
      "search_term": "reconstruction metrics",
      "search_query": "(all:\"acoustic tokens\") OR (all:\"reconstruction metrics\")",
      "records_returned": 100,
      "records_added": 0,
      "error": null
    },
    {
      "anchor": "acoustic tokens",
      "search_term": "pesq",
      "search_query": "(all:\"acoustic tokens\") OR (all:\"pesq\")",
      "records_returned": 100,
      "records_added": 0,
      "error": null
    },
    {
      "anchor": "acoustic tokens",
      "search_term": "stoi",
      "search_query": "(all:\"acoustic tokens\") OR (all:\"stoi\")",
      "records_returned": 100,
      "records_added": 0,
      "error": null
    },
    {
      "anchor": "acoustic tokens",
      "search_term": "discrete speech tokens",
      "search_query": "(all:\"acoustic tokens\") OR (all:\"discrete speech tokens\")",
      "records_returned": 98,
      "records_added": 0,
      "error": null
    },
    {
      "anchor": "acoustic tokens",
      "search_term": "speech tokenization",
      "search_query": "(all:\"acoustic tokens\") OR (all:\"speech tokenization\")",
      "records_returned": 100,
      "records_added": 0,
      "error": null
    },
    {
      "anchor": "acoustic tokens",
      "search_term": "speech token vocoder",
      "search_query": "(all:\"acoustic tokens\") OR (all:\"speech token vocoder\")",
      "records_returned": 67,
      "records_added": 0,
      "error": null
    },
    {
      "anchor": "semantic tokens",
      "search_term": "offline clustering",
      "search_query": "(all:\"semantic tokens\") OR (all:\"offline clustering\")",
      "records_returned": 100,
      "records_added": 8,
      "error": null
    },
    {
      "anchor": "semantic tokens",
      "search_term": "k-means",
      "search_query": "(all:\"semantic tokens\") OR (all:\"k-means\")",
      "records_returned": 100,
      "records_added": 0,
      "error": null
    },
    {
      "anchor": "semantic tokens",
      "search_term": "vector quantization",
      "search_query": "(all:\"semantic tokens\") OR (all:\"vector quantization\")",
      "records_returned": 100,
      "records_added": 0,
      "error": null
    },
    {
      "anchor": "semantic tokens",
      "search_term": "acoustic tokens",
      "search_query": "(all:\"semantic tokens\") OR (all:\"acoustic tokens\")",
      "records_returned": 100,
      "records_added": 0,
      "error": null
    },
    {
      "anchor": "semantic tokens",
      "search_term": "semantic distillation",
      "search_query": "(all:\"semantic tokens\") OR (all:\"semantic distillation\")",
      "records_returned": 100,
      "records_added": 0,
      "error": null
    },
    {
      "anchor": "semantic tokens",
      "search_term": "neural codec",
      "search_query": "(all:\"semantic tokens\") OR (all:\"neural codec\")",
      "records_returned": 100,
      "records_added": 0,
      "error": null
    },
    {
      "anchor": "semantic tokens",
      "search_term": "semantic tokens",
      "search_query": "(all:\"semantic tokens\") OR (all:\"semantic tokens\")",
      "records_returned": 100,
      "records_added": 7,
      "error": null
    },
    {
      "anchor": "semantic tokens",
      "search_term": "self supervised learning",
      "search_query": "(all:\"semantic tokens\") OR (all:\"self supervised learning\")",
      "records_returned": 100,
      "records_added": 0,
      "error": null
    },
    {
      "anchor": "semantic tokens",
      "search_term": "hubert",
      "search_query": "(all:\"semantic tokens\") OR (all:\"hubert\")",
      "records_returned": 100,
      "records_added": 0,
      "error": null
    },
    {
      "anchor": "semantic tokens",
      "search_term": "deduplication",
      "search_query": "(all:\"semantic tokens\") OR (all:\"deduplication\")",
      "records_returned": 100,
      "records_added": 0,
      "error": null
    },
    {
      "anchor": "semantic tokens",
      "search_term": "acoustic bpe",
      "search_query": "(all:\"semantic tokens\") OR (all:\"acoustic bpe\")",
      "records_returned": 100,
      "records_added": 0,
      "error": null
    },
    {
      "anchor": "semantic tokens",
      "search_term": "variable frame rate",
      "search_query": "(all:\"semantic tokens\") OR (all:\"variable frame rate\")",
      "records_returned": 100,
      "records_added": 0,
      "error": null
    },
    {
      "anchor": "semantic tokens",
      "search_term": "reconstruction metrics",
      "search_query": "(all:\"semantic tokens\") OR (all:\"reconstruction metrics\")",
      "records_returned": 100,
      "records_added": 0,
      "error": null
    },
    {
      "anchor": "semantic tokens",
      "search_term": "pesq",
      "search_query": "(all:\"semantic tokens\") OR (all:\"pesq\")",
      "records_returned": 100,
      "records_added": 0,
      "error": null
    },
    {
      "anchor": "semantic tokens",
      "search_term": "stoi",
      "search_query": "(all:\"semantic tokens\") OR (all:\"stoi\")",
      "records_returned": 100,
      "records_added": 0,
      "error": null
    },
    {
      "anchor": "semantic tokens",
      "search_term": "discrete speech tokens",
      "search_query": "(all:\"semantic tokens\") OR (all:\"discrete speech tokens\")",
      "records_returned": 100,
      "records_added": 0,
      "error": null
    },
    {
      "anchor": "semantic tokens",
      "search_term": "speech tokenization",
      "search_query": "(all:\"semantic tokens\") OR (all:\"speech tokenization\")",
      "records_returned": 100,
      "records_added": 0,
      "error": null
    },
    {
      "anchor": "semantic tokens",
      "search_term": "speech token vocoder",
      "search_query": "(all:\"semantic tokens\") OR (all:\"speech token vocoder\")",
      "records_returned": 100,
      "records_added": 0,
      "error": null
    }
  ]
}
```

#### workspaces/discrete_audio_tokens_more_than_a_survey-api/harvest/dblp_records.json

```json
[
  {
    "key": "conf/icassp/ShenGD0024",
    "title": "Acoustic BPE for Speech Generation with Discrete Tokens.",
    "year": "2024",
    "url": "https://dblp.org/rec/conf/icassp/ShenGD0024"
  },
  {
    "key": "journals/corr/abs-2310-14580",
    "title": "Acoustic BPE for Speech Generation with Discrete Tokens.",
    "year": "2023",
    "url": "https://dblp.org/rec/journals/corr/abs-2310-14580"
  },
  {
    "key": "conf/acl/0003GXLCLL25",
    "title": "Analyzing and Mitigating Inconsistency in Discrete Speech Tokens for Neural Codec Language Models.",
    "year": "2025",
    "url": "https://dblp.org/rec/conf/acl/0003GXLCLL25"
  },
  {
    "key": "journals/corr/abs-2411-08742",
    "title": "A Comparative Study of Discrete Speech Tokens for Semantic-Related Tasks with Large Language Models.",
    "year": "2024",
    "url": "https://dblp.org/rec/journals/corr/abs-2411-08742"
  },
  {
    "key": "conf/interspeech/OndaIFSM25",
    "title": "Discrete Tokens Exhibit Interlanguage Speech Intelligibility Benefit: an Analytical Study Towards Accent-robust ASR Only with Native Speech Data.",
    "year": "2025",
    "url": "https://dblp.org/rec/conf/interspeech/OndaIFSM25"
  },
  {
    "key": "journals/corr/abs-2505-16182",
    "title": "Discrete Tokens Exhibit Interlanguage Speech Intelligibility Benefit: an Analytical Study Towards Accent-robust ASR Only with Native Speech Data.",
    "year": "2025",
    "url": "https://dblp.org/rec/journals/corr/abs-2505-16182"
  },
  {
    "key": "journals/corr/abs-2508-17863",
    "title": "Speech Discrete Tokens or Continuous Features? A Comparative Analysis for Spoken Language Understanding in SpeechLLMs.",
    "year": "2025",
    "url": "https://dblp.org/rec/journals/corr/abs-2508-17863"
  },
  {
    "key": "journals/corr/abs-2509-09631",
    "title": "DiFlow-TTS: Discrete Flow Matching with Factorized Speech Tokens for Low-Latency Zero-Shot Text-To-Speech.",
    "year": "2025",
    "url": "https://dblp.org/rec/journals/corr/abs-2509-09631"
  },
  {
    "key": "conf/interspeech/ErdoganWCBTZH23",
    "title": "TokenSplit: Using Discrete Speech Representations for Direct, Refined, and Transcript-Conditioned Speech Separation and Recognition.",
    "year": "2023",
    "url": "https://dblp.org/rec/conf/interspeech/ErdoganWCBTZH23"
  },
  {
    "key": "journals/corr/abs-2308-10415",
    "title": "TokenSplit: Using Discrete Speech Representations for Direct, Refined, and Transcript-Conditioned Speech Separation and Recognition.",
    "year": "2023",
    "url": "https://dblp.org/rec/journals/corr/abs-2308-10415"
  },
  {
    "key": "conf/icassp/WangXGHXCLDL25",
    "title": "Phone-purity Guided Discrete Tokens for Dysarthric Speech Recognition.",
    "year": "2025",
    "url": "https://dblp.org/rec/conf/icassp/WangXGHXCLDL25"
  },
  {
    "key": "journals/corr/abs-2501-04379",
    "title": "Phone-purity Guided Discrete Tokens for Dysarthric Speech Recognition.",
    "year": "2025",
    "url": "https://dblp.org/rec/journals/corr/abs-2501-04379"
  },
  {
    "key": "journals/corr/abs-2502-06490",
    "title": "Recent Advances in Discrete Speech Tokens: A Review.",
    "year": "2025",
    "url": "https://dblp.org/rec/journals/corr/abs-2502-06490"
  },
  {
    "key": "journals/corr/abs-2506-16738",
    "title": "LM-SPT: LM-Aligned Semantic Distillation for Speech Tokenization.",
    "year": "2025",
    "url": "https://dblp.org/rec/journals/corr/abs-2506-16738"
  },
  {
    "key": "conf/eusipco/RouxRWD24",
    "title": "A Comprehensive Analysis of Tokenization and Self-Supervised Learning in End-to-End Automatic Speech Recognition Applied on French Language.",
    "year": "2024",
    "url": "https://dblp.org/rec/conf/eusipco/RouxRWD24"
  },
  {
    "key": "journals/corr/abs-2509-04685",
    "title": "Say More with Less: Variable-Frame-Rate Speech Tokenization via Adaptive Clustering and Implicit Duration Coding.",
    "year": "2025",
    "url": "https://dblp.org/rec/journals/corr/abs-2509-04685"
  },
  {
    "key": "journals/corr/abs-2310-07246",
    "title": "Vec-Tok Speech: speech vectorization and tokenization for neural speech generation.",
    "year": "2023",
    "url": "https://dblp.org/rec/journals/corr/abs-2310-07246"
  },
  {
    "key": "conf/interspeech/KandoMT25",
    "title": "Exploring the Effect of Segmentation and Vocabulary Size on Speech Tokenization for Speech Language Models.",
    "year": "2025",
    "url": "https://dblp.org/rec/conf/interspeech/KandoMT25"
  },
  {
    "key": "journals/corr/abs-2505-17446",
    "title": "Exploring the Effect of Segmentation and Vocabulary Size on Speech Tokenization for Speech Language Models.",
    "year": "2025",
    "url": "https://dblp.org/rec/journals/corr/abs-2505-17446"
  },
  {
    "key": "conf/acl/HuangMK24",
    "title": "RepCodec: A Speech Representation Codec for Speech Tokenization.",
    "year": "2024",
    "url": "https://dblp.org/rec/conf/acl/HuangMK24"
  },
  {
    "key": "conf/interspeech/MessicaA24",
    "title": "NAST: Noise Aware Speech Tokenization for Speech Language Models.",
    "year": "2024",
    "url": "https://dblp.org/rec/conf/interspeech/MessicaA24"
  },
  {
    "key": "journals/corr/abs-2406-11037",
    "title": "NAST: Noise Aware Speech Tokenization for Speech Language Models.",
    "year": "2024",
    "url": "https://dblp.org/rec/journals/corr/abs-2406-11037"
  },
  {
    "key": "journals/corr/abs-2309-00169",
    "title": "RepCodec: A Speech Representation Codec for Speech Tokenization.",
    "year": "2023",
    "url": "https://dblp.org/rec/journals/corr/abs-2309-00169"
  },
  {
    "key": "journals/speech/AsoTTS20",
    "title": "Acoustic model-based subword tokenization and prosodic-context extraction without language knowledge for text-to-speech synthesis.",
    "year": "2020",
    "url": "https://dblp.org/rec/journals/speech/AsoTTS20"
  },
  {
    "key": "conf/icassp/SinghD025",
    "title": "BEST-STD: Bidirectional Mamba-Enhanced Speech Tokenization for Spoken Term Detection.",
    "year": "2025",
    "url": "https://dblp.org/rec/conf/icassp/SinghD025"
  },
  {
    "key": "conf/interspeech/KhuranaKLBNGZHH25",
    "title": "Factorized RVQ-GAN For Disentangled Speech Tokenization.",
    "year": "2025",
    "url": "https://dblp.org/rec/conf/interspeech/KhuranaKLBNGZHH25"
  },
  {
    "key": "conf/icassp/WeiCLL17",
    "title": "Personalized acoustic modeling by weakly supervised multi-task deep learning using acoustic tokens discovered from unlabeled data.",
    "year": "2017",
    "url": "https://dblp.org/rec/conf/icassp/WeiCLL17"
  },
  {
    "key": "journals/corr/WeiCLL17",
    "title": "Personalized Acoustic Modeling by Weakly Supervised Multi-Task Deep Learning using Acoustic Tokens Discovered from Unlabeled Data.",
    "year": "2017",
    "url": "https://dblp.org/rec/journals/corr/WeiCLL17"
  },
  {
    "key": "journals/corr/abs-2507-12825",
    "title": "Autoregressive Speech Enhancement via Acoustic Tokens.",
    "year": "2025",
    "url": "https://dblp.org/rec/journals/corr/abs-2507-12825"
  },
  {
    "key": "journals/corr/abs-2509-14882",
    "title": "Llama-Mimi: Speech Language Models with Interleaved Semantic and Acoustic Tokens.",
    "year": "2025",
    "url": "https://dblp.org/rec/journals/corr/abs-2509-14882"
  },
  {
    "key": "journals/taslp/FengZM24",
    "title": "Masking Hierarchical Tokens for Underwater Acoustic Target Recognition With Self-Supervised Learning.",
    "year": "2024",
    "url": "https://dblp.org/rec/journals/taslp/FengZM24"
  },
  {
    "key": "conf/sigtype/SanPAHKAJ24",
    "title": "Predicting positive transfer for improved low-resource speech recognition using acoustic pseudo-tokens.",
    "year": "2024",
    "url": "https://dblp.org/rec/conf/sigtype/SanPAHKAJ24"
  },
  {
    "key": "journals/corr/abs-2402-02302",
    "title": "Predicting positive transfer for improved low-resource speech recognition using acoustic pseudo-tokens.",
    "year": "2024",
    "url": "https://dblp.org/rec/journals/corr/abs-2402-02302"
  },
  {
    "key": "conf/icdip/ZhouWLWT23",
    "title": "UATR-MSG-Transformer: A Deep Learning Network for Underwater Acoustic Target Recognition Based on Spectrogram Feature Fusion and Transformer with Messenger Tokens.",
    "year": "2023",
    "url": "https://dblp.org/rec/conf/icdip/ZhouWLWT23"
  },
  {
    "key": "journals/bdcc/RodionovLKOGP25",
    "title": "Integration of Associative Tokens into Thematic Hyperspace: A Method for Determining Semantically Significant Clusters in Dynamic Text Streams.",
    "year": "2025",
    "url": "https://dblp.org/rec/journals/bdcc/RodionovLKOGP25"
  },
  {
    "key": "journals/spl/PengXXXL25",
    "title": "Large Model Empowered Multi-Modal Semantic Communication With Selective Tokens for Training.",
    "year": "2025",
    "url": "https://dblp.org/rec/journals/spl/PengXXXL25"
  },
  {
    "key": "journals/tacl/HaslettC25",
    "title": "How Much Semantic Information is Available in Large Language Model Tokens?",
    "year": "2025",
    "url": "https://dblp.org/rec/journals/tacl/HaslettC25"
  },
  {
    "key": "conf/cvpr/KalibhatKNZSSKF25",
    "title": "Understanding the Effect of using Semantically Meaningful Tokens for Visual Representation Learning.",
    "year": "2025",
    "url": "https://dblp.org/rec/conf/cvpr/KalibhatKNZSSKF25"
  },
  {
    "key": "conf/icassp/ZhaoMLXXZAGLF25",
    "title": "Textless Streaming Speech-to-Speech Translation using Semantic Speech Tokens.",
    "year": "2025",
    "url": "https://dblp.org/rec/conf/icassp/ZhaoMLXXZAGLF25"
  },
  {
    "key": "journals/corr/abs-2505-13775",
    "title": "Beyond Semantics: The Unreasonable Effectiveness of Reasonless Intermediate Tokens.",
    "year": "2025",
    "url": "https://dblp.org/rec/journals/corr/abs-2505-13775"
  },
  {
    "key": "journals/corr/abs-2506-19028",
    "title": "Quantifying Fairness in LLMs Beyond Tokens: A Semantic and Statistical Perspective.",
    "year": "2025",
    "url": "https://dblp.org/rec/journals/corr/abs-2506-19028"
  },
  {
    "key": "journals/corr/abs-2508-02401",
    "title": "CompressKV: Semantic Retrieval Heads Know What Tokens are Not Important Before Generation.",
    "year": "2025",
    "url": "https://dblp.org/rec/journals/corr/abs-2508-02401"
  },
  {
    "key": "journals/corr/abs-2508-03695",
    "title": "Trokens: Semantic-Aware Relational Trajectory Tokens for Few-Shot Action Recognition.",
    "year": "2025",
    "url": "https://dblp.org/rec/journals/corr/abs-2508-03695"
  }
]
```

#### workspaces/discrete_audio_tokens_more_than_a_survey-api/harvest/dblp_title_arxiv_matches.json

```json
[
  {
    "dblp_key": "conf/icassp/ShenGD0024",
    "title": "Acoustic BPE for Speech Generation with Discrete Tokens.",
    "status": "matched",
    "arxiv_ids": [
      "2310.14580"
    ],
    "query": "ti:\"Acoustic BPE for Speech Generation with Discrete Tokens.\""
  },
  {
    "dblp_key": "journals/corr/abs-2310-14580",
    "title": "Acoustic BPE for Speech Generation with Discrete Tokens.",
    "status": "duplicate_title"
  },
  {
    "dblp_key": "conf/acl/0003GXLCLL25",
    "title": "Analyzing and Mitigating Inconsistency in Discrete Speech Tokens for Neural Codec Language Models.",
    "status": "no_match",
    "query": "ti:\"Analyzing and Mitigating Inconsistency in Discrete Speech Tokens for Neural Codec Language Models.\""
  },
  {
    "dblp_key": "journals/corr/abs-2411-08742",
    "title": "A Comparative Study of Discrete Speech Tokens for Semantic-Related Tasks with Large Language Models.",
    "status": "matched",
    "arxiv_ids": [
      "2411.08742"
    ],
    "query": "ti:\"A Comparative Study of Discrete Speech Tokens for Semantic-Related Tasks with Large Language Models.\""
  },
  {
    "dblp_key": "conf/interspeech/OndaIFSM25",
    "title": "Discrete Tokens Exhibit Interlanguage Speech Intelligibility Benefit: an Analytical Study Towards Accent-robust ASR Only with Native Speech Data.",
    "status": "matched",
    "arxiv_ids": [
      "2505.16182"
    ],
    "query": "ti:\"Discrete Tokens Exhibit Interlanguage Speech Intelligibility Benefit: an Analytical Study Towards Accent-robust ASR Only with Native Speech Data.\""
  },
  {
    "dblp_key": "journals/corr/abs-2505-16182",
    "title": "Discrete Tokens Exhibit Interlanguage Speech Intelligibility Benefit: an Analytical Study Towards Accent-robust ASR Only with Native Speech Data.",
    "status": "duplicate_title"
  },
  {
    "dblp_key": "journals/corr/abs-2508-17863",
    "title": "Speech Discrete Tokens or Continuous Features? A Comparative Analysis for Spoken Language Understanding in SpeechLLMs.",
    "status": "matched",
    "arxiv_ids": [
      "2508.17863"
    ],
    "query": "ti:\"Speech Discrete Tokens or Continuous Features? A Comparative Analysis for Spoken Language Understanding in SpeechLLMs.\""
  },
  {
    "dblp_key": "journals/corr/abs-2509-09631",
    "title": "DiFlow-TTS: Discrete Flow Matching with Factorized Speech Tokens for Low-Latency Zero-Shot Text-To-Speech.",
    "status": "matched",
    "arxiv_ids": [
      "2509.09631"
    ],
    "query": "ti:\"DiFlow-TTS: Discrete Flow Matching with Factorized Speech Tokens for Low-Latency Zero-Shot Text-To-Speech.\""
  },
  {
    "dblp_key": "conf/interspeech/ErdoganWCBTZH23",
    "title": "TokenSplit: Using Discrete Speech Representations for Direct, Refined, and Transcript-Conditioned Speech Separation and Recognition.",
    "status": "matched",
    "arxiv_ids": [
      "2308.10415"
    ],
    "query": "ti:\"TokenSplit: Using Discrete Speech Representations for Direct, Refined, and Transcript-Conditioned Speech Separation and Recognition.\""
  },
  {
    "dblp_key": "journals/corr/abs-2308-10415",
    "title": "TokenSplit: Using Discrete Speech Representations for Direct, Refined, and Transcript-Conditioned Speech Separation and Recognition.",
    "status": "duplicate_title"
  },
  {
    "dblp_key": "conf/icassp/WangXGHXCLDL25",
    "title": "Phone-purity Guided Discrete Tokens for Dysarthric Speech Recognition.",
    "status": "matched",
    "arxiv_ids": [
      "2501.04379"
    ],
    "query": "ti:\"Phone-purity Guided Discrete Tokens for Dysarthric Speech Recognition.\""
  },
  {
    "dblp_key": "journals/corr/abs-2501-04379",
    "title": "Phone-purity Guided Discrete Tokens for Dysarthric Speech Recognition.",
    "status": "duplicate_title"
  },
  {
    "dblp_key": "journals/corr/abs-2502-06490",
    "title": "Recent Advances in Discrete Speech Tokens: A Review.",
    "status": "matched",
    "arxiv_ids": [
      "2502.06490"
    ],
    "query": "ti:\"Recent Advances in Discrete Speech Tokens: A Review.\""
  },
  {
    "dblp_key": "journals/corr/abs-2506-16738",
    "title": "LM-SPT: LM-Aligned Semantic Distillation for Speech Tokenization.",
    "status": "matched",
    "arxiv_ids": [
      "2506.16738"
    ],
    "query": "ti:\"LM-SPT: LM-Aligned Semantic Distillation for Speech Tokenization.\""
  },
  {
    "dblp_key": "conf/eusipco/RouxRWD24",
    "title": "A Comprehensive Analysis of Tokenization and Self-Supervised Learning in End-to-End Automatic Speech Recognition Applied on French Language.",
    "status": "no_match",
    "query": "ti:\"A Comprehensive Analysis of Tokenization and Self-Supervised Learning in End-to-End Automatic Speech Recognition Applied on French Language.\""
  },
  {
    "dblp_key": "journals/corr/abs-2509-04685",
    "title": "Say More with Less: Variable-Frame-Rate Speech Tokenization via Adaptive Clustering and Implicit Duration Coding.",
    "status": "matched",
    "arxiv_ids": [
      "2509.04685"
    ],
    "query": "ti:\"Say More with Less: Variable-Frame-Rate Speech Tokenization via Adaptive Clustering and Implicit Duration Coding.\""
  },
  {
    "dblp_key": "journals/corr/abs-2310-07246",
    "title": "Vec-Tok Speech: speech vectorization and tokenization for neural speech generation.",
    "status": "matched",
    "arxiv_ids": [
      "2310.07246"
    ],
    "query": "ti:\"Vec-Tok Speech: speech vectorization and tokenization for neural speech generation.\""
  },
  {
    "dblp_key": "conf/interspeech/KandoMT25",
    "title": "Exploring the Effect of Segmentation and Vocabulary Size on Speech Tokenization for Speech Language Models.",
    "status": "matched",
    "arxiv_ids": [
      "2505.17446"
    ],
    "query": "ti:\"Exploring the Effect of Segmentation and Vocabulary Size on Speech Tokenization for Speech Language Models.\""
  },
  {
    "dblp_key": "journals/corr/abs-2505-17446",
    "title": "Exploring the Effect of Segmentation and Vocabulary Size on Speech Tokenization for Speech Language Models.",
    "status": "duplicate_title"
  },
  {
    "dblp_key": "conf/acl/HuangMK24",
    "title": "RepCodec: A Speech Representation Codec for Speech Tokenization.",
    "status": "matched",
    "arxiv_ids": [
      "2309.00169"
    ],
    "query": "ti:\"RepCodec: A Speech Representation Codec for Speech Tokenization.\""
  },
  {
    "dblp_key": "conf/interspeech/MessicaA24",
    "title": "NAST: Noise Aware Speech Tokenization for Speech Language Models.",
    "status": "matched",
    "arxiv_ids": [
      "2406.11037"
    ],
    "query": "ti:\"NAST: Noise Aware Speech Tokenization for Speech Language Models.\""
  },
  {
    "dblp_key": "journals/corr/abs-2406-11037",
    "title": "NAST: Noise Aware Speech Tokenization for Speech Language Models.",
    "status": "duplicate_title"
  },
  {
    "dblp_key": "journals/corr/abs-2309-00169",
    "title": "RepCodec: A Speech Representation Codec for Speech Tokenization.",
    "status": "duplicate_title"
  },
  {
    "dblp_key": "journals/speech/AsoTTS20",
    "title": "Acoustic model-based subword tokenization and prosodic-context extraction without language knowledge for text-to-speech synthesis.",
    "status": "no_match",
    "query": "ti:\"Acoustic model-based subword tokenization and prosodic-context extraction without language knowledge for text-to-speech synthesis.\""
  },
  {
    "dblp_key": "conf/icassp/SinghD025",
    "title": "BEST-STD: Bidirectional Mamba-Enhanced Speech Tokenization for Spoken Term Detection.",
    "status": "matched",
    "arxiv_ids": [
      "2411.14100"
    ],
    "query": "ti:\"BEST-STD: Bidirectional Mamba-Enhanced Speech Tokenization for Spoken Term Detection.\""
  },
  {
    "dblp_key": "conf/interspeech/KhuranaKLBNGZHH25",
    "title": "Factorized RVQ-GAN For Disentangled Speech Tokenization.",
    "status": "matched",
    "arxiv_ids": [
      "2506.15456"
    ],
    "query": "ti:\"Factorized RVQ-GAN For Disentangled Speech Tokenization.\""
  },
  {
    "dblp_key": "conf/icassp/WeiCLL17",
    "title": "Personalized acoustic modeling by weakly supervised multi-task deep learning using acoustic tokens discovered from unlabeled data.",
    "status": "matched",
    "arxiv_ids": [
      "1706.07793"
    ],
    "query": "ti:\"Personalized acoustic modeling by weakly supervised multi-task deep learning using acoustic tokens discovered from unlabeled data.\""
  },
  {
    "dblp_key": "journals/corr/WeiCLL17",
    "title": "Personalized Acoustic Modeling by Weakly Supervised Multi-Task Deep Learning using Acoustic Tokens Discovered from Unlabeled Data.",
    "status": "duplicate_title"
  },
  {
    "dblp_key": "journals/corr/abs-2507-12825",
    "title": "Autoregressive Speech Enhancement via Acoustic Tokens.",
    "status": "matched",
    "arxiv_ids": [
      "2507.12825"
    ],
    "query": "ti:\"Autoregressive Speech Enhancement via Acoustic Tokens.\""
  },
  {
    "dblp_key": "journals/corr/abs-2509-14882",
    "title": "Llama-Mimi: Speech Language Models with Interleaved Semantic and Acoustic Tokens.",
    "status": "matched",
    "arxiv_ids": [
      "2509.14882"
    ],
    "query": "ti:\"Llama-Mimi: Speech Language Models with Interleaved Semantic and Acoustic Tokens.\""
  },
  {
    "dblp_key": "journals/taslp/FengZM24",
    "title": "Masking Hierarchical Tokens for Underwater Acoustic Target Recognition With Self-Supervised Learning.",
    "status": "no_match",
    "query": "ti:\"Masking Hierarchical Tokens for Underwater Acoustic Target Recognition With Self-Supervised Learning.\""
  },
  {
    "dblp_key": "conf/sigtype/SanPAHKAJ24",
    "title": "Predicting positive transfer for improved low-resource speech recognition using acoustic pseudo-tokens.",
    "status": "matched",
    "arxiv_ids": [
      "2402.02302"
    ],
    "query": "ti:\"Predicting positive transfer for improved low-resource speech recognition using acoustic pseudo-tokens.\""
  },
  {
    "dblp_key": "journals/corr/abs-2402-02302",
    "title": "Predicting positive transfer for improved low-resource speech recognition using acoustic pseudo-tokens.",
    "status": "duplicate_title"
  },
  {
    "dblp_key": "conf/icdip/ZhouWLWT23",
    "title": "UATR-MSG-Transformer: A Deep Learning Network for Underwater Acoustic Target Recognition Based on Spectrogram Feature Fusion and Transformer with Messenger Tokens.",
    "status": "no_match",
    "query": "ti:\"UATR-MSG-Transformer: A Deep Learning Network for Underwater Acoustic Target Recognition Based on Spectrogram Feature Fusion and Transformer with Messenger Tokens.\""
  },
  {
    "dblp_key": "journals/bdcc/RodionovLKOGP25",
    "title": "Integration of Associative Tokens into Thematic Hyperspace: A Method for Determining Semantically Significant Clusters in Dynamic Text Streams.",
    "status": "no_match",
    "query": "ti:\"Integration of Associative Tokens into Thematic Hyperspace: A Method for Determining Semantically Significant Clusters in Dynamic Text Streams.\""
  },
  {
    "dblp_key": "journals/spl/PengXXXL25",
    "title": "Large Model Empowered Multi-Modal Semantic Communication With Selective Tokens for Training.",
    "status": "no_match",
    "query": "ti:\"Large Model Empowered Multi-Modal Semantic Communication With Selective Tokens for Training.\""
  },
  {
    "dblp_key": "journals/tacl/HaslettC25",
    "title": "How Much Semantic Information is Available in Large Language Model Tokens?",
    "status": "no_match",
    "query": "ti:\"How Much Semantic Information is Available in Large Language Model Tokens?\""
  },
  {
    "dblp_key": "conf/cvpr/KalibhatKNZSSKF25",
    "title": "Understanding the Effect of using Semantically Meaningful Tokens for Visual Representation Learning.",
    "status": "matched",
    "arxiv_ids": [
      "2405.16401"
    ],
    "query": "ti:\"Understanding the Effect of using Semantically Meaningful Tokens for Visual Representation Learning.\""
  },
  {
    "dblp_key": "conf/icassp/ZhaoMLXXZAGLF25",
    "title": "Textless Streaming Speech-to-Speech Translation using Semantic Speech Tokens.",
    "status": "matched",
    "arxiv_ids": [
      "2410.03298"
    ],
    "query": "ti:\"Textless Streaming Speech-to-Speech Translation using Semantic Speech Tokens.\""
  },
  {
    "dblp_key": "journals/corr/abs-2505-13775",
    "title": "Beyond Semantics: The Unreasonable Effectiveness of Reasonless Intermediate Tokens.",
    "status": "matched",
    "arxiv_ids": [
      "2505.13775"
    ],
    "query": "ti:\"Beyond Semantics: The Unreasonable Effectiveness of Reasonless Intermediate Tokens.\""
  },
  {
    "dblp_key": "journals/corr/abs-2506-19028",
    "title": "Quantifying Fairness in LLMs Beyond Tokens: A Semantic and Statistical Perspective.",
    "status": "matched",
    "arxiv_ids": [
      "2506.19028"
    ],
    "query": "ti:\"Quantifying Fairness in LLMs Beyond Tokens: A Semantic and Statistical Perspective.\""
  },
  {
    "dblp_key": "journals/corr/abs-2508-02401",
    "title": "CompressKV: Semantic Retrieval Heads Know What Tokens are Not Important Before Generation.",
    "status": "matched",
    "arxiv_ids": [
      "2508.02401"
    ],
    "query": "ti:\"CompressKV: Semantic Retrieval Heads Know What Tokens are Not Important Before Generation.\""
  },
  {
    "dblp_key": "journals/corr/abs-2508-03695",
    "title": "Trokens: Semantic-Aware Relational Trajectory Tokens for Few-Shot Action Recognition.",
    "status": "matched",
    "arxiv_ids": [
      "2508.03695"
    ],
    "query": "ti:\"Trokens: Semantic-Aware Relational Trajectory Tokens for Few-Shot Action Recognition.\""
  }
]
```

#### workspaces/discrete_audio_tokens_more_than_a_survey-api/harvest/semantic_scholar_records.json

```json
[]
```

#### workspaces/discrete_audio_tokens_more_than_a_survey-api/criteria/combined_notes.txt

```text
### PDF Background (Survey Summaries)
### PDF Topic Definition
本篇系統性綜述聚焦於「離散語音標記（Discrete Speech Tokens）」的技術發展與應用，特別是在大語言模型（LLM）時代下的語音生成、理解與跨模態語言建模。離散語音標記指的是將連續語音訊號經過編碼與量化，轉換為一系列離散、緊湊且符號化的單元，方便於儲存、傳輸，並能與現有的文字語言模型架構無縫整合。主題涵蓋兩大核心類型：聲學標記（Acoustic Tokens）與語意標記（Semantic Tokens），分別著重於語音重建/壓縮與語音語意抽象。評估面向包括重建品質、語者轉換、語意建模能力、下游任務表現、資訊密度、比特率、流式處理能力、可擴展性等。

### PDF Key Trends
- **離散語音標記的雙主線發展**：聲學標記（如神經語音編解碼器）強調壓縮與重建；語意標記（如SSL模型）強調語音語意抽象與下游語言任務。
- **語音與文字的融合**：離散標記讓語音能以類似文字token的方式進行語言建模，推動語音LLM、端到端語音對話、語音生成等新應用。
- **多樣化的量化方法**：從k-means聚類、向量量化（VQ）、殘差VQ（RVQ）、分組VQ（GVQ）、有限純量量化（FSQ）到Gumbel-Softmax等，提升壓縮效率與資訊表達力。
- **語意蒸餾與解耦**：結合語音自監督學習（SSL）特徵、語意教師模型、語者/內容解耦等，提升標記的語意表現與下游可用性。
- **長度縮減與可變速率標記**：為解決語音token序列過長，發展如deduplication、acoustic BPE、可變速率（VFR）tokenization等技術。
- **應用廣泛**：涵蓋語音理解（ASR、意圖分類、語音翻譯）、語音生成（TTS、VC）、語音對話模型（SLM）、多語言/多任務統一建模等。

### PDF Capability Highlights
- 能將連續語音訊號轉換為高資訊密度、低比特率的離散符號序列。
- 支援多種量化策略與神經網路架構（CNN、Transformer、U-Net等）。
- 可針對語音重建、語意建模、語者/內容解耦等不同目標進行優化。
- 能與大語言模型架構無縫整合，實現語音與文字的統一建模。
- 支援流式（streaming）處理與低延遲應用需求。

### PDF Inclusion Signals
- 關鍵字：「discrete speech tokens」、「neural audio codec」、「speech tokenizer」、「spoken language modeling」、「semantic tokens」、「acoustic tokens」、「vector quantization」、「self-supervised learning」、「speech generation」、「token vocoder」。
- 章節參考：Section III（聲學標記）、Section IV（語意標記）、Section V（長度縮減與可變速率）、Section VI（分析與評測）、Section VII（應用）、Section VIII（挑戰與展望）。
- 涉及語音tokenization於語音生成、理解、對話、語音LLM等應用。
- 探討tokenization方法對下游語音任務（如ASR、TTS、VC、SLU、S2ST）之影響。
- 具體比較不同token類型在重建、語意建模、語者轉換等多維度的性能。

### PDF Exclusion Signals
- 只討論傳統連續語音特徵（如MFCC、梅爾頻譜）而未涉及離散化/量化者。
- 僅針對音樂、環境聲音等非語音離散標記技術，未聚焦語音應用。
- 只關注傳統信號處理編碼器（如MP3、Opus）而無神經網路或現代VQ方法。
- 未涉及語音與語言模型結合、語音token下游應用、或僅為單一技術細節（如單一VQ算法改進）。
- 研究主題偏向語者辨識、情緒辨識等單一下游任務，未討論tokenization對多任務/多模態語音建模的影響。

### PDF Notes
- Recent Advances in Discrete Speech Tokens: A Review: 
  - 系統性梳理離散語音標記的技術發展、分類、量化方法、神經架構、語意蒸餾、解耦、長度縮減、可變速率、下游應用與挑戰，並提供跨類型統一的實驗比較與未來展望，是LLM時代語音tokenization領域的代表性綜述。
### Web Search Notes
### Topic Definition
離散音訊標記（Discrete Audio Tokens）是指將連續音訊波形，透過神經音訊編碼器與量化機制（如向量量化、殘差向量量化等），轉換為有限詞彙集合中的離散符號序列。此類表示旨在在大幅降低位元率與序列長度的同時，保留可感知音質、語音語義（如音素、語義結構）以及說話人或聲學特徵，使音訊能以「類文字 token」的形式被語言模型處理。該概念最初源自神經音訊編碼（neural audio codec），近年則成為音訊語言模型（Audio Language Models, ALMs）與多模態大型語言模型的重要基石。([arxiv.org](https://arxiv.org/abs/2506.10274?utm_source=openai))

在研究脈絡上，離散音訊標記不僅服務於重建任務（codec），更被視為一種通用中介表示，可支援語音生成、語音理解、音樂建模與一般聲音建模等下游任務。相較於傳統連續特徵（如 Mel-spectrogram），離散標記更利於自回歸或 Transformer 式語言建模，並促進跨模態對齊與長期結構建模，因此逐漸從「編碼工具」演進為「表徵學習核心能力」。([sciencestack.ai](https://www.sciencestack.ai/paper/2209.03143v2?utm_source=openai))

### Summary
近年研究顯示，離散音訊標記正從單純的語音 codec 發展為支援語義、聲學與長時結構的多層次表示。研究亮點包括極低位元率下的高保真重建，以及可直接用於音訊語言模型與多模態生成。整體趨勢顯示，token 設計與訓練目標已成為影響音訊智慧系統能力的關鍵因素。([arxiv.org](https://arxiv.org/abs/2506.10274?utm_source=openai))

### Summary Topics
S1: 神經音訊編碼與離散化方法（VQ、RVQ、多碼本）  
S2: 語義導向與聲學導向音訊標記的分工與融合  
S3: 離散音訊標記於音訊語言模型與生成任務中的應用  
S4: 位元率、重建品質與下游任務效能之權衡分析  

### Inclusion Criteria (Required)
1. 主題定義：離散音訊標記（Discrete Audio Tokens）是指將連續音訊訊號轉換為有限詞彙集合中的離散符號序列，並用於重建、生成或理解等音訊任務。  
   條件：論文需明確提出或分析「離散化音訊表示」或「audio tokenization」作為核心研究對象，且全文需為英文、可進行學術評估。  
   source: https://arxiv.org/abs/2506.10274 （2025-06-12）  
   topic id: S1, S2  

2. 條件：論文需為同儕審查論文或可追溯之預印本（如 arXiv），並提供完整方法描述與實驗或分析。  
   source: https://arxiv.org/abs/2209.03143 （2022-09-07）  
   topic id: S3  

### Inclusion Criteria (Any-of Groups)
- Group 技術實作取向  
  * Option: 提出或分析神經音訊 codec（如 SoundStream、EnCodec）並以離散 token 形式輸出。  
    source: https://arxiv.org/abs/2209.03143 （2022-09-07）  
    topic ids: S1, S3  
  * Option: 著重語義強化或超低位元率之離散音訊標記設計（如語義編碼器、雙編碼架構）。  
    source: https://arxiv.org/abs/2405.00233 （2024-04-30）  
    topic ids: S2, S4  

- Group 應用與分析取向  
  * Option: 系統性比較、benchmark 或綜述離散音訊標記方法與下游任務效能。  
    source: https://arxiv.org/abs/2506.10274 （2025-06-12）  
    topic ids: S4  
  * Option: 將離散音訊標記應用於音訊語言模型、生成或理解任務，並分析其效益。  
    source: https://arxiv.org/abs/2504.10344 （2025-04-14）  
    topic ids: S3  

### Exclusion Criteria
- 僅使用連續音訊特徵（如 Mel-spectrogram、MFCC），未涉及任何離散化或 token 設計之研究。  
  source: internal  
  topic ids: S1  
- 僅為工程實作或程式庫說明，未提供方法創新、系統性分析或實驗驗證。  
  source: internal  
  topic ids: S4  
- 研究焦點為純文字或純影像 token，僅附帶音訊作為資料來源，未探討音訊離散表示本身。  
  source: internal  
  topic ids: S2  

### Sources
https://arxiv.org/abs/2506.10274  
https://arxiv.org/abs/2209.03143  
https://arxiv.org/abs/2405.00233  
https://arxiv.org/abs/2504.10344
```

#### workspaces/discrete_audio_tokens_more_than_a_survey-api/criteria/pdf_background.txt

```text
### PDF Topic Definition
本篇系統性綜述聚焦於「離散語音標記（Discrete Speech Tokens）」的技術發展與應用，特別是在大語言模型（LLM）時代下的語音生成、理解與跨模態語言建模。離散語音標記指的是將連續語音訊號經過編碼與量化，轉換為一系列離散、緊湊且符號化的單元，方便於儲存、傳輸，並能與現有的文字語言模型架構無縫整合。主題涵蓋兩大核心類型：聲學標記（Acoustic Tokens）與語意標記（Semantic Tokens），分別著重於語音重建/壓縮與語音語意抽象。評估面向包括重建品質、語者轉換、語意建模能力、下游任務表現、資訊密度、比特率、流式處理能力、可擴展性等。

### PDF Key Trends
- **離散語音標記的雙主線發展**：聲學標記（如神經語音編解碼器）強調壓縮與重建；語意標記（如SSL模型）強調語音語意抽象與下游語言任務。
- **語音與文字的融合**：離散標記讓語音能以類似文字token的方式進行語言建模，推動語音LLM、端到端語音對話、語音生成等新應用。
- **多樣化的量化方法**：從k-means聚類、向量量化（VQ）、殘差VQ（RVQ）、分組VQ（GVQ）、有限純量量化（FSQ）到Gumbel-Softmax等，提升壓縮效率與資訊表達力。
- **語意蒸餾與解耦**：結合語音自監督學習（SSL）特徵、語意教師模型、語者/內容解耦等，提升標記的語意表現與下游可用性。
- **長度縮減與可變速率標記**：為解決語音token序列過長，發展如deduplication、acoustic BPE、可變速率（VFR）tokenization等技術。
- **應用廣泛**：涵蓋語音理解（ASR、意圖分類、語音翻譯）、語音生成（TTS、VC）、語音對話模型（SLM）、多語言/多任務統一建模等。

### PDF Capability Highlights
- 能將連續語音訊號轉換為高資訊密度、低比特率的離散符號序列。
- 支援多種量化策略與神經網路架構（CNN、Transformer、U-Net等）。
- 可針對語音重建、語意建模、語者/內容解耦等不同目標進行優化。
- 能與大語言模型架構無縫整合，實現語音與文字的統一建模。
- 支援流式（streaming）處理與低延遲應用需求。

### PDF Inclusion Signals
- 關鍵字：「discrete speech tokens」、「neural audio codec」、「speech tokenizer」、「spoken language modeling」、「semantic tokens」、「acoustic tokens」、「vector quantization」、「self-supervised learning」、「speech generation」、「token vocoder」。
- 章節參考：Section III（聲學標記）、Section IV（語意標記）、Section V（長度縮減與可變速率）、Section VI（分析與評測）、Section VII（應用）、Section VIII（挑戰與展望）。
- 涉及語音tokenization於語音生成、理解、對話、語音LLM等應用。
- 探討tokenization方法對下游語音任務（如ASR、TTS、VC、SLU、S2ST）之影響。
- 具體比較不同token類型在重建、語意建模、語者轉換等多維度的性能。

### PDF Exclusion Signals
- 只討論傳統連續語音特徵（如MFCC、梅爾頻譜）而未涉及離散化/量化者。
- 僅針對音樂、環境聲音等非語音離散標記技術，未聚焦語音應用。
- 只關注傳統信號處理編碼器（如MP3、Opus）而無神經網路或現代VQ方法。
- 未涉及語音與語言模型結合、語音token下游應用、或僅為單一技術細節（如單一VQ算法改進）。
- 研究主題偏向語者辨識、情緒辨識等單一下游任務，未討論tokenization對多任務/多模態語音建模的影響。

### PDF Notes
- Recent Advances in Discrete Speech Tokens: A Review: 
  - 系統性梳理離散語音標記的技術發展、分類、量化方法、神經架構、語意蒸餾、解耦、長度縮減、可變速率、下游應用與挑戰，並提供跨類型統一的實驗比較與未來展望，是LLM時代語音tokenization領域的代表性綜述。
```

#### workspaces/discrete_audio_tokens_more_than_a_survey-api/criteria/web_search_notes.txt

```text
### Topic Definition
離散音訊標記（Discrete Audio Tokens）是指將連續音訊波形，透過神經音訊編碼器與量化機制（如向量量化、殘差向量量化等），轉換為有限詞彙集合中的離散符號序列。此類表示旨在在大幅降低位元率與序列長度的同時，保留可感知音質、語音語義（如音素、語義結構）以及說話人或聲學特徵，使音訊能以「類文字 token」的形式被語言模型處理。該概念最初源自神經音訊編碼（neural audio codec），近年則成為音訊語言模型（Audio Language Models, ALMs）與多模態大型語言模型的重要基石。([arxiv.org](https://arxiv.org/abs/2506.10274?utm_source=openai))

在研究脈絡上，離散音訊標記不僅服務於重建任務（codec），更被視為一種通用中介表示，可支援語音生成、語音理解、音樂建模與一般聲音建模等下游任務。相較於傳統連續特徵（如 Mel-spectrogram），離散標記更利於自回歸或 Transformer 式語言建模，並促進跨模態對齊與長期結構建模，因此逐漸從「編碼工具」演進為「表徵學習核心能力」。([sciencestack.ai](https://www.sciencestack.ai/paper/2209.03143v2?utm_source=openai))

### Summary
近年研究顯示，離散音訊標記正從單純的語音 codec 發展為支援語義、聲學與長時結構的多層次表示。研究亮點包括極低位元率下的高保真重建，以及可直接用於音訊語言模型與多模態生成。整體趨勢顯示，token 設計與訓練目標已成為影響音訊智慧系統能力的關鍵因素。([arxiv.org](https://arxiv.org/abs/2506.10274?utm_source=openai))

### Summary Topics
S1: 神經音訊編碼與離散化方法（VQ、RVQ、多碼本）  
S2: 語義導向與聲學導向音訊標記的分工與融合  
S3: 離散音訊標記於音訊語言模型與生成任務中的應用  
S4: 位元率、重建品質與下游任務效能之權衡分析  

### Inclusion Criteria (Required)
1. 主題定義：離散音訊標記（Discrete Audio Tokens）是指將連續音訊訊號轉換為有限詞彙集合中的離散符號序列，並用於重建、生成或理解等音訊任務。  
   條件：論文需明確提出或分析「離散化音訊表示」或「audio tokenization」作為核心研究對象，且全文需為英文、可進行學術評估。  
   source: https://arxiv.org/abs/2506.10274 （2025-06-12）  
   topic id: S1, S2  

2. 條件：論文需為同儕審查論文或可追溯之預印本（如 arXiv），並提供完整方法描述與實驗或分析。  
   source: https://arxiv.org/abs/2209.03143 （2022-09-07）  
   topic id: S3  

### Inclusion Criteria (Any-of Groups)
- Group 技術實作取向  
  * Option: 提出或分析神經音訊 codec（如 SoundStream、EnCodec）並以離散 token 形式輸出。  
    source: https://arxiv.org/abs/2209.03143 （2022-09-07）  
    topic ids: S1, S3  
  * Option: 著重語義強化或超低位元率之離散音訊標記設計（如語義編碼器、雙編碼架構）。  
    source: https://arxiv.org/abs/2405.00233 （2024-04-30）  
    topic ids: S2, S4  

- Group 應用與分析取向  
  * Option: 系統性比較、benchmark 或綜述離散音訊標記方法與下游任務效能。  
    source: https://arxiv.org/abs/2506.10274 （2025-06-12）  
    topic ids: S4  
  * Option: 將離散音訊標記應用於音訊語言模型、生成或理解任務，並分析其效益。  
    source: https://arxiv.org/abs/2504.10344 （2025-04-14）  
    topic ids: S3  

### Exclusion Criteria
- 僅使用連續音訊特徵（如 Mel-spectrogram、MFCC），未涉及任何離散化或 token 設計之研究。  
  source: internal  
  topic ids: S1  
- 僅為工程實作或程式庫說明，未提供方法創新、系統性分析或實驗驗證。  
  source: internal  
  topic ids: S4  
- 研究焦點為純文字或純影像 token，僅附帶音訊作為資料來源，未探討音訊離散表示本身。  
  source: internal  
  topic ids: S2  

### Sources
https://arxiv.org/abs/2506.10274  
https://arxiv.org/abs/2209.03143  
https://arxiv.org/abs/2405.00233  
https://arxiv.org/abs/2504.10344
```

#### workspaces/discrete_audio_tokens_more_than_a_survey-api/criteria/formatter_prompt.json

```json
[
  {
    "role": "system",
    "content": "你是系統性回顧的資料整理助理，需將研究助理的筆記轉為結構化 JSON。\n僅能輸出單一 JSON 物件，勿加入額外敘述或 Markdown。"
  },
  {
    "role": "user",
    "content": "以下內容結合了兩種來源：\n1) PDF Background (Survey Summaries)：模型閱讀本地 PDF 後的背景整理，僅供提供更準確的主題定義與條件靈感，來源欄請勿引用非 https 連結。\n2) Web Search Notes：OpenAI Web Search 所產出的即時筆記與來源。\n請輸出最終 JSON，並確保所有 source 欄位皆為 https URL。\n主題：Discrete Audio Tokens: More Than a Survey!。\ninclusion_criteria.required 段落僅能包含主題定義逐字條款與英文可評估性條款；其餘條件請歸入 any_of 群組。\n不得要求標題/摘要必須包含特定字串或關鍵字；避免任何硬字串匹配條款。\n將以下筆記整合後再輸出：\n---\n### PDF Background (Survey Summaries)\n### PDF Topic Definition\n本篇系統性綜述聚焦於「離散語音標記（Discrete Speech Tokens）」的技術發展與應用，特別是在大語言模型（LLM）時代下的語音生成、理解與跨模態語言建模。離散語音標記指的是將連續語音訊號經過編碼與量化，轉換為一系列離散、緊湊且符號化的單元，方便於儲存、傳輸，並能與現有的文字語言模型架構無縫整合。主題涵蓋兩大核心類型：聲學標記（Acoustic Tokens）與語意標記（Semantic Tokens），分別著重於語音重建/壓縮與語音語意抽象。評估面向包括重建品質、語者轉換、語意建模能力、下游任務表現、資訊密度、比特率、流式處理能力、可擴展性等。\n\n### PDF Key Trends\n- **離散語音標記的雙主線發展**：聲學標記（如神經語音編解碼器）強調壓縮與重建；語意標記（如SSL模型）強調語音語意抽象與下游語言任務。\n- **語音與文字的融合**：離散標記讓語音能以類似文字token的方式進行語言建模，推動語音LLM、端到端語音對話、語音生成等新應用。\n- **多樣化的量化方法**：從k-means聚類、向量量化（VQ）、殘差VQ（RVQ）、分組VQ（GVQ）、有限純量量化（FSQ）到Gumbel-Softmax等，提升壓縮效率與資訊表達力。\n- **語意蒸餾與解耦**：結合語音自監督學習（SSL）特徵、語意教師模型、語者/內容解耦等，提升標記的語意表現與下游可用性。\n- **長度縮減與可變速率標記**：為解決語音token序列過長，發展如deduplication、acoustic BPE、可變速率（VFR）tokenization等技術。\n- **應用廣泛**：涵蓋語音理解（ASR、意圖分類、語音翻譯）、語音生成（TTS、VC）、語音對話模型（SLM）、多語言/多任務統一建模等。\n\n### PDF Capability Highlights\n- 能將連續語音訊號轉換為高資訊密度、低比特率的離散符號序列。\n- 支援多種量化策略與神經網路架構（CNN、Transformer、U-Net等）。\n- 可針對語音重建、語意建模、語者/內容解耦等不同目標進行優化。\n- 能與大語言模型架構無縫整合，實現語音與文字的統一建模。\n- 支援流式（streaming）處理與低延遲應用需求。\n\n### PDF Inclusion Signals\n- 關鍵字：「discrete speech tokens」、「neural audio codec」、「speech tokenizer」、「spoken language modeling」、「semantic tokens」、「acoustic tokens」、「vector quantization」、「self-supervised learning」、「speech generation」、「token vocoder」。\n- 章節參考：Section III（聲學標記）、Section IV（語意標記）、Section V（長度縮減與可變速率）、Section VI（分析與評測）、Section VII（應用）、Section VIII（挑戰與展望）。\n- 涉及語音tokenization於語音生成、理解、對話、語音LLM等應用。\n- 探討tokenization方法對下游語音任務（如ASR、TTS、VC、SLU、S2ST）之影響。\n- 具體比較不同token類型在重建、語意建模、語者轉換等多維度的性能。\n\n### PDF Exclusion Signals\n- 只討論傳統連續語音特徵（如MFCC、梅爾頻譜）而未涉及離散化/量化者。\n- 僅針對音樂、環境聲音等非語音離散標記技術，未聚焦語音應用。\n- 只關注傳統信號處理編碼器（如MP3、Opus）而無神經網路或現代VQ方法。\n- 未涉及語音與語言模型結合、語音token下游應用、或僅為單一技術細節（如單一VQ算法改進）。\n- 研究主題偏向語者辨識、情緒辨識等單一下游任務，未討論tokenization對多任務/多模態語音建模的影響。\n\n### PDF Notes\n- Recent Advances in Discrete Speech Tokens: A Review: \n  - 系統性梳理離散語音標記的技術發展、分類、量化方法、神經架構、語意蒸餾、解耦、長度縮減、可變速率、下游應用與挑戰，並提供跨類型統一的實驗比較與未來展望，是LLM時代語音tokenization領域的代表性綜述。\n### Web Search Notes\n### Topic Definition\n離散音訊標記（Discrete Audio Tokens）是指將連續音訊波形，透過神經音訊編碼器與量化機制（如向量量化、殘差向量量化等），轉換為有限詞彙集合中的離散符號序列。此類表示旨在在大幅降低位元率與序列長度的同時，保留可感知音質、語音語義（如音素、語義結構）以及說話人或聲學特徵，使音訊能以「類文字 token」的形式被語言模型處理。該概念最初源自神經音訊編碼（neural audio codec），近年則成為音訊語言模型（Audio Language Models, ALMs）與多模態大型語言模型的重要基石。([arxiv.org](https://arxiv.org/abs/2506.10274?utm_source=openai))\n\n在研究脈絡上，離散音訊標記不僅服務於重建任務（codec），更被視為一種通用中介表示，可支援語音生成、語音理解、音樂建模與一般聲音建模等下游任務。相較於傳統連續特徵（如 Mel-spectrogram），離散標記更利於自回歸或 Transformer 式語言建模，並促進跨模態對齊與長期結構建模，因此逐漸從「編碼工具」演進為「表徵學習核心能力」。([sciencestack.ai](https://www.sciencestack.ai/paper/2209.03143v2?utm_source=openai))\n\n### Summary\n近年研究顯示，離散音訊標記正從單純的語音 codec 發展為支援語義、聲學與長時結構的多層次表示。研究亮點包括極低位元率下的高保真重建，以及可直接用於音訊語言模型與多模態生成。整體趨勢顯示，token 設計與訓練目標已成為影響音訊智慧系統能力的關鍵因素。([arxiv.org](https://arxiv.org/abs/2506.10274?utm_source=openai))\n\n### Summary Topics\nS1: 神經音訊編碼與離散化方法（VQ、RVQ、多碼本）  \nS2: 語義導向與聲學導向音訊標記的分工與融合  \nS3: 離散音訊標記於音訊語言模型與生成任務中的應用  \nS4: 位元率、重建品質與下游任務效能之權衡分析  \n\n### Inclusion Criteria (Required)\n1. 主題定義：離散音訊標記（Discrete Audio Tokens）是指將連續音訊訊號轉換為有限詞彙集合中的離散符號序列，並用於重建、生成或理解等音訊任務。  \n   條件：論文需明確提出或分析「離散化音訊表示」或「audio tokenization」作為核心研究對象，且全文需為英文、可進行學術評估。  \n   source: https://arxiv.org/abs/2506.10274 （2025-06-12）  \n   topic id: S1, S2  \n\n2. 條件：論文需為同儕審查論文或可追溯之預印本（如 arXiv），並提供完整方法描述與實驗或分析。  \n   source: https://arxiv.org/abs/2209.03143 （2022-09-07）  \n   topic id: S3  \n\n### Inclusion Criteria (Any-of Groups)\n- Group 技術實作取向  \n  * Option: 提出或分析神經音訊 codec（如 SoundStream、EnCodec）並以離散 token 形式輸出。  \n    source: https://arxiv.org/abs/2209.03143 （2022-09-07）  \n    topic ids: S1, S3  \n  * Option: 著重語義強化或超低位元率之離散音訊標記設計（如語義編碼器、雙編碼架構）。  \n    source: https://arxiv.org/abs/2405.00233 （2024-04-30）  \n    topic ids: S2, S4  \n\n- Group 應用與分析取向  \n  * Option: 系統性比較、benchmark 或綜述離散音訊標記方法與下游任務效能。  \n    source: https://arxiv.org/abs/2506.10274 （2025-06-12）  \n    topic ids: S4  \n  * Option: 將離散音訊標記應用於音訊語言模型、生成或理解任務，並分析其效益。  \n    source: https://arxiv.org/abs/2504.10344 （2025-04-14）  \n    topic ids: S3  \n\n### Exclusion Criteria\n- 僅使用連續音訊特徵（如 Mel-spectrogram、MFCC），未涉及任何離散化或 token 設計之研究。  \n  source: internal  \n  topic ids: S1  \n- 僅為工程實作或程式庫說明，未提供方法創新、系統性分析或實驗驗證。  \n  source: internal  \n  topic ids: S4  \n- 研究焦點為純文字或純影像 token，僅附帶音訊作為資料來源，未探討音訊離散表示本身。  \n  source: internal  \n  topic ids: S2  \n\n### Sources\nhttps://arxiv.org/abs/2506.10274  \nhttps://arxiv.org/abs/2209.03143  \nhttps://arxiv.org/abs/2405.00233  \nhttps://arxiv.org/abs/2504.10344\n---"
  }
]
```

#### workspaces/discrete_audio_tokens_more_than_a_survey-api/criteria/formatter_raw.txt

```text
{
  "topic": {
    "title": "Discrete Audio Tokens: More Than a Survey!",
    "definition": "Discrete audio/speech tokens are discrete, compact, symbol-like units produced by encoding and quantizing a continuous audio (especially speech) waveform into a sequence of symbols from a finite vocabulary, enabling storage/transmission efficiency and seamless integration with language-model-style sequence modeling for audio reconstruction, generation, understanding, and cross-/multi-modal modeling. The scope includes both acoustic tokens (focused on reconstruction/compression) and semantic tokens (focused on linguistic/semantic abstraction), and considers tokenization methods, quantization strategies, sequence-length reduction, variable-rate tokenization, streaming/latency concerns, and evaluation across reconstruction quality, bitrate/information density, and downstream task performance.",
    "scope_notes": {
      "core_token_types": [
        "acoustic tokens (neural audio codecs; reconstruction/compression oriented)",
        "semantic tokens (linguistic/semantic abstraction; often derived from SSL features/teachers)",
        "hybrid or multi-level tokens combining acoustic and semantic information"
      ],
      "representative_methods": [
        "k-means clustering",
        "vector quantization (VQ)",
        "residual vector quantization (RVQ)",
        "grouped vector quantization (GVQ)",
        "finite scalar quantization (FSQ)",
        "Gumbel-Softmax / differentiable quantization"
      ],
      "sequence_efficiency_methods": [
        "deduplication / run-length style reduction",
        "acoustic BPE or learned token merging",
        "variable frame-rate (VFR) tokenization"
      ],
      "evaluation_dimensions": [
        "reconstruction quality and perceptual audio quality",
        "bitrate / token rate and information density",
        "speaker/content disentanglement and voice conversion capability",
        "semantic modeling quality and downstream performance (e.g., ASR/SLU/S2ST/TTS/VC)",
        "streaming capability and latency",
        "scalability and robustness across languages/domains"
      ],
      "typical_applications": [
        "spoken language modeling / speech LLMs",
        "audio language models and multimodal LLMs",
        "speech generation (TTS) and voice conversion (VC)",
        "speech understanding (ASR, intent classification, SLU)",
        "speech-to-speech translation (S2ST)",
        "general audio modeling when discrete tokenization is central"
      ]
    }
  },
  "inclusion_criteria": {
    "required": [
      {
        "criterion": "The study must explicitly propose, analyze, or evaluate discrete audio/speech tokenization as a core object of study, where a continuous audio signal is converted into a sequence of discrete symbols from a finite vocabulary for audio reconstruction, generation, and/or understanding tasks.",
        "source": "https://arxiv.org/abs/2506.10274"
      },
      {
        "criterion": "The full text must be in English and available for academic evaluation.",
        "source": "https://arxiv.org/abs/2506.10274"
      }
    ],
    "any_of_groups": [
      {
        "group_name": "Study type / research maturity",
        "options": [
          {
            "criterion": "Peer-reviewed paper or a traceable preprint (e.g., arXiv) that provides sufficient methodological detail plus experiments and/or substantive analysis relevant to discrete audio tokens.",
            "source": "https://arxiv.org/abs/2209.03143"
          }
        ]
      },
      {
        "group_name": "Tokenization / codec implementation focus",
        "options": [
          {
            "criterion": "Proposes or analyzes a neural audio codec that outputs discrete tokens (e.g., codec-style token sequences intended for compression and reconstruction).",
            "source": "https://arxiv.org/abs/2209.03143"
          },
          {
            "criterion": "Focuses on semantic-enhanced and/or ultra-low-bitrate discrete audio token design (e.g., semantic encoders, teacher-distilled semantics, dual-encoder or disentangled architectures) and evaluates trade-offs between bitrate, quality, and/or downstream utility.",
            "source": "https://arxiv.org/abs/2405.00233"
          }
        ]
      },
      {
        "group_name": "Applications, benchmarks, and analyses",
        "options": [
          {
            "criterion": "Provides a systematic comparison, benchmark, or survey/review of discrete audio token methods and evaluates token choices against reconstruction and/or downstream task performance.",
            "source": "https://arxiv.org/abs/2506.10274"
          },
          {
            "criterion": "Applies discrete audio tokens to audio language modeling, audio generation, or audio understanding, and includes analysis of the benefits/limitations of tokenization choices.",
            "source": "https://arxiv.org/abs/2504.10344"
          }
        ]
      },
      {
        "group_name": "Efficiency, length reduction, and deployment constraints",
        "options": [
          {
            "criterion": "Investigates token sequence length reduction and/or variable-rate tokenization (e.g., deduplication, token merging/BPE-style schemes, variable frame-rate tokens) and reports impacts on modeling and/or downstream performance.",
            "source": "https://arxiv.org/abs/2506.10274"
          },
          {
            "criterion": "Addresses streaming or low-latency constraints for discrete audio token generation/consumption and evaluates the impact on quality and/or task performance.",
            "source": "https://arxiv.org/abs/2506.10274"
          }
        ]
      }
    ]
  },
  "exclusion_criteria": [
    {
      "criterion": "Studies that only use continuous audio features (e.g., Mel-spectrogram, MFCC) without any discrete quantization/token design or analysis of discrete tokenization.",
      "source": "https://arxiv.org/abs/2506.10274"
    },
    {
      "criterion": "Works focused on traditional signal-processing codecs (e.g., MP3/Opus-style) without neural encoding/modern quantization-based discrete token representations relevant to language-model-style token sequences.",
      "source": "https://arxiv.org/abs/2209.03143"
    },
    {
      "criterion": "Engineering-only reports (e.g., library/tool descriptions) without methodological contribution, systematic analysis, or experimental validation related to discrete audio tokens.",
      "source": "https://arxiv.org/abs/2506.10274"
    },
    {
      "criterion": "Studies where audio is merely a data modality while the core tokenization contribution is for text or images, and the work does not analyze discrete audio representations themselves.",
      "source": "https://arxiv.org/abs/2504.10344"
    },
    {
      "criterion": "Tokenization methods for non-speech audio only (e.g., music/environmental sound) when the study does not make its discrete token approach applicable to speech tasks or does not evaluate speech-relevant implications.",
      "source": "https://arxiv.org/abs/2506.10274"
    }
  ],
  "topic_clusters": [
    {
      "id": "S1",
      "name": "Neural audio codec & discretization methods",
      "description": "Discrete token formation from waveforms via neural encoders and quantizers (VQ/RVQ/multi-codebook/FSQ, etc.), including bitrate–quality trade-offs and reconstruction.",
      "sources": [
        "https://arxiv.org/abs/2209.03143",
        "https://arxiv.org/abs/2506.10274"
      ]
    },
    {
      "id": "S2",
      "name": "Semantic vs. acoustic tokens (and their fusion)",
      "description": "Designs that target semantic abstraction and/or disentanglement (speaker/content) versus pure acoustic fidelity; hybrid multi-level token schemes; semantic distillation from SSL/teachers.",
      "sources": [
        "https://arxiv.org/abs/2405.00233",
        "https://arxiv.org/abs/2506.10274"
      ]
    },
    {
      "id": "S3",
      "name": "Audio language models & generation/understanding applications",
      "description": "Using discrete audio tokens as LM-compatible sequences for spoken language modeling, audio LMs, multimodal LLM integration, and downstream tasks (ASR/SLU/S2ST/TTS/VC).",
      "sources": [
        "https://arxiv.org/abs/2504.10344",
        "https://arxiv.org/abs/2209.03143"
      ]
    },
    {
      "id": "S4",
      "name": "Evaluation and trade-off analyses",
      "description": "Systematic evaluation across reconstruction quality, bitrate/token rate, information density, streaming/latency, scalability, and downstream task performance; benchmarks and surveys.",
      "sources": [
        "https://arxiv.org/abs/2506.10274",
        "https://arxiv.org/abs/2405.00233"
      ]
    }
  ],
  "data_extraction_fields": {
    "bibliographic": [
      "title",
      "authors",
      "year",
      "venue_or_preprint_server",
      "url"
    ],
    "tokenization_method": [
      "input_audio_type (speech / general audio / multilingual)",
      "token_type (acoustic / semantic / hybrid)",
      "encoder_architecture",
      "quantization_method (VQ/RVQ/GVQ/FSQ/k-means/Gumbel-Softmax/other)",
      "codebook_size_and_structure (single/multi-codebook; residual levels)",
      "token_rate_or_frame_rate",
      "bitrate (if reported)",
      "sequence_length_reduction (dedup/BPE/VFR/etc.)",
      "streaming_support (yes/no; latency details)"
    ],
    "training_objectives": [
      "reconstruction losses",
      "perceptual/adversarial losses",
      "semantic distillation/teacher signals",
      "disentanglement objectives",
      "LM training objective (AR/MLM/other)"
    ],
    "evaluation": [
      "reconstruction metrics (e.g., MOS, PESQ, STOI, SDR, other)",
      "downstream tasks evaluated (ASR, TTS, VC, SLU, S2ST, etc.)",
      "task metrics (e.g., WER, BLEU, accuracy)",
      "ablation/comparison of token designs",
      "reported limitations/failure cases"
    ]
  },
  "sources": [
    "https://arxiv.org/abs/2506.10274",
    "https://arxiv.org/abs/2209.03143",
    "https://arxiv.org/abs/2405.00233",
    "https://arxiv.org/abs/2504.10344"
  ]
}
```

#### workspaces/discrete_audio_tokens_more_than_a_survey-api/criteria/criteria.json

```json
{
  "topic": "Discrete Audio Tokens: More Than a Survey!",
  "recency_hint": "過去3年",
  "mode": "pdf+web",
  "generated_at": "2026-01-07T18:11:30.417875+00:00",
  "cutoff_before_date": null,
  "exclude_title": null,
  "source_validation": null,
  "search_prompt": "你是系統性回顧助理。\n我們正準備撰寫與該主題相關的 survey/systematic review，需產出可直接用於收錄/排除的篩選 paper 規則。\n請使用內建 web search，且至少引用 3 個 https 來源。\n輸出語言：全部以中文撰寫。\n主題：Discrete Audio Tokens: More Than a Survey!。\n來源頁面需提供明確年月日（YYYY-MM-DD）；僅有年份或年月者視為不合格來源。\n請先以純文字整理資訊，不要輸出 JSON、Markdown 表格或程式碼區塊。\n依序撰寫下列段落：\n### Topic Definition\n- 以 1–2 段中文精準定義主題，可包含背景脈絡與核心能力描述。\n### Summary\n- 以 2–3 句中文概述趨勢與亮點。\n### Summary Topics\n- 列 3–4 個主題節點，格式為 `S1: 描述`。\n### Inclusion Criteria (Required)\n- 僅保留必須同時滿足的條件：① 主題定義條款（以『主題定義：』+定義原文開頭）、② 提供英文可評估性的條件。\n- 每條附上來源 (source) 與對應 topic id；一般條件需為 https。\n### Inclusion Criteria (Any-of Groups)\n- 針對技術覆蓋或差異化條件建立至少一個群組，格式為 `- Group 名稱` 搭配 `* Option:`，各自附上 source 與 topic ids。\n- 群組語意為 OR：只需滿足任一群組中的任一 option 即可。\n- 若筆記中原本在 Required 段落出現多個技術細節條件，請搬移到任選群組，不要重複留在 Required。\n- 若確實沒有任選條件，再寫 `(none)`。\n### Exclusion Criteria\n- 條列需要排除的情境，同樣附來源與 topic ids；若屬於系統設定（如 exclude_title），可標示 source: internal 或留空。\n- source 必須能直接支持該排除條件；若找不到合適來源，請用 internal。\n### Sources\n- 逐行呈現所有引用來源 (https)，不包含 internal/空白來源。\n- 優先引用一手論文頁（arXiv/期刊/會議/出版社），避免動態排行榜、搜尋結果頁或彙整站作為核心依據。",
  "structured_prompt_template": "你是系統性回顧助理。\n主題：Discrete Audio Tokens: More Than a Survey!。\n我們正準備撰寫與該主題相關的 survey/systematic review，需產出可直接用於收錄/排除的篩選 paper 規則。\n請使用內建 web search，且至少引用 3 個 https 來源。\n輸出語言：全部以中文撰寫。\n來源頁面需提供明確年月日（YYYY-MM-DD）；僅有年份或年月者視為不合格來源。\n僅輸出單一 JSON 物件，鍵為：topic_definition、summary、summary_topics、inclusion_criteria、exclusion_criteria；JSON 外勿輸出其他文字。\ntopic_definition：以中文撰寫，1–2 段清楚定義主題，可補充背景脈絡與核心能力描述。\ntopic_definition 的來源應優先引用一手論文頁（如 arXiv/期刊/會議頁），避免彙整站、排行榜或動態搜尋結果頁。\nsummary：中文、簡潔扼要。\nsummary_topics：列出 3–4 項主題，每項含 id（如 S1、S2）與 description；用詞與 summary 一致。\ninclusion_criteria：每條含 criterion、source、topic_ids（至少 1 個）；僅能使用正向條件（不得寫否定句）。\ninclusion_criteria 的第一條必須以『主題定義：』+ topic_definition 原文開頭，之後接上『—』或『:』與具體條件（需逐字包含 topic_definition）。\ninclusion_criteria 中至少一條需明確要求英文（例如提供英文全文或英文評估語料）。\n若條件之間為 OR 關係，請放入 inclusion_criteria.any_of 的 options。\nany_of 群組語意：只需滿足「任一群組中的任一 option」即可；群組彼此為 OR，而非全部都必須滿足。\ninclusion_criteria 的範圍僅量廣泛，不可限縮在特定的小範圍內。\nexclusion_criteria：列『具體剔除情境』，不可是 inclusion 的鏡像否定（例如僅單一語言或單一應用、與主題無關）；每條同樣含 source、topic_ids。\nsource 規則：一般條件必須是 https；若條件屬於系統設定（例如 exclude_title），可用 source=internal 或留空，且這類來源不要放入 sources 清單。\n來源一致性：source 必須能直接支持該條件，不可使用會與條件相矛盾的來源；若找不到合適來源，請用 source=internal。\n來源選擇：避免動態排行榜、搜尋結果頁或彙整站，優先使用一手論文頁或正式出版頁。\n一致性：每條 criterion 必須對應至少一個 summary topic（以 topic_ids 連結）。",
  "web_search_notes": "### Topic Definition\n離散音訊標記（Discrete Audio Tokens）是指將連續音訊波形，透過神經音訊編碼器與量化機制（如向量量化、殘差向量量化等），轉換為有限詞彙集合中的離散符號序列。此類表示旨在在大幅降低位元率與序列長度的同時，保留可感知音質、語音語義（如音素、語義結構）以及說話人或聲學特徵，使音訊能以「類文字 token」的形式被語言模型處理。該概念最初源自神經音訊編碼（neural audio codec），近年則成為音訊語言模型（Audio Language Models, ALMs）與多模態大型語言模型的重要基石。([arxiv.org](https://arxiv.org/abs/2506.10274?utm_source=openai))\n\n在研究脈絡上，離散音訊標記不僅服務於重建任務（codec），更被視為一種通用中介表示，可支援語音生成、語音理解、音樂建模與一般聲音建模等下游任務。相較於傳統連續特徵（如 Mel-spectrogram），離散標記更利於自回歸或 Transformer 式語言建模，並促進跨模態對齊與長期結構建模，因此逐漸從「編碼工具」演進為「表徵學習核心能力」。([sciencestack.ai](https://www.sciencestack.ai/paper/2209.03143v2?utm_source=openai))\n\n### Summary\n近年研究顯示，離散音訊標記正從單純的語音 codec 發展為支援語義、聲學與長時結構的多層次表示。研究亮點包括極低位元率下的高保真重建，以及可直接用於音訊語言模型與多模態生成。整體趨勢顯示，token 設計與訓練目標已成為影響音訊智慧系統能力的關鍵因素。([arxiv.org](https://arxiv.org/abs/2506.10274?utm_source=openai))\n\n### Summary Topics\nS1: 神經音訊編碼與離散化方法（VQ、RVQ、多碼本）  \nS2: 語義導向與聲學導向音訊標記的分工與融合  \nS3: 離散音訊標記於音訊語言模型與生成任務中的應用  \nS4: 位元率、重建品質與下游任務效能之權衡分析  \n\n### Inclusion Criteria (Required)\n1. 主題定義：離散音訊標記（Discrete Audio Tokens）是指將連續音訊訊號轉換為有限詞彙集合中的離散符號序列，並用於重建、生成或理解等音訊任務。  \n   條件：論文需明確提出或分析「離散化音訊表示」或「audio tokenization」作為核心研究對象，且全文需為英文、可進行學術評估。  \n   source: https://arxiv.org/abs/2506.10274 （2025-06-12）  \n   topic id: S1, S2  \n\n2. 條件：論文需為同儕審查論文或可追溯之預印本（如 arXiv），並提供完整方法描述與實驗或分析。  \n   source: https://arxiv.org/abs/2209.03143 （2022-09-07）  \n   topic id: S3  \n\n### Inclusion Criteria (Any-of Groups)\n- Group 技術實作取向  \n  * Option: 提出或分析神經音訊 codec（如 SoundStream、EnCodec）並以離散 token 形式輸出。  \n    source: https://arxiv.org/abs/2209.03143 （2022-09-07）  \n    topic ids: S1, S3  \n  * Option: 著重語義強化或超低位元率之離散音訊標記設計（如語義編碼器、雙編碼架構）。  \n    source: https://arxiv.org/abs/2405.00233 （2024-04-30）  \n    topic ids: S2, S4  \n\n- Group 應用與分析取向  \n  * Option: 系統性比較、benchmark 或綜述離散音訊標記方法與下游任務效能。  \n    source: https://arxiv.org/abs/2506.10274 （2025-06-12）  \n    topic ids: S4  \n  * Option: 將離散音訊標記應用於音訊語言模型、生成或理解任務，並分析其效益。  \n    source: https://arxiv.org/abs/2504.10344 （2025-04-14）  \n    topic ids: S3  \n\n### Exclusion Criteria\n- 僅使用連續音訊特徵（如 Mel-spectrogram、MFCC），未涉及任何離散化或 token 設計之研究。  \n  source: internal  \n  topic ids: S1  \n- 僅為工程實作或程式庫說明，未提供方法創新、系統性分析或實驗驗證。  \n  source: internal  \n  topic ids: S4  \n- 研究焦點為純文字或純影像 token，僅附帶音訊作為資料來源，未探討音訊離散表示本身。  \n  source: internal  \n  topic ids: S2  \n\n### Sources\nhttps://arxiv.org/abs/2506.10274  \nhttps://arxiv.org/abs/2209.03143  \nhttps://arxiv.org/abs/2405.00233  \nhttps://arxiv.org/abs/2504.10344",
  "structured_payload": {
    "topic": {
      "title": "Discrete Audio Tokens: More Than a Survey!",
      "definition": "Discrete audio/speech tokens are discrete, compact, symbol-like units produced by encoding and quantizing a continuous audio (especially speech) waveform into a sequence of symbols from a finite vocabulary, enabling storage/transmission efficiency and seamless integration with language-model-style sequence modeling for audio reconstruction, generation, understanding, and cross-/multi-modal modeling. The scope includes both acoustic tokens (focused on reconstruction/compression) and semantic tokens (focused on linguistic/semantic abstraction), and considers tokenization methods, quantization strategies, sequence-length reduction, variable-rate tokenization, streaming/latency concerns, and evaluation across reconstruction quality, bitrate/information density, and downstream task performance.",
      "scope_notes": {
        "core_token_types": [
          "acoustic tokens (neural audio codecs; reconstruction/compression oriented)",
          "semantic tokens (linguistic/semantic abstraction; often derived from SSL features/teachers)",
          "hybrid or multi-level tokens combining acoustic and semantic information"
        ],
        "representative_methods": [
          "k-means clustering",
          "vector quantization (VQ)",
          "residual vector quantization (RVQ)",
          "grouped vector quantization (GVQ)",
          "finite scalar quantization (FSQ)",
          "Gumbel-Softmax / differentiable quantization"
        ],
        "sequence_efficiency_methods": [
          "deduplication / run-length style reduction",
          "acoustic BPE or learned token merging",
          "variable frame-rate (VFR) tokenization"
        ],
        "evaluation_dimensions": [
          "reconstruction quality and perceptual audio quality",
          "bitrate / token rate and information density",
          "speaker/content disentanglement and voice conversion capability",
          "semantic modeling quality and downstream performance (e.g., ASR/SLU/S2ST/TTS/VC)",
          "streaming capability and latency",
          "scalability and robustness across languages/domains"
        ],
        "typical_applications": [
          "spoken language modeling / speech LLMs",
          "audio language models and multimodal LLMs",
          "speech generation (TTS) and voice conversion (VC)",
          "speech understanding (ASR, intent classification, SLU)",
          "speech-to-speech translation (S2ST)",
          "general audio modeling when discrete tokenization is central"
        ]
      }
    },
    "inclusion_criteria": {
      "required": [
        {
          "criterion": "The study must explicitly propose, analyze, or evaluate discrete audio/speech tokenization as a core object of study, where a continuous audio signal is converted into a sequence of discrete symbols from a finite vocabulary for audio reconstruction, generation, and/or understanding tasks.",
          "source": "https://arxiv.org/abs/2506.10274"
        },
        {
          "criterion": "The full text must be in English and available for academic evaluation.",
          "source": "https://arxiv.org/abs/2506.10274"
        }
      ],
      "any_of_groups": [
        {
          "group_name": "Study type / research maturity",
          "options": [
            {
              "criterion": "Peer-reviewed paper or a traceable preprint (e.g., arXiv) that provides sufficient methodological detail plus experiments and/or substantive analysis relevant to discrete audio tokens.",
              "source": "https://arxiv.org/abs/2209.03143"
            }
          ]
        },
        {
          "group_name": "Tokenization / codec implementation focus",
          "options": [
            {
              "criterion": "Proposes or analyzes a neural audio codec that outputs discrete tokens (e.g., codec-style token sequences intended for compression and reconstruction).",
              "source": "https://arxiv.org/abs/2209.03143"
            },
            {
              "criterion": "Focuses on semantic-enhanced and/or ultra-low-bitrate discrete audio token design (e.g., semantic encoders, teacher-distilled semantics, dual-encoder or disentangled architectures) and evaluates trade-offs between bitrate, quality, and/or downstream utility.",
              "source": "https://arxiv.org/abs/2405.00233"
            }
          ]
        },
        {
          "group_name": "Applications, benchmarks, and analyses",
          "options": [
            {
              "criterion": "Provides a systematic comparison, benchmark, or survey/review of discrete audio token methods and evaluates token choices against reconstruction and/or downstream task performance.",
              "source": "https://arxiv.org/abs/2506.10274"
            },
            {
              "criterion": "Applies discrete audio tokens to audio language modeling, audio generation, or audio understanding, and includes analysis of the benefits/limitations of tokenization choices.",
              "source": "https://arxiv.org/abs/2504.10344"
            }
          ]
        },
        {
          "group_name": "Efficiency, length reduction, and deployment constraints",
          "options": [
            {
              "criterion": "Investigates token sequence length reduction and/or variable-rate tokenization (e.g., deduplication, token merging/BPE-style schemes, variable frame-rate tokens) and reports impacts on modeling and/or downstream performance.",
              "source": "https://arxiv.org/abs/2506.10274"
            },
            {
              "criterion": "Addresses streaming or low-latency constraints for discrete audio token generation/consumption and evaluates the impact on quality and/or task performance.",
              "source": "https://arxiv.org/abs/2506.10274"
            }
          ]
        }
      ]
    },
    "exclusion_criteria": [
      {
        "criterion": "Studies that only use continuous audio features (e.g., Mel-spectrogram, MFCC) without any discrete quantization/token design or analysis of discrete tokenization.",
        "source": "https://arxiv.org/abs/2506.10274"
      },
      {
        "criterion": "Works focused on traditional signal-processing codecs (e.g., MP3/Opus-style) without neural encoding/modern quantization-based discrete token representations relevant to language-model-style token sequences.",
        "source": "https://arxiv.org/abs/2209.03143"
      },
      {
        "criterion": "Engineering-only reports (e.g., library/tool descriptions) without methodological contribution, systematic analysis, or experimental validation related to discrete audio tokens.",
        "source": "https://arxiv.org/abs/2506.10274"
      },
      {
        "criterion": "Studies where audio is merely a data modality while the core tokenization contribution is for text or images, and the work does not analyze discrete audio representations themselves.",
        "source": "https://arxiv.org/abs/2504.10344"
      },
      {
        "criterion": "Tokenization methods for non-speech audio only (e.g., music/environmental sound) when the study does not make its discrete token approach applicable to speech tasks or does not evaluate speech-relevant implications.",
        "source": "https://arxiv.org/abs/2506.10274"
      }
    ],
    "topic_clusters": [
      {
        "id": "S1",
        "name": "Neural audio codec & discretization methods",
        "description": "Discrete token formation from waveforms via neural encoders and quantizers (VQ/RVQ/multi-codebook/FSQ, etc.), including bitrate–quality trade-offs and reconstruction.",
        "sources": [
          "https://arxiv.org/abs/2209.03143",
          "https://arxiv.org/abs/2506.10274"
        ]
      },
      {
        "id": "S2",
        "name": "Semantic vs. acoustic tokens (and their fusion)",
        "description": "Designs that target semantic abstraction and/or disentanglement (speaker/content) versus pure acoustic fidelity; hybrid multi-level token schemes; semantic distillation from SSL/teachers.",
        "sources": [
          "https://arxiv.org/abs/2405.00233",
          "https://arxiv.org/abs/2506.10274"
        ]
      },
      {
        "id": "S3",
        "name": "Audio language models & generation/understanding applications",
        "description": "Using discrete audio tokens as LM-compatible sequences for spoken language modeling, audio LMs, multimodal LLM integration, and downstream tasks (ASR/SLU/S2ST/TTS/VC).",
        "sources": [
          "https://arxiv.org/abs/2504.10344",
          "https://arxiv.org/abs/2209.03143"
        ]
      },
      {
        "id": "S4",
        "name": "Evaluation and trade-off analyses",
        "description": "Systematic evaluation across reconstruction quality, bitrate/token rate, information density, streaming/latency, scalability, and downstream task performance; benchmarks and surveys.",
        "sources": [
          "https://arxiv.org/abs/2506.10274",
          "https://arxiv.org/abs/2405.00233"
        ]
      }
    ],
    "data_extraction_fields": {
      "bibliographic": [
        "title",
        "authors",
        "year",
        "venue_or_preprint_server",
        "url"
      ],
      "tokenization_method": [
        "input_audio_type (speech / general audio / multilingual)",
        "token_type (acoustic / semantic / hybrid)",
        "encoder_architecture",
        "quantization_method (VQ/RVQ/GVQ/FSQ/k-means/Gumbel-Softmax/other)",
        "codebook_size_and_structure (single/multi-codebook; residual levels)",
        "token_rate_or_frame_rate",
        "bitrate (if reported)",
        "sequence_length_reduction (dedup/BPE/VFR/etc.)",
        "streaming_support (yes/no; latency details)"
      ],
      "training_objectives": [
        "reconstruction losses",
        "perceptual/adversarial losses",
        "semantic distillation/teacher signals",
        "disentanglement objectives",
        "LM training objective (AR/MLM/other)"
      ],
      "evaluation": [
        "reconstruction metrics (e.g., MOS, PESQ, STOI, SDR, other)",
        "downstream tasks evaluated (ASR, TTS, VC, SLU, S2ST, etc.)",
        "task metrics (e.g., WER, BLEU, accuracy)",
        "ablation/comparison of token designs",
        "reported limitations/failure cases"
      ]
    },
    "sources": [
      "https://arxiv.org/abs/2506.10274",
      "https://arxiv.org/abs/2209.03143",
      "https://arxiv.org/abs/2405.00233",
      "https://arxiv.org/abs/2504.10344"
    ]
  },
  "pdf_background": "### PDF Topic Definition\n本篇系統性綜述聚焦於「離散語音標記（Discrete Speech Tokens）」的技術發展與應用，特別是在大語言模型（LLM）時代下的語音生成、理解與跨模態語言建模。離散語音標記指的是將連續語音訊號經過編碼與量化，轉換為一系列離散、緊湊且符號化的單元，方便於儲存、傳輸，並能與現有的文字語言模型架構無縫整合。主題涵蓋兩大核心類型：聲學標記（Acoustic Tokens）與語意標記（Semantic Tokens），分別著重於語音重建/壓縮與語音語意抽象。評估面向包括重建品質、語者轉換、語意建模能力、下游任務表現、資訊密度、比特率、流式處理能力、可擴展性等。\n\n### PDF Key Trends\n- **離散語音標記的雙主線發展**：聲學標記（如神經語音編解碼器）強調壓縮與重建；語意標記（如SSL模型）強調語音語意抽象與下游語言任務。\n- **語音與文字的融合**：離散標記讓語音能以類似文字token的方式進行語言建模，推動語音LLM、端到端語音對話、語音生成等新應用。\n- **多樣化的量化方法**：從k-means聚類、向量量化（VQ）、殘差VQ（RVQ）、分組VQ（GVQ）、有限純量量化（FSQ）到Gumbel-Softmax等，提升壓縮效率與資訊表達力。\n- **語意蒸餾與解耦**：結合語音自監督學習（SSL）特徵、語意教師模型、語者/內容解耦等，提升標記的語意表現與下游可用性。\n- **長度縮減與可變速率標記**：為解決語音token序列過長，發展如deduplication、acoustic BPE、可變速率（VFR）tokenization等技術。\n- **應用廣泛**：涵蓋語音理解（ASR、意圖分類、語音翻譯）、語音生成（TTS、VC）、語音對話模型（SLM）、多語言/多任務統一建模等。\n\n### PDF Capability Highlights\n- 能將連續語音訊號轉換為高資訊密度、低比特率的離散符號序列。\n- 支援多種量化策略與神經網路架構（CNN、Transformer、U-Net等）。\n- 可針對語音重建、語意建模、語者/內容解耦等不同目標進行優化。\n- 能與大語言模型架構無縫整合，實現語音與文字的統一建模。\n- 支援流式（streaming）處理與低延遲應用需求。\n\n### PDF Inclusion Signals\n- 關鍵字：「discrete speech tokens」、「neural audio codec」、「speech tokenizer」、「spoken language modeling」、「semantic tokens」、「acoustic tokens」、「vector quantization」、「self-supervised learning」、「speech generation」、「token vocoder」。\n- 章節參考：Section III（聲學標記）、Section IV（語意標記）、Section V（長度縮減與可變速率）、Section VI（分析與評測）、Section VII（應用）、Section VIII（挑戰與展望）。\n- 涉及語音tokenization於語音生成、理解、對話、語音LLM等應用。\n- 探討tokenization方法對下游語音任務（如ASR、TTS、VC、SLU、S2ST）之影響。\n- 具體比較不同token類型在重建、語意建模、語者轉換等多維度的性能。\n\n### PDF Exclusion Signals\n- 只討論傳統連續語音特徵（如MFCC、梅爾頻譜）而未涉及離散化/量化者。\n- 僅針對音樂、環境聲音等非語音離散標記技術，未聚焦語音應用。\n- 只關注傳統信號處理編碼器（如MP3、Opus）而無神經網路或現代VQ方法。\n- 未涉及語音與語言模型結合、語音token下游應用、或僅為單一技術細節（如單一VQ算法改進）。\n- 研究主題偏向語者辨識、情緒辨識等單一下游任務，未討論tokenization對多任務/多模態語音建模的影響。\n\n### PDF Notes\n- Recent Advances in Discrete Speech Tokens: A Review: \n  - 系統性梳理離散語音標記的技術發展、分類、量化方法、神經架構、語意蒸餾、解耦、長度縮減、可變速率、下游應用與挑戰，並提供跨類型統一的實驗比較與未來展望，是LLM時代語音tokenization領域的代表性綜述。",
  "combined_notes": "### PDF Background (Survey Summaries)\n### PDF Topic Definition\n本篇系統性綜述聚焦於「離散語音標記（Discrete Speech Tokens）」的技術發展與應用，特別是在大語言模型（LLM）時代下的語音生成、理解與跨模態語言建模。離散語音標記指的是將連續語音訊號經過編碼與量化，轉換為一系列離散、緊湊且符號化的單元，方便於儲存、傳輸，並能與現有的文字語言模型架構無縫整合。主題涵蓋兩大核心類型：聲學標記（Acoustic Tokens）與語意標記（Semantic Tokens），分別著重於語音重建/壓縮與語音語意抽象。評估面向包括重建品質、語者轉換、語意建模能力、下游任務表現、資訊密度、比特率、流式處理能力、可擴展性等。\n\n### PDF Key Trends\n- **離散語音標記的雙主線發展**：聲學標記（如神經語音編解碼器）強調壓縮與重建；語意標記（如SSL模型）強調語音語意抽象與下游語言任務。\n- **語音與文字的融合**：離散標記讓語音能以類似文字token的方式進行語言建模，推動語音LLM、端到端語音對話、語音生成等新應用。\n- **多樣化的量化方法**：從k-means聚類、向量量化（VQ）、殘差VQ（RVQ）、分組VQ（GVQ）、有限純量量化（FSQ）到Gumbel-Softmax等，提升壓縮效率與資訊表達力。\n- **語意蒸餾與解耦**：結合語音自監督學習（SSL）特徵、語意教師模型、語者/內容解耦等，提升標記的語意表現與下游可用性。\n- **長度縮減與可變速率標記**：為解決語音token序列過長，發展如deduplication、acoustic BPE、可變速率（VFR）tokenization等技術。\n- **應用廣泛**：涵蓋語音理解（ASR、意圖分類、語音翻譯）、語音生成（TTS、VC）、語音對話模型（SLM）、多語言/多任務統一建模等。\n\n### PDF Capability Highlights\n- 能將連續語音訊號轉換為高資訊密度、低比特率的離散符號序列。\n- 支援多種量化策略與神經網路架構（CNN、Transformer、U-Net等）。\n- 可針對語音重建、語意建模、語者/內容解耦等不同目標進行優化。\n- 能與大語言模型架構無縫整合，實現語音與文字的統一建模。\n- 支援流式（streaming）處理與低延遲應用需求。\n\n### PDF Inclusion Signals\n- 關鍵字：「discrete speech tokens」、「neural audio codec」、「speech tokenizer」、「spoken language modeling」、「semantic tokens」、「acoustic tokens」、「vector quantization」、「self-supervised learning」、「speech generation」、「token vocoder」。\n- 章節參考：Section III（聲學標記）、Section IV（語意標記）、Section V（長度縮減與可變速率）、Section VI（分析與評測）、Section VII（應用）、Section VIII（挑戰與展望）。\n- 涉及語音tokenization於語音生成、理解、對話、語音LLM等應用。\n- 探討tokenization方法對下游語音任務（如ASR、TTS、VC、SLU、S2ST）之影響。\n- 具體比較不同token類型在重建、語意建模、語者轉換等多維度的性能。\n\n### PDF Exclusion Signals\n- 只討論傳統連續語音特徵（如MFCC、梅爾頻譜）而未涉及離散化/量化者。\n- 僅針對音樂、環境聲音等非語音離散標記技術，未聚焦語音應用。\n- 只關注傳統信號處理編碼器（如MP3、Opus）而無神經網路或現代VQ方法。\n- 未涉及語音與語言模型結合、語音token下游應用、或僅為單一技術細節（如單一VQ算法改進）。\n- 研究主題偏向語者辨識、情緒辨識等單一下游任務，未討論tokenization對多任務/多模態語音建模的影響。\n\n### PDF Notes\n- Recent Advances in Discrete Speech Tokens: A Review: \n  - 系統性梳理離散語音標記的技術發展、分類、量化方法、神經架構、語意蒸餾、解耦、長度縮減、可變速率、下游應用與挑戰，並提供跨類型統一的實驗比較與未來展望，是LLM時代語音tokenization領域的代表性綜述。\n### Web Search Notes\n### Topic Definition\n離散音訊標記（Discrete Audio Tokens）是指將連續音訊波形，透過神經音訊編碼器與量化機制（如向量量化、殘差向量量化等），轉換為有限詞彙集合中的離散符號序列。此類表示旨在在大幅降低位元率與序列長度的同時，保留可感知音質、語音語義（如音素、語義結構）以及說話人或聲學特徵，使音訊能以「類文字 token」的形式被語言模型處理。該概念最初源自神經音訊編碼（neural audio codec），近年則成為音訊語言模型（Audio Language Models, ALMs）與多模態大型語言模型的重要基石。([arxiv.org](https://arxiv.org/abs/2506.10274?utm_source=openai))\n\n在研究脈絡上，離散音訊標記不僅服務於重建任務（codec），更被視為一種通用中介表示，可支援語音生成、語音理解、音樂建模與一般聲音建模等下游任務。相較於傳統連續特徵（如 Mel-spectrogram），離散標記更利於自回歸或 Transformer 式語言建模，並促進跨模態對齊與長期結構建模，因此逐漸從「編碼工具」演進為「表徵學習核心能力」。([sciencestack.ai](https://www.sciencestack.ai/paper/2209.03143v2?utm_source=openai))\n\n### Summary\n近年研究顯示，離散音訊標記正從單純的語音 codec 發展為支援語義、聲學與長時結構的多層次表示。研究亮點包括極低位元率下的高保真重建，以及可直接用於音訊語言模型與多模態生成。整體趨勢顯示，token 設計與訓練目標已成為影響音訊智慧系統能力的關鍵因素。([arxiv.org](https://arxiv.org/abs/2506.10274?utm_source=openai))\n\n### Summary Topics\nS1: 神經音訊編碼與離散化方法（VQ、RVQ、多碼本）  \nS2: 語義導向與聲學導向音訊標記的分工與融合  \nS3: 離散音訊標記於音訊語言模型與生成任務中的應用  \nS4: 位元率、重建品質與下游任務效能之權衡分析  \n\n### Inclusion Criteria (Required)\n1. 主題定義：離散音訊標記（Discrete Audio Tokens）是指將連續音訊訊號轉換為有限詞彙集合中的離散符號序列，並用於重建、生成或理解等音訊任務。  \n   條件：論文需明確提出或分析「離散化音訊表示」或「audio tokenization」作為核心研究對象，且全文需為英文、可進行學術評估。  \n   source: https://arxiv.org/abs/2506.10274 （2025-06-12）  \n   topic id: S1, S2  \n\n2. 條件：論文需為同儕審查論文或可追溯之預印本（如 arXiv），並提供完整方法描述與實驗或分析。  \n   source: https://arxiv.org/abs/2209.03143 （2022-09-07）  \n   topic id: S3  \n\n### Inclusion Criteria (Any-of Groups)\n- Group 技術實作取向  \n  * Option: 提出或分析神經音訊 codec（如 SoundStream、EnCodec）並以離散 token 形式輸出。  \n    source: https://arxiv.org/abs/2209.03143 （2022-09-07）  \n    topic ids: S1, S3  \n  * Option: 著重語義強化或超低位元率之離散音訊標記設計（如語義編碼器、雙編碼架構）。  \n    source: https://arxiv.org/abs/2405.00233 （2024-04-30）  \n    topic ids: S2, S4  \n\n- Group 應用與分析取向  \n  * Option: 系統性比較、benchmark 或綜述離散音訊標記方法與下游任務效能。  \n    source: https://arxiv.org/abs/2506.10274 （2025-06-12）  \n    topic ids: S4  \n  * Option: 將離散音訊標記應用於音訊語言模型、生成或理解任務，並分析其效益。  \n    source: https://arxiv.org/abs/2504.10344 （2025-04-14）  \n    topic ids: S3  \n\n### Exclusion Criteria\n- 僅使用連續音訊特徵（如 Mel-spectrogram、MFCC），未涉及任何離散化或 token 設計之研究。  \n  source: internal  \n  topic ids: S1  \n- 僅為工程實作或程式庫說明，未提供方法創新、系統性分析或實驗驗證。  \n  source: internal  \n  topic ids: S4  \n- 研究焦點為純文字或純影像 token，僅附帶音訊作為資料來源，未探討音訊離散表示本身。  \n  source: internal  \n  topic ids: S2  \n\n### Sources\nhttps://arxiv.org/abs/2506.10274  \nhttps://arxiv.org/abs/2209.03143  \nhttps://arxiv.org/abs/2405.00233  \nhttps://arxiv.org/abs/2504.10344",
  "augmented_formatter_messages": [
    {
      "role": "system",
      "content": "你是系統性回顧的資料整理助理，需將研究助理的筆記轉為結構化 JSON。\n僅能輸出單一 JSON 物件，勿加入額外敘述或 Markdown。"
    },
    {
      "role": "user",
      "content": "以下內容結合了兩種來源：\n1) PDF Background (Survey Summaries)：模型閱讀本地 PDF 後的背景整理，僅供提供更準確的主題定義與條件靈感，來源欄請勿引用非 https 連結。\n2) Web Search Notes：OpenAI Web Search 所產出的即時筆記與來源。\n請輸出最終 JSON，並確保所有 source 欄位皆為 https URL。\n主題：Discrete Audio Tokens: More Than a Survey!。\ninclusion_criteria.required 段落僅能包含主題定義逐字條款與英文可評估性條款；其餘條件請歸入 any_of 群組。\n不得要求標題/摘要必須包含特定字串或關鍵字；避免任何硬字串匹配條款。\n將以下筆記整合後再輸出：\n---\n### PDF Background (Survey Summaries)\n### PDF Topic Definition\n本篇系統性綜述聚焦於「離散語音標記（Discrete Speech Tokens）」的技術發展與應用，特別是在大語言模型（LLM）時代下的語音生成、理解與跨模態語言建模。離散語音標記指的是將連續語音訊號經過編碼與量化，轉換為一系列離散、緊湊且符號化的單元，方便於儲存、傳輸，並能與現有的文字語言模型架構無縫整合。主題涵蓋兩大核心類型：聲學標記（Acoustic Tokens）與語意標記（Semantic Tokens），分別著重於語音重建/壓縮與語音語意抽象。評估面向包括重建品質、語者轉換、語意建模能力、下游任務表現、資訊密度、比特率、流式處理能力、可擴展性等。\n\n### PDF Key Trends\n- **離散語音標記的雙主線發展**：聲學標記（如神經語音編解碼器）強調壓縮與重建；語意標記（如SSL模型）強調語音語意抽象與下游語言任務。\n- **語音與文字的融合**：離散標記讓語音能以類似文字token的方式進行語言建模，推動語音LLM、端到端語音對話、語音生成等新應用。\n- **多樣化的量化方法**：從k-means聚類、向量量化（VQ）、殘差VQ（RVQ）、分組VQ（GVQ）、有限純量量化（FSQ）到Gumbel-Softmax等，提升壓縮效率與資訊表達力。\n- **語意蒸餾與解耦**：結合語音自監督學習（SSL）特徵、語意教師模型、語者/內容解耦等，提升標記的語意表現與下游可用性。\n- **長度縮減與可變速率標記**：為解決語音token序列過長，發展如deduplication、acoustic BPE、可變速率（VFR）tokenization等技術。\n- **應用廣泛**：涵蓋語音理解（ASR、意圖分類、語音翻譯）、語音生成（TTS、VC）、語音對話模型（SLM）、多語言/多任務統一建模等。\n\n### PDF Capability Highlights\n- 能將連續語音訊號轉換為高資訊密度、低比特率的離散符號序列。\n- 支援多種量化策略與神經網路架構（CNN、Transformer、U-Net等）。\n- 可針對語音重建、語意建模、語者/內容解耦等不同目標進行優化。\n- 能與大語言模型架構無縫整合，實現語音與文字的統一建模。\n- 支援流式（streaming）處理與低延遲應用需求。\n\n### PDF Inclusion Signals\n- 關鍵字：「discrete speech tokens」、「neural audio codec」、「speech tokenizer」、「spoken language modeling」、「semantic tokens」、「acoustic tokens」、「vector quantization」、「self-supervised learning」、「speech generation」、「token vocoder」。\n- 章節參考：Section III（聲學標記）、Section IV（語意標記）、Section V（長度縮減與可變速率）、Section VI（分析與評測）、Section VII（應用）、Section VIII（挑戰與展望）。\n- 涉及語音tokenization於語音生成、理解、對話、語音LLM等應用。\n- 探討tokenization方法對下游語音任務（如ASR、TTS、VC、SLU、S2ST）之影響。\n- 具體比較不同token類型在重建、語意建模、語者轉換等多維度的性能。\n\n### PDF Exclusion Signals\n- 只討論傳統連續語音特徵（如MFCC、梅爾頻譜）而未涉及離散化/量化者。\n- 僅針對音樂、環境聲音等非語音離散標記技術，未聚焦語音應用。\n- 只關注傳統信號處理編碼器（如MP3、Opus）而無神經網路或現代VQ方法。\n- 未涉及語音與語言模型結合、語音token下游應用、或僅為單一技術細節（如單一VQ算法改進）。\n- 研究主題偏向語者辨識、情緒辨識等單一下游任務，未討論tokenization對多任務/多模態語音建模的影響。\n\n### PDF Notes\n- Recent Advances in Discrete Speech Tokens: A Review: \n  - 系統性梳理離散語音標記的技術發展、分類、量化方法、神經架構、語意蒸餾、解耦、長度縮減、可變速率、下游應用與挑戰，並提供跨類型統一的實驗比較與未來展望，是LLM時代語音tokenization領域的代表性綜述。\n### Web Search Notes\n### Topic Definition\n離散音訊標記（Discrete Audio Tokens）是指將連續音訊波形，透過神經音訊編碼器與量化機制（如向量量化、殘差向量量化等），轉換為有限詞彙集合中的離散符號序列。此類表示旨在在大幅降低位元率與序列長度的同時，保留可感知音質、語音語義（如音素、語義結構）以及說話人或聲學特徵，使音訊能以「類文字 token」的形式被語言模型處理。該概念最初源自神經音訊編碼（neural audio codec），近年則成為音訊語言模型（Audio Language Models, ALMs）與多模態大型語言模型的重要基石。([arxiv.org](https://arxiv.org/abs/2506.10274?utm_source=openai))\n\n在研究脈絡上，離散音訊標記不僅服務於重建任務（codec），更被視為一種通用中介表示，可支援語音生成、語音理解、音樂建模與一般聲音建模等下游任務。相較於傳統連續特徵（如 Mel-spectrogram），離散標記更利於自回歸或 Transformer 式語言建模，並促進跨模態對齊與長期結構建模，因此逐漸從「編碼工具」演進為「表徵學習核心能力」。([sciencestack.ai](https://www.sciencestack.ai/paper/2209.03143v2?utm_source=openai))\n\n### Summary\n近年研究顯示，離散音訊標記正從單純的語音 codec 發展為支援語義、聲學與長時結構的多層次表示。研究亮點包括極低位元率下的高保真重建，以及可直接用於音訊語言模型與多模態生成。整體趨勢顯示，token 設計與訓練目標已成為影響音訊智慧系統能力的關鍵因素。([arxiv.org](https://arxiv.org/abs/2506.10274?utm_source=openai))\n\n### Summary Topics\nS1: 神經音訊編碼與離散化方法（VQ、RVQ、多碼本）  \nS2: 語義導向與聲學導向音訊標記的分工與融合  \nS3: 離散音訊標記於音訊語言模型與生成任務中的應用  \nS4: 位元率、重建品質與下游任務效能之權衡分析  \n\n### Inclusion Criteria (Required)\n1. 主題定義：離散音訊標記（Discrete Audio Tokens）是指將連續音訊訊號轉換為有限詞彙集合中的離散符號序列，並用於重建、生成或理解等音訊任務。  \n   條件：論文需明確提出或分析「離散化音訊表示」或「audio tokenization」作為核心研究對象，且全文需為英文、可進行學術評估。  \n   source: https://arxiv.org/abs/2506.10274 （2025-06-12）  \n   topic id: S1, S2  \n\n2. 條件：論文需為同儕審查論文或可追溯之預印本（如 arXiv），並提供完整方法描述與實驗或分析。  \n   source: https://arxiv.org/abs/2209.03143 （2022-09-07）  \n   topic id: S3  \n\n### Inclusion Criteria (Any-of Groups)\n- Group 技術實作取向  \n  * Option: 提出或分析神經音訊 codec（如 SoundStream、EnCodec）並以離散 token 形式輸出。  \n    source: https://arxiv.org/abs/2209.03143 （2022-09-07）  \n    topic ids: S1, S3  \n  * Option: 著重語義強化或超低位元率之離散音訊標記設計（如語義編碼器、雙編碼架構）。  \n    source: https://arxiv.org/abs/2405.00233 （2024-04-30）  \n    topic ids: S2, S4  \n\n- Group 應用與分析取向  \n  * Option: 系統性比較、benchmark 或綜述離散音訊標記方法與下游任務效能。  \n    source: https://arxiv.org/abs/2506.10274 （2025-06-12）  \n    topic ids: S4  \n  * Option: 將離散音訊標記應用於音訊語言模型、生成或理解任務，並分析其效益。  \n    source: https://arxiv.org/abs/2504.10344 （2025-04-14）  \n    topic ids: S3  \n\n### Exclusion Criteria\n- 僅使用連續音訊特徵（如 Mel-spectrogram、MFCC），未涉及任何離散化或 token 設計之研究。  \n  source: internal  \n  topic ids: S1  \n- 僅為工程實作或程式庫說明，未提供方法創新、系統性分析或實驗驗證。  \n  source: internal  \n  topic ids: S4  \n- 研究焦點為純文字或純影像 token，僅附帶音訊作為資料來源，未探討音訊離散表示本身。  \n  source: internal  \n  topic ids: S2  \n\n### Sources\nhttps://arxiv.org/abs/2506.10274  \nhttps://arxiv.org/abs/2209.03143  \nhttps://arxiv.org/abs/2405.00233  \nhttps://arxiv.org/abs/2504.10344\n---"
    }
  ],
  "formatter_raw": "{\n  \"topic\": {\n    \"title\": \"Discrete Audio Tokens: More Than a Survey!\",\n    \"definition\": \"Discrete audio/speech tokens are discrete, compact, symbol-like units produced by encoding and quantizing a continuous audio (especially speech) waveform into a sequence of symbols from a finite vocabulary, enabling storage/transmission efficiency and seamless integration with language-model-style sequence modeling for audio reconstruction, generation, understanding, and cross-/multi-modal modeling. The scope includes both acoustic tokens (focused on reconstruction/compression) and semantic tokens (focused on linguistic/semantic abstraction), and considers tokenization methods, quantization strategies, sequence-length reduction, variable-rate tokenization, streaming/latency concerns, and evaluation across reconstruction quality, bitrate/information density, and downstream task performance.\",\n    \"scope_notes\": {\n      \"core_token_types\": [\n        \"acoustic tokens (neural audio codecs; reconstruction/compression oriented)\",\n        \"semantic tokens (linguistic/semantic abstraction; often derived from SSL features/teachers)\",\n        \"hybrid or multi-level tokens combining acoustic and semantic information\"\n      ],\n      \"representative_methods\": [\n        \"k-means clustering\",\n        \"vector quantization (VQ)\",\n        \"residual vector quantization (RVQ)\",\n        \"grouped vector quantization (GVQ)\",\n        \"finite scalar quantization (FSQ)\",\n        \"Gumbel-Softmax / differentiable quantization\"\n      ],\n      \"sequence_efficiency_methods\": [\n        \"deduplication / run-length style reduction\",\n        \"acoustic BPE or learned token merging\",\n        \"variable frame-rate (VFR) tokenization\"\n      ],\n      \"evaluation_dimensions\": [\n        \"reconstruction quality and perceptual audio quality\",\n        \"bitrate / token rate and information density\",\n        \"speaker/content disentanglement and voice conversion capability\",\n        \"semantic modeling quality and downstream performance (e.g., ASR/SLU/S2ST/TTS/VC)\",\n        \"streaming capability and latency\",\n        \"scalability and robustness across languages/domains\"\n      ],\n      \"typical_applications\": [\n        \"spoken language modeling / speech LLMs\",\n        \"audio language models and multimodal LLMs\",\n        \"speech generation (TTS) and voice conversion (VC)\",\n        \"speech understanding (ASR, intent classification, SLU)\",\n        \"speech-to-speech translation (S2ST)\",\n        \"general audio modeling when discrete tokenization is central\"\n      ]\n    }\n  },\n  \"inclusion_criteria\": {\n    \"required\": [\n      {\n        \"criterion\": \"The study must explicitly propose, analyze, or evaluate discrete audio/speech tokenization as a core object of study, where a continuous audio signal is converted into a sequence of discrete symbols from a finite vocabulary for audio reconstruction, generation, and/or understanding tasks.\",\n        \"source\": \"https://arxiv.org/abs/2506.10274\"\n      },\n      {\n        \"criterion\": \"The full text must be in English and available for academic evaluation.\",\n        \"source\": \"https://arxiv.org/abs/2506.10274\"\n      }\n    ],\n    \"any_of_groups\": [\n      {\n        \"group_name\": \"Study type / research maturity\",\n        \"options\": [\n          {\n            \"criterion\": \"Peer-reviewed paper or a traceable preprint (e.g., arXiv) that provides sufficient methodological detail plus experiments and/or substantive analysis relevant to discrete audio tokens.\",\n            \"source\": \"https://arxiv.org/abs/2209.03143\"\n          }\n        ]\n      },\n      {\n        \"group_name\": \"Tokenization / codec implementation focus\",\n        \"options\": [\n          {\n            \"criterion\": \"Proposes or analyzes a neural audio codec that outputs discrete tokens (e.g., codec-style token sequences intended for compression and reconstruction).\",\n            \"source\": \"https://arxiv.org/abs/2209.03143\"\n          },\n          {\n            \"criterion\": \"Focuses on semantic-enhanced and/or ultra-low-bitrate discrete audio token design (e.g., semantic encoders, teacher-distilled semantics, dual-encoder or disentangled architectures) and evaluates trade-offs between bitrate, quality, and/or downstream utility.\",\n            \"source\": \"https://arxiv.org/abs/2405.00233\"\n          }\n        ]\n      },\n      {\n        \"group_name\": \"Applications, benchmarks, and analyses\",\n        \"options\": [\n          {\n            \"criterion\": \"Provides a systematic comparison, benchmark, or survey/review of discrete audio token methods and evaluates token choices against reconstruction and/or downstream task performance.\",\n            \"source\": \"https://arxiv.org/abs/2506.10274\"\n          },\n          {\n            \"criterion\": \"Applies discrete audio tokens to audio language modeling, audio generation, or audio understanding, and includes analysis of the benefits/limitations of tokenization choices.\",\n            \"source\": \"https://arxiv.org/abs/2504.10344\"\n          }\n        ]\n      },\n      {\n        \"group_name\": \"Efficiency, length reduction, and deployment constraints\",\n        \"options\": [\n          {\n            \"criterion\": \"Investigates token sequence length reduction and/or variable-rate tokenization (e.g., deduplication, token merging/BPE-style schemes, variable frame-rate tokens) and reports impacts on modeling and/or downstream performance.\",\n            \"source\": \"https://arxiv.org/abs/2506.10274\"\n          },\n          {\n            \"criterion\": \"Addresses streaming or low-latency constraints for discrete audio token generation/consumption and evaluates the impact on quality and/or task performance.\",\n            \"source\": \"https://arxiv.org/abs/2506.10274\"\n          }\n        ]\n      }\n    ]\n  },\n  \"exclusion_criteria\": [\n    {\n      \"criterion\": \"Studies that only use continuous audio features (e.g., Mel-spectrogram, MFCC) without any discrete quantization/token design or analysis of discrete tokenization.\",\n      \"source\": \"https://arxiv.org/abs/2506.10274\"\n    },\n    {\n      \"criterion\": \"Works focused on traditional signal-processing codecs (e.g., MP3/Opus-style) without neural encoding/modern quantization-based discrete token representations relevant to language-model-style token sequences.\",\n      \"source\": \"https://arxiv.org/abs/2209.03143\"\n    },\n    {\n      \"criterion\": \"Engineering-only reports (e.g., library/tool descriptions) without methodological contribution, systematic analysis, or experimental validation related to discrete audio tokens.\",\n      \"source\": \"https://arxiv.org/abs/2506.10274\"\n    },\n    {\n      \"criterion\": \"Studies where audio is merely a data modality while the core tokenization contribution is for text or images, and the work does not analyze discrete audio representations themselves.\",\n      \"source\": \"https://arxiv.org/abs/2504.10344\"\n    },\n    {\n      \"criterion\": \"Tokenization methods for non-speech audio only (e.g., music/environmental sound) when the study does not make its discrete token approach applicable to speech tasks or does not evaluate speech-relevant implications.\",\n      \"source\": \"https://arxiv.org/abs/2506.10274\"\n    }\n  ],\n  \"topic_clusters\": [\n    {\n      \"id\": \"S1\",\n      \"name\": \"Neural audio codec & discretization methods\",\n      \"description\": \"Discrete token formation from waveforms via neural encoders and quantizers (VQ/RVQ/multi-codebook/FSQ, etc.), including bitrate–quality trade-offs and reconstruction.\",\n      \"sources\": [\n        \"https://arxiv.org/abs/2209.03143\",\n        \"https://arxiv.org/abs/2506.10274\"\n      ]\n    },\n    {\n      \"id\": \"S2\",\n      \"name\": \"Semantic vs. acoustic tokens (and their fusion)\",\n      \"description\": \"Designs that target semantic abstraction and/or disentanglement (speaker/content) versus pure acoustic fidelity; hybrid multi-level token schemes; semantic distillation from SSL/teachers.\",\n      \"sources\": [\n        \"https://arxiv.org/abs/2405.00233\",\n        \"https://arxiv.org/abs/2506.10274\"\n      ]\n    },\n    {\n      \"id\": \"S3\",\n      \"name\": \"Audio language models & generation/understanding applications\",\n      \"description\": \"Using discrete audio tokens as LM-compatible sequences for spoken language modeling, audio LMs, multimodal LLM integration, and downstream tasks (ASR/SLU/S2ST/TTS/VC).\",\n      \"sources\": [\n        \"https://arxiv.org/abs/2504.10344\",\n        \"https://arxiv.org/abs/2209.03143\"\n      ]\n    },\n    {\n      \"id\": \"S4\",\n      \"name\": \"Evaluation and trade-off analyses\",\n      \"description\": \"Systematic evaluation across reconstruction quality, bitrate/token rate, information density, streaming/latency, scalability, and downstream task performance; benchmarks and surveys.\",\n      \"sources\": [\n        \"https://arxiv.org/abs/2506.10274\",\n        \"https://arxiv.org/abs/2405.00233\"\n      ]\n    }\n  ],\n  \"data_extraction_fields\": {\n    \"bibliographic\": [\n      \"title\",\n      \"authors\",\n      \"year\",\n      \"venue_or_preprint_server\",\n      \"url\"\n    ],\n    \"tokenization_method\": [\n      \"input_audio_type (speech / general audio / multilingual)\",\n      \"token_type (acoustic / semantic / hybrid)\",\n      \"encoder_architecture\",\n      \"quantization_method (VQ/RVQ/GVQ/FSQ/k-means/Gumbel-Softmax/other)\",\n      \"codebook_size_and_structure (single/multi-codebook; residual levels)\",\n      \"token_rate_or_frame_rate\",\n      \"bitrate (if reported)\",\n      \"sequence_length_reduction (dedup/BPE/VFR/etc.)\",\n      \"streaming_support (yes/no; latency details)\"\n    ],\n    \"training_objectives\": [\n      \"reconstruction losses\",\n      \"perceptual/adversarial losses\",\n      \"semantic distillation/teacher signals\",\n      \"disentanglement objectives\",\n      \"LM training objective (AR/MLM/other)\"\n    ],\n    \"evaluation\": [\n      \"reconstruction metrics (e.g., MOS, PESQ, STOI, SDR, other)\",\n      \"downstream tasks evaluated (ASR, TTS, VC, SLU, S2ST, etc.)\",\n      \"task metrics (e.g., WER, BLEU, accuracy)\",\n      \"ablation/comparison of token designs\",\n      \"reported limitations/failure cases\"\n    ]\n  },\n  \"sources\": [\n    \"https://arxiv.org/abs/2506.10274\",\n    \"https://arxiv.org/abs/2209.03143\",\n    \"https://arxiv.org/abs/2405.00233\",\n    \"https://arxiv.org/abs/2504.10344\"\n  ]\n}"
}
```

#### workspaces/discrete_audio_tokens_more_than_a_survey-api/snowball_rounds/round_01/round_meta.json

```json
{
  "round": 1,
  "seed_review": "workspaces/discrete_audio_tokens_more_than_a_survey/review/latte_review_results.json",
  "seed_count": 130,
  "raw_count": 823,
  "filtered_count": 450,
  "dedup_removed": 12,
  "dedup_removed_by": {
    "openalex_id": 1,
    "doi": 1,
    "title": 10
  },
  "for_review_count": 438,
  "review_ran": true,
  "review_outcome": {
    "include": 37,
    "exclude": 399,
    "other": 2
  },
  "included_total": 167,
  "criteria_hash": "f84221d054a803ad95a17603644a25baad70b61eee481db03ed19d5879ab99fc"
}
```

#### workspaces/discrete_audio_tokens_more_than_a_survey-api/snowball_rounds/round_02/round_meta.json

```json
{
  "round": 2,
  "seed_review": "workspaces/discrete_audio_tokens_more_than_a_survey/snowball_rounds/round_01/latte_review_results.json",
  "seed_count": 37,
  "raw_count": 4611,
  "filtered_count": 2924,
  "dedup_removed": 151,
  "dedup_removed_by": {
    "openalex_id": 119,
    "doi": 10,
    "title": 22
  },
  "for_review_count": 2773,
  "review_ran": true,
  "review_outcome": {
    "exclude": 2507,
    "include": 248,
    "other": 18
  },
  "included_total": 415,
  "criteria_hash": "f84221d054a803ad95a17603644a25baad70b61eee481db03ed19d5879ab99fc"
}
```

#### workspaces/discrete_audio_tokens_more_than_a_survey-api/snowball_rounds/round_03/round_meta.json

```json
{
  "round": 3,
  "seed_review": "workspaces/discrete_audio_tokens_more_than_a_survey/snowball_rounds/round_02/latte_review_results.json",
  "seed_count": 248,
  "raw_count": 6616,
  "filtered_count": 4159,
  "dedup_removed": 1079,
  "dedup_removed_by": {
    "openalex_id": 1020,
    "doi": 4,
    "title": 55
  },
  "for_review_count": 3080,
  "review_ran": true,
  "review_outcome": {
    "exclude": 2830,
    "include": 233,
    "other": 17
  },
  "included_total": 648,
  "criteria_hash": "f84221d054a803ad95a17603644a25baad70b61eee481db03ed19d5879ab99fc"
}
```

#### workspaces/discrete_audio_tokens_more_than_a_survey-api/snowball_title_f1_tables.md

```text
# Snowball Title-only F1 Tables

Note: exact match after title normalization (strip `{}`, TeX commands, punctuation, lowercase).

## Discrete Audio Tokens

| Round | Retrieved | TP | Precision | Recall | F1 | Note |
| --- | --- | --- | --- | --- | --- | --- |
| round_01 | 166 | 49 | 0.295181 | 0.150307 | 0.199187 |  |
| round_02 | 414 | 67 | 0.161836 | 0.205521 | 0.181081 |  |
| round_03 | 645 | 70 | 0.108527 | 0.214724 | 0.144181 |  |

## Spoken Language Models

| Round | Retrieved | TP | Precision | Recall | F1 | Note |
| --- | --- | --- | --- | --- | --- | --- |
| round_01 | 64 | 15 | 0.234375 | 0.077320 | 0.116279 |  |
| round_02 | 68 | 17 | 0.250000 | 0.087629 | 0.129771 |  |
| round_03 | 70 | 17 | 0.242857 | 0.087629 | 0.128788 |  |
| round_04 | 70 | 17 | 0.242857 | 0.087629 | 0.128788 |  |
```

### 3.3 大型產物（統計摘要 + 校驗資訊）

下列檔案過大，未內嵌全文；以校驗值、行數、統計摘要呈現。

| path | size_bytes | lines | sha256 |
| --- | --- | --- | --- |
| workspaces/discrete_audio_tokens_more_than_a_survey-api/harvest/arxiv_metadata.json | 2139494 | 33641 | 27ed15431d22c39780c323350470ba5b107d10fdbef2d7473e1c7cd6f1cfb98e |
| workspaces/discrete_audio_tokens_more_than_a_survey-api/review/latte_review_results.json | 2641164 | 23137 | c095785c76b40ca64550ea87e04ef601029b7c9334eaa98fee771e80fba15a48 |
| workspaces/discrete_audio_tokens_more_than_a_survey-api/snowball_rounds/final_included.json | 369475 | 8426 | 0693666da5efb0cef3fd85b3821660d7aaa8788ceb2aa801a69f0eb8cddc2177 |
| workspaces/discrete_audio_tokens_more_than_a_survey-api/snowball_rounds/final_included.csv | 224487 | 649 | f4ca4f49d29d2a5ee50771a7848654646410b58a0bba9eb82ffe6b742241fa2e |
| workspaces/discrete_audio_tokens_more_than_a_survey-api/snowball_rounds/review_registry.json | 4024257 | 88069 | 3259bedfec24bed1066331050fb99e68bc13a2df29854daf413c341a5c765451 |
| workspaces/discrete_audio_tokens_more_than_a_survey-api/snowball_rounds/round_01/candidates_for_review.json | 1232155 | 5696 | 86776179b03df3934d940ae721e3a7982a4c93cceb348e6650d3780f2554e0d4 |
| workspaces/discrete_audio_tokens_more_than_a_survey-api/snowball_rounds/round_01/latte_review_results.json | 2652581 | 14498 | cb396695c30b2b9dc566295adf3ca874459ec11afbdd2be46dc1bc63027c423c |
| workspaces/discrete_audio_tokens_more_than_a_survey-api/snowball_rounds/round_01/snowball_for_review.csv | 4272663 | 445 | 0b2e485bb43e7a098e3f3d6da5e8985153984604e265c05f246baca68c16b304 |
| workspaces/discrete_audio_tokens_more_than_a_survey-api/snowball_rounds/round_01/snowball_results.csv | 4311119 | 457 | 5463eec216c57a2e9341e136bf53939d653d1be0a139c0270000ae2705f8e03c |
| workspaces/discrete_audio_tokens_more_than_a_survey-api/snowball_rounds/round_01/snowball_results_raw.csv | 6713839 | 830 | d6f61732679b944065c8b641e311fdc41653004bf947c31292542dd8469c58a1 |
| workspaces/discrete_audio_tokens_more_than_a_survey-api/snowball_rounds/round_02/candidates_for_review.json | 7538072 | 36051 | 3ad017e4c1f037727a69c18b8c863f0bc77a03dd636c176cbcf749b62ac2f158 |
| workspaces/discrete_audio_tokens_more_than_a_survey-api/snowball_rounds/round_02/latte_review_results.json | 16936063 | 92186 | c4aa1ee49c0df7e710650f067195e51595d198af08bf69ab7fbb661b5cf61145 |
| workspaces/discrete_audio_tokens_more_than_a_survey-api/snowball_rounds/round_02/snowball_for_review.csv | 8504044 | 2807 | 3c6065ae2456c800567649115ea751ba992b1c403e64f4219d3ae3e5973a9a1f |
| workspaces/discrete_audio_tokens_more_than_a_survey-api/snowball_rounds/round_02/snowball_results.csv | 11269390 | 2958 | b62653b74ec56fd0c6bf0919df1225e5b16b2b9a017b86890717d8e3a3a573aa |
| workspaces/discrete_audio_tokens_more_than_a_survey-api/snowball_rounds/round_02/snowball_results_raw.csv | 16111711 | 4646 | 2f1a42a609092b71ca30124d38603709480dc971d3a2c6af6fda28f6c0e08f97 |
| workspaces/discrete_audio_tokens_more_than_a_survey-api/snowball_rounds/round_03/candidates_for_review.json | 8037318 | 40042 | e85b6c6be85ba6471640099d37535697693cc68a5c61e51359b428a83c246385 |
| workspaces/discrete_audio_tokens_more_than_a_survey-api/snowball_rounds/round_03/latte_review_results.json | 18412260 | 102809 | 118a1dd472fb325a341c2ccb42a6af2d898006b76daa3f60d601a604718fff87 |
| workspaces/discrete_audio_tokens_more_than_a_survey-api/snowball_rounds/round_03/snowball_for_review.csv | 8567255 | 3174 | f7d909301e4339062864c1f51e0c741efc7c94324ffd64769bd1e868ddec773e |
| workspaces/discrete_audio_tokens_more_than_a_survey-api/snowball_rounds/round_03/snowball_results.csv | 14170090 | 4260 | 7f8b36f5c64850cc740c3008499317f896ddfc27e4a3d14730b03724176ecbd3 |
| workspaces/discrete_audio_tokens_more_than_a_survey-api/snowball_rounds/round_03/snowball_results_raw.csv | 19942121 | 6753 | f2716ff7f9c4f0bb2888ce1c7e4d13d11b6af490e9d9e95b1b90dc0508be5de5 |
| workspaces/discrete_audio_tokens_more_than_a_survey-api/seed/downloads/arxiv/2502.06490.pdf | 1438984 | 13256 | afd8c05a6bf56afd5b7560c716081cca6023953f1d89706543c463d52ba6e4a8 |
| workspaces/discrete_audio_tokens_more_than_a_survey-api/seed/downloads/arxiv_raw/2502.06490.pdf | 1438984 | 13256 | afd8c05a6bf56afd5b7560c716081cca6023953f1d89706543c463d52ba6e4a8 |


**大型產物統計摘要**

```json
{
  "harvest/arxiv_metadata.json": {
    "type": "list",
    "count": 502
  },
  "harvest/dblp_records.json": {
    "type": "list",
    "count": 43
  },
  "harvest/dblp_title_arxiv_matches.json": {
    "type": "list",
    "count": 43
  },
  "harvest/semantic_scholar_records.json": {
    "type": "list",
    "count": 0
  },
  "harvest/query_plan.json": {
    "type": "dict",
    "key_count": 12,
    "keys": [
      "topic",
      "generated_at",
      "anchors",
      "search_terms",
      "scope",
      "boolean_operator",
      "top_k_per_query",
      "start_date",
      "end_date",
      "cutoff_date",
      "queries_run",
      "queries"
    ]
  },
  "review/latte_review_results.json": {
    "count": 502,
    "final_verdict_counts": {
      "include (seed_filter)": 1,
      "include (junior:5)": 108,
      "exclude (junior:1)": 275,
      "exclude (junior:2)": 50,
      "exclude (senior:2)": 26,
      "include (junior:4)": 14,
      "include (senior:5)": 4,
      "maybe (senior:3)": 8,
      "include (senior:4)": 3,
      "exclude (senior:1)": 3,
      "discard (published_on_or_after_cutoff:2025-06-18)": 1,
      "discard (published_on_or_after_cutoff:2025-06-20)": 1,
      "discard (published_on_or_after_cutoff:2025-06-23)": 1,
      "discard (published_on_or_after_cutoff:2025-07-17)": 1,
      "discard (published_on_or_after_cutoff:2025-08-04)": 1,
      "discard (published_on_or_after_cutoff:2025-08-05)": 1,
      "discard (published_on_or_after_cutoff:2025-08-25)": 1,
      "discard (published_on_or_after_cutoff:2025-09-04)": 1,
      "discard (published_on_or_after_cutoff:2025-09-11)": 1,
      "discard (published_on_or_after_cutoff:2025-09-18)": 1
    }
  },
  "snowball_rounds/round_meta.json": {
    "round_01": {
      "round": 1,
      "seed_review": "workspaces/discrete_audio_tokens_more_than_a_survey/review/latte_review_results.json",
      "seed_count": 130,
      "raw_count": 823,
      "filtered_count": 450,
      "dedup_removed": 12,
      "dedup_removed_by": {
        "openalex_id": 1,
        "doi": 1,
        "title": 10
      },
      "for_review_count": 438,
      "review_ran": true,
      "review_outcome": {
        "include": 37,
        "exclude": 399,
        "other": 2
      },
      "included_total": 167,
      "criteria_hash": "f84221d054a803ad95a17603644a25baad70b61eee481db03ed19d5879ab99fc"
    },
    "round_02": {
      "round": 2,
      "seed_review": "workspaces/discrete_audio_tokens_more_than_a_survey/snowball_rounds/round_01/latte_review_results.json",
      "seed_count": 37,
      "raw_count": 4611,
      "filtered_count": 2924,
      "dedup_removed": 151,
      "dedup_removed_by": {
        "openalex_id": 119,
        "doi": 10,
        "title": 22
      },
      "for_review_count": 2773,
      "review_ran": true,
      "review_outcome": {
        "exclude": 2507,
        "include": 248,
        "other": 18
      },
      "included_total": 415,
      "criteria_hash": "f84221d054a803ad95a17603644a25baad70b61eee481db03ed19d5879ab99fc"
    },
    "round_03": {
      "round": 3,
      "seed_review": "workspaces/discrete_audio_tokens_more_than_a_survey/snowball_rounds/round_02/latte_review_results.json",
      "seed_count": 248,
      "raw_count": 6616,
      "filtered_count": 4159,
      "dedup_removed": 1079,
      "dedup_removed_by": {
        "openalex_id": 1020,
        "doi": 4,
        "title": 55
      },
      "for_review_count": 3080,
      "review_ran": true,
      "review_outcome": {
        "exclude": 2830,
        "include": 233,
        "other": 17
      },
      "included_total": 648,
      "criteria_hash": "f84221d054a803ad95a17603644a25baad70b61eee481db03ed19d5879ab99fc"
    }
  },
  "snowball_rounds/final_included.json": {
    "count": 648
  },
  "snowball_rounds/review_registry.json": {
    "type": "dict",
    "key_count": 4,
    "keys": [
      "version",
      "criteria_hash",
      "entries",
      "updated_at"
    ]
  }
}
```

### 3.4 workspace 產物清單（完整檔案清單 + 校驗值）

| path | size_bytes | lines | sha256 |
| --- | --- | --- | --- |
| workspaces/discrete_audio_tokens_more_than_a_survey-api/config.json | 111 | 4 | 0a339bf32746beb8a3dbe03b0c2f75b7daceb168d038630d83d10ae62a6c8039 |
| workspaces/discrete_audio_tokens_more_than_a_survey-api/criteria/combined_notes.txt | 8342 | 94 | 800c8827a5704bdbf08d69217dbc078bb7cef4d853d66ed775ae0c96ea46208c |
| workspaces/discrete_audio_tokens_more_than_a_survey-api/criteria/criteria.json | 52596 | 229 | f84221d054a803ad95a17603644a25baad70b61eee481db03ed19d5879ab99fc |
| workspaces/discrete_audio_tokens_more_than_a_survey-api/criteria/formatter_prompt.json | 9413 | 10 | 1d2e1219e42a4e54f8809ed92037ee10f295a9f248b55c433aa25b7047351c70 |
| workspaces/discrete_audio_tokens_more_than_a_survey-api/criteria/formatter_raw.txt | 10205 | 204 | 12fa0d8d3d8b332a931ee1704f20b5f1374beb08fe40bc6a50a17d83e125f448 |
| workspaces/discrete_audio_tokens_more_than_a_survey-api/criteria/pdf_background.txt | 4059 | 35 | 93a1510f66b240792ec1ac5b70dc6df2dc7da60d39ca64846939d2831d3dfa93 |
| workspaces/discrete_audio_tokens_more_than_a_survey-api/criteria/web_search_notes.txt | 4223 | 57 | 1f9d62e4e9d1dc28cbe834061e163330e482e0c5797b4133b658e17628e980db |
| workspaces/discrete_audio_tokens_more_than_a_survey-api/cutoff/cutoff.json | 554 | 18 | 24ceb6ff926340fc2139fb1b6e68847d198fcc5a77ea2a3d43dbefdefcf7bc43 |
| workspaces/discrete_audio_tokens_more_than_a_survey-api/harvest/arxiv_metadata.json | 2139494 | 33641 | 27ed15431d22c39780c323350470ba5b107d10fdbef2d7473e1c7cd6f1cfb98e |
| workspaces/discrete_audio_tokens_more_than_a_survey-api/harvest/dblp_records.json | 10502 | 260 | 441ef09dfbeb8a12ccd0948a058f297f12ea3bef4c484086bc809d8ad821f411 |
| workspaces/discrete_audio_tokens_more_than_a_survey-api/harvest/dblp_title_arxiv_matches.json | 13566 | 329 | 5d2936e86b60a07fc3990674a8181c67f2ea248ff0ac5171370e988951580e29 |
| workspaces/discrete_audio_tokens_more_than_a_survey-api/harvest/query_plan.json | 18930 | 615 | dd513def3983a54143a40d58dd3f2086ee9689e655e9aa67ab7b8103eb9b1747 |
| workspaces/discrete_audio_tokens_more_than_a_survey-api/harvest/semantic_scholar_records.json | 2 | 1 | 4f53cda18c2baa0c0354bb5f9a3ecbe5ed12ab4d8e11ba873c2f11161202b945 |
| workspaces/discrete_audio_tokens_more_than_a_survey-api/keywords/keyword_extractor_usage_20260107_101539Z.json | 866 | 35 | 32b3b0984f16735ac8e840c18c448640b297346cd305a964df1e72cc2139a782 |
| workspaces/discrete_audio_tokens_more_than_a_survey-api/keywords/keywords.json | 7969 | 232 | 7ae892678d4c6c10e3aa257ae031925d3f341a705dda159d2a0d7a5ca25f5239 |
| workspaces/discrete_audio_tokens_more_than_a_survey-api/review/latte_review_results.json | 2641164 | 23137 | c095785c76b40ca64550ea87e04ef601029b7c9334eaa98fee771e80fba15a48 |
| workspaces/discrete_audio_tokens_more_than_a_survey-api/seed/downloads/arxiv/2502.06490.pdf | 1438984 | 13256 | afd8c05a6bf56afd5b7560c716081cca6023953f1d89706543c463d52ba6e4a8 |
| workspaces/discrete_audio_tokens_more_than_a_survey-api/seed/downloads/arxiv_raw/2502.06490.pdf | 1438984 | 13256 | afd8c05a6bf56afd5b7560c716081cca6023953f1d89706543c463d52ba6e4a8 |
| workspaces/discrete_audio_tokens_more_than_a_survey-api/seed/downloads/download_results.json | 3636 | 79 | 94cbbef315edb36c16ed85dff06fa184fdb7e1c22047ca1de9a18ae09881b063 |
| workspaces/discrete_audio_tokens_more_than_a_survey-api/seed/filters/llm_screening.json | 1905 | 24 | 26d26ebce3f8bb5f521e5f29c59fc61fec6122e10f238fc001ebae966f453561 |
| workspaces/discrete_audio_tokens_more_than_a_survey-api/seed/filters/selected_ids.json | 82 | 7 | 060dd3b806af53f367b01c37998dbedc3d48b900e06f03b94a0e95437ec55f8c |
| workspaces/discrete_audio_tokens_more_than_a_survey-api/seed/queries/arxiv.json | 5710 | 26 | 844af6335202d90562c526e33fcbd0e36bdbb4a2438f0256afcee7e590bcd981 |
| workspaces/discrete_audio_tokens_more_than_a_survey-api/seed/queries/seed_rewrite.json | 1738 | 44 | e2e2e2832954ac86187414bfb4ea57a5400c7f7dafd424951dcb9e8ba47cc0c2 |
| workspaces/discrete_audio_tokens_more_than_a_survey-api/seed/queries/seed_selection.json | 2847 | 80 | 4a2cd2480d7f17bd9be1ecc4534cefba8ec92963d1838b43d5612831eaf3012b |
| workspaces/discrete_audio_tokens_more_than_a_survey-api/snowball_rounds/final_included.csv | 224487 | 649 | f4ca4f49d29d2a5ee50771a7848654646410b58a0bba9eb82ffe6b742241fa2e |
| workspaces/discrete_audio_tokens_more_than_a_survey-api/snowball_rounds/final_included.json | 369475 | 8426 | 0693666da5efb0cef3fd85b3821660d7aaa8788ceb2aa801a69f0eb8cddc2177 |
| workspaces/discrete_audio_tokens_more_than_a_survey-api/snowball_rounds/review_registry.json | 4024257 | 88069 | 3259bedfec24bed1066331050fb99e68bc13a2df29854daf413c341a5c765451 |
| workspaces/discrete_audio_tokens_more_than_a_survey-api/snowball_rounds/round_01/candidates_for_review.json | 1232155 | 5696 | 86776179b03df3934d940ae721e3a7982a4c93cceb348e6650d3780f2554e0d4 |
| workspaces/discrete_audio_tokens_more_than_a_survey-api/snowball_rounds/round_01/dedup_report.json | 219 | 10 | 0e8caf93e6aa4b28526eb02de9cd073e93367293c9e90e42b46c15ca47a00bc9 |
| workspaces/discrete_audio_tokens_more_than_a_survey-api/snowball_rounds/round_01/final_included.csv | 55814 | 168 | 451045fb3da1d41e99cb4d34af2ef372c837c88671d7a6d9bfa018969157f555 |
| workspaces/discrete_audio_tokens_more_than_a_survey-api/snowball_rounds/round_01/final_included.json | 93092 | 2173 | 0f35a95cb36b75e7cb1374fe460b24d5df1dc45b0432671f6c487d2a0694f8fc |
| workspaces/discrete_audio_tokens_more_than_a_survey-api/snowball_rounds/round_01/latte_review_results.json | 2652581 | 14498 | cb396695c30b2b9dc566295adf3ca874459ec11afbdd2be46dc1bc63027c423c |
| workspaces/discrete_audio_tokens_more_than_a_survey-api/snowball_rounds/round_01/round_meta.json | 533 | 22 | 06745c593597a0f7d77a4ad614844c0cfae940ad95f02fc77da72a4815f8ba51 |
| workspaces/discrete_audio_tokens_more_than_a_survey-api/snowball_rounds/round_01/screening_included.csv | 429915 | 131 | aa13e8b7e86f3f402c61039de3fb0575fa76658c8607e9c99b4d00f126562d1d |
| workspaces/discrete_audio_tokens_more_than_a_survey-api/snowball_rounds/round_01/snowball_for_review.csv | 4272663 | 445 | 0b2e485bb43e7a098e3f3d6da5e8985153984604e265c05f246baca68c16b304 |
| workspaces/discrete_audio_tokens_more_than_a_survey-api/snowball_rounds/round_01/snowball_results.csv | 4311119 | 457 | 5463eec216c57a2e9341e136bf53939d653d1be0a139c0270000ae2705f8e03c |
| workspaces/discrete_audio_tokens_more_than_a_survey-api/snowball_rounds/round_01/snowball_results_raw.csv | 6713839 | 830 | d6f61732679b944065c8b641e311fdc41653004bf947c31292542dd8469c58a1 |
| workspaces/discrete_audio_tokens_more_than_a_survey-api/snowball_rounds/round_02/candidates_for_review.json | 7538072 | 36051 | 3ad017e4c1f037727a69c18b8c863f0bc77a03dd636c176cbcf749b62ac2f158 |
| workspaces/discrete_audio_tokens_more_than_a_survey-api/snowball_rounds/round_02/dedup_report.json | 223 | 10 | c4e28004e89c78ce90ab864e389b6af643793f5fe575b67d7457bbcb2aa89b5f |
| workspaces/discrete_audio_tokens_more_than_a_survey-api/snowball_rounds/round_02/final_included.csv | 143096 | 416 | 2e918baba0d207cd280ed493794d38bab7adddd36e8283ab59fec90f4d40f497 |
| workspaces/discrete_audio_tokens_more_than_a_survey-api/snowball_rounds/round_02/final_included.json | 235904 | 5397 | 2447e6d5f51b1e47130990cd2edb3a04de8d8227cfc2c211ba896aeda26db866 |
| workspaces/discrete_audio_tokens_more_than_a_survey-api/snowball_rounds/round_02/latte_review_results.json | 16936063 | 92186 | c4aa1ee49c0df7e710650f067195e51595d198af08bf69ab7fbb661b5cf61145 |
| workspaces/discrete_audio_tokens_more_than_a_survey-api/snowball_rounds/round_02/round_meta.json | 560 | 22 | 464cb92f45ae490b749855cda40773fd1259c68747a31d07593c857a0dd664bd |
| workspaces/discrete_audio_tokens_more_than_a_survey-api/snowball_rounds/round_02/screening_included.csv | 150476 | 38 | 8f5140e0e6c125982050567a148aba9d26015338773a2e193a112bfa1d6582e9 |
| workspaces/discrete_audio_tokens_more_than_a_survey-api/snowball_rounds/round_02/snowball_for_review.csv | 8504044 | 2807 | 3c6065ae2456c800567649115ea751ba992b1c403e64f4219d3ae3e5973a9a1f |
| workspaces/discrete_audio_tokens_more_than_a_survey-api/snowball_rounds/round_02/snowball_results.csv | 11269390 | 2958 | b62653b74ec56fd0c6bf0919df1225e5b16b2b9a017b86890717d8e3a3a573aa |
| workspaces/discrete_audio_tokens_more_than_a_survey-api/snowball_rounds/round_02/snowball_results_raw.csv | 16111711 | 4646 | 2f1a42a609092b71ca30124d38603709480dc971d3a2c6af6fda28f6c0e08f97 |
| workspaces/discrete_audio_tokens_more_than_a_survey-api/snowball_rounds/round_03/candidates_for_review.json | 8037318 | 40042 | e85b6c6be85ba6471640099d37535697693cc68a5c61e51359b428a83c246385 |
| workspaces/discrete_audio_tokens_more_than_a_survey-api/snowball_rounds/round_03/dedup_report.json | 224 | 10 | db80c28e8cfb0ed60787a323583bf8f0c85274d9949093b3b70f3f0407ebfa17 |
| workspaces/discrete_audio_tokens_more_than_a_survey-api/snowball_rounds/round_03/final_included.csv | 224487 | 649 | f4ca4f49d29d2a5ee50771a7848654646410b58a0bba9eb82ffe6b742241fa2e |
| workspaces/discrete_audio_tokens_more_than_a_survey-api/snowball_rounds/round_03/final_included.json | 369475 | 8426 | 0693666da5efb0cef3fd85b3821660d7aaa8788ceb2aa801a69f0eb8cddc2177 |
| workspaces/discrete_audio_tokens_more_than_a_survey-api/snowball_rounds/round_03/latte_review_results.json | 18412260 | 102809 | 118a1dd472fb325a341c2ccb42a6af2d898006b76daa3f60d601a604718fff87 |
| workspaces/discrete_audio_tokens_more_than_a_survey-api/snowball_rounds/round_03/round_meta.json | 562 | 22 | 037bc3048b67a74856d6861db040e28ce6f33a7b14ce5d166d89825d13ca5e84 |
| workspaces/discrete_audio_tokens_more_than_a_survey-api/snowball_rounds/round_03/screening_included.csv | 988930 | 249 | b76a6e68089436fd02e15e543deec0a8216231671cc9497479c07f4913d1e88a |
| workspaces/discrete_audio_tokens_more_than_a_survey-api/snowball_rounds/round_03/snowball_for_review.csv | 8567255 | 3174 | f7d909301e4339062864c1f51e0c741efc7c94324ffd64769bd1e868ddec773e |
| workspaces/discrete_audio_tokens_more_than_a_survey-api/snowball_rounds/round_03/snowball_results.csv | 14170090 | 4260 | 7f8b36f5c64850cc740c3008499317f896ddfc27e4a3d14730b03724176ecbd3 |
| workspaces/discrete_audio_tokens_more_than_a_survey-api/snowball_rounds/round_03/snowball_results_raw.csv | 19942121 | 6753 | f2716ff7f9c4f0bb2888ce1c7e4d13d11b6af490e9d9e95b1b90dc0508be5de5 |
| workspaces/discrete_audio_tokens_more_than_a_survey-api/snowball_title_f1_tables.md | 808 | 20 | 46ca153fe5a75921470b1bebd1ae5170bc3c63ddf48c345de68e8834428e3ea5 |


## 4. workspace: workspaces/discrete_audio_tokens_more_than_a_survey（Codex CLI）

### 4.1 重要摘要

- seed 階段未能下載任何 PDF。
- seed rewrite 嘗試 10 次，仍僅產生同義或近義片語，arXiv 結果仍只命中同名論文。
- 由於 cutoff 強制啟用且與同名標題高度相似，候選被全部移除。

### 4.2 主要小型產物（全文內嵌）

#### workspaces/discrete_audio_tokens_more_than_a_survey/config.json

```json
{
  "topic": "Discrete Audio Tokens: More Than a Survey!",
  "updated_at": "2026-01-13T14:58:11.466036+00:00"
}
```

#### workspaces/discrete_audio_tokens_more_than_a_survey/cutoff/cutoff.json

```json
{
  "topic_title": "Discrete Audio Tokens: More Than a Survey!",
  "topic_title_normalized": "discrete audio tokens more than a survey",
  "target_paper": {
    "source": "arxiv",
    "id": "2506.10274",
    "title": "Discrete Audio Tokens: More Than a Survey!",
    "published_date": "2025-06-12",
    "published_raw": "2025-06-12"
  },
  "cutoff_date": "2025-06-12",
  "policy": {
    "exclude_same_title": true,
    "exclude_on_or_after_cutoff_date": true
  },
  "derived_from": "seed_selection",
  "generated_at": "2026-01-13T14:08:36.642144+00:00"
}
```

#### workspaces/discrete_audio_tokens_more_than_a_survey/seed/queries/arxiv.json

```json
[
  {
    "id": "http://arxiv.org/abs/2506.10274v3",
    "title": "Discrete Audio Tokens: More Than a Survey!",
    "summary": "Discrete audio tokens are compact representations that aim to preserve perceptual quality, phonetic content, and speaker characteristics while enabling efficient storage and inference, as well as competitive performance across diverse downstream tasks. They provide a practical alternative to continuous features, enabling the integration of speech and audio into modern large language models (LLMs). As interest in token-based audio processing grows, various tokenization methods have emerged, and several surveys have reviewed the latest progress in the field. However, existing studies often focus on specific domains or tasks and lack a unified comparison across various benchmarks. This paper presents a systematic review and benchmark of discrete audio tokenizers, covering three domains: speech, music, and general audio. We propose a taxonomy of tokenization approaches based on encoder-decoder, quantization techniques, training paradigm, streamability, and application domains. We evaluate tokenizers on multiple benchmarks for reconstruction, downstream performance, and acoustic language modeling, and analyze trade-offs through controlled ablation studies. Our findings highlight key limitations, practical considerations, and open challenges, providing insight and guidance for future research in this rapidly evolving area. For more information, including our main results and tokenizer database, please refer to our website: https://poonehmousavi.github.io/dates-website/.",
    "published": "2025-06-12T01:35:43Z"
  }
]
```

#### workspaces/discrete_audio_tokens_more_than_a_survey/seed/queries/seed_selection.json

```json
{
  "topic": "Discrete Audio Tokens: More Than a Survey!",
  "topic_variants": [
    "Discrete Audio Tokens: More Than a Survey!",
    "discrete audio tokens: more than a survey",
    "Discrete Audio Tokens",
    "discrete audio tokens: more than a surveys"
  ],
  "cutoff_by_similar_title": true,
  "similarity_threshold": 0.8,
  "title_filter_applied": true,
  "title_filter_keywords": [
    "survey",
    "review",
    "overview"
  ],
  "cutoff_reason": "cutoff_removed_all_candidates",
  "cutoff_candidate": {
    "arxiv_id": "2506.10274",
    "title": "Discrete Audio Tokens: More Than a Survey!",
    "published": "2025-06-12T01:35:43Z",
    "published_date": "2025-06-12",
    "similarity": {
      "best_variant": "Discrete Audio Tokens: More Than a Survey!",
      "sequence_ratio": 1.0,
      "token_containment": 1.0,
      "topic": "Discrete Audio Tokens: More Than a Survey!",
      "title": "Discrete Audio Tokens: More Than a Survey!",
      "score": 1.0
    }
  },
  "cutoff_date": "2025-06-12",
  "topic_title_normalized": "discrete audio tokens more than a survey",
  "records_total": 1,
  "records_after_title_filter": 1,
  "records_after_filter": 0,
  "download_top_k": 5,
  "download_selected": [],
  "candidates": [
    {
      "arxiv_id": "2506.10274",
      "title": "Discrete Audio Tokens: More Than a Survey!",
      "published": "2025-06-12T01:35:43Z",
      "published_date": "2025-06-12",
      "similarity": {
        "best_variant": "Discrete Audio Tokens: More Than a Survey!",
        "sequence_ratio": 1.0,
        "token_containment": 1.0,
        "topic": "Discrete Audio Tokens: More Than a Survey!",
        "title": "Discrete Audio Tokens: More Than a Survey!",
        "score": 1.0
      }
    }
  ],
  "anchor_mode": "phrase",
  "search_query": "(all:\"discrete audio tokens\" OR all:\"discrete audio tokenization\" OR all:\"discrete acoustic tokens\") AND (all:\"survey\" OR all:\"review\" OR all:\"overview\" OR all:\"systematic review\" OR all:\"systematic literature review\" OR all:\"scoping review\" OR all:\"mapping study\" OR all:\"tutorial\")",
  "scope": "all",
  "boolean_operator": "AND",
  "raw_query": null
}
```

#### workspaces/discrete_audio_tokens_more_than_a_survey/seed/queries/seed_rewrite.json

```json
{
  "topic": "Discrete Audio Tokens: More Than a Survey!",
  "trigger_reason": "cutoff_removed_all_candidates",
  "attempts": [
    {
      "attempt": 1,
      "model": "gpt-5.2",
      "provider": "openai",
      "raw_output": "discrete audio tokens  \ndiscrete acoustic tokens  \ndiscrete audio units",
      "parsed_phrases": [
        "discrete audio tokens",
        "discrete acoustic tokens",
        "discrete audio units"
      ],
      "parsed_phrase": "discrete audio tokens",
      "status": "ok",
      "error": null
    },
    {
      "attempt": 2,
      "model": "gpt-5.2",
      "provider": "openai",
      "raw_output": "discrete audio tokens\nquantized audio tokens\naudio token quantization",
      "parsed_phrases": [
        "discrete audio tokens",
        "quantized audio tokens",
        "audio token quantization"
      ],
      "parsed_phrase": "discrete audio tokens",
      "status": "ok",
      "error": null
    },
    {
      "attempt": 3,
      "model": "gpt-5.2",
      "provider": "openai",
      "raw_output": "discrete audio tokens  \ndiscrete audio tokenization  \ndiscrete audio token representations",
      "parsed_phrases": [
        "discrete audio tokens",
        "discrete audio tokenization",
        "discrete audio token representations"
      ],
      "parsed_phrase": "discrete audio tokens",
      "status": "ok",
      "error": null
    },
    {
      "attempt": 4,
      "model": "gpt-5.2",
      "provider": "openai",
      "raw_output": "discrete audio tokens\nquantized audio tokens\ndiscrete audio tokenization",
      "parsed_phrases": [
        "discrete audio tokens",
        "quantized audio tokens",
        "discrete audio tokenization"
      ],
      "parsed_phrase": "discrete audio tokens",
      "status": "ok",
      "error": null
    },
    {
      "attempt": 5,
      "model": "gpt-5.2",
      "provider": "openai",
      "raw_output": "discrete audio tokens\ndiscrete audio tokenization\nquantized audio tokens",
      "parsed_phrases": [
        "discrete audio tokens",
        "discrete audio tokenization",
        "quantized audio tokens"
      ],
      "parsed_phrase": "discrete audio tokens",
      "status": "ok",
      "error": null
    },
    {
      "attempt": 6,
      "model": "gpt-5.2",
      "provider": "openai",
      "raw_output": "discrete audio tokens\ndiscrete audio tokenization\nquantized audio tokens",
      "parsed_phrases": [
        "discrete audio tokens",
        "discrete audio tokenization",
        "quantized audio tokens"
      ],
      "parsed_phrase": "discrete audio tokens",
      "status": "ok",
      "error": null
    },
    {
      "attempt": 7,
      "model": "gpt-5.2",
      "provider": "openai",
      "raw_output": "discrete audio tokenization\ndiscrete audio token representations\ndiscrete audio token modeling",
      "parsed_phrases": [
        "discrete audio tokenization",
        "discrete audio token representations",
        "discrete audio token modeling"
      ],
      "parsed_phrase": "discrete audio tokenization",
      "status": "ok",
      "error": null
    },
    {
      "attempt": 8,
      "model": "gpt-5.2",
      "provider": "openai",
      "raw_output": "discrete audio tokens\nquantized audio tokens\ndiscrete audio tokenization",
      "parsed_phrases": [
        "discrete audio tokens",
        "quantized audio tokens",
        "discrete audio tokenization"
      ],
      "parsed_phrase": "discrete audio tokens",
      "status": "ok",
      "error": null
    },
    {
      "attempt": 9,
      "model": "gpt-5.2",
      "provider": "openai",
      "raw_output": "discrete audio tokens\ndiscrete audio tokenization\ndiscrete audio tokenizers",
      "parsed_phrases": [
        "discrete audio tokens",
        "discrete audio tokenization",
        "discrete audio tokenizers"
      ],
      "parsed_phrase": "discrete audio tokens",
      "status": "ok",
      "error": null
    },
    {
      "attempt": 10,
      "model": "gpt-5.2",
      "provider": "openai",
      "raw_output": "discrete audio tokens\ndiscrete audio tokenization\ndiscrete acoustic tokens",
      "parsed_phrases": [
        "discrete audio tokens",
        "discrete audio tokenization",
        "discrete acoustic tokens"
      ],
      "parsed_phrase": "discrete audio tokens",
      "status": "ok",
      "error": null
    }
  ],
  "selected_queries": [
    "discrete audio tokens",
    "discrete audio tokenization",
    "discrete acoustic tokens"
  ],
  "original_seed_query": "(all:\"Discrete Audio Tokens: More Than a Survey!\" OR all:\"discrete audio tokens: more than a survey\" OR all:\"Discrete Audio Tokens\" OR all:\"discrete audio tokens: more than a surveys\") AND (all:\"survey\" OR all:\"review\" OR all:\"overview\" OR all:\"systematic review\" OR all:\"systematic literature review\" OR all:\"scoping review\" OR all:\"mapping study\" OR all:\"tutorial\")",
  "cutoff_reason": "cutoff_removed_all_candidates",
  "cutoff_candidate_title": "Discrete Audio Tokens: More Than a Survey!",
  "generated_at": "2026-01-13T15:04:22.486406+00:00",
  "preview_only": false
}
```

#### workspaces/discrete_audio_tokens_more_than_a_survey/seed/downloads/download_results.json

```json
{
  "topic": "Discrete Audio Tokens: More Than a Survey!",
  "anchors": [
    "Discrete Audio Tokens: More Than a Survey!",
    "discrete audio tokens: more than a survey",
    "Discrete Audio Tokens",
    "discrete audio tokens: more than a surveys"
  ],
  "survey_terms": [
    "survey",
    "review",
    "overview",
    "systematic review",
    "systematic literature review",
    "scoping review",
    "mapping study",
    "tutorial"
  ],
  "anchor_mode": "phrase",
  "search_query": "(all:\"Discrete Audio Tokens: More Than a Survey!\" OR all:\"discrete audio tokens: more than a survey\" OR all:\"Discrete Audio Tokens\" OR all:\"discrete audio tokens: more than a surveys\") AND (all:\"survey\" OR all:\"review\" OR all:\"overview\" OR all:\"systematic review\" OR all:\"systematic literature review\" OR all:\"scoping review\" OR all:\"mapping study\" OR all:\"tutorial\")",
  "raw_query": null,
  "max_results": 25,
  "download_top_k": 5,
  "downloaded_at": "2026-01-13T14:58:11.681623+00:00",
  "downloads": {
    "arxiv": [],
    "semantic_scholar": [],
    "dblp": []
  },
  "rewrite_attempts": 10,
  "rewrite_query": "discrete audio tokens",
  "rewrite_queries": [
    "discrete audio tokens",
    "discrete audio tokenization",
    "discrete acoustic tokens"
  ]
}
```

#### workspaces/discrete_audio_tokens_more_than_a_survey/seed/filters/llm_screening.json

```json
{
  "topic": "Discrete Audio Tokens: More Than a Survey!",
  "model": "gpt-5-mini",
  "generated_at": "2026-01-13T14:10:02.380874+00:00",
  "papers": [],
  "fallback": {
    "enabled": true,
    "triggered": false,
    "min_selected": 2,
    "selected_before": 0,
    "selected_after": 0,
    "added": [],
    "prompt_path": null
  }
}
```

#### workspaces/discrete_audio_tokens_more_than_a_survey/seed/filters/selected_ids.json

```json
{
  "selected": [],
  "rejected": [],
  "fallback_added": []
}
```

### 4.3 workspace 產物清單（完整檔案清單 + 校驗值）

| path | size_bytes | lines | sha256 |
| --- | --- | --- | --- |
| workspaces/discrete_audio_tokens_more_than_a_survey/config.json | 111 | 4 | 15bccf68482903cc8cfff633bd53372e862af8594775c07366dd138389e620b6 |
| workspaces/discrete_audio_tokens_more_than_a_survey/cutoff/cutoff.json | 554 | 18 | 5ccfb4b1908969ff57ba96ef8fa8d98d38dca98741d0c884f4a7a9479c016397 |
| workspaces/discrete_audio_tokens_more_than_a_survey/seed/downloads/download_results.json | 1279 | 37 | 3d7fde7bc2d3438f18ecadbd1321afeca95570bbfe57407de44f324764a0c6b9 |
| workspaces/discrete_audio_tokens_more_than_a_survey/seed/filters/llm_screening.json | 335 | 15 | 453901d3cca3b010462d80cd8c9dfa112a2ccd534919b2655dc54497157eff4c |
| workspaces/discrete_audio_tokens_more_than_a_survey/seed/filters/selected_ids.json | 62 | 5 | 99a9a9f10ab83bbe5e5c40138306999803d2240455e1d6bd3e2e228aa6d5e178 |
| workspaces/discrete_audio_tokens_more_than_a_survey/seed/queries/arxiv.json | 1664 | 8 | 41267f88a4cdacab4e759432a73d519ece615bec3fce453fadb818b5d5a2e1cb |
| workspaces/discrete_audio_tokens_more_than_a_survey/seed/queries/seed_rewrite.json | 5112 | 156 | 787242eb5a94e9d207ad100268621cb06cdaf36dcbca3149f42940f65230dc71 |
| workspaces/discrete_audio_tokens_more_than_a_survey/seed/queries/seed_selection.json | 2163 | 60 | 31c3eedf66df8ad655c6d32a249f7f9a7182afee8c86887a4ec84c6901bff702 |


## 5. Prompts（本次流程涉及的 prompt 全文）

本節列出所有在兩個 workspace 中實際使用或被記錄的 prompt。
若未在實際流程中觸發，會標示為「未觸發」。


### 5.1 resources/LLM/prompts/seed/seed_query_rewrite.md

使用情況：API: 使用（seed rewrite） / Codex CLI: 使用（seed rewrite）

```text
# seed query rewrite

you are given a single research topic string.
rewrite it into 1 to 3 short search phrases that slightly broaden retrieval while preserving the same core research meaning.

goals
- improve recall when the original topic string is too narrow for search.
- preserve the exact core technical concept; do not introduce new concepts or adjacent subtopics.
- keep each phrase specific enough to avoid drifting into overly broad, generic umbrella terms.

how to rewrite
1) extract anchors
- identify the smallest set of distinctive technical terms from the topic that uniquely identify the concept.
- anchors must be domain-specific; avoid choosing only generic methodological words if more distinctive terms exist.
- treat the anchors as mandatory: do not drop them.

2) generate 1 to 3 phrases
- each phrase must include all anchors, or a very close synonym / standard abbreviation / standard expansion of an anchor.
- do not output phrases that are strict subsets of another output phrase.
- if you output multiple phrases, keep them at similar specificity (no “broad fallback” phrase).
- prefer 2 to 6 words per phrase; keep phrases short and noun-phrase-like.
- do not add document-type words (e.g., survey/review) unless they are part of the core concept.

3) final self-check before responding
- output is 1 to 3 lines only.
- one phrase per line.
- lowercase only.
- letters/numbers/spaces only.
- no quotes, no punctuation, no bullets, no numbering, no explanations, no extra whitespace lines.

topic
<<topic>>
```

### 5.2 resources/LLM/prompts/filter_seed/llm_screening.md

使用情況：API: 使用（filter-seed） / Codex CLI: 未觸發（無 PDF）

```text
- Role: Literature Screening Assistant
- Task: Decide whether the paper should be used for keyword extraction for the given topic.
- Constraints:
  - Use ONLY the title and abstract provided below.
  - Output STRICT JSON only, no extra text.
  - decision must be "yes" or "no" (lowercase).
  - reason must be a single short Chinese sentence.
  - If uncertain, choose "no".
  - confidence must be a number between 0 and 1.
  - The paper MUST clearly be a survey/review/overview-type work as stated in the title or abstract.
    If it is not explicitly described as a survey/review/overview (or equivalent), decision must be "no".
  - The paper MUST be primarily and directly about the given topic, not just a passing mention.
    If the topic is only tangentially related or peripheral, decision must be "no".

Topic: <<topic>>
Keywords hint (optional): <<keywords_hint>>

Paper:
title: <<title>>
abstract: <<abstract>>

Output JSON (no extra keys):
{
  "decision": "yes|no",
  "reason": "一句話中文理由",
  "confidence": 0.0
}
```

### 5.3 resources/LLM/prompts/filter_seed/llm_screening_fallback.md

使用情況：API: 未觸發 / Codex CLI: 未觸發

```text
- Role: Literature Screening Assistant
- Task: Decide whether the paper should be used for keyword extraction when seed papers are scarce.
- Constraints:
  - Use ONLY the title and abstract provided below.
  - Output STRICT JSON only, no extra text.
  - decision must be "yes" or "no" (lowercase).
  - reason must be a single short Chinese sentence.
  - confidence must be a number between 0 and 1.
  - This is fallback mode: the paper does NOT need to be explicitly a survey/review/overview.
    If it is strongly and directly about the topic (core methods/terms/taxonomy), you may choose "yes".
  - If the topic is only tangentially related or peripheral, decision must be "no".
  - If uncertain, choose "no".

Topic: <<topic>>
Keywords hint (optional): <<keywords_hint>>

Paper:
title: <<title>>
abstract: <<abstract>>

Output JSON (no extra keys):
{
  "decision": "yes|no",
  "reason": "一句話中文理由",
  "confidence": 0.0
}
```

### 5.4 resources/LLM/prompts/keyword_extractor/generate_search_terms.md

使用情況：API: 使用（keywords per-PDF） / Codex CLI: 未觸發（無 PDF）

```text
- Role: Academic Search Strategy Designer and Systematic Review Analyst
- Background: The user uploads one or more survey papers (PDFs). Your goal is to extract high-quality search terms and prepare a metadata-aligned JSON summary for downstream systematic-review tooling.
- Profile: You design evidence-grounded, reproducible search strategies for literature reviews. You prioritize deduplication, clarity, and coverage.
- Skills: Systematic review methodology, taxonomy-driven term extraction, boolean query synthesis, deduplication and synonym consolidation, concise rationale writing.
- Goals: Produce a JSON-only output containing anchor terms, categorized search terms, and per-paper metadata entries (including detected keywords with evidence). Ground every field in the PDFs and the provided metadata.
- Constraints:
  - Use only information present in the uploaded PDFs or in the metadata block appended below.
  - Copy each paper title and abstract exactly as provided; do not paraphrase or truncate them.
  - Prefer multi-paper-supported terms; mark single-paper terms with lower confidence.
  - Keep each rationale under 20 words; cite page numbers if available; otherwise use "page": "n/a".
  - Keep total recommended search terms <= <<max_queries>> (default 50).
  - Keep each search term as a concise noun phrase (ideally 1–2 words, maximum 3); never output full sentences or tokens with underscores.
  - Output strictly valid JSON, no extra text.
- Downstream usage (important):
  - The output anchor_terms and search_terms will be used to construct boolean search queries for arXiv-style engines.
  - anchor_terms are treated as stable topic anchors; search_terms are category-specific query terms.
  - Queries are built by combining anchor_terms with search_terms (e.g., (anchor OR anchor OR ...) AND (term OR term OR ...)).
  - Matching is mostly literal, so anchor_terms and search_terms must be searchable, generalizable phrases (not full titles, not overly specific wording).
  - Avoid punctuation-heavy strings, quotes, dataset IDs, or long phrases; prefer 1–3 word noun phrases likely to appear in titles/abstracts.
  - Do not add meta terms like "survey/review" unless the topic itself explicitly centers on surveys/reviews.
- Topic interpretation (important):
  - The provided topic_hint may be either (1) a broad research area or (2) a specific paper title (possibly exact).
  - Silently decide which type topic_hint is; do not output the decision.
  - Never output topic_hint itself as anchor_terms.
  - If topic_hint is type (2), you must NOT copy the title, subtitle, punctuation, or create abbreviations from it. Derive anchors only from the PDFs/metadata.
  - If topic_hint is type (1), you may use common field abbreviations only when they appear in the PDFs/metadata and are widely used in the field.
  - Anchor_terms must appear verbatim (case-insensitive) in the titles/abstracts; use 1–3 word noun phrases without punctuation.
  - Abbreviations are allowed only if they appear in the PDFs/metadata and are widely used in the field; never invent acronyms.
  - When an abbreviation is used, include its long-form anchor term alongside it (do not output acronym-only anchors).
  - Do not inject external domain assumptions; derive anchor_terms from the PDFs/metadata only.
- Workflow:
  1) Review the provided paper metadata (see block below) to capture canonical identifiers, titles, abstracts, publication years, and URLs.
  2) Read the PDFs and identify the central task/topic; propose 2–4 anchor_terms aligned with the metadata guidance.
  3) For each paper, extract candidate terms grouped by categories: <<category_list>>.
     <<category_coverage_note>>
<<additional_category_note>>
  4) Normalize and merge across papers: lemmatize, deduplicate, and consolidate related phrasing for each category.
  5) Identify supporting evidence for detected keywords (quotes + page numbers when available) so each term can be traced back to the PDFs.
  6) Keep each `papers[*]` entry aligned with the metadata block; copy titles/abstracts verbatim and supply detected keywords with evidence.
- Runtime overrides (current request):
  - topic_hint: <<topic_hint>>
  - language: <<language>>
  - include_ethics: <<include_ethics>>
  - max_queries: <<max_queries>>
  - seed_anchors: <<seed_anchors_info>>
  - custom_categories: <<custom_categories_info>>
  - exclude_terms: <<exclude_terms_info>>
  - anchor_terms: <<anchor_guidance>>
- Provided paper metadata (copy titles/abstracts exactly; keep ordering):
<<paper_metadata_block>>
- OutputFormat (strict JSON):
{
  "topic": "<<topic_or_inferred>>",
  "anchor_terms": ["…", "…"],
  "search_terms": {
    "<category>": ["…"],
    "<category>": ["…"]
  },
  "papers": [
    {
      "id": "<stable short id>",
      "source_id": "arXiv:<identifier>",
      "title": "<copy title exactly>",
      "abstract": "<copy abstract exactly>",
      "year": "<YYYY or unknown>",
      "source_url": "<https://arxiv.org/abs/...>",
      "detected_keywords": [
        {
          "term": "…",
          "category": "<category label>",
          "evidence": {"quote": "…", "page": "n/a|<number>"},
          "confidence": 0.0
        }
      ]
    }
  ]
}
- Example (illustrative only; copy structure, not content):
```json
{
  "topic": "Challenges of Abstractive Dialogue Summarization",
  "anchor_terms": [
    "dialogue summarization",
    "dialog summarization",
    "conversation summarization"
  ],
  "search_terms": {
    "core_concepts": ["technique", "dataset", "evaluation"],
    "technical_terms": ["language model", "semantic representation", "information extraction"],
    "advanced_concepts": ["topic segmentation", "personalization"],
    "implementation": ["automatic", "training"],
    "subdomains": ["meeting summarization", "customer service summarization"],
    "ethical": ["privacy", "cost"]
  },
  "papers": [
    {
      "id": "cads_taxonomy_2025",
      "source_id": "arXiv:2501.01234",
      "title": "CADS: A Systematic Review of Abstractive Dialogue Summarization",
      "abstract": "We categorize 133 dialogue summarization papers published between 2019–2024 across six challenge areas (language, structure, comprehension, speaker, salience, factuality) and map them to techniques, datasets, and metrics.",
      "year": "2025",
      "source_url": "https://arxiv.org/abs/2501.01234",
      "detected_keywords": [
        {
          "term": "language challenge",
          "category": "core_concepts",
          "evidence": {"quote": "We outline the language challenge covering informal dialogue and colloquialisms.", "page": "n/a"},
          "confidence": 0.6
        },
        {
          "term": "meeting summarization",
          "category": "subdomains",
          "evidence": {"quote": "The taxonomy highlights datasets for meeting summarization such as AMI and ICSI.", "page": "n/a"},
          "confidence": 0.5
        }
      ]
    }
  ]
}
```
- Notes:
  - Keep "papers" in the same order as the metadata block.
  - Do not emit additional top-level keys beyond the schema above.
```

### 5.5 resources/LLM/prompts/keyword_extractor/aggregate_terms.md

使用情況：API: 使用（keywords aggregation） / Codex CLI: 未觸發（無 PDF）

```text
- Role: Search Term Aggregator
- Background: You are given JSON outputs produced independently for multiple survey PDFs. Each JSON contains candidate terms with evidence. Your task is to merge them into a single consolidated JSON that matches the generator schema and retains canonical metadata.
- Topic focus: <<topic_hint>>
- Anchor policy: <<anchor_policy>>
- Constraints:
  - Preserve evidence by keeping the strongest quote per term and counting support across papers.
  - Merge spelling variants and morphological variants so each category list remains deduplicated.
  - Ensure resulting search terms stay concise (1–3 word noun phrases; no underscores or sentence-length entries).
  - Copy titles, abstracts, years, and URLs exactly as provided in the block below; do not paraphrase.
  - Ensure "papers" remain aligned with the provided ordering.
  - Output strictly valid JSON only.
- Workflow:
  1) Load all input JSONs.
  2) Normalize: lowercase, lemmatize, strip punctuation; map variants to a canonical form.
  3) Merge: aggregate support evidence (limit to 2 quotes per term) and keep the highest confidence noted in the inputs.
  4) Rebuild anchor_terms (top 2–4 by global weight) and ensure search_terms cover the category set provided by the inputs; <<category_coverage_note>>.
  <<additional_category_note>>
  5) Keep `papers` synchronized with the metadata block; retain detected keyword evidence and avoid introducing new top-level fields.
- Provided metadata (copy verbatim; preserve ordering):
<<paper_metadata_block>>
- Output: Same schema as generate_search_terms.md.

Input placeholder:
<<partial_json_list>>
```


## 6. 失敗原因與差異分析

### 6.1 為何 Codex CLI workspace 沒有 seed PDF

- `seed_selection.json` 顯示 `records_total` 為 1，且唯一候選為同名論文（Discrete Audio Tokens: More Than a Survey!）。
- cutoff 強制排除同名/相似標題與 cutoff_date 之後的論文，導致 `records_after_filter` 變成 0。
- `seed_rewrite.json` 雖嘗試 10 次，但重寫片語集中在「discrete audio tokens / tokenization / acoustic tokens」等同義表達，外部查核顯示對應 query 仍只命中同名論文。

### 6.2 API workspace 為何成功取得 seed

- API workspace 的 rewrite 產生 `discrete speech tokens` 與 `audio tokenization discrete tokens`，外部查核顯示該 query 命中 4 筆。
- 在同名 cutoff 之後仍保留 1 篇早於 cutoff_date 的 survey（arXiv:2502.06490）。
- `seed_selection.json` 顯示 `records_total=4`、`records_after_title_filter=2`、`records_after_filter=1`，因此能下載 1 份 PDF。

### 6.3 關於「random seed 導致未成功 retrieve」的說明

使用者說明：`workspaces/discrete_audio_tokens_more_than_a_survey` 未成功 retrieve 是因為 random seed。
檔案與程式碼事實：
- 目前 artifacts 中沒有記錄 random seed 或 RNG 狀態的欄位。
- `src/pipelines/topic_pipeline.py` 在 seed 搜尋與 selection 流程中未使用隨機抽樣。
結論：無法確定 random seed 是否為導因；現有證據不足以支持此說法。

### 6.4 數據一致性觀察（路徑對齊）

以下檔案內部引用的路徑指向非 -api workspace，需留意：
- `workspaces/discrete_audio_tokens_more_than_a_survey-api/seed/downloads/download_results.json` 的 `pdf_path` 指向 `workspaces/discrete_audio_tokens_more_than_a_survey/seed/downloads/...`。
- `workspaces/discrete_audio_tokens_more_than_a_survey-api/keywords/keywords.json` 的 `pdf_path` 指向非 -api workspace。
- `workspaces/discrete_audio_tokens_more_than_a_survey-api/snowball_rounds/round_01/round_meta.json` 等 `seed_review` 路徑指向非 -api workspace。
這些為路徑記錄不一致，屬於結果紀錄層面的問題（並非檔案缺失）；需要時可再做後續修正或對齊。


## 7. 補充：此報告涵蓋的限制

- 本報告不修改任何 pipeline 行為。
- 對於超大型產物（review/snowball 等），僅提供統計摘要與校驗資訊，完整內容仍以原始檔案為準。
- 若需將大型檔案全文內嵌於報告，可另外指定要納入的檔案清單。
