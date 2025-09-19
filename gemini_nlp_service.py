# Copyright 2025 Emcie Co Ltd.
# Gemini NLP Service implementation based on Google's OpenAI-compatible API
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
import logging
from openai import (
    APIConnectionError,
    APIResponseValidationError,
    APITimeoutError,
    AsyncClient,
    BadRequestError,
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
    "Google Gemini API rate limit exceeded. Possible reasons:\n"
    "1. Your account may have insufficient API credits.\n"
    "2. You may be using a free-tier account with limited request capacity.\n"
    "3. You might have exceeded the requests-per-minute limit for your account.\n\n"
    "Recommended actions:\n"
    "- Check your Google AI Studio account balance and billing status.\n"
    "- Review your API usage limits in Google's dashboard.\n"
    "- For more details on rate limits and usage tiers, visit:\n"
    "  https://ai.google.dev/pricing\n"
)


class GeminiEstimatingTokenizer(EstimatingTokenizer):
    def __init__(self, model_name: str) -> None:
        self.model_name = model_name
        # Use GPT-4 tokenizer as approximation for Gemini models
        self.encoding = tiktoken.encoding_for_model("gpt-4")

    @override
    async def estimate_token_count(self, prompt: str) -> int:
        tokens = self.encoding.encode(prompt)
        return len(tokens)


