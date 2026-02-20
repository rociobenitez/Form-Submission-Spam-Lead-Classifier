import hashlib
import re
from urllib.parse import urlparse, urlunparse

PHONE_REGEX = re.compile(
    r"""
    (?<!\d)               # evita pegarse a otro número
    (?:\+?\d{1,3}[\s-]?)? # prefijo opcional (+34, +1, etc.)
    \d(?:[\s-]?\d){7,11}  # cuerpo del número (separadores solo entre dígitos)
    (?!\d)                # evita pegarse a otro número
    """,
    re.VERBOSE,
)

URL_REGEX = re.compile(
    r"""
    (?i)\b(
        (?:https?://|www\.)\S+
        |
        (?<!@)                       # evita nombre@gmail.com
        [a-z0-9-]+(?:\.[a-z0-9-]+)+
        (?:/[^\s]*)?
    )
    """,
    re.VERBOSE,
)

EMAIL_REGEX = re.compile(r"""(?i)\b[a-z0-9._%+-]+@[a-z0-9.-]+\.[a-z]{2,}\b""")


def normalize_text(value) -> str:
    if value is None:
        return ""
    text = str(value).strip()
    if not text or text.lower() in {"nan", "none"}:
        return ""
    return text


def anonymize_name(name: str, salt: str = "gf_v1") -> str:
    """
    Pseudonimiza un nombre de forma estable:
    mismo input -> mismo output, sin exponer el nombre real.
    Args:
        name (str): El nombre a anonimizar.
        salt (str): Un valor adicional para asegurar que el hash sea único y no reversible.
    Returns:
        str: El nombre anonimizado.
    """
    name = normalize_text(name)
    # Si el nombre es vacío o inválido, devolvemos una cadena vacía
    # para evitar generar hashes de valores no significativos.
    if not name:
        return ""
    normalized = " ".join(name.lower().split())  # quita dobles espacios y normaliza
    raw = f"{salt}:{normalized}".encode("utf-8")
    digest = hashlib.sha256(raw).hexdigest()[:8]  # corto para que sea manejable
    return f"NAME_{digest}"


def email_to_domain(email: str) -> str:
    """
    Devuelve el dominio del email (ej: 'gmail.com').
    Si el email es inválido o vacío, devuelve ''.
    Args:
        email (str): El email a procesar.
    Returns:
        str: El dominio del email o '' si no es válido.
    """
    email = normalize_text(email)
    if "@" not in email:
        return ""

    domain = email.split("@")[-1].strip()
    # Limpiar caracteres que podrían estar pegados al dominio
    domain = domain.strip(" >),;\"'")

    # Validación mínima: que tenga un punto y no tenga espacios
    if " " in domain or "." not in domain:
        return ""

    return domain


def mask_phones_in_message(message: str) -> str:
    """
    Sustituye cualquier número de teléfono detectado en el texto por [PHONE]
    Args:
        message (str): El texto a procesar.
    Returns:
        str: El texto con los números de teléfono enmascarados.
    """
    text = normalize_text(message)
    return PHONE_REGEX.sub("[PHONE]", text)


def phone_count(message: str) -> int:
    """
    Cuenta cuántos teléfonos detecta en el texto usando PHONE_REGEX.
    Args:
        message (str): El texto a procesar.
    Returns:
        int: El número de teléfonos detectados.
    """
    text = normalize_text(message)
    if not text:
        return 0

    return sum(1 for _ in PHONE_REGEX.finditer(text))


def mask_urls_in_message(message: str) -> str:
    """
    Sustituye URLs detectadas en el texto por [URL].
    Args:
        message (str): El texto a procesar.
    Returns:
        str: El texto con las URLs enmascaradas.
    """
    text = normalize_text(message)
    return URL_REGEX.sub("[URL]", text)


def url_count(message: str) -> int:
    """
    Cuenta cuántas URLs detecta en el texto usando URL_REGEX.
    Args:
        message (str): El texto a procesar.
    Returns:
        int: El número de URLs detectadas.
    """
    text = normalize_text(message)
    if not text:
        return 0
    return sum(1 for _ in URL_REGEX.finditer(text))


def anonymize_origin_url(url: str) -> str:
    """
    Sustituye el dominio de una URL por [DOMAIN], manteniendo
    protocolo, ruta, query y fragment.
    Args:
        url (str): La URL a anonimizar.
    Returns:
        str: La URL con el dominio anonimizado.
    """
    text = normalize_text(url)
    parsed = urlparse(text)

    # Si no hay netloc (URL mal formada), devolver anonimizada
    if not parsed.netloc:
        return "[DOMAIN]"

    anonymized_netloc = "[DOMAIN]"

    return urlunparse(
        (
            parsed.scheme,
            anonymized_netloc,
            parsed.path,
            parsed.params,
            parsed.query,
            parsed.fragment,
        )
    )


def mask_emails_in_message(message: str) -> str:
    """
    Sustituye emails detectados en el texto por [EMAIL].
    Args:
        message (str): El texto a procesar.
    Returns:
        str: El texto con los emails enmascarados.
    """
    text = normalize_text(message)
    return EMAIL_REGEX.sub("[EMAIL]", text)


def email_count(message: str) -> int:
    """
    Cuenta cuántos emails detecta en el texto usando EMAIL_REGEX.
    Args:
        message (str): El texto a procesar.
    Returns:
        int: El número de emails detectados.
    """
    text = normalize_text(message)
    if not text:
        return 0

    return sum(1 for _ in EMAIL_REGEX.finditer(text))
