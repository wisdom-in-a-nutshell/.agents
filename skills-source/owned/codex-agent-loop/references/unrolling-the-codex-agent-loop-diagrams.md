# Unrolling The Codex Agent Loop Diagrams

Source:

- `https://openai.com/index/unrolling-the-codex-agent-loop/`

These Mermaid diagrams are faithful structural reconstructions of the article's five main visuals. They preserve the logic and teaching intent of the original diagrams, not the exact illustration style.

## 1. Agent Loop

```mermaid
flowchart LR
    U[User Input] --> P[Prompt Assembly]
    P --> M[Model Inference]
    M --> D{Model Output}
    D -->|assistant message| A[Assistant Message]
    D -->|tool call| T[Tool Execution]
    T --> O[Tool Observation]
    O --> R[Append Result To Prompt]
    R --> M
    A --> X[Turn Ends]
```

What it teaches:

- the model does not always answer directly
- tool use is part of the loop
- tool results feed back into the next model call

## 2. Multi-Turn Agent Loop

```mermaid
flowchart TB
    subgraph T1[Turn 1]
        U1[User Message]
        P1[Prompt With History So Far]
        M1[Model + Tool Loop]
        A1[Assistant Message]
        U1 --> P1 --> M1 --> A1
    end

    A1 --> H[Conversation History Grows]

    subgraph T2[Turn 2]
        U2[Next User Message]
        P2[Prompt = Prior History + New Message]
        M2[Model + Tool Loop]
        A2[Assistant Message]
        U2 --> P2 --> M2 --> A2
    end

    H --> P2
```

What it teaches:

- threads persist across turns
- every new turn includes prior conversation history
- prompt size grows over time

## 3. Snapshot 1: Initial Prompt To First Tool Call

```mermaid
flowchart LR
    S[Server System Message]
    T[Tools]
    I[Instructions]
    N[Input Items]

    S --> P[Composed Prompt]
    T --> P
    I --> P
    N --> P

    P --> M[Model]
    M --> TH[Thought]
    M --> FC[Function Call]
    FC --> FN[Tool Name]
    FC --> FA[Tool Input]
```

What it teaches:

- prompt assembly includes multiple structured layers
- the first model step can end in a tool request instead of a user-facing answer

## 4. Snapshot 2: Tool Result Appended Back Into Prompt

```mermaid
flowchart LR
    P0[Original Prompt]
    R[Reasoning Item]
    C[Function Call Item]
    O[Function Call Output]

    P0 --> P1[Expanded Prompt]
    R --> P1
    C --> P1
    O --> P1

    P1 --> M[Model]
    M --> TH[Updated Thought]
    M --> NX[Next Action]
```

What it teaches:

- the old prompt remains an exact prefix
- new items are appended after tool use
- the next model call reasons over the previous state plus the new observation

## 5. Snapshot 3: Final Answer And Next Turn Hand-Off

```mermaid
flowchart LR
    P[Expanded Prompt With Tool Results]
    P --> M[Model]
    M --> TH[Final Thought]
    M --> A[Assistant Answer]
    A --> U[User Sees Result]
    U --> N[Next User Message]
    N --> P2[Next Turn Prompt = Previous History + New Message]
```

What it teaches:

- a turn ends with an assistant message
- the next user message starts a new turn
- prior turn artifacts remain part of the ongoing thread state

## Applying These Diagrams

- Use the thread/turn model when reasoning about long-lived personal assistants.
- Keep base assistant identity stable across turns.
- Treat local memory and context as information appended around the loop, not as a replacement for the loop.
- When boot behavior changes by mode or repository, prefer a local routing layer over rewriting the whole base prompt.
