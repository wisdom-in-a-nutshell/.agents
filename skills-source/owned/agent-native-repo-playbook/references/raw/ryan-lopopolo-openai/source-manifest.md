# Harness Engineering Source Manifest

Raw source index for future updates to `agent-native-repo-playbook`.

Use this file for provenance and targeted lookup only. Do not load every raw
transcript by default. Prefer `rg` over the raw transcript files, then read only
the relevant sections before creating a distilled reference.

## Rules

- Keep this as source inventory, not synthesis.
- Keep distilled operating guidance in a separate reference file.
- Do not copy full article bodies into this skill by default; store URLs and
  synthesize our own notes later.
- Treat transcript speaker labels as useful but not authoritative. Verify
  labels before quoting or turning a claim into guidance.

## Source Scores

Score meaning: relevance to improving the skill for solo, agent-native repository
audits where humans set intent and agents write code.

| Score | Meaning |
| --- | --- |
| 5 | Core source for this skill. Mine deeply. |
| 4 | Strong supporting source. Mine for specific patterns. |
| 3 | Useful context. Use selectively. |
| 2 | Background only. Do not prioritize. |
| 1 | Low relevance. Keep only for provenance. |

## Sources

| ID | Score | Type | Title | Source | Local Raw File | Notes |
| --- | ---: | --- | --- | --- | --- | --- |
| `openai-harness-engineering` | 5 | Article | Harness engineering | https://openai.com/index/harness-engineering/ | `openai-harness-engineering-article-text.md` | Primary article. Text-reference version only; later synthesize into our own compact patterns. |
| `youtube-am_oeAoUhew` | 5 | Video transcript | Harness Engineering: How to Build Software When Humans Steer, Agents Execute - Ryan Lopopolo, OpenAI | https://www.youtube.com/watch?v=am_oeAoUhew | `youtube-harness-engineering-how-to-build-software-when-humans-steer-agents-execute-ryan-lopopolo-openai-transcript.txt` | AI Engineer talk and Q&A. Highest signal for repo legibility, guardrails, review agents, and validation loops. |
| `youtube-CeOXx-XTYek` | 5 | Video transcript | Extreme Harness Engineering: 1M LOC, 1B toks/day, 0% human code or review - Ryan Lopopolo, OpenAI | https://www.youtube.com/watch?v=CeOXx-XTYek | `youtube-extreme-harness-engineering-1m-loc-1b-toks-day-0-percent-human-code-or-review-ryan-lopopolo-openai-transcript.txt` | Latent Space interview. Highest signal for skill design, repository scaffolding, feedback loops, and orchestration. |
| `youtube-U2O14Jd3MBU` | 4 | Video transcript | Paul McMillan & Ryan Lopopolo - Code Is Free: Securing Software \| [un]prompted 2026 | https://www.youtube.com/watch?v=U2O14Jd3MBU | `youtube-paul-mcmillan-and-ryan-lopopolo-code-is-free-securing-software-unprompted-2026-transcript.txt` | Security-focused supporting source. Mine for threat-model docs, security guardrails, and CI-based agent review patterns. |
| `youtube-8suwvrF0Lv0` | 4 | Video transcript | I got an inside look at how OpenAI PMs ship code | https://www.youtube.com/watch?v=8suwvrF0Lv0 | `youtube-i-got-an-inside-look-at-how-openai-pms-ship-code-transcript.txt` | PM/product collaboration source. Mine for cross-functional repo legibility, app-driving skills, and validation proof-of-work. |

## Transcript Artifacts

All video transcripts were generated through WIN's artifact-backed
`/media/transcribe/artifacts` endpoint with provider `local_transcription`.
Speaker identification was requested for each transcript.

