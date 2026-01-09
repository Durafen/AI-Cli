# OpenRouter Free Models

OpenRouter provides free access to several high-quality AI models. This guide covers the best options for ai-cli usage.

## Top Recommended Models

### 1. MiMo-V2-Flash (Xiaomi) — Best Overall

| Spec | Value |
|------|-------|
| Model ID | `xiaomi/mimo-v2-flash:free` |
| Parameters | 309B total / 15B active (MoE) |
| Context | 256K tokens |
| Alias | `mimo` |

**Strengths**: #1 open-source model on SWE-bench Verified. Performance comparable to Claude Sonnet 4.5 at ~3.5% cost. Hybrid-thinking toggle, excellent for coding, reasoning, and agentic workflows.

### 2. Devstral 2 (Mistral) — Best for Coding

| Spec | Value |
|------|-------|
| Model ID | `mistralai/devstral-2512:free` |
| Parameters | 123B dense |
| Context | 256K tokens |
| Alias | `devstral` |

**Strengths**: Purpose-built for agentic coding. Handles multi-file changes, codebase exploration, and architecture-level context. State-of-the-art for software engineering tasks.

### 3. DeepSeek R1 0528 — Best for Reasoning

| Spec | Value |
|------|-------|
| Model ID | `deepseek/deepseek-r1-0528:free` |
| Parameters | 671B total / 37B active (MoE) |
| Context | 164K tokens |
| Alias | `r1` (add to config) |

**Strengths**: Latest official DeepSeek reasoning model. Handles complex multi-step problems, math, and logical deduction. 20% faster than original R1.

### 4. Qwen3 Coder 480B — Best for Large Codebases

| Spec | Value |
|------|-------|
| Model ID | `qwen/qwen3-coder-480b-a35b-07-25:free` |
| Parameters | 480B total / 35B active (MoE) |
| Context | 262K tokens |
| Alias | `qwen-coder` (add to config) |

**Strengths**: Largest context window among coding models (262K). Optimized for repository-scale code generation, understanding large codebases, and maintaining context across many files.

### 5. Llama 3.3 70B — Best General Purpose

| Spec | Value |
|------|-------|
| Model ID | `meta-llama/llama-3.3-70b-instruct:free` |
| Parameters | 70B dense |
| Context | 131K tokens |
| Alias | `llama` (add to config) |

**Strengths**: Meta's most capable open model. Strong multilingual support, reliable for general tasks, good balance of speed and quality. High adoption and battle-tested.

## Other Notable Free Models

| Model | ID | Params | Context | Best For |
|-------|-----|--------|---------|----------|
| DeepSeek R1T2 Chimera | `tngtech/deepseek-r1t2-chimera:free` | 671B/37B | 164K | Balanced speed/reasoning |
| Gemini 2.0 Flash | `google/gemini-2.0-flash-exp:free` | - | 1.05M | Speed, multimodal |
| Gemma 3 27B | `google/gemma-3-27b-it:free` | 27B | 131K | Quick general tasks |
| GPT-OSS 120B | `openai/gpt-oss-120b:free` | 117B/5.1B | 131K | Reasoning, agentic |

## Usage Recommendations

```bash
# Set mimo as default for daily use
ai default mimo

# Use devstral for pure coding tasks
ai devstral "refactor this function to use async/await"

# Use reasoning models for complex problems
ai r1 "explain the time complexity of this algorithm"

# Use qwen-coder for large codebase questions
ai qwen-coder "how does authentication flow work in this repo?"

# Use llama for general queries
ai llama "summarize the key points of this article"
```

## Configuration

Default aliases in `ai.py`:

```python
"mimo": ("openrouter", "xiaomi/mimo-v2-flash:free"),
"devstral": ("openrouter", "mistralai/devstral-2512:free"),
"chimera": ("openrouter", "tngtech/deepseek-r1t2-chimera:free"),
```

Recommended additions for top 5:

```python
"r1": ("openrouter", "deepseek/deepseek-r1-0528:free"),
"qwen-coder": ("openrouter", "qwen/qwen3-coder-480b-a35b-07-25:free"),
"llama": ("openrouter", "meta-llama/llama-3.3-70b-instruct:free"),
```

## Notes

- All free models require `OPENROUTER_API_KEY` in `.env`
- Free models enforce `:free` suffix in model ID
- Run `ai init` to auto-discover available free models
- Model availability may change; check [OpenRouter Free Models](https://openrouter.ai/collections/free-models)

## References

- [OpenRouter Free Models Collection](https://openrouter.ai/collections/free-models)
- [OpenRouter Rankings](https://openrouter.ai/rankings)
- [OpenRouter API Docs](https://openrouter.ai/docs)
