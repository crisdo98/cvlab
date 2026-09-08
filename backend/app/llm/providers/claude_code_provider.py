"""Claude Code provider.

Routes CVLab's LLM calls through the Claude Agent SDK — Claude Code packaged as
a library — rather than the Anthropic HTTP API. There is no API key: it
authenticates with a Claude Code OAuth token, minted by `claude setup-token`.

The token is read from two places, in order:

1. `config.api_key`, the token saved in AI settings (encrypted at rest, like
   every other provider credential).
2. `CLAUDE_CODE_OAUTH_TOKEN` in the server's environment, when nothing is
   saved. This keeps an existing .env deployment working untouched.

A login performed on someone's own machine is *not* one of these. Claude Code
stores that in the OS keychain, which a server — in a container especially —
cannot read, so a token has to be handed over explicitly.

Two things about this provider are deliberate and worth keeping:

1. **Every tool is switched off.** The Agent SDK ships the full Claude Code
   harness — file read/write, bash, web fetch, subagents. CVLab only ever wants
   text back, so the agent is given no tools and a single turn. It cannot touch
   the filesystem, run commands, or reach the network on its own.

2. **Local settings are not loaded.** `setting_sources=None` keeps the user's
   CLAUDE.md, project settings and installed plugins out of these calls. A CV
   grammar check should not change behaviour because of what happens to be in
   the working directory.

The SDK ships a self-contained `claude` binary, so nothing else needs
installing — no Node, no global npm package.
"""

import json
import logging
import re
from typing import Any, Dict, Optional

from .base import BaseLLMProvider, LLMConfig, LLMResponse, StructuredLLMResponse

logger = logging.getLogger(__name__)

# Fenced JSON, with or without a language tag.
_FENCE = re.compile(r"```(?:json)?\s*(.*?)```", re.DOTALL)


