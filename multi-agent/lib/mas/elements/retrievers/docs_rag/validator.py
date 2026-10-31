"""
elements/retrievers/docs_rag/validator.py

Validator for DocsRag Retriever - checks RAG service health.
"""

from mas.application.elements.validation import (
    BaseElementValidator,
    ValidationCode,
    ValidationContext,
    ValidationMessage,
    ValidatorReport,
)
from mas.elements.providers.rag_client.client import (
    RagClient,
    RagClientError,
    RagConnectionError,
)
from mas.elements.providers.rag_client.config import RagProviderConfig
from mas.elements.retrievers.docs_rag.config import DocsRagRetrieverConfig


class DocsRagRetrieverValidator(BaseElementValidator):
    """
    Validates DocsRag Retriever configuration.

    Checks:
    - RAG service reachability
    - RAG service health
    """

    def validate(
        self,
        config: DocsRagRetrieverConfig,
        context: ValidationContext,
    ) -> ValidatorReport:
        """
        Validate DocsRag Retriever config.

        The retriever uses the default RAG service URL.
        We check if that service is healthy.

        Returns ValidatorReport (service adds metadata).
        """
        messages: list[ValidationMessage] = []

        # Get default RAG URL from provider config
        provider_config = RagProviderConfig()
        base_url = provider_config.base_url

        try:
            with RagClient(
                base_url=base_url,
                timeout=context.timeout_seconds,
            ) as client:
                health = client.health_check()

            if health.is_healthy:
                messages.append(
                    self._info(
                        "CONNECTION_OK",
                        f"RAG service is healthy at {base_url}",
                    )
                )
            else:
                messages.append(
                    self._error(
                        ValidationCode.ENDPOINT_UNREACHABLE.value,
                        f"RAG service unhealthy: {health.message}",
                    )
                )

        except RagConnectionError as e:
            messages.append(
                self._error(
                    ValidationCode.ENDPOINT_UNREACHABLE.value,
                    f"Cannot connect to RAG service: {str(e)}",
                )
            )
        except RagClientError as e:
            messages.append(
                self._error(
                    ValidationCode.NETWORK_ERROR.value,
                    f"RAG error: {str(e)}",
                )
            )
        except Exception as e:
            messages.append(
                self._error(
                    ValidationCode.NETWORK_ERROR.value,
                    f"Unexpected error: {type(e).__name__}",
                )
            )

        return self._build_report(messages=messages)