class GeminiSchematicGenerator(SchematicGenerator[T]):
    supported_gemini_params = ["temperature", "max_tokens"]
    supported_hints = supported_gemini_params + ["strict"]

    def __init__(
        self,
        model_name: str,
        logger: Logger,
        tokenizer_model_name: str | None = None,
    ) -> None:
        self.model_name = model_name
        self._logger = logger

        # 设置很长的超时时间，避免任何超时问题
        from httpx import Timeout

        long_timeout = Timeout(
            connect=60.0,    # 连接超时60秒
            read=300.0,      # 读取超时5分钟
            write=60.0,      # 写入超时60秒
            pool=120.0       # 连接池超时2分钟
        )

        self._client = AsyncClient(
            api_key=os.environ["GEMINI_API_KEY"],
            base_url="https://generativelanguage.googleapis.com/v1beta/openai/",
            timeout=long_timeout,
            max_retries=5,   # 增加重试次数
            http_client=None
        )

        self._tokenizer = GeminiEstimatingTokenizer(
            model_name=tokenizer_model_name or self.model_name
        )

    def _create_client(self):
        """重新创建HTTP客户端的方法"""
        # 设置很长的超时时间，避免任何超时问题
        from httpx import Timeout

        long_timeout = Timeout(
            connect=60.0,    # 连接超时60秒
            read=300.0,      # 读取超时5分钟
            write=60.0,      # 写入超时60秒
            pool=120.0       # 连接池超时2分钟
        )

        self._client = AsyncClient(
            api_key=os.environ["GEMINI_API_KEY"],
            base_url="https://generativelanguage.googleapis.com/v1beta/openai/",
            timeout=long_timeout,
            max_retries=5,   # 增加重试次数
            http_client=None
        )

    @property
    @override
    def id(self) -> str:
        return f"gemini/{self.model_name}"

    @property
    @override
    def tokenizer(self) -> GeminiEstimatingTokenizer:
        return self._tokenizer

    @override
    async def generate(
        self,
        prompt: str | PromptBuilder,
        hints: Mapping[str, Any] = {},
    ) -> SchematicGenerationResult[T]:
        with self._logger.scope("GeminiSchematicGenerator"):
            with self._logger.operation(
                f"LLM Request ({self.schema.__name__})", level=LogLevel.TRACE
            ):
                # 添加自定义重试机制
                max_retries = 3
                last_exception = None
                original_model = self.model_name

                for attempt in range(max_retries):
                    try:
                        if attempt > 0:
                            # 第二次及以后的尝试升级到Pro模型
                            if attempt == 1 and self.model_name == "gemini-2.5-flash":
                                self._logger.info("升级到 gemini-2.5-pro 模型进行重试")
                                self.model_name = "gemini-2.5-pro"
                                # 重新创建客户端以使用新模型
                                self._create_client()

                            self._logger.info(f"重试第 {attempt} 次 (共 {max_retries} 次)，使用模型: {self.model_name}")
                            # 指数退避等待
                            import asyncio
                            wait_time = min(2 ** attempt, 10)  # 最多等待10秒
                            await asyncio.sleep(wait_time)

                        return await self._do_generate(prompt, hints)

                    except (ValidationError, json.JSONDecodeError, Exception) as e:
                        last_exception = e
                        self._logger.warning(f"第 {attempt + 1} 次尝试失败 (模型: {self.model_name}): {type(e).__name__}: {e}")

                        # 如果是最后一次尝试，抛出异常
                        if attempt == max_retries - 1:
                            self._logger.error(f"所有重试都失败了，共尝试 {max_retries} 次")
                            # 恢复原始模型
                            self.model_name = original_model
                            self._create_client()
                            raise
                        continue

                # 如果所有重试都失败，抛出最后一个异常
                raise last_exception

    async def _do_generate(
        self,
        prompt: str | PromptBuilder,
        hints: Mapping[str, Any] = {},
    ) -> SchematicGenerationResult[T]:
        if isinstance(prompt, PromptBuilder):
            prompt = prompt.build()

        gemini_api_arguments = {k: v for k, v in hints.items() if k in self.supported_gemini_params}

        if hints.get("strict", False):
            t_start = time.time()
            try:
                # 添加性能日志
                self._logger.info(f"开始Gemini API调用: {self.model_name}, prompt长度: {len(prompt)}")
                api_start = time.time()

                response = await self._client.beta.chat.completions.parse(
                    messages=[{"role": "user", "content": prompt}],
                    model=self.model_name,
                    response_format=self.schema,
                    **gemini_api_arguments,
                )

                api_end = time.time()
                self._logger.info(f"Gemini API调用完成: {self.model_name}, 耗时: {api_end - api_start:.2f}秒")
            except RateLimitError:
                self._logger.error(RATE_LIMIT_ERROR_MESSAGE)
                raise
            except BadRequestError:
                # 400 errors should be raised directly without retry
                raise

            t_end = time.time()

            if response.usage:
                self._logger.trace(response.usage.model_dump_json(indent=2))

            parsed_object = response.choices[0].message.parsed
            assert parsed_object

            assert response.usage
            assert response.usage.prompt_tokens_details

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
                            "cached_input_tokens": response.usage.prompt_tokens_details.cached_tokens
                            or 0
                        },
                    ),
                ),
            )

        else:
            try:
                t_start = time.time()
                # 添加性能日志
                self._logger.info(f"开始Gemini API调用(JSON): {self.model_name}, prompt长度: {len(prompt)}")
                api_start = time.time()

                response = await self._client.chat.completions.create(
                    messages=[{"role": "user", "content": prompt}],
                    model=self.model_name,
                    response_format={"type": "json_object"},
                    **gemini_api_arguments,
                )

                api_end = time.time()
                self._logger.info(f"Gemini API调用完成(JSON): {self.model_name}, 耗时: {api_end - api_start:.2f}秒")
                t_end = time.time()
            except RateLimitError:
                self._logger.error(RATE_LIMIT_ERROR_MESSAGE)
                raise
            except BadRequestError:
                # 400 errors should be raised directly without retry
                raise

            if response.usage:
                self._logger.trace(response.usage.model_dump_json(indent=2))

            raw_content = response.choices[0].message.content or "{}"

            try:
                json_content = json.loads(normalize_json_output(raw_content))
            except json.JSONDecodeError:
                self._logger.warning(f"Invalid JSON returned by {self.model_name}:\n{raw_content})")
                json_content = jsonfinder.only_json(raw_content)[2]
                self._logger.warning("Found JSON content within model response; continuing...")

            try:
                # 添加字段补全逻辑，处理缺少必需字段的情况
                if isinstance(json_content, dict):
                    # 确保包含必需字段
                    if 'tool_calls_for_candidate_tool' in json_content:
                        tool_calls = json_content['tool_calls_for_candidate_tool']
                        if isinstance(tool_calls, list):
                            for tool_call in tool_calls:
                                if isinstance(tool_call, dict):
                                    # 补全缺少的必需字段
                                    if 'same_call_is_already_staged' not in tool_call:
                                        tool_call['same_call_is_already_staged'] = False
                                        self._logger.info("补全 same_call_is_already_staged 字段")
                                    if 'relevant_subtleties' not in tool_call:
                                        tool_call['relevant_subtleties'] = ""
                                        self._logger.info("补全 relevant_subtleties 字段")
                        else:
                            # 如果tool_calls_for_candidate_tool不是数组，重置为空数组
                            self._logger.warning("tool_calls_for_candidate_tool 不是数组格式，重置为空数组")
                            json_content['tool_calls_for_candidate_tool'] = []
                    else:
                        # 如果缺少tool_calls_for_candidate_tool字段，添加空数组
                        self._logger.warning("缺少 tool_calls_for_candidate_tool 字段，添加空数组")
                        json_content['tool_calls_for_candidate_tool'] = []

                self._logger.info(f"补全后的JSON: {json.dumps(json_content, indent=2, ensure_ascii=False)}")
                content = self.schema.model_validate(json_content)

                assert response.usage

                # Handle case where prompt_tokens_details might be None
                cached_tokens = 0
                if response.usage.prompt_tokens_details and hasattr(response.usage.prompt_tokens_details, 'cached_tokens'):
                    cached_tokens = response.usage.prompt_tokens_details.cached_tokens or 0

                return self._build_generation_result(content, response, t_start, t_end)

            except ValidationError as e:
                # 提供更详细的错误信息和修复建议
                self._logger.error(f"Pydantic验证错误: {e}")
                self._logger.error(f"错误详情: {e.errors()}")
                self._logger.error(f"原始JSON内容: {json.dumps(json_content, indent=2, ensure_ascii=False)}")
                self._logger.error(f"原始响应: {raw_content}")

                # 尝试修复常见的JSON结构问题
                try:
                    if isinstance(json_content, dict):
                        # 如果缺少tool_calls_for_candidate_tool字段，添加空数组
                        if 'tool_calls_for_candidate_tool' not in json_content:
                            self._logger.info("添加缺失的 tool_calls_for_candidate_tool 字段")
                            json_content['tool_calls_for_candidate_tool'] = []

                        # 确保tool_calls_for_candidate_tool是数组
                        if not isinstance(json_content['tool_calls_for_candidate_tool'], list):
                            self._logger.warning("修正 tool_calls_for_candidate_tool 为数组格式")
                            json_content['tool_calls_for_candidate_tool'] = []

                        # 为每个工具调用补全缺少的字段
                        for tool_call in json_content.get('tool_calls_for_candidate_tool', []):
                            if not isinstance(tool_call, dict):
                                # 如果不是字典，跳过或替换为空字典
                                continue

                            # 补全缺少的必需字段
                            if 'same_call_is_already_staged' not in tool_call:
                                tool_call['same_call_is_already_staged'] = False
                                self._logger.info("补全 same_call_is_already_staged 字段")
                            if 'relevant_subtleties' not in tool_call:
                                tool_call['relevant_subtleties'] = ""
                                self._logger.info("补全 relevant_subtleties 字段")

                        self._logger.info(f"修复后的JSON: {json.dumps(json_content, indent=2, ensure_ascii=False)}")

                        # 重新验证
                        content = self.schema.model_validate(json_content)
                        self._logger.info("成功修复JSON结构问题")
                        return self._build_generation_result(content, response, t_start, t_end)

                except Exception as fix_error:
                    self._logger.error(f"修复JSON失败: {fix_error}")
                    self._logger.error(f"修复时JSON内容: {json.dumps(json_content, indent=2, ensure_ascii=False)}")
                    # 如果修复失败，抛出ValidationError让外层重试
                    raise

                # 如果修复失败，重新抛出原始错误
                raise

    def _build_generation_result(self, content, response, t_start, t_end):
        """构建生成结果的辅助方法"""
        # Handle case where prompt_tokens_details might be None
        cached_tokens = 0
        if response.usage and response.usage.prompt_tokens_details and hasattr(response.usage.prompt_tokens_details, 'cached_tokens'):
            cached_tokens = response.usage.prompt_tokens_details.cached_tokens or 0

        return SchematicGenerationResult(
            content=content,
            info=GenerationInfo(
                schema_name=self.schema.__name__,
                model=self.id,
                duration=(t_end - t_start),
                usage=UsageInfo(
                    input_tokens=response.usage.prompt_tokens if response.usage else 0,
                    output_tokens=response.usage.completion_tokens if response.usage else 0,
                    extra={
                        "cached_input_tokens": cached_tokens
                    },
                ),
            ),
        )


