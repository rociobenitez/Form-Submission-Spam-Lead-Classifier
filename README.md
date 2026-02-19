# Spam Classifier

### Estructura del proyecto

```
gf-spam-classifier/
├─ README.md
├─ pyproject.toml            # (o requirements.txt si prefieres)
├─ .gitignore
├─ data/
│  ├─ raw/                   # CSV exportado desde Gravity Forms (sin tocar)
│  ├─ interim/               # datos limpiados, normalizados, fusionados
│  └─ processed/             # dataset final para entrenar (X/y)
├─ models/
│  ├─ artifacts/             # model.joblib, vectorizer.joblib, metadata.json
│  └─ reports/               # métricas, matriz de confusión, etc.
├─ src/
│  ├─ __init__.py
│  ├─ config.py              # paths, seeds, etiquetas, thresholds
│  ├─ preprocessing/
│  │  ├─ __init__.py
│  │  └─ text_cleaning.py    # limpieza + normalización texto
│  ├─ dataset/
│  │  ├─ __init__.py
│  │  └─ build_dataset.py    # cargar CSV(s) y generar "text" + "label"
│  ├─ training/
│  │  ├─ __init__.py
│  │  ├─ train.py            # entrenar y guardar artefactos
│  │  └─ evaluate.py         # métricas + reportes + errores típicos
│  ├─ inference/
│  │  ├─ __init__.py
│  │  └─ predict.py          # predecir sobre un CSV nuevo
│  └─ utils/
│     ├─ __init__.py
│     └─ io.py               # lectura/escritura CSV, validaciones, logs
└─ tests/
   ├─ test_text_cleaning.py
   └─ test_training_smoke.py
```

## Definición del proyecto

**Entrada**

Un CSV exportado de Gravity Forms con campos típicos: nombre, email, teléfono, mensaje, asunto, etc.

**Salida**

- Métricas (classification_report)
- Un archivo predictions.csv con:
  - `id` (si existe)
  - `text` (texto consolidado)
  - `pred_label`
  - `confidence` (si LogisticRegression)
  - `true_label` (si estaba etiquetado)
  - `is_correct` (para revisar rápido)
- Un modelo guardado (vectorizador + clasificador)

## Dataset inicial

200 ejemplos para arrancar (mejor 300).

Balance aproximado:

- 60–80 spam
- 40–60 publicidad
- 60–80 lead útil
- 20–40 duda (puedes crear “duda” solo como salida, pero al inicio yo la usaría también como etiqueta si hay casos ambiguos)

> 3 clases al entrenar (lead/spam/publicidad) y “duda” como resultado por umbral.

### Normas claras de etiquetado (consistencia)

- `lead`: intención clara de contacto por servicio del cliente
- `publicidad`: oferta de servicios externos (“te hago SEO”, “marketing”, “guest post”)
- `spam`: basura/estafa/irrelevante/automatizado

Ambiguos: como `lead` o `publicidad` según intención principal, y confiar en el umbral `duda` en inferencia.

### Umbrales para “duda”

Si entrenamos con LogisticRegression:

- confidence >= 0.70 → etiqueta final
- confidence <= 0.40 → etiqueta final (si la clase gana con margen)
- entre 0.40 y 0.70 → duda

Así reducimos falsos positivos.

## Fuentes

### Fuente 1: Exportar datos reales de Gravity Forms

- Exportación de entries de los últimos X meses del/los clientes con más volumen.
- Meter el CSV en data/raw/.

Privacidad: si usamos datos reales, minimizamos riesgos:

- En text_cleaning.py, reemplazamos emails/teléfonos/URLs por tokens: [EMAIL], [PHONE], [URL]
  - Esto reduce overfitting y permite compartir el repo sin datos sensibles.

**Campos exportados:**

- ID Entrada
- Nombre
- Email
- Mensaje
- Fecha entrada
- URL de origen
- Agente de usuario
- IP del usuario
- Submission Speed (tiempo entre cargar formulario y enviar)

Ejemplo:

- submission speed < 1000 ms → sospechoso (bot)
- agente de usuario raro → sospechoso
- muchas IP repetidas → patrón

### Fuente 2: dataset “semiautomático” con reglas para pre-etiquetar (y tú solo revisas)

Para acelerar el etiquetado, hacemos un pre-labeling por heurísticas:

- si contiene >2 URLs → probable spam/publicidad
- si contiene palabras típicas (“SEO”, “backlinks”, “guest post”, “crypto”, “investment”, “rank your website”) → publicidad/spam
- si email dominio raro + texto genérico → spam

Luego revisamos y corregimos.

### Fuente 3: “negativos” fáciles (spam)

En muchos casos tienes spam muy obvio. Etiquetado rápido:

- mensajes con enlaces
- mensajes en inglés genérico tipo “Hello dear”
- mensajes que ofrecen servicios SEO

Ese spam nos ayuda a que el baseline salga fuerte desde el principio.

## Limpieza

El script `sanitize_raw_csv.py` hace:

- Lee el CSV exportado de Gravity Forms
- Genera data-sanitized.csv con:
  - `email_domain` (solo el dominio: gmail.com, empresa.com…)
  - `message_sanitized` (con [EMAIL], [URL], [PHONE])
  - `name_sanitized` (limpio básico)
  - `text` (columna final para ML: nombre + dominio + mensaje sanitizado)
- Genera labeling.csv listo para etiquetar manualmente con columnas:
  - `row_id`
  - `text`
  - `label` (vacía para rellenarla)

Ejecuta:

```bash
python src/utils/sanitize_raw_csv.py \
  --input data/raw/data.csv \
  --out-sanitized data/processed/data-sanitized.csv \
  --out-labeling data/interim/labeling.csv
```

Abre `data/interim/labeling.csv` con Excel/Sheets y rellena `label` con:

- `lead`
- `spam`
- `publicidad`

## Reglas de etiquetado

- SPAM si:
  - submission speed < 1500 ms
  - contiene más de 1 URL
  - contiene palabras tipo:
    - "seo"
    - "backlinks"
    - "crypto"
    - "investment"
    - "rank your website"
    - "guest post"
- PUBLICIDAD si:
  - ofrece servicios
  - incluye precios
  - tono comercial claro
- LEAD si:
  - menciona servicio real del cliente
  - pregunta por presupuesto
  - usa contexto coherente con la web
