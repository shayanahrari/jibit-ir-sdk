"""High-level Identicator inquiry operations."""

from __future__ import annotations

from typing import Any, TypeVar

from pydantic import BaseModel

from jibit.engine import RequestOptions
from jibit.response import APIResponse
from jibit.retry import OperationSafety
from jibit.services.base import (
    RequestExecutor,
    compact_values,
    request_validation_error,
    typed_request,
    validate_request,
)
from jibit.services.identicator.models import (
    BalancesResponse,
    CardInquiryResponse,
    DailyUsageReportResponse,
    DepositInquiryResponse,
    FlexibleInquiryResponse,
    IbanInquiryResponse,
    IdenticatorHealthResponse,
    IdentityResponse,
    IdentitySimilarityRequest,
    IdentitySimilarityResponse,
    MatchingRequest,
    MatchingResponse,
    PostalResponse,
    ServiceAvailabilityResponse,
    WgsResponse,
)
from jibit.types import ServiceName

_SERVICE = ServiceName.IDENTICATOR
ModelT = TypeVar("ModelT", bound=BaseModel)


class IdenticatorService:
    """Expose read-oriented banking, identity, postal, and matching inquiries."""

    def __init__(self, executor: RequestExecutor) -> None:
        self._executor = executor

    def inquire_deposit(
        self,
        *,
        bank: str,
        number: str,
        include_iban: bool = False,
        track_id: str | None = None,
    ) -> APIResponse[DepositInquiryResponse]:
        """Inquire an account number and optionally request IBAN conversion."""
        return self._get(
            "inquire_deposit",
            "/ide/v1/deposits",
            DepositInquiryResponse,
            {"bank": bank, "number": number, "iban": include_iban},
            track_id,
        )

    def inquire_iban(
        self, value: str, *, track_id: str | None = None
    ) -> APIResponse[IbanInquiryResponse]:
        """Return documented owner and account information for an IBAN."""
        return self._get(
            "inquire_iban", "/ide/v1/ibans", IbanInquiryResponse, {"value": value}, track_id
        )

    def inquire_card(
        self,
        number: str,
        *,
        include_deposit: bool = False,
        include_iban: bool = False,
        include_national_code: bool = False,
        track_id: str | None = None,
    ) -> APIResponse[CardInquiryResponse]:
        """Inquire a bank card and request at most one documented conversion."""
        if sum((include_deposit, include_iban, include_national_code)) > 1:
            raise request_validation_error(
                service=_SERVICE.value,
                operation="inquire_card",
                method="GET",
                endpoint="/ide/v1/cards",
                message="At most one card conversion flag can be true",
            )
        return self._get(
            "inquire_card",
            "/ide/v1/cards",
            CardInquiryResponse,
            {
                "number": number,
                "deposit": include_deposit,
                "iban": include_iban,
                "nationalCode": include_national_code,
            },
            track_id,
        )

    def match(
        self,
        request: MatchingRequest | None = None,
        *,
        track_id: str | None = None,
        **identifiers: str,
    ) -> APIResponse[MatchingResponse]:
        """Match one validated pair of banking or identity identifiers."""
        if request is not None and identifiers:
            raise request_validation_error(
                service=_SERVICE.value,
                operation="match",
                method="POST",
                endpoint="/ide/v1/services/matching",
                message="Provide request or identifier keywords, not both",
            )
        request = request or validate_request(
            MatchingRequest,
            identifiers,
            service=_SERVICE.value,
            operation="match",
            method="POST",
            endpoint="/ide/v1/services/matching",
        )
        return typed_request(
            self._executor,
            RequestOptions(
                service=_SERVICE,
                operation="match",
                method="POST",
                path="/ide/v1/services/matching",
                safety=OperationSafety.IDEMPOTENT,
                headers=self._track_header(track_id),
                json=request.to_payload(),
            ),
            MatchingResponse,
        )

    def inquire_postal_address(
        self, code: str, *, track_id: str | None = None
    ) -> APIResponse[PostalResponse]:
        """Return address information for a postal code."""
        return self._get(
            "inquire_postal_address",
            "/ide/v1/services/postal",
            PostalResponse,
            {"code": code},
            track_id,
        )

    def inquire_postal_coordinates(
        self, code: str, *, track_id: str | None = None
    ) -> APIResponse[WgsResponse]:
        """Return WGS coordinates for a postal code."""
        return self._get(
            "inquire_postal_coordinates",
            "/ide/v1/services/postal/wgs",
            WgsResponse,
            {"code": code},
            track_id,
        )

    def inquire_identity(
        self,
        *,
        national_code: str,
        birth_date: str,
        complete_info: bool = False,
        without_photo: bool = True,
        track_id: str | None = None,
    ) -> APIResponse[IdentityResponse]:
        """Return civil identity data while excluding the photo by safe default."""
        return self._get(
            "inquire_identity",
            "/ide/v1/services/identity",
            IdentityResponse,
            {
                "nationalCode": national_code,
                "birthDate": birth_date,
                "completeInfo": complete_info,
                "withoutPhoto": without_photo,
            },
            track_id,
        )

    def compare_identity_names(
        self,
        request: IdentitySimilarityRequest | None = None,
        *,
        track_id: str | None = None,
        **identity: str,
    ) -> APIResponse[IdentitySimilarityResponse]:
        """Compare supplied names against civil identity information."""
        if request is not None and identity:
            raise request_validation_error(
                service=_SERVICE.value,
                operation="compare_identity_names",
                method="POST",
                endpoint="/ide/v1/services/identity/similarity",
                message="Provide request or identity keywords, not both",
            )
        request = request or validate_request(
            IdentitySimilarityRequest,
            identity,
            service=_SERVICE.value,
            operation="compare_identity_names",
            method="POST",
            endpoint="/ide/v1/services/identity/similarity",
        )
        return typed_request(
            self._executor,
            RequestOptions(
                service=_SERVICE,
                operation="compare_identity_names",
                method="POST",
                path="/ide/v1/services/identity/similarity",
                safety=OperationSafety.IDEMPOTENT,
                headers=self._track_header(track_id),
                json=request.to_payload(),
            ),
            IdentitySimilarityResponse,
        )

    def inquire_foreigner_identity(
        self, fida: str, *, track_id: str | None = None
    ) -> APIResponse[FlexibleInquiryResponse]:
        """Return documented foreign-resident identity data."""
        return self._get(
            "inquire_foreigner_identity",
            "/ide/v1/services/foreigners/identity",
            FlexibleInquiryResponse,
            {"fida": fida},
            track_id,
        )

    def inquire_legal_identity(
        self,
        national_code: str,
        *,
        sign_holders: bool = False,
        members: bool = False,
        news: bool = False,
        certificates: bool = False,
        company_children: bool = False,
        company_parents: bool = False,
        track_id: str | None = None,
    ) -> APIResponse[FlexibleInquiryResponse]:
        """Return legal-entity information with explicit nested-data expansion flags."""
        return self._get(
            "inquire_legal_identity",
            "/ide/v1/services/identity/legal",
            FlexibleInquiryResponse,
            {
                "nationalCode": national_code,
                "signHolders": sign_holders,
                "members": members,
                "news": news,
                "certificates": certificates,
                "companyChildren": company_children,
                "companyParents": company_parents,
            },
            track_id,
        )

    def inquire_legal_sign_holders(
        self, national_code: str, *, track_id: str | None = None
    ) -> APIResponse[FlexibleInquiryResponse]:
        """Return the documented legal sign-holder expansion for one entity."""
        return self._get(
            "inquire_legal_sign_holders",
            "/ide/v1/services/identity/legal/sign-holders",
            FlexibleInquiryResponse,
            {"nationalCode": national_code},
            track_id,
        )

    def inquire_military_qualification(
        self, national_code: str, *, track_id: str | None = None
    ) -> APIResponse[FlexibleInquiryResponse]:
        """Return documented military-service qualification information."""
        return self._get(
            "inquire_military_qualification",
            "/ide/v1/services/social/msq",
            FlexibleInquiryResponse,
            {"nationalCode": national_code},
            track_id,
        )

    def inquire_sana(
        self, national_code: str, *, track_id: str | None = None
    ) -> APIResponse[FlexibleInquiryResponse]:
        """Return whether the national code is registered with Sana."""
        return self._get(
            "inquire_sana",
            "/ide/v1/services/social/sana",
            FlexibleInquiryResponse,
            {"nationalCode": national_code},
            track_id,
        )

    def inquire_corporation(
        self, code: str, *, track_id: str | None = None
    ) -> APIResponse[FlexibleInquiryResponse]:
        """Return documented guild or corporation identity data."""
        return self._get(
            "inquire_corporation",
            "/ide/v1/services/corporation/identity",
            FlexibleInquiryResponse,
            {"code": code},
            track_id,
        )

    def inquire_cheque(
        self,
        *,
        national_code: str,
        sayad_id: str,
        holder: bool = False,
        track_id: str | None = None,
    ) -> APIResponse[FlexibleInquiryResponse]:
        """Return documented cheque information for the requested perspective."""
        return self._get(
            "inquire_cheque",
            "/ide/v1/services/cheque/inquiry",
            FlexibleInquiryResponse,
            {"nationalCode": national_code, "sayadId": sayad_id, "holder": holder},
            track_id,
        )

    def get_balances(self, *, track_id: str | None = None) -> APIResponse[BalancesResponse]:
        """Return the configured client's Identicator balances."""
        return self._get("get_balances", "/ide/v1/balances", BalancesResponse, {}, track_id)

    def get_daily_usage_report(self, year_month_day: str) -> APIResponse[DailyUsageReportResponse]:
        """Return the client usage report for the documented provider date string."""
        return self._get(
            "get_daily_usage_report",
            "/ide/v1/reports/daily",
            DailyUsageReportResponse,
            {"yearMonthDay": year_month_day},
            None,
        )

    def service_availability(
        self, *, card_to_iban: bool = True, track_id: str | None = None
    ) -> APIResponse[ServiceAvailabilityResponse]:
        """Return provider availability for the documented card-to-IBAN service."""
        return self._get(
            "service_availability",
            "/ide/v1/services/availability",
            ServiceAvailabilityResponse,
            {"cardToIBAN": card_to_iban},
            track_id,
        )

    def health(self) -> APIResponse[IdenticatorHealthResponse]:
        """Return the public Identicator health status."""
        return typed_request(
            self._executor,
            RequestOptions(
                service=_SERVICE,
                operation="health",
                method="GET",
                path="/ide/health",
                safety=OperationSafety.READ_ONLY,
            ),
            IdenticatorHealthResponse,
        )

    def _get(
        self,
        operation: str,
        path: str,
        model: type[ModelT],
        params: dict[str, Any],
        track_id: str | None,
    ) -> APIResponse[ModelT]:
        return typed_request(
            self._executor,
            RequestOptions(
                service=_SERVICE,
                operation=operation,
                method="GET",
                path=path,
                safety=OperationSafety.READ_ONLY,
                headers=self._track_header(track_id),
                params=compact_values(params),
            ),
            model,
        )

    @staticmethod
    def _track_header(track_id: str | None) -> dict[str, str]:
        return {"X-TRACK-ID": track_id} if track_id is not None else {}
