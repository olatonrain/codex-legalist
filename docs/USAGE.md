# Usage Guide

## Starting a Trial

### 1. Via the Web Interface

After running `./deploy.sh`, open [http://localhost:8000](http://localhost:8000). The interface provides:

- Case description input with jurisdiction and case type selectors
- A "Start Trial" button that runs the full agent society
- Live transcript with colour-coded agent messages
- Evidence board and jury monitor
- Verdict dashboard with win-probability gauge

### 2. Via the API

## API Reference

| Method | Endpoint                    | Description                                           |
| ------ | --------------------------- | ----------------------------------------------------- |
| `GET`  | `/api/health`               | Health check                                          |
| `GET`  | `/api/jurisdictions`        | List supported countries and legal parameters         |
| `POST` | `/api/demo`                 | Load a demo case, returns opening sequence            |
| `POST` | `/api/trial/start`          | Start a live LLM trial, returns opening sequence      |
| `POST` | `/api/trial/step`           | Run one phase step, returns new transcript entries    |
| `POST` | `/api/trial/magistrate`     | Run magistrate clarifying-question node               |
| `POST` | `/api/trial/human_question` | Agent submits a question to the human                 |
| `POST` | `/api/trial/human_answer`   | Human submits an answer to an agent                   |
| `POST` | `/api/upload`               | Parse an uploaded case file (PDF/DOCX/TXT, max 10 MB) |
| `POST` | `/api/upload_audio`         | Transcribe an uploaded audio file (max 10 MB)         |
| `POST` | `/api/benchmark/run`        | Run benchmark comparison                              |

---

## Demo Cases

Three built-in demo cases are available. Use the `/api/demo` endpoint with the `demo_key` field:

### State v. Marcus Webb — Grand Theft Auto (`theft`)

```json
{
  "demo_key": "theft",
  "country": "United States",
  "case_type": "Criminal",
  "shadow_juries": 20
}
```

A criminal case involving a stolen Tesla. The prosecution relies on CCTV footage, the defence presents an alibi witness. Tests circumstantial evidence and witness credibility.

### Nexus Corp. v. Aether Labs — NDA Breach (`contract`)

```json
{
  "demo_key": "contract",
  "country": "United States",
  "case_type": "Civil",
  "shadow_juries": 20
}
```

A civil case alleging breach of a non-disclosure agreement. Features competing expert witnesses (materials scientists), documentary evidence, and a damages phase.

### State v. Emilia Vance — Double Homicide by Arson (`vance`)

```json
{
  "demo_key": "vance",
  "country": "United States",
  "case_type": "Criminal",
  "shadow_juries": 20
}
```

A criminal arson and homicide case. Tests multiple evidence types: accelerant forensics, cell tower data, eyewitness testimony with impeachment (the eyewitness is a convicted perjurer), and a defence expert proposing an alternative electrical-fire theory.

---

## Uploading Your Own Case

### File Upload (`POST /api/upload`)

Accepts **PDF**, **DOCX**, and **TXT** files up to 10 MB. The extracted text becomes the case description for a new trial.

```bash
curl -X POST http://localhost:8000/api/upload \
  -F "file=@sample_cases/theft.txt"
```

Response:

```json
{
  "filename": "theft.txt",
  "text": "The defendant, Marcus Webb, is charged with...",
  "char_count": 342
}
```

The returned `text` field should then be passed to `/api/trial/start` or `/api/trial/magistrate` as the `case_text`.

Ready-made sample files are available in the [`sample_cases/`](../sample_cases/) directory.

### Voice Upload (`POST /api/upload_audio`)

Accepts audio files up to 10 MB. The file is transcribed using Qwen audio models and the transcript text is returned.

```bash
curl -X POST http://localhost:8000/api/upload_audio \
  -F "file=@case_facts.wav"
```

---

## Magistrate Mode

Before starting a full trial, you can run the Magistrate agent to analyse the case and generate clarifying questions:

```bash
curl -X POST http://localhost:8000/api/trial/magistrate \
  -H "Content-Type: application/json" \
  -d '{
    "case_text": "The defendant is accused of...",
    "country": "United Kingdom",
    "case_type": "Criminal"
  }'
```

The Magistrate will:

- Ask up to 5 strategic clarifying questions about gaps in the facts
- Identify missing evidence
- Name potential missing witnesses
- Prepare a witness queue for examination

---

## Jurisdiction Selection

Sixteen jurisdictions are supported. Each adapts the trial's procedure, evidence rules, burden of proof, and form of address.

| Country                      | System     | Procedure     | Jury                 |
| ---------------------------- | ---------- | ------------- | -------------------- |
| United Kingdom               | Common Law | Adversarial   | Yes                  |
| United States                | Common Law | Adversarial   | Yes                  |
| Nigeria                      | Common Law | Adversarial   | No (bench trial)     |
| Canada                       | Common Law | Adversarial   | Yes                  |
| Australia                    | Common Law | Adversarial   | Yes                  |
| India                        | Common Law | Adversarial   | No                   |
| Kenya                        | Common Law | Adversarial   | No                   |
| Ireland                      | Common Law | Adversarial   | Yes                  |
| France                       | Civil Law  | Inquisitorial | No                   |
| Germany                      | Civil Law  | Inquisitorial | No                   |
| Japan                        | Civil Law  | Inquisitorial | No (lay judges)      |
| Brazil                       | Civil Law  | Inquisitorial | No                   |
| South Africa                 | Mixed      | Adversarial   | No                   |
| International Criminal Court | Custom     | Adversarial   | No (panel of judges) |

---

## Verdicts & Shadow Juries

After the trial concludes, the API returns a `verdict_data` object:

```json
{
  "verdict": "NOT GUILTY",
  "probability": 0.32,
  "sensitivity": "2 of 20 shadow juries found the evidence met the burden of proof. The defence successfully raised doubt.",
  "juries": 20
}
```

- **verdict** — Guilty / Not Guilty (criminal), Liable / Not Liable (civil)
- **probability** — Fraction of shadow juries that found the burden of proof met (0.0–1.0)
- **sensitivity** — Narrative summary of shadow jury consensus
- **juries** — Number of shadow juries that deliberated
- **sentence** — (Civil cases only) Damages awarded with rationale

The shadow jury count is configurable (5-50). Higher counts produce more stable probabilities but take longer.
