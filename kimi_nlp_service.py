# Copyright 2025 Emcie Co Ltd.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

from __future__ import annotations
from itertools import chain
import time
from openai import (
    APIConnectionError,
    APIResponseValidationError,
    APITimeoutError,
    AsyncClient,
    ConflictError,
    InternalServerError,
    RateLimitError,
)
from typing import Any, Mapping
from typing_extensions import override
import json
import jsonfinder  # type: ignore
import os

from pydantic import ValidationError
import tiktoken

from parlant.adapters.nlp.common import normalize_json_output
from parlant.core.engines.alpha.canned_response_generator import (
    CannedResponseDraftSchema,
    CannedResponseSelectionSchema,
)
from parlant.core.engines.alpha.guideline_matching.generic.journey_node_selection_batch import (
    JourneyNodeSelectionSchema,
)
from parlant.core.engines.alpha.prompt_builder import PromptBuilder
from parlant.core.engines.alpha.tool_calling.single_tool_batch import SingleToolBatchSchema
from parlant.core.loggers import LogLevel, Logger
from parlant.core.nlp.policies import policy, retry
from parlant.core.nlp.tokenization import EstimatingTokenizer
from parlant.core.nlp.service import NLPService
from parlant.core.nlp.embedding import Embedder, EmbeddingResult
from parlant.core.nlp.generation import (
    T,
    SchematicGenerator,
    SchematicGenerationResult,
)
from parlant.core.nlp.generation_info import GenerationInfo, UsageInfo
from parlant.core.nlp.moderation import ModerationCheck, ModerationService, ModerationTag


RATE_LIMIT_ERROR_MESSAGE = (
    "Kimi API rate limit exceeded. Possible reasons:\n"
    "1. Your account may have insufficient API credits.\n"
    "2. You may be using a free-tier account with limited request capacity.\n"
    "3. You might have exceeded the requests-per-minute limit for your account.\n\n"
    "Recommended actions:\n"
    "- Check your Kimi account balance and billing status.\n"
    "- Review your API usage limits in Kimi's dashboard.\n"
)


class KimiEstimatingTokenizer(EstimatingTokenizer):
    def __init__(self, model_name: str) -> None:
        self.model_name = model_name
        try:
            self.encoding = tiktoken.encoding_for_model(model_name)
        except KeyError:
            # Fallback to a default encoding if the model is not recognized
            self.encoding = tiktoken.get_encoding("cl100k_base")

    @override
    async def estimate_token_count(self, prompt: str) -> int:
        tokens = self.encoding.encode(prompt)
        return len(tokens)


