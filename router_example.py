"""
Esempio: router che sceglie il modello in base alla complessità della domanda.

1. Claude Haiku 5.5 classifica la domanda: semplice / media / complessa.
2. La domanda va al modello adatto:
     semplice  -> claude-haiku-5-5   (effort low)
     media     -> claude-sonnet-5-5  (effort medium)
     complessa -> claude-opus-5-5    (effort high)
3. Stampa il modello usato e una stima del costo.

Pensato per domande indipendenti (es. assistenza, Q&A). Per conversazioni
lunghe su un unico compito è meglio un solo modello o l'advisor tool:
la cache non è condivisa tra modelli diversi.

Requisiti:  pip install -U anthropic
Credenziali: ANTHROPIC_API_KEY oppure `ant auth login`.
"""

import json

import anthropic

client = anthropic.Anthropic()

CLASSIFIER = "claude-haiku-5-5"

# livello -> (modello, effort)
ROUTES = {
    "semplice": ("claude-haiku-5-5", "low"),
    "media": ("claude-sonnet-5-5", "medium"),
    "complessa": ("claude-opus-5-5", "high"),
}
DEFAULT_LEVEL = "media"  # se la classificazione fallisce

# Prezzi in $ per 1M token (input, output) - Claude API, novembre 2026.
# Haiku 5.5: prezzo valido per prompt fino a 100K token.
PRICES = {
    "claude-haiku-5-5": (0.10, 0.50),
    "claude-sonnet-5-5": (2.00, 10.00),
    "claude-opus-5-5": (4.00, 20.00),
}

# Fallback automatico in caso di refusal: disponibile per Sonnet 5.5 e Opus 5.5,
# non per Haiku 5.5.
FALLBACK_MODELS = {"claude-sonnet-5-5", "claude-opus-5-5"}

CLASSIFIER_SYSTEM = """Classifica la complessità della domanda dell'utente.

- semplice: risposta breve o fattuale, definizioni, traduzioni, riformulazioni,
  piccoli calcoli, domande con una risposta nota.
- media: spiegazioni articolate, testi di media lunghezza, codice di routine,
  analisi con pochi passaggi.
- complessa: ragionamento in molti passaggi, architetture e progettazione,
  debugging difficile, matematica non banale, analisi strategiche, testi lunghi
  che richiedono pianificazione.

Nel dubbio tra due livelli scegli quello più alto."""

CLASSIFIER_SCHEMA = {
    "type": "object",
    "properties": {
        "livello": {"type": "string", "enum": list(ROUTES)},
        "motivo": {"type": "string"},
    },
    "required": ["livello", "motivo"],
    "additionalProperties": False,
}


def cost(model: str, usage) -> float:
    price_in, price_out = PRICES[model]
    input_tokens = (
        usage.input_tokens
        + (usage.cache_creation_input_tokens or 0)
        + (usage.cache_read_input_tokens or 0)
    )
    return (input_tokens * price_in + usage.output_tokens * price_out) / 1_000_000


def classify(question: str) -> tuple[str, str, float]:
    """Restituisce (livello, motivo, costo della classificazione)."""
    try:
        response = client.messages.create(
            model=CLASSIFIER,
            max_tokens=2048,
            system=CLASSIFIER_SYSTEM,
            output_config={
                "effort": "low",
                "format": {"type": "json_schema", "schema": CLASSIFIER_SCHEMA},
            },
            messages=[{"role": "user", "content": question}],
        )
    except anthropic.APIError as e:
        return DEFAULT_LEVEL, f"classificatore non disponibile ({e.__class__.__name__})", 0.0

    spent = cost(CLASSIFIER, response.usage)
    if response.stop_reason != "end_turn":  # refusal, max_tokens, ...
        return DEFAULT_LEVEL, f"classificazione non riuscita ({response.stop_reason})", spent

    text = next(b.text for b in response.content if b.type == "text")
    data = json.loads(text)
    return data["livello"], data["motivo"], spent


def answer(question: str, model: str, effort: str):
    kwargs = dict(
        model=model,
        max_tokens=64000,
        output_config={"effort": effort},
        messages=[{"role": "user", "content": question}],
    )
    if model in FALLBACK_MODELS:
        kwargs["betas"] = ["server-side-fallback-2026-07-01"]
        kwargs["fallbacks"] = "default"

    # Streaming: evita i timeout sulle risposte lunghe.
    with client.beta.messages.stream(**kwargs) as stream:
        return stream.get_final_message()


def ask(question: str) -> str:
    level, reason, classify_cost = classify(question)
    model, effort = ROUTES[level]

    response = answer(question, model, effort)
    answer_cost = cost(model, response.usage)

    print(f"\n=== {question[:70]}")
    print(f"Livello: {level} ({reason})")
    print(f"Modello: {model}, effort {effort}")
    if response.model != model:
        print(f"(risposta servita da {response.model} per fallback)")
    print(
        f"Costo stimato: ${classify_cost + answer_cost:.5f} "
        f"(classificazione ${classify_cost:.5f} + risposta ${answer_cost:.5f})"
    )

    if response.stop_reason == "refusal":
        return f"[Richiesta rifiutata: {response.stop_details}]"
    return "".join(b.text for b in response.content if b.type == "text")


if __name__ == "__main__":
    questions = [
        "Come si dice 'royalty' in italiano?",
        "Spiegami la differenza tra KDP Select e la distribuzione ampia per un ebook.",
        "Progetta una strategia di lancio in 90 giorni per una serie fantasy di 3 "
        "libri, con budget pubblicitario limitato, ottimizzando il read-through.",
    ]
    for q in questions:
        print(ask(q))
