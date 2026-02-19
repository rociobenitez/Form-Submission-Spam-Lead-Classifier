#!/usr/bin/env python3

"""
- Lee CSV exportado de Gravity Forms.
- Sanitiza PII: emails -> [EMAIL], urls -> [URL], phones -> [PHONE]
- Genera:
  1) data-sanitized.csv (para entrenar)
  2) labeling.csv con pre-etiquetado heurístico:
     row_id, text, auto_label, auto_score, auto_reasons, label (vacío)

Uso:
python utils/sanitize_raw_csv.py \
  --input data/raw/gravity_export.csv \
  --out-sanitized data/processed/data-sanitized.csv \
  --out-labeling data/interim/labeling.csv
"""

from __future__ import annotations

import argparse
import re
from pathlib import Path
from typing import List, Tuple

import pandas as pd


# -----------------------------
# Regex de sanitización
# -----------------------------
EMAIL_REGEX = re.compile(r"\b[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}\b", re.IGNORECASE)

URL_REGEX = re.compile(
    r"(?i)\b((?:https?://|www\.)\S+|\b[a-z0-9-]+\.(?:com|es|net|org|io|co|info|biz)\b\S*)"
)

PHONE_REGEX = re.compile(r"(?<!\d)(?:\+?\d[\d\s().-]{7,}\d)(?!\d)")

URL_COUNT_REGEX = re.compile(r"(?i)(https?://|www\.)")


# -----------------------------
# Heurísticas
# -----------------------------
SPAM_KEYWORDS = [
    "crypto", "investment", "forex", "bitcoin", "loan", "casino", "betting",
    "escort", "adult", "viagra", "pharmacy", "click here", "earn money",
]
AD_KEYWORDS = [
    "seo", "backlink", "backlinks", "guest post", "guestposting", "link building",
    "marketing", "rank your website", "google ranking", "traffic", "outreach",
    "press release", "advertising", "ads", "agency",
    "posicionamiento", "seo", "linkbuilding", "marketing", "agencia", "presupuesto seo",
]

# submission speed (ms)
BOT_SPEED_MS_THRESHOLD = 1500  # ajustar si hay muchos falsos positivos


def normalize_spaces(text: str) -> str:
    """Normaliza espacios repetidos y recorta."""
    return re.sub(r"\s+", " ", text).strip()


def extract_email_domain(email: str) -> str:
    """Extrae el dominio del email. Si no es válido, devuelve vacío."""
    if not isinstance(email, str):
        return ""
    email = email.strip().lower()
    if "@" not in email:
        return ""
    domain = email.split("@")[-1]
    # Limpiar casos raros con caracteres finales
    domain = re.sub(r"[^\w.-]", "", domain)
    return domain


def sanitize_text(text: str) -> str:
    """
    Sustituye:
    - Emails por [EMAIL]
    - URLs por [URL]
    - Teléfonos por [PHONE]
    y normaliza espacios.
    """
    if not isinstance(text, str):
        return ""

    t = text
    t = EMAIL_REGEX.sub("[EMAIL]", t)
    t = URL_REGEX.sub("[URL]", t)
    t = PHONE_REGEX.sub("[PHONE]", t)
    t = t.lower()
    t = normalize_spaces(t)
    return t


def coalesce_str(df: pd.DataFrame, col: str) -> pd.Series:
    """Devuelve la columna como string seguro (sin NaN)"""
    if col not in df.columns:
        # si no existe, devolvemos serie vacía
        return pd.Series([""] * len(df))
    return df[col].fillna("").astype(str)


def build_text_field(
    name_s: str,
    email_domain: str,
    message_s: str,
    include_domain: bool = True,
) -> str:
    """
    Construye el campo 'text' que alimentará al modelo.
    Esto es lo que entrenas con TF-IDF.
    """
    parts = []
    if name_s:
        parts.append(name_s)
    if include_domain and email_domain:
        parts.append(email_domain)
    if message_s:
        parts.append(message_s)
    return normalize_spaces(" ".join(parts))



def contains_any(text: str, keywords: List[str]) -> List[str]:
    hits = []
    for kw in keywords:
        if kw in text:
            hits.append(kw)
    return hits