class KimiSchematicGenerator(SchematicGenerator[T]):
    supported_kimi_params = ["temperature", "logit_bias", "max_tokens"]
    supported_hints = supported_kimi_params + ["strict"]

    def __init__(
        self,
        model_name: str,
        logger: Logger,
        tokenizer_model_name: str | None = None,
    ) -> None:
        self.model_name = model_name
        self._logger = logger

        self._client = AsyncClient(
            api_key=os.environ["KIMI_API_KEY"],
            base_url=os.environ.get("KIMI_BASE_URL", "https://api.moonshot.cn/v1")
        )

        self._tokenizer = KimiEstimatingTokenizer(
            model_name=tokenizer_model_name or self.model_name
        )

    @property
    @override
    def id(self) -> str:
        return f"kimi/{self.model_name}"

    @property
    @override
    def tokenizer(self) -> KimiEstimatingTokenizer:
        return self._tokenizer

    @policy(
        [
            retry(
                exceptions=(
                    APIConnectionError,
                    APITimeoutError,
                    ConflictError,
                    RateLimitError,
                    APIResponseValidationError,
                ),
            ),
            retry(InternalServerError, max_exceptions=2, wait_times=(1.0, 5.0)),
        ]
    )
    @override
    async def generate(
        self,
        prompt: str | PromptBuilder,
        hints: Mapping[str, Any] = {},
    ) -> SchematicGenerationResult[T]:
        return await self._do_generate(prompt, hints)

    async def _do_generate(
        self,
        prompt: str | PromptBuilder,
        hints: Mapping[str, Any] = {},
    ) -> SchematicGenerationResult[T]:
        if isinstance(prompt, PromptBuilder):
            prompt = prompt.build()

        kimi_api_arguments = {k: v for k, v in hints.items() if k in self.supported_kimi_params}

        if hints.get("strict", False):
            t_start = time.time()
            try:
                response = await self._client.beta.chat.completions.parse(
                    messages=[{"role": "user", "content": prompt}],
                    model=self.model_name,
                    response_format=self.schema,
                    **kimi_api_arguments,
                )
            except RateLimitError:
                self._logger.error(RATE_LIMIT_ERROR_MESSAGE)
                raise

            t_end = time.time()

            if response.usage:
                pass  # Usage logging removed

            parsed_object = response.choices[0].message.parsed
            assert parsed_object

            assert response.usage

            cached_tokens = 0
            if response.usage.prompt_tokens_details:
                cached_tokens = response.usage.prompt_tokens_details.cached_tokens or 0

            return SchematicGenerationResult[T](
                content=parsed_object,
                info=GenerationInfo(
                    schema_name=self.schema.__name__,
                    model=self.id,
                    duration=(t_end - t_start),
                    usage=UsageInfo(
                        input_tokens=response.usage.prompt_tokens,
                        output_tokens=response.usage.completion_tokens,
                        extra={
                            "cached_input_tokens": cached_tokens
                        },
                    ),
                ),
            )

        else:
            try:
                t_start = time.time()
                response = await self._client.chat.completions.create(
                    messages=[{"role": "user", "content": prompt}],
                    model=self.model_name,
                    response_format={"type": "json_object"},
                    **kimi_api_arguments,
                )
                t_end = time.time()
            except RateLimitError:
                self._logger.error(RATE_LIMIT_ERROR_MESSAGE)
                raise

            if response.usage:
                pass  # Usage logging removed

            raw_content = response.choices[0].message.content or "{}"

            try:
                json_content = json.loads(normalize_json_output(raw_content))
            except json.JSONDecodeError:
                self._logger.warning(f"Invalid JSON returned by {self.model_name}:\n{raw_content})")
                json_content = jsonfinder.only_json(raw_content)[2]
                self._logger.warning("Found JSON content within model response; continuing...")

            try:
                # 确保JSON包含所有必需的字段，特别是subtleties_to_be_aware_of
                if hasattr(self.schema, '__fields__') and 'subtleties_to_be_aware_of' in self.schema.__fields__:
                    if 'subtleties_to_be_aware_of' not in json_content:
                        json_content['subtleties_to_be_aware_of'] = ""
                
                content = self.schema.model_validate(json_content)

                assert response.usage

                cached_tokens = 0
                if response.usage.prompt_tokens_details:
                    cached_tokens = response.usage.prompt_tokens_details.cached_tokens or 0

                return SchematicGenerationResult(
                    content=content,
                    info=GenerationInfo(
                        schema_name=self.schema.__name__,
                        model=self.id,
                        duration=(t_end - t_start),
                        usage=UsageInfo(
                            input_tokens=response.usage.prompt_tokens,
                            output_tokens=response.usage.completion_tokens,
                            extra={
                                "cached_input_tokens": cached_tokens
                            },
                        ),
                    ),
                )

            except ValidationError as e:
                self._logger.error(
                    f"Error: {e.json(indent=2)}\nJSON content returned by {self.model_name} does not match expected schema:\n{raw_content}"
                )
                raise


class Kimi_K2_0905_Preview(KimiSchematicGenerator[T]):
    def __init__(self, logger: Logger) -> None:
        super().__init__(model_name="kimi-k2-0905-preview", logger=logger)

    @property
    @override
    def max_tokens(self) -> int:
        return 128 * 1024