class ClaudeCodeProvider(BaseLLMProvider):
    """LLM provider backed by the Claude Agent SDK."""

    #: Model aliases Claude Code accepts, plus explicit ids.
    VALID_MODEL_HINTS = ("opus", "sonnet", "haiku", "claude-")

    def __init__(self, config: LLMConfig):
        super().__init__(config)
        #: Why the last test_connection() failed, if it did. Read by the API so
        #: it can report the real cause rather than assuming a credentials
        #: problem.
        self.last_error: Optional[str] = None
        self._validate_config()

    # ------------------------------------------------------------------ setup

    def validate_config(self) -> bool:
        """Validate configuration.

        Unlike the API-backed providers this needs no key: credentials come
        from Claude Code itself.
        """
        if not self.config.model:
            raise ValueError("Claude Code provider requires a model name")

        model = self.config.model.lower()
        if not any(hint in model for hint in self.VALID_MODEL_HINTS):
            raise ValueError(
                f"'{self.config.model}' does not look like a Claude model. "
                "Use an alias such as 'opus' or 'sonnet', or a full model id."
            )
        return True

    def _options(self, system_prompt: Optional[str], stderr_sink=None):
        """Build agent options with the harness locked down to text only.

        `stderr_sink` receives the CLI's stderr lines. The SDK reports a failed
        subprocess as "Command failed with exit code N / Check stderr output for
        details", so without this the actual reason — an expired token, a usage
        limit, an unknown model — never reaches the caller.
        """
        from claude_agent_sdk import ClaudeAgentOptions

        # The SDK merges this over os.environ for the CLI subprocess, so a saved
        # token wins and an unset one leaves any CLAUDE_CODE_OAUTH_TOKEN in the
        # environment in place. Passing it per call avoids mutating global
        # process state, which would race across concurrent requests.
        env = {"CLAUDE_CODE_OAUTH_TOKEN": self.config.api_key} if self.config.api_key else {}

        return ClaudeAgentOptions(
            env=env,
            stderr=stderr_sink,
            model=self.config.model,
            system_prompt=system_prompt,
            # One turn, no tools: this is a completion, not an agent session.
            max_turns=1,
            allowed_tools=[],
            disallowed_tools=[
                "Bash", "Read", "Write", "Edit", "Glob", "Grep",
                "WebFetch", "WebSearch", "Task", "NotebookEdit",
            ],
            # No permission mode is set on purpose. "bypassPermissions" maps to
            # --dangerously-skip-permissions, which the CLI refuses to run as
            # root — and the container runs as root, so it failed instantly with
            # a message the SDK swallowed. Nothing needs bypassing anyway: this
            # call grants no tools at all (see allowed_tools/disallowed_tools
            # above), so there is no permission for a human to be asked about.
            # Ignore CLAUDE.md, project settings and plugins.
            setting_sources=None,
        )

    # -------------------------------------------------------------- execution

    async def _run(self, prompt: str, system_prompt: Optional[str]) -> tuple[str, Optional[int]]:
        """Run one query and return (text, tokens_used)."""
        from claude_agent_sdk import (
            AssistantMessage,
            CLINotFoundError,
            ClaudeSDKError,
            ResultMessage,
            TextBlock,
            query,
        )

        chunks: list[str] = []
        tokens: Optional[int] = None
        stderr_lines: list[str] = []

        try:
            options = self._options(system_prompt, stderr_sink=stderr_lines.append)
            async for message in query(prompt=prompt, options=options):
                if isinstance(message, AssistantMessage):
                    for block in message.content:
                        if isinstance(block, TextBlock):
                            chunks.append(block.text)
                elif isinstance(message, ResultMessage):
                    usage = getattr(message, "usage", None)
                    if isinstance(usage, dict):
                        tokens = (usage.get("input_tokens") or 0) + (
                            usage.get("output_tokens") or 0
                        ) or None
        except CLINotFoundError as exc:
            raise RuntimeError(
                "The Claude Code CLI could not be found. It ships with the "
                "claude-agent-sdk package — reinstall it if this persists."
            ) from exc
        except ClaudeSDKError as exc:
            # The CLI puts the human-readable reason on stderr ("You've hit your
            # session limit", "Invalid API key", ...). Lead with that when we
            # have it; the SDK's own text says nothing useful on its own.
            detail = self._summarise_stderr(stderr_lines)
            if detail:
                raise RuntimeError(f"Claude Code call failed: {detail}") from exc
            raise RuntimeError(f"Claude Code call failed: {exc}") from exc

        text = "".join(chunks).strip()
        if not text:
            raise RuntimeError("Claude Code returned no content")
        return text, tokens

    async def generate_completion(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None,
        **kwargs: Any,
    ) -> LLMResponse:
        """Generate text.

        `temperature` and `max_tokens` are accepted for interface compatibility
        but not forwarded: Claude Code manages sampling and output length
        itself, and silently ignoring them here is better than pretending they
        were applied.
        """
        text, tokens = await self._run(prompt, system_prompt)
        return LLMResponse(
            content=text,
            model=self.config.model,
            provider="claude_code",
            tokens_used=tokens,
            finish_reason="end_turn",
        )

    async def generate_structured_output(
        self,
        prompt: str,
        schema: Dict[str, Any],
        system_prompt: Optional[str] = None,
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None,
        **kwargs: Any,
    ) -> StructuredLLMResponse:
        """Generate JSON matching `schema`.

        The Agent SDK has no equivalent of the API's structured-output
        constraint, so the schema goes in the prompt and the reply is parsed.
        """
        instruction = (
            "Reply with a single JSON object and nothing else — no prose, no "
            "explanation, no code fence. It must match this JSON schema:\n"
            f"{json.dumps(schema, indent=2)}"
        )
        combined_system = f"{system_prompt}\n\n{instruction}" if system_prompt else instruction

        text, tokens = await self._run(prompt, combined_system)
        return StructuredLLMResponse(
            data=self._parse_json(text),
            model=self.config.model,
            provider="claude_code",
            tokens_used=tokens,
        )

    @staticmethod
    def _parse_json(text: str) -> Dict[str, Any]:
        """Pull a JSON object out of a reply.

        Asked for bare JSON the model usually obliges, but a code fence or a
        sentence of preamble is common enough to be worth handling rather than
        failing the whole request over.
        """
        candidates = [text]

        fenced = _FENCE.search(text)
        if fenced:
            candidates.insert(0, fenced.group(1))

        # Last resort: the outermost braces.
        start, end = text.find("{"), text.rfind("}")
        if start != -1 and end > start:
            candidates.append(text[start : end + 1])

        for candidate in candidates:
            try:
                parsed = json.loads(candidate.strip())
            except (json.JSONDecodeError, ValueError):
                continue
            if isinstance(parsed, dict):
                return parsed

        raise ValueError(f"Claude Code did not return JSON. Got: {text[:200]}")

    # ------------------------------------------------------------- diagnostics

    @staticmethod
    def _summarise_stderr(lines: list[str]) -> str:
        """Condense captured stderr into one line worth showing a user."""
        text = " ".join(line.strip() for line in lines if line.strip())
        if not text:
            return ""
        # The CLI is chatty on startup; keep this bounded.
        return text[:400]

    async def test_connection(self) -> bool:
        """Check that Claude Code is installed and authenticated.

        On failure the reason is kept on `last_error` so callers can report what
        actually went wrong instead of guessing at authentication.
        """
        self.last_error = None
        try:
            text, _ = await self._run("Reply with exactly: ok", None)
            if "ok" in text.lower():
                return True
            self.last_error = "Claude Code replied, but not with the expected text."
            return False
        except Exception as exc:
            logger.warning("Claude Code connection test failed: %s", exc)
            self.last_error = str(exc)
            return False
