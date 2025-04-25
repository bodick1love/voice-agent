import os
import logging
from typing import Union, AsyncGenerator

import aiohttp
from dotenv import load_dotenv
from livekit.agents import (
    AutoSubscribe,
    JobContext,
    JobProcess,
    WorkerOptions,
    cli,
    llm,
    metrics,
)
from livekit.agents.pipeline import VoicePipelineAgent
from livekit.plugins import (
    cartesia,
    openai,
    deepgram,
    silero,
)

# Setup environment and logging
load_dotenv(dotenv_path=".env.local")
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("voice-agent")

# Constants & Config
VALIDATION_SERVER_URL = os.getenv("VALIDATION_SERVER_URL", "http://localhost:5000/validate")
CHARS_PER_SECOND = float(os.getenv("CHARS_PER_SECOND", "12.5"))


def prewarm(proc: JobProcess):
    proc.userdata["vad"] = silero.VAD.load()


async def before_tts_cb(
    agent: VoicePipelineAgent, text_input: Union[str, AsyncGenerator[str, None]]
) -> str:
    logger.info("Processing text before TTS")

    # Handle both string and async generator cases
    full_text = ""
    if hasattr(text_input, "__aiter__"):
        try:
            async for text_chunk in text_input:
                full_text += text_chunk
        except Exception as e:
            logger.error(f"Error processing async generator: {e}")
            return text_input
    else:
        full_text = text_input

    logger.info(f"Full text collected: {full_text[:100]}...")

    # Estimate audio length
    estimated_length = len(full_text) / CHARS_PER_SECOND
    logger.info(f"Estimated audio length: {estimated_length:.2f} seconds")

    # Send to validation server
    try:
        logger.info(f"Sending request to validation server: {VALIDATION_SERVER_URL}")
        logger.info(
            f"Request payload: text length={len(full_text)}, estimated_length={estimated_length:.2f}"
        )

        async with aiohttp.ClientSession() as session:
            async with session.post(
                VALIDATION_SERVER_URL,
                json={"text": full_text, "estimated_length": estimated_length},
                headers={"Content-Type": "application/json"},
                timeout=aiohttp.ClientTimeout(total=5),
            ) as response:
                logger.info(f"Validation server response status: {response.status}")

                if response.status == 200:
                    result = await response.json()
                    logger.info(f"Validation server response: {result}")

                    if "modified_text" in result:
                        logger.info("Using server-modified text")
                        return result["modified_text"]
                    else:
                        logger.info("Server approved text without changes")
                        return full_text
                else:
                    response_text = await response.text()
                    logger.error(f"Validation server error: {response.status}")
                    logger.error(f"Response body: {response_text[:500]}...")

    except aiohttp.ClientConnectorError as e:
        logger.error(f"Connection error to validation server: {e}")
        logger.error(f"URL attempted: {VALIDATION_SERVER_URL}")

    except aiohttp.ClientResponseError as e:
        logger.error(f"Response error: {e}")

    except aiohttp.ClientError as e:
        logger.error(f"Client error: {e}")

    except Exception as e:
        logger.error(f"Unexpected error communicating with validation server: {e}")

    return full_text


async def entrypoint(ctx: JobContext):
    initial_ctx = llm.ChatContext().append(
        role="system",
        text=(
            "You are a voice assistant created by LiveKit. Your interface with users will be voice. "
            "You should use short and concise responses, and avoid usage of unpronounceable punctuation. "
            "You were created as a demo to showcase the capabilities of LiveKit's agents framework."
        ),
    )

    logger.info(f"Connecting to room {ctx.room.name}")
    await ctx.connect(auto_subscribe=AutoSubscribe.AUDIO_ONLY)

    participant = await ctx.wait_for_participant()
    logger.info(f"Starting voice assistant for participant {participant.identity}")

    agent = VoicePipelineAgent(
        vad=ctx.proc.userdata["vad"],
        stt=deepgram.STT(),
        llm=openai.LLM(model="gpt-4o-mini"),
        tts=cartesia.TTS(),
        turn_detector=None,
        min_endpointing_delay=1.0,
        max_endpointing_delay=5.0,
        chat_ctx=initial_ctx,
        before_tts_cb=before_tts_cb,
    )

    usage_collector = metrics.UsageCollector()

    @agent.on("metrics_collected")
    def on_metrics_collected(agent_metrics: metrics.AgentMetrics):
        metrics.log_metrics(agent_metrics)
        usage_collector.collect(agent_metrics)

    agent.start(ctx.room, participant)

    await agent.say("Hey, how can I help you today?", allow_interruptions=True)


if __name__ == "__main__":
    cli.run_app(
        WorkerOptions(
            entrypoint_fnc=entrypoint,
            prewarm_fnc=prewarm,
        ),
    )