class KimiEmbedder(Embedder):
    supported_arguments = ["dimensions"]

    def __init__(self, model_name: str, logger: Logger) -> None:
        self.model_name = model_name

        self._logger = logger
        self._client = AsyncClient(
            api_key=os.environ["KIMI_API_KEY"],
            base_url=os.environ.get("KIMI_BASE_URL", "https://api.moonshot.cn/v1")
        )
        self._tokenizer = KimiEstimatingTokenizer(model_name=self.model_name)

    @property
    @override
    def id(self) -> str:
        return f"kimi/{self.model_name}"

    @property
    @override
    def tokenizer(self) -> KimiEstimatingTokenizer:
        return self._tokenizer

    @policy(
        [
            retry(
                exceptions=(
                    APIConnectionError,
                    APITimeoutError,
                    ConflictError,
                    RateLimitError,
                    APIResponseValidationError,
                ),
            ),
            retry(InternalServerError, max_exceptions=2, wait_times=(1.0, 5.0)),
        ]
    )
    @override
    async def embed(
        self,
        texts: list[str],
        hints: Mapping[str, Any] = {},
    ) -> EmbeddingResult:
        filtered_hints = {k: v for k, v in hints.items() if k in self.supported_arguments}
        try:
            response = await self._client.embeddings.create(
                model=self.model_name,
                input=texts,
                **filtered_hints,
            )
        except RateLimitError:
            self._logger.error(RATE_LIMIT_ERROR_MESSAGE)
            raise

        vectors = [data_point.embedding for data_point in response.data]
        return EmbeddingResult(vectors=vectors)


class KimiTextEmbedding(KimiEmbedder):
    def __init__(self, logger: Logger) -> None:
        super().__init__(model_name="text-embedding-v1", logger=logger)

    @property
    @override
    def max_tokens(self) -> int:
        return 8192

    @property
    def dimensions(self) -> int:
        return 1536


class KimiModerationService(ModerationService):
    def __init__(self, model_name: str, logger: Logger) -> None:
        self.model_name = model_name
        self._logger = logger

        self._client = AsyncClient(
            api_key=os.environ["KIMI_API_KEY"],
            base_url=os.environ.get("KIMI_BASE_URL", "https://api.moonshot.cn/v1")
        )

    @override
    async def check(self, content: str) -> ModerationCheck:
        def extract_tags(category: str) -> list[ModerationTag]:
            mapping: dict[str, list[ModerationTag]] = {
                "sexual": ["sexual"],
                "sexual_minors": ["sexual", "illicit"],
                "harassment": ["harassment"],
                "harassment_threatening": ["harassment", "illicit"],
                "hate": ["hate"],
                "hate_threatening": ["hate", "illicit"],
                "illicit": ["illicit"],
                "illicit_violent": ["illicit", "violence"],
                "self_harm": ["self-harm"],
                "self_harm_intent": ["self-harm", "violence"],
                "self_harm_instructions": ["self-harm", "illicit"],
                "violence": ["violence"],
                "violence_graphic": ["violence", "harassment"],
            }

            return mapping.get(category.replace("/", "_").replace("-", "_"), [])

        self._logger.info("Kimi Moderation Request")
        try:
            response = await self._client.moderations.create(
                input=content,
                model=self.model_name,
            )
        except Exception:
            # Fallback to no moderation if service is not available
            return ModerationCheck(flagged=False, tags=[])

        result = response.results[0]

        return ModerationCheck(
            flagged=result.flagged,
            tags=list(
                set(
                    chain.from_iterable(
                        extract_tags(category)
                        for category, detected in result.categories
                        if detected
                    )
                )
            ),
        )


class KimiModeration(KimiModerationService):
    def __init__(self, logger: Logger) -> None:
        super().__init__(model_name="moderation-latest", logger=logger)


class KimiService(NLPService):
    @staticmethod
    def verify_environment() -> str | None:
        """Returns an error message if the environment is not set up correctly."""

        if not os.environ.get("KIMI_API_KEY"):
            return """\
You're using the Kimi NLP service, but KIMI_API_KEY is not set.
Please set KIMI_API_KEY in your environment before running Parlant.
"""

        return None

    def __init__(
        self,
        logger: Logger,
    ) -> None:
        self._logger = logger
        self._logger.info("Initialized KimiService")

    @override
    async def get_schematic_generator(self, t: type[T]) -> KimiSchematicGenerator[T]:
        return Kimi_K2_0905_Preview[t](self._logger)  # type: ignore

    @override
    async def get_embedder(self) -> Embedder:
        return KimiTextEmbedding(self._logger)

    @override
    async def get_moderation_service(self) -> ModerationService:
        return KimiModeration(self._logger)