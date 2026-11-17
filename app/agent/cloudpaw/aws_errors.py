"""Turn the AWS errors you meet when running locally into one sentence that says what to do.

Running `play.py` or `agentcore dev` with an expired SSO session used to end in a 30-line traceback. This keeps the cause
(your AWS session) separate from the robot code, which was fine.
"""

from __future__ import annotations

from typing import Optional

try:  # botocore is always there in the kit; the guard keeps this importable in a bare environment
    from botocore.exceptions import (
        ClientError,
        CredentialRetrievalError,
        NoCredentialsError,
        NoRegionError,
        PartialCredentialsError,
        TokenRetrievalError,
        UnauthorizedSSOTokenError,
    )
except ImportError:  # pragma: no cover
    ClientError = CredentialRetrievalError = NoCredentialsError = NoRegionError = None  # type: ignore
    PartialCredentialsError = TokenRetrievalError = UnauthorizedSSOTokenError = None  # type: ignore

_LOGIN = "aws sso login --profile <tu-perfil>   (y vuelve a lanzar con AWS_PROFILE=<tu-perfil>)"
_OFFLINE = "Sin AWS puedes probar el robot igual: python play.py --offline"

_EXPIRED_CODES = {"ExpiredToken", "ExpiredTokenException", "RequestExpired"}
_BAD_CREDENTIAL_CODES = {"UnrecognizedClientException", "InvalidSignatureException", "InvalidClientTokenId", "SignatureDoesNotMatch"}
_ACCESS_CODES = {"AccessDeniedException", "AccessDenied", "UnauthorizedOperation"}


def explain_aws_error(exc: BaseException) -> Optional[str]:
    """A message for credential / session / access problems, or None when the error is something else (a real bug)."""
    chain = []
    seen = set()
    e: Optional[BaseException] = exc
    while e is not None and id(e) not in seen:  # the AWS error is often wrapped by the SDK
        seen.add(id(e))
        chain.append(e)
        e = e.__cause__ or e.__context__

    for err in chain:
        if TokenRetrievalError is not None and isinstance(err, (TokenRetrievalError, UnauthorizedSSOTokenError)):
            return f"Tu sesión de AWS (SSO) caducó o no es válida.\n  Arréglalo con: {_LOGIN}\n  {_OFFLINE}"
        if NoCredentialsError is not None and isinstance(err, (NoCredentialsError, PartialCredentialsError, CredentialRetrievalError)):
            return f"No hay credenciales de AWS en esta terminal.\n  Arréglalo con: {_LOGIN}\n  {_OFFLINE}"
        if NoRegionError is not None and isinstance(err, NoRegionError):
            return "No hay región de AWS configurada.\n  Arréglalo con: export AWS_REGION=us-east-1"
        if ClientError is not None and isinstance(err, ClientError):
            code = err.response.get("Error", {}).get("Code", "")
            if code in _EXPIRED_CODES:
                return f"Las credenciales de AWS caducaron.\n  Arréglalo con: {_LOGIN}\n  {_OFFLINE}"
            if code in _BAD_CREDENTIAL_CODES:
                return f"AWS rechazó las credenciales ({code}).\n  Revisa que sean las de esta cuenta: {_LOGIN}"
            if code in _ACCESS_CODES:
                return (
                    f"AWS dice que no tienes permiso o acceso al modelo ({code}).\n"
                    "  Revisa que el modelo esté disponible en tu cuenta y región, o prueba otro: export CLOUDPAW_MODEL_ID=us.amazon.nova-lite-v1:0"
                )
    return None
