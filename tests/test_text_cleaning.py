import pytest

from process_data import (
    anonymize_name,
    anonymize_origin_url,
    email_count,
    email_to_domain,
    mask_emails_in_message,
    mask_phones_in_message,
    mask_urls_in_message,
    normalize_text,
    phone_count,
)


@pytest.mark.parametrize(
    "value,expected",
    [
        (None, ""),
        ("", ""),
        ("   ", ""),
        (" NaN ", ""),
        (" none ", ""),
        ("hola", "hola"),
        (123, "123"),
    ],
)
def test_normalize_text(value, expected):
    assert normalize_text(value) == expected


def test_anonymize_name_empty_is_empty():
    assert anonymize_name("") == ""
    assert anonymize_name(None) == ""


@pytest.mark.parametrize(
    "text,expected",
    [
        ("Mira https://www.dominiodeejemplo.es/contacto/ y dime", "Mira [URL] y dime"),
        ("Visita www.google.com ahora", "Visita [URL] ahora"),
        ("Te dejo dominiodeejemplo.es/contacto para verlo", "Te dejo [URL] para verlo"),
    ],
)
def test_mask_urls_in_message_masks_urls(text, expected):
    assert mask_urls_in_message(text) == expected


def test_mask_urls_in_message_does_not_touch_emails():
    text = "Mi email es rocio@gmail.com (no debería tocarlo)"
    assert mask_urls_in_message(text) == text


def test_mask_emails_in_message_and_count():
    text = "Contacta a rocio@gmail.com y a test+1@acme.co.uk"
    assert mask_emails_in_message(text) == "Contacta a [EMAIL] y a [EMAIL]"
    assert email_count(text) == 2


def test_mask_phones_in_message_and_count():
    text = "Llámame al +34 600 123 456 o al 911-223-344"
    assert mask_phones_in_message(text) == "Llámame al [PHONE] o al [PHONE]"
    assert phone_count(text) == 2


def test_email_to_domain():
    assert email_to_domain("rocio@gmail.com") == "gmail.com"
    assert email_to_domain("") == ""
    assert email_to_domain("no-es-email") == ""


@pytest.mark.parametrize(
    "url,expected",
    [
        ("https://www.dominiodeejemplo.es/contacto/", "https://[DOMAIN]/contacto/"),
        ("dominiodeejemplo.es/contacto/", "[DOMAIN]"),
        ("http://localhost:8000/test", "http://[DOMAIN]/test"),
    ],
)
def test_anonymize_origin_url(url, expected):
    assert anonymize_origin_url(url) == expected