def heuristic_label(row: dict) -> Tuple[str, float, str]:
    """
    Devuelve:
      auto_label: spam | publicidad | lead | unknown
      auto_score:  0..1
      auto_reasons: string con motivos
    """
    reasons: List[str] = []
    score = 0.0

    text = row.get("text", "") or ""
    message_raw = row.get("message_raw", "") or ""
    message_sanitized = row.get("message_sanitized", "") or ""
    user_agent = row.get("user_agent", "") or ""
    speed_ms = row.get("submission_speed_ms", "")

    # Cuenta URLs antes de sanitizar (más fiable)
    url_count_raw = len(URL_REGEX.findall(message_raw))

    # Cuenta tokens [URL] después de sanitizar (útil también)
    url_count_token = message_sanitized.count("[URL]")

    url_count = max(url_count_raw, url_count_token)
    if url_count >= 2:
        score += 0.50
        reasons.append(f"many_urls({url_count})")
    elif url_count == 1:
        score += 0.20
        reasons.append("one_url")

    # Palabras clave
    spam_hits = contains_any(text, SPAM_KEYWORDS)
    if spam_hits:
        score += 0.50
        reasons.append(f"spam_keywords({','.join(spam_hits[:5])})")

    ad_hits = contains_any(text, AD_KEYWORDS)
    if ad_hits:
        score += 0.45
        reasons.append(f"ad_keywords({','.join(ad_hits[:5])})")

    # Submission speed
    speed_val = None
    speed_str = str(speed_ms).strip()

    if speed_str:
        try:
            # Caso 1: número directo
            speed_val = int(float(speed_str.replace(",", "")))
        except Exception:
            # Caso 2: JSON-like -> extraer el primer número que aparezca
            m = re.search(r"\d+", speed_str)
            if m:
                speed_val = int(m.group(0))

    # User-Agent sospechoso (muy básico)
    ua_lower = (user_agent or "").lower()
    if ua_lower and any(x in ua_lower for x in ["python", "curl", "wget", "bot", "spider", "scrapy"]):
        score += 0.30
        reasons.append("suspicious_user_agent")

    # Decisión de etiqueta:
    # - Si hay señales de spam -> spam
    # - Si hay señales de publicidad -> publicidad
    # - Si no hay señales -> unknown (no asumimos lead para no contaminar)
    # - Si ambas (ad + spam) -> spam (más conservador)
    auto_label = "unknown"

    has_spam_signal = any(r.startswith("spam_keywords") for r in reasons) or any(r.startswith("many_urls") for r in reasons)
    has_ad_signal = any(r.startswith("ad_keywords") for r in reasons)

    if has_spam_signal and has_ad_signal:
        auto_label = "spam"
        reasons.append("tie_breaker=spam")
    elif has_spam_signal:
        auto_label = "spam"
    elif has_ad_signal:
        auto_label = "publicidad"
    else:
        auto_label = "unknown"

    # Cap score
    score = min(score, 1.0)

    return auto_label, score, ";".join(reasons)


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Sanitiza CSV de Gravity Forms y genera labeling con auto_label.")
    p.add_argument("--input", required=True, help="CSV raw exportado de Gravity Forms.")
    p.add_argument("--out-sanitized", required=True, help="Salida CSV sanitizado.")
    p.add_argument("--out-labeling", required=True, help="Salida CSV para etiquetar manualmente.")
    p.add_argument("--col-id", default="ID Entrada")
    p.add_argument("--col-name", default="Nombre")
    p.add_argument("--col-email", default="Email")
    p.add_argument("--col-message", default="Mensaje")
    p.add_argument("--col-user-agent", default="Agente de usuario")
    p.add_argument("--col-speed", default="Submission Speed (ms)")
    p.add_argument("--keep-all-columns", action="store_true")
    return p.parse_args()


def main() -> None:
    args = parse_args()

    input_path = Path(args.input)
    out_sanitized = Path(args.out_sanitized)
    out_labeling = Path(args.out_labeling)

    out_sanitized.parent.mkdir(parents=True, exist_ok=True)
    out_labeling.parent.mkdir(parents=True, exist_ok=True)

    # CSV separator robust: primero coma, si falla ;.
    try:
        df = pd.read_csv(input_path)
    except Exception:
        df = pd.read_csv(input_path, sep=";")

    s_id = coalesce_str(df, args.col_id)
    s_name = coalesce_str(df, args.col_name)
    s_email = coalesce_str(df, args.col_email)
    s_message = coalesce_str(df, args.col_message)
    s_ua = coalesce_str(df, args.col_user_agent)
    s_speed = coalesce_str(df, args.col_speed)

    email_domain = s_email.apply(extract_email_domain)

    name_sanitized = s_name.apply(sanitize_text)
    message_sanitized = s_message.apply(sanitize_text)

    text = [
        build_text_field(n, d, m)
        for n, d, m in zip(name_sanitized, email_domain, message_sanitized)
    ]

    # Dataset sanitizado
    base_cols = {
        "row_id": s_id,
        "name_sanitized": name_sanitized,
        "email_domain": email_domain,
        "message_raw": s_message,
        "message_sanitized": message_sanitized,
        "user_agent": s_ua.astype(str).str.lower(),
        "submission_speed_ms": s_speed,
        "text": text,
    }

    if args.keep_all_columns:
        df_out = df.copy()
        for k, v in base_cols.items():
            df_out[k] = v
    else:
        df_out = pd.DataFrame(base_cols)

    df_out.to_csv(out_sanitized, index=False)

    # Labeling con auto_label
    labeling_df = pd.DataFrame(
        {
            "row_id": s_id,
            "text": text,
            "auto_label": [""] * len(df),
            "auto_score": [0.0] * len(df),
            "auto_reasons": [""] * len(df),
            "label": [""] * len(df),  # aquí corriges tú manualmente
        }
    )

    # Aplicar heurísticas
    for idx in range(len(labeling_df)):
        row = {
            "text": labeling_df.at[idx, "text"],
            "message_raw": df_out.at[idx, "message_raw"],
            "message_sanitized": df_out.at[idx, "message_sanitized"],
            "user_agent": df_out.at[idx, "user_agent"],
            "submission_speed_ms": df_out.at[idx, "submission_speed_ms"],
        }
        al, sc, rs = heuristic_label(row)
        labeling_df.at[idx, "auto_label"] = al
        labeling_df.at[idx, "auto_score"] = sc
        labeling_df.at[idx, "auto_reasons"] = rs

    labeling_df.to_csv(out_labeling, index=False)

    print(f"OK. Sanitized saved to: {out_sanitized}")
    print(f"OK. Labeling saved to: {out_labeling}")
    print("Siguiente paso: abre labeling.csv y rellena la columna 'label' con: lead | spam | publicidad")


if __name__ == "__main__":
    main()
