import pandas as pd
import re

from utils.text_cleaning import (
    anonymize_name,
    email_to_domain,
    mask_emails_in_message,
    mask_urls_in_message,
    mask_phones_in_message,
    email_count,
    phone_count,
    url_count,
    anonymize_origin_url,
)

INPUT_PATH = "../data/raw/data.csv"
OUTPUT_PATH_INTERIM = "../data/interim/data_clean.csv"
OUTPUT_PATH_FINAL = "../data/processed/data_clean.csv"

COLUMN_RENAME_MAP = {
    "Nombre": "name",
    "Email": "email",
    "Mensaje": "message",
    "ID Entrada": "entry_id",
    "Fecha entrada": "entry_date",
    "URL de origen": "origin_url",
    "Agente de usuario": "user_agent",
    "IP del usuario": "user_ip",
    "Submission Speed (ms)": "submission_speed_ms",
}

OUTPUT_COLS = [
    "entry_id",
    "entry_date",
    "name_anon",
    "email_domain",
    "message_clean",
    "origin_url_anon",
    "user_agent",
    "user_ip",
    "submission_speed_ms",
    "email_count_msg",
    "phone_count_msg",
    "url_count_msg",
]

df = pd.read_csv(INPUT_PATH)
# print("(Filas, Columnas): ", df.shape)
# print("Filas:", len(df))
# print("Columnas:", list(df.columns))
# print(df.head(3))

df = df.rename(columns=COLUMN_RENAME_MAP)
df["name_anon"] = df["name"].apply(anonymize_name)
df["email_domain"] = df["email"].apply(email_to_domain)
df["email_count_msg"] = df["message"].apply(email_count)
df["phone_count_msg"] = df["message"].apply(phone_count)
df["url_count_msg"] = df["message"].apply(url_count)
df["message_clean"] = (
    df["message"]
    .apply(mask_emails_in_message)
    .apply(mask_urls_in_message)
    .apply(mask_phones_in_message)
    .apply(
        lambda x: re.sub(r"\s+", " ", x).strip()
    )  # Eliminar espacios extra entre el mensaje
)

# Columnas después de procesamiento:
# print("Columnas:", list(df.columns))

df["origin_url_anon"] = df["origin_url"].apply(anonymize_origin_url)

# Verificar resultado del procesamiento
# print(
#     df[
#         [
#             "name",
#             "name_anon",
#             "email",
#             "email_domain",
#             "message",
#             "message_clean",
#             "email_count_msg",
#             "phone_count_msg",
#             "origin_url",
#             "origin_url_anon",
#         ]
#     ].head(5)
# )

df[OUTPUT_COLS].to_csv(OUTPUT_PATH_INTERIM, index=False)
print("Saved:", OUTPUT_PATH_INTERIM)

df_processed = df[OUTPUT_COLS].copy()
df_processed["label"] = ""  # después serán: spam/not_spam/doubt/ads

df_processed.to_csv(OUTPUT_PATH_FINAL, index=False)
print("Saved:", OUTPUT_PATH_FINAL)