class Gemini_Pro(GeminiSchematicGenerator[T]):
    def __init__(self, logger: Logger) -> None:
        super().__init__(model_name="gemini-2.5-flash", logger=logger)

    @property
    @override
    def max_tokens(self) -> int:
        return 128 * 1024


class Gemini_Flash(GeminiSchematicGenerator[T]):
    def __init__(self, logger: Logger) -> None:
        super().__init__(model_name="gemini-2.5-flash", logger=logger)

    @property
    @override
    def max_tokens(self) -> int:
        return 128 * 1024


class Gemini_Pro_002(GeminiSchematicGenerator[T]):
    def __init__(self, logger: Logger) -> None:
        super().__init__(model_name="gemini-2.5-flash", logger=logger)

    @property
    @override
    def max_tokens(self) -> int:
        return 128 * 1024


class Gemini_Flash_002(GeminiSchematicGenerator[T]):
    def __init__(self, logger: Logger) -> None:
        super().__init__(model_name="gemini-2.5-flash", logger=logger)

    @property
    @override
    def max_tokens(self) -> int:
        return 128 * 1024


class GeminiEmbedder(Embedder):
    supported_arguments = ["dimensions"]

    def __init__(self, model_name: str, logger: Logger) -> None:
        self.model_name = model_name

        self._logger = logger
        # 设置很长的超时时间，避免任何超时问题
        from httpx import Timeout

        long_timeout = Timeout(
            connect=60.0,    # 连接超时60秒
            read=300.0,      # 读取超时5分钟
            write=60.0,      # 写入超时60秒
            pool=120.0       # 连接池超时2分钟
        )

        self._client = AsyncClient(
            api_key=os.environ["GEMINI_API_KEY"],
            base_url="https://generativelanguage.googleapis.com/v1beta/openai/",
            timeout=long_timeout,
            max_retries=5,   # 增加重试次数
            http_client=None
        )
        self._tokenizer = GeminiEstimatingTokenizer(model_name=self.model_name)

    @property
    @override
    def id(self) -> str:
        return f"gemini/{self.model_name}"

    @property
    @override
    def tokenizer(self) -> GeminiEstimatingTokenizer:
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
        except BadRequestError:
            # 400 errors should be raised directly without retry
            raise

        vectors = [data_point.embedding for data_point in response.data]
        return EmbeddingResult(vectors=vectors)


