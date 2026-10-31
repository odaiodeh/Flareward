"""Compose async retrieval with immutable application messages."""

from typing import Any

from mas.application.ports.retrieval import BaseRetriever
from mas.domain.messages import ChatMessage


class RetrieverCapableMixin:
    def __init__(self, *, retriever: BaseRetriever | None = None, **kwargs: Any):
        super().__init__(**kwargs)
        self.retriever = retriever

    async def augment_with_context(self, user_message: ChatMessage) -> ChatMessage:
        if self.retriever is None or not user_message.content:
            return user_message
        context = await self.retriever.retrieve(user_message.content)
        if not context:
            return user_message
        return user_message.model_copy(
            update={
                "content": f"context: {context}\nuser:\n{user_message.content}",
            }
        )
