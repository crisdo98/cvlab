"""Credential handling for the Claude Code provider.

Claude Code takes an OAuth token rather than an API key, and the token can come
from either AI settings or the server's environment. These cover the precedence
between the two, which is the part that is easy to get subtly wrong.
"""

import os
from unittest.mock import patch

import pytest

from app.llm.providers.base import LLMConfig
from app.llm.providers.claude_code_provider import ClaudeCodeProvider


def _provider(api_key=None):
    return ClaudeCodeProvider(
        LLMConfig(provider="claude_code", model="sonnet", api_key=api_key)
    )


class TestTokenPrecedence:
    def test_saved_token_is_passed_to_the_sdk(self):
        options = _provider(api_key="sk-ant-oat-saved")._options(None)
        assert options.env["CLAUDE_CODE_OAUTH_TOKEN"] == "sk-ant-oat-saved"

    def test_no_saved_token_leaves_the_environment_alone(self):
        """An empty env dict means the SDK inherits CLAUDE_CODE_OAUTH_TOKEN from
        the process, which is how an existing .env deployment keeps working."""
        options = _provider(api_key=None)._options(None)
        assert "CLAUDE_CODE_OAUTH_TOKEN" not in options.env

    def test_blank_token_is_treated_as_unset(self):
        """A cleared field must not override a working environment token with ''."""
        options = _provider(api_key="")._options(None)
        assert "CLAUDE_CODE_OAUTH_TOKEN" not in options.env

    @patch.dict(os.environ, {"CLAUDE_CODE_OAUTH_TOKEN": "sk-ant-oat-from-env"})
    def test_saved_token_wins_over_the_environment(self):
        options = _provider(api_key="sk-ant-oat-saved")._options(None)
        assert options.env["CLAUDE_CODE_OAUTH_TOKEN"] == "sk-ant-oat-saved"


class TestConfigValidation:
    def test_no_token_is_still_a_valid_config(self):
        """Validation must not demand a token: the environment may supply it."""
        assert _provider(api_key=None).validate_config() is True

    def test_model_is_still_required(self):
        with pytest.raises(ValueError, match="model"):
            ClaudeCodeProvider(LLMConfig(provider="claude_code", model=""))

    def test_the_harness_stays_locked_down(self):
        """The token must not arrive alongside a re-enabled toolset."""
        options = _provider(api_key="sk-ant-oat-saved")._options(None)
        assert options.allowed_tools == []
        assert "Bash" in options.disallowed_tools
        assert options.setting_sources is None
