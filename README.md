# 🧠 LiveKit Voice Agent

This enhancement integrates a **text validation service** into the [voice-pipeline-agent-python](https://github.com/livekit-examples/voice-pipeline-agent-python) project to ensure that input text passed to the TTS engine does not exceed the recommended length. The validation happens through a dedicated Flask microservice and supports dynamic input types including async generators.

## Workflow Summary

I started by cloning the `livekit-pipeline-voice-agent` repository. After setup, I noticed some dependencies were missing from the `requirements.txt`, so I manually inspected the codebase and installed the required packages.

Once the environment was stable, I connected all necessary APIs (OpenAI, Deepgram, Cartesia and other) using secure keys stored in `.env.local`.

To ensure the input text doesn't produce audio over 60 seconds, I implemented a `before_tts_cb()` function that:
- Accepts both `str` and `AsyncGenerator[str, None]` as input types,
- Calculates estimated speech duration,
- Sends the data to an external Flask validation server,
- Optionally trims the text if too long.

The Flask server exposes a single `/validate` endpoint. It receives a JSON payload (`text`, `estimated_length`) and returns:
- A flag indicating whether the original text is acceptable,
- If not, a trimmed version from the **middle of the text**, while trying to respect sentence boundaries using punctuation.

I exposed the server via **ngrok**, making it publicly accessible for the voice agent. I also extracted all magic numbers and configuration values into environment variables like so:

```env
FLASK_PORT=5000
VALIDATION_SERVER_URL=https://your-ngrok-url.ngrok.io/validate 
CHARS_PER_SECOND=12.5 
MAX_AUDIO_LENGTH_SECONDS=60
```


- 🧪 Tuned validation logic and Flask server behavior based on logs and edge cases (e.g., early/late punctuation, async text input).

---

## ⚠️ Challenges Encountered

| Challenge | Solution |
|----------|----------|
| ❌ Missing dependencies after cloning | Manually resolved and updated environment |
| ❌ Inconsistent text input types (`str` vs `AsyncGenerator`) | Added detection and async handling |
| ❌ Sentence-aware text trimming | Implemented naive punctuation-based trimming |
| ❌ Hardcoded values in business logic | Moved to `.env`|

---
## 🚀 Getting Started

### 1. 🔁 Clone the Repository

```bash
git clone https://github.com/bodick1love/voice-agent.git
cd voice-agent
```

### 2. 🧪 Set Up Your Virtual Environment

```bash
python3 -m venv .venv
source .venv/bin/activate  # For Windows: .venv\Scripts\activate
pip install -r requirements.txt
```

### 3. 🧩 Run the Flask Validation Server

```bash
python app.py
```

To expose it publicly using [ngrok](https://ngrok.com):

```bash
ngrok http <YOUR_FLASK_PORT>
```

### 4. 🗣️ Launch the Voice Agent

```bash
python agent.py dev
```

### 5. 🧪 Test the Integration

Open your frontend app and initiate a voice call. The agent should validate the transcribed text before sending it to the TTS engine.

---

👤 **Author:** [Bohdan Yarema](https://github.com/bodick1love)
