"""High-level MzaHub contract creation, inquiry, cancellation, and download."""

from __future__ import annotations

import base64
from datetime import datetime
from typing import Any, TypeVar

from pydantic import BaseModel, Field

from jibit.engine import RequestOptions
from jibit.models import JibitRequestModel
from jibit.response import APIResponse
from jibit.retry import OperationSafety
from jibit.services.base import RequestExecutor, typed_request, validate_request
from jibit.services.contracts.models import (
    ContractResult,
    ContractSummary,
    InitiateContractRequest,
    InitiateContractResult,
    RealIp,
    SignedDocument,
    Signer,
)
from jibit.types import ServiceName

_SERVICE = ServiceName.CONTRACTS
_PATH = "/mzahub/v1/contracts"
ModelT = TypeVar("ModelT", bound=BaseModel)


class ContractService:
    """Expose the merchant-managed MzaHub contract lifecycle."""

    def __init__(self, executor: RequestExecutor) -> None:
        self._executor = executor

    def initiate(
        self,
        *,
        track_id: str,
        pdf: bytes,
        redirect_url: str,
        signers: list[Signer | dict[str, Any]],
        real_ip: str,
        expire_at: datetime | None = None,
        description: str | None = None,
        signature_appearance: str | None = None,
    ) -> APIResponse[InitiateContractResult]:
        """Create one contract once; reconcile by track_id after uncertainty."""
        request = self._validate(
            InitiateContractRequest,
            {
                "track_id": track_id,
                "base64_file": base64.b64encode(pdf).decode("ascii"),
                "redirect_url": redirect_url,
                "signers": signers,
                "expire_at": expire_at,
                "description": description,
                "signature_appearance": signature_appearance,
            },
            operation="initiate",
            method="POST",
            path=_PATH,
        )
        return self._typed(
            "initiate",
            "POST",
            _PATH,
            OperationSafety.UNSAFE,
            InitiateContractResult,
            real_ip=real_ip,
            json=request.to_provider_payload(),
        )

    def inquire(self, track_id: str, *, real_ip: str) -> APIResponse[ContractResult]:
        """Reconcile a contract and signer state by the caller's track ID."""
        track_id = self._track_id(track_id, operation="inquire")
        return self._typed(
            "inquire",
            "GET",
            _PATH,
            OperationSafety.READ_ONLY,
            ContractResult,
            real_ip=real_ip,
            params={"trackId": track_id},
        )

    def cancel(self, track_id: str, *, real_ip: str) -> APIResponse[ContractSummary]:
        """Cancel one contract without automatic replay."""
        track_id = self._track_id(track_id, operation="cancel")
        return self._typed(
            "cancel",
            "POST",
            f"{_PATH}/cancel",
            OperationSafety.UNSAFE,
            ContractSummary,
            real_ip=real_ip,
            params={"trackId": track_id},
        )

    def download_signed(self, track_id: str, *, real_ip: str) -> APIResponse[SignedDocument]:
        """Download signed contract bytes after a signed-state inquiry."""
        track_id = self._track_id(track_id, operation="download_signed")
        ip = self._real_ip(real_ip, operation="download_signed")
        raw = self._executor.execute(
            RequestOptions(
                _SERVICE,
                "download_signed",
                "GET",
                f"{_PATH}/download-signed",
                OperationSafety.READ_ONLY,
                headers={"X-REAL-IP": ip},
                params={"trackId": track_id},
            )
        )
        content_type = next(
            (value for key, value in raw.headers.items() if key.lower() == "content-type"),
            None,
        )
        return APIResponse(SignedDocument(content=raw.content, content_type=content_type), raw)

    def _typed(
        self,
        operation: str,
        method: str,
        path: str,
        safety: OperationSafety,
        model: type[ModelT],
        *,
        real_ip: str,
        params: dict[str, Any] | None = None,
        json: dict[str, Any] | None = None,
    ) -> APIResponse[ModelT]:
        ip = self._real_ip(real_ip, operation=operation)
        return typed_request(
            self._executor,
            RequestOptions(
                _SERVICE,
                operation,
                method,
                path,
                safety,
                headers={"X-REAL-IP": ip},
                params=params,
                json=json,
            ),
            model,
        )

    @staticmethod
    def _real_ip(value: str, *, operation: str) -> str:
        return str(
            ContractService._validate(
                RealIp,
                {"value": value},
                operation=operation,
                method="POST",
                path=_PATH,
            ).value
        )

    @staticmethod
    def _track_id(value: str, *, operation: str) -> str:
        class _TrackId(JibitRequestModel):
            value: str = Field(min_length=1, max_length=200, pattern=r"^[A-Za-z0-9_-]+$")

        return ContractService._validate(
            _TrackId,
            {"value": value},
            operation=operation,
            method="GET",
            path=_PATH,
        ).value

    @staticmethod
    def _validate(model: type[ModelT], values: dict[str, Any], **context: str) -> ModelT:
        return validate_request(
            model,
            values,
            service=_SERVICE.value,
            endpoint=context.pop("path"),
            **context,
        )