| ID | Job ID | Transcript URL | Words URL | Sentences URL | Speaker Mapping |
| --- | --- | --- | --- | --- | --- |
| `youtube-am_oeAoUhew` | `TRANSCRIPTION_ARTIFACTS_16274b424c3c8e80` | https://storage.aipodcast.ing/cache/transcripts/media/am_oeAoUhew/local_transcription/diarized/transcript.txt | https://storage.aipodcast.ing/cache/transcripts/media/am_oeAoUhew/local_transcription/diarized/words.json | https://storage.aipodcast.ing/cache/transcripts/media/am_oeAoUhew/local_transcription/diarized/sentences.json | `speaker_0=Unknown`, `speaker_1=Ryan Lopopolo`, `speaker_2=Vibhu Sapra` |
| `youtube-CeOXx-XTYek` | `TRANSCRIPTION_ARTIFACTS_6020b9793dcd8162` | https://storage.aipodcast.ing/cache/transcripts/media/CeOXx-XTYek/local_transcription/diarized/transcript.txt | https://storage.aipodcast.ing/cache/transcripts/media/CeOXx-XTYek/local_transcription/diarized/words.json | https://storage.aipodcast.ing/cache/transcripts/media/CeOXx-XTYek/local_transcription/diarized/sentences.json | `speaker_0=Ryan Lopopolo`, `speaker_1=Shawn Wang`, `speaker_2=Alessio Fanelli` |
| `youtube-U2O14Jd3MBU` | `TRANSCRIPTION_ARTIFACTS_e4b6d41e9a074f26` | https://storage.aipodcast.ing/cache/transcripts/media/U2O14Jd3MBU/local_transcription/diarized/transcript.txt | https://storage.aipodcast.ing/cache/transcripts/media/U2O14Jd3MBU/local_transcription/diarized/words.json | https://storage.aipodcast.ing/cache/transcripts/media/U2O14Jd3MBU/local_transcription/diarized/sentences.json | `speaker_0=Paul McMillan`, `speaker_1=Ryan Lopopolo`, `speaker_2=Unknown`, `speaker_3=Unknown`, `speaker_4=Unknown` |
| `youtube-8suwvrF0Lv0` | `TRANSCRIPTION_ARTIFACTS_e17a8af19f4c3f6a` | https://storage.aipodcast.ing/cache/transcripts/media/8suwvrF0Lv0/local_transcription/diarized/transcript.txt | https://storage.aipodcast.ing/cache/transcripts/media/8suwvrF0Lv0/local_transcription/diarized/words.json | https://storage.aipodcast.ing/cache/transcripts/media/8suwvrF0Lv0/local_transcription/diarized/sentences.json | `speaker_0=Aakash Gupta`, `speaker_1=Ryan Lopopolo` |

## Local Generation Cache

The transcription JSON envelopes and text files were also cached locally during
source intake:

- `/Users/dobby/.agents/tmp/transcripts/am_oeAoUhew.json`
- `/Users/dobby/.agents/tmp/transcripts/am_oeAoUhew.txt`
- `/Users/dobby/.agents/tmp/transcripts/CeOXx-XTYek.json`
- `/Users/dobby/.agents/tmp/transcripts/CeOXx-XTYek.txt`
- `/Users/dobby/.agents/tmp/transcripts/U2O14Jd3MBU.json`
- `/Users/dobby/.agents/tmp/transcripts/U2O14Jd3MBU.txt`
- `/Users/dobby/.agents/tmp/transcripts/8suwvrF0Lv0.json`
- `/Users/dobby/.agents/tmp/transcripts/8suwvrF0Lv0.txt`

These cache files are disposable; the durable raw transcript copies live next to
this manifest.

## Suggested Search Terms

Use these with `rg -n -i` over
`references/raw/ryan-lopopolo-openai/*.txt` and
`references/raw/ryan-lopopolo-openai/openai-harness-engineering-article-text.md`:

- `slop|guardrail|lint|test|review agent|CI|validation`
- `AGENTS.md|skills|context|documentation|repo|repository`
- `human time|attention|tokens|parallel|continue|full job`
- `threat model|security|dependency|supply chain|SARIF`
- `PM|designer|product|QA|smoke test|user journey`
