# Part of Odoo. See LICENSE file for full copyright and licensing details.
"""Abstract base for Panama PAC providers and shared response types.

Concrete providers (Factura Fácil, HKA, eFacturaPTY, …) live in their
own modules, subclass `PACProvider`, and register themselves in the
`res.company.l10n_pa_pac_provider` Selection field via
`account_move._l10n_pa_get_pac_provider()`.
"""
from __future__ import annotations

import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any

_logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------
# Exception hierarchy
# ---------------------------------------------------------------------


class PACError(Exception):
    """Base for all PAC-related errors. User-facing messages should be in Spanish."""


class PACAPIError(PACError):
    """PAC API returned a non-success response (e.g. HTTP 4xx/5xx with a payload)."""


class PACValidationError(PACError):
    """Invoice data fails PAC pre-validation before the wire is touched."""


class PACAuthError(PACError):
    """PAC authentication failed (invalid credentials, expired token, etc.)."""


class PACConnectionError(PACError):
    """Network or transport-level failure (timeout, DNS, TLS, …)."""


# ---------------------------------------------------------------------
# Response data carriers
# ---------------------------------------------------------------------


@dataclass
class PACResponse:
    """Normalized PAC response for a send/cancel operation."""
    success: bool
    cufe: str = ''
    authorized_xml: str = ''
    qr_payload: str = ''
    raw_response: str = ''
    pac_status_code: str = ''
    pac_status_message: str = ''
    errors: list[dict[str, str]] = field(default_factory=list)
    extra: dict[str, Any] = field(default_factory=dict)


@dataclass
class PACStatus:
    """Normalized status query response."""
    cufe: str
    state: str  # 'authorized' | 'rejected' | 'cancelled' | 'pending' | 'unknown'
    pac_status_code: str = ''
    pac_status_message: str = ''
    raw_response: str = ''


# ---------------------------------------------------------------------
# Abstract provider
# ---------------------------------------------------------------------


class PACProvider(ABC):
    """Abstract base for all Panama PAC providers.

    Each concrete provider is constructed with the calling
    `res.company` so it can read its own company-scoped credentials and
    sandbox/production toggle from `ir.config_parameter` or company
    fields. Providers are stateless beyond the company reference;
    instantiate per call.
    """

    #: Selection key used in `res.company.l10n_pa_pac_provider`.
    code: str = ''

    #: Human-readable name shown in the company configuration.
    name: str = ''

    def __init__(self, company):
        self.company = company
        self.env = company.env

    # ---- Operations every provider must implement -----------------------

    @abstractmethod
    def send_invoice(self, move) -> PACResponse:
        """Submit a DGI XML built from `move` and return a normalized response.

        Implementations should:
          1. Call `move._l10n_pa_generate_xml()` for the unsigned doc.
          2. POST it to the PAC endpoint with provider-specific framing.
          3. Map PAC errors to `PACError` subclasses; do NOT raise inside
             this method — return `PACResponse(success=False, errors=…)`.
          4. On success, populate `cufe`, `authorized_xml`, `qr_payload`.
        """

    @abstractmethod
    def get_status(self, cufe: str) -> PACStatus:
        """Query the PAC for the current state of a previously-sent CUFE."""

    @abstractmethod
    def cancel_invoice(self, move, reason: str) -> PACResponse:
        """Register an Anulación event with the PAC for an authorized move."""

    @abstractmethod
    def validate_ruc(self, ruc: str, dv: str) -> bool:
        """Verify a RUC + DV pair against the PAC's RUC lookup service."""