class GeminiTextEmbedding(GeminiEmbedder):
    def __init__(self, logger: Logger) -> None:
        super().__init__(model_name="text-embedding-004", logger=logger)

    @property
    @override
    def max_tokens(self) -> int:
        return 8192

    @property
    def dimensions(self) -> int:
        return 768


class GeminiModerationService(ModerationService):
    def __init__(self, model_name: str, logger: Logger) -> None:
        self.model_name = model_name
        self._logger = logger

        # 设置很长的超时时间，避免任何超时问题
        from httpx import Timeout

        long_timeout = Timeout(
            connect=60.0,    # 连接超时60秒
            read=300.0,      # 读取超时5分钟
            write=60.0,      # 写入超时60秒
            pool=120.0       # 连接池超时2分钟
        )

        self._client = AsyncClient(
            api_key=os.environ["GEMINI_API_KEY"],
            base_url="https://generativelanguage.googleapis.com/v1beta/openai/",
            timeout=long_timeout,
            max_retries=5,   # 增加重试次数
            http_client=None
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

        with self._logger.operation("Gemini Moderation Request", level=LogLevel.TRACE):
            try:
                response = await self._client.moderations.create(
                    input=content,
                    model=self.model_name,
                )
            except Exception as e:
                # If moderation API is not available, return safe result
                self._logger.warning(f"Gemini moderation API not available: {e}")
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


class GeminiModeration(GeminiModerationService):
    def __init__(self, logger: Logger) -> None:
        super().__init__(model_name="gemini-moderation", logger=logger)


class GeminiService(NLPService):
    @staticmethod
    def verify_environment() -> str | None:
        """Returns an error message if the environment is not set up correctly."""

        if not os.environ.get("GEMINI_API_KEY"):
            return """\
You're using the Gemini NLP service, but GEMINI_API_KEY is not set.
Please set GEMINI_API_KEY in your environment before running Parlant.
"""

        return None

    def __init__(
        self,
        logger: Logger,
    ) -> None:
        self._logger = logger
        self._logger.info("Initialized GeminiService")

    @override
    async def get_schematic_generator(self, t: type[T]) -> GeminiSchematicGenerator[T]:
        # 优化：优先使用更快的Flash模型
        return {
            SingleToolBatchSchema: Gemini_Flash[SingleToolBatchSchema],
            JourneyNodeSelectionSchema: Gemini_Flash[JourneyNodeSelectionSchema],
            CannedResponseDraftSchema: Gemini_Flash[CannedResponseDraftSchema],
            CannedResponseSelectionSchema: Gemini_Flash[CannedResponseSelectionSchema],
        }.get(t, Gemini_Flash[t])(self._logger)  # type: ignore

    @override
    async def get_embedder(self) -> Embedder:
        return GeminiTextEmbedding(self._logger)

    @override
    async def get_moderation_service(self) -> ModerationService:
        return GeminiModeration(self._logger)