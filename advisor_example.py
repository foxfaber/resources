"""
Esempio: advisor tool della Claude API (beta).

- Executor: claude-sonnet-5-5 (economico, genera quasi tutti i token)
- Advisor:  claude-opus-5-5   (più capace, consultato solo quando serve)

Requisiti:  pip install -U anthropic
Credenziali: ANTHROPIC_API_KEY oppure `ant auth login`.
"""

import anthropic

EXECUTOR = "claude-sonnet-5-5"
ADVISOR = "claude-opus-5-5"

BETAS = [
    "advisor-tool-2026-03-01",
    "server-side-fallback-2026-07-01",  # fallback automatico in caso di refusal
]

ADVISOR_TOOL = {
    "type": "advisor_20260301",
    "name": "advisor",
    "model": ADVISOR,
    "max_uses": 3,  # al massimo 3 consultazioni per richiesta
    "caching": {"type": "ephemeral", "ttl": "5m"},  # cache del prompt dell'advisor
}

# Sonnet 5.5 non accetta tool_choice forzato: si guida l'uso dell'advisor dal prompt.
SYSTEM = (
    "Sei un assistente tecnico. Prima di pianificare un lavoro complesso o di "
    "prendere una decisione difficile, consulta il tool `advisor`. Per le parti "
    "semplici procedi da solo, senza consultarlo."
)

client = anthropic.Anthropic()


def ask(messages: list) -> anthropic.types.beta.BetaMessage:
    """Esegue un turno completo, gestendo pause_turn (turni lunghi interrotti dal server)."""
    while True:
        with client.beta.messages.stream(
            model=EXECUTOR,
            max_tokens=64000,
            betas=BETAS,
            fallbacks="default",
            system=SYSTEM,
            output_config={"effort": "medium"},
            tools=[ADVISOR_TOOL],
            messages=messages,
        ) as stream:
            response = stream.get_final_message()

        # Rimanda SEMPRE l'intero content (anche i blocchi dell'advisor).
        messages.append({"role": "assistant", "content": response.content})

        if response.stop_reason == "pause_turn":
            continue  # il server ha messo in pausa: si riprende rimandando la cronologia
        return response


def show(response) -> None:
    if response.stop_reason == "refusal":
        print("Richiesta rifiutata:", response.stop_details)
        return

    for block in response.content:
        if block.type == "text":
            print(block.text)
        elif block.type == "advisor_tool_result":
            c = block.content
            if c.type == "advisor_result":  # advisor che restituisce testo in chiaro
                print(f"\n[advisor] {c.text}\n")
            elif c.type == "advisor_redacted_result":  # Opus 5.5: consiglio cifrato
                print("\n[advisor consultato — consiglio cifrato, usato dall'executor]\n")
            elif c.type == "advisor_tool_result_error":
                print(f"\n[advisor errore: {c.error_code}]\n")

    print("\nUsage:", response.usage)


if __name__ == "__main__":
    messages = [
        {
            "role": "user",
            "content": "Progetta uno schema di database per una piattaforma di "
            "self-publishing che traccia vendite, royalty e pagine lette per "
            "libro, serie e marketplace. Poi scrivi le CREATE TABLE in PostgreSQL.",
        }
    ]
    show(ask(messages))

    # Secondo turno: la cronologia (con i blocchi advisor) è già in `messages`.
    messages.append({"role": "user", "content": "Aggiungi gli indici per le query mensili."})
    show(ask(messages))
