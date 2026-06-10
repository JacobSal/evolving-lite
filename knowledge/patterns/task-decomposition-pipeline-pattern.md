---
template_version: "1.0"
template_type: pattern
title: "Task Decomposition Pipeline"
type: pattern
category: architecture
created: 2024-12-09
source: Dexter (virattt/dexter)
confidence: 90%
tags: [multi-agent, autonomous, research, planning, execution]
use_cases: [complex-queries, research-tasks, multi-step-analysis, advisory-systems]
complexity: high
---

# Task Decomposition Pipeline

## Problem

**Komplexe Anfragen werden oberflächlich oder unvollständig beantwortet.**

**Context**:
- User stellt eine Frage die mehrere Aspekte hat
- KI versucht alles in einem Durchgang zu beantworten
- Wichtige Teile werden vergessen oder übersprungen
- Keine systematische Datensammlung

**Symptoms**:
- Antworten sind oberflächlich trotz detaillierter Frage
- Teile der Frage werden ignoriert
- Keine konkreten Zahlen oder Daten
- Inkonsistente Qualität bei ähnlichen Anfragen

**Why this is a problem**:
Bei beratungsintensiven Themen (Steuern, Finanzen, Recht) brauchen Nutzer vollständige, fundierte Antworten. Eine oberflächliche Antwort kann zu falschen Entscheidungen führen und Vertrauen zerstören.

---

## Solution

**Task Decomposition Pipeline** löst das durch systematische Zerlegung in Phasen: Erst planen, dann ausführen, dann zusammenfassen.

### Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                         User Query                              │
│     "Vergleiche Steuern in Portugal vs Zypern für Freelancer"   │
└────────────────────────────┬────────────────────────────────────┘
                             │
                             ▼
┌─────────────────────────────────────────────────────────────────┐
│                     PHASE 1: PLANNER                            │
│                                                                 │
│  Input: User Query                                              │
│  Output: Liste von High-Level Tasks                             │
│                                                                 │
│  Beispiel-Output:                                               │
│  ├── Task 1: Portugal Steuersystem für Freelancer recherchieren │
│  ├── Task 2: Zypern Steuersystem für Freelancer recherchieren   │
│  ├── Task 3: Konkrete Steuerberechnung für beide Länder         │
│  └── Task 4: Vergleich erstellen mit Empfehlung                 │
└────────────────────────────┬────────────────────────────────────┘
                             │
                             ▼
┌─────────────────────────────────────────────────────────────────┐
│                    PHASE 2: EXECUTOR                            │
│                                                                 │
│  Für jeden Task:                                                │
│  1. Subtasks identifizieren (welche Tools/Quellen?)             │
│  2. Tools aufrufen und Daten sammeln                            │
│  3. Ergebnisse speichern (Context Management)                   │
│  4. Validieren ob vollständig                                   │
│                                                                 │
│  Task 1 → Subtasks:                                             │
│  ├── Knowledge Base: "Portugal NHR Regime"                      │
│  ├── Tool: get_tax_info("Portugal", "freelancer")               │
│  └── Tool: calculate_tax("Portugal", income=80000)              │
└────────────────────────────┬────────────────────────────────────┘
                             │
                             ▼
┌─────────────────────────────────────────────────────────────────┐
│                   PHASE 3: SYNTHESIZER                          │
│                                                                 │
│  Input: Alle gesammelten Daten aus Phase 2                      │
│  Output: Strukturierte, fundierte Antwort                       │
│                                                                 │
│  - Fasst alle Recherche-Ergebnisse zusammen                     │
│  - Erstellt Vergleichstabellen                                  │
│  - Gibt konkrete Empfehlung mit Begründung                      │
│  - Nennt nächste Schritte                                       │
└─────────────────────────────────────────────────────────────────┘
```

### Components

**1. Planner Agent**
- **Role**: Zerlegt komplexe Anfragen in bearbeitbare Tasks
- **Responsibilities**:
  - Query analysieren und verstehen
  - 1-5 High-Level Tasks erstellen
  - Sicherstellen dass alle Aspekte abgedeckt sind
- **Key Features**:
  - Erstellt ZIELE, keine Einzelschritte
  - Jeder Task ist ein "Research Goal"
  - Unabhängig voneinander ausführbar

**2. Executor Agent**
- **Role**: Führt jeden Task systematisch aus
- **Responsibilities**:
  - Task in Subtasks zerlegen
  - Passende Tools/Quellen auswählen
  - Daten sammeln und speichern
  - Selbst-Validierung (sind Daten vollständig?)
- **Key Features**:
  - Agentic Loop (max. 5 Iterationen pro Subtask)
  - Speichert Ergebnisse auf Disk (nicht Memory)
  - Kann bei Fehlern selbst korrigieren

**3. Synthesizer Agent**
- **Role**: Erstellt finale Antwort aus allen Daten
- **Responsibilities**:
  - Relevante Daten auswählen
  - Strukturierte Antwort formulieren
  - Empfehlungen ableiten
- **Key Features**:
  - Lädt nur relevante Contexts
  - Streaming-Output möglich
  - Quellenangaben inkludieren

**4. Context Manager (optional)**
- **Role**: Verwaltet gesammelte Daten
- **Responsibilities**:
  - Speichert Tool-Outputs auf Disk
  - Ermöglicht Query-basiertes Retrieval
  - Verhindert Memory-Overflow

### How It Works

**Step 1: Planning**
```
Input: "Vergleiche Steuern Portugal vs Zypern für 80k Freelancer"

Planner Output:
{
  "tasks": [
    {"id": 1, "description": "Portugal Steuerregime für Freelancer analysieren"},
    {"id": 2, "description": "Zypern Steuerregime für Freelancer analysieren"},
    {"id": 3, "description": "Steuerberechnung für 80.000€ in beiden Ländern"},
    {"id": 4, "description": "Vergleichsmatrix erstellen mit Empfehlung"}
  ]
}
```

**Step 2: Execution (für jeden Task)**
```
Task 1: "Portugal Steuerregime für Freelancer analysieren"

Executor identifiziert Subtasks:
├── Subtask 1.1: Knowledge Base durchsuchen → "NHR Regime Details"
├── Subtask 1.2: Aktuelle Steuersätze holen → 20% flat rate
├── Subtask 1.3: Besonderheiten für Freelancer → keine Sozialabgaben-Pflicht
└── Subtask 1.4: Aufenthaltsbedingungen → 183 Tage Regel

Ergebnisse werden gespeichert:
.context/query_abc123/
├── task1_subtask1_kb_result.json
├── task1_subtask2_tax_rates.json
├── task1_subtask3_freelancer_rules.json
└── task1_subtask4_residency.json
```

**Step 3: Synthesis**
```
Synthesizer lädt alle relevanten Contexts und erstellt:

## Steuervergleich: Portugal vs Zypern (Freelancer, 80.000€)

### Portugal (NHR Regime)
- Steuersatz: 20% flat
- Steuer bei 80k: 16.000€
- Besonderheiten: 10 Jahre gültig, keine Sozialabgaben-Pflicht
- Aufenthalt: min. 183 Tage/Jahr

### Zypern
- Steuersatz: 12.5% Corporate
- Steuer bei 80k: 10.000€ (als Ltd)
- Besonderheiten: Non-Dom Status, 60 Tage Regel möglich
- Aufenthalt: Flexibler

### Empfehlung
Zypern bietet 6.000€/Jahr Ersparnis, aber erfordert Ltd-Gründung...

### Nächste Schritte
1. ...
2. ...
```

---

## Example

### Real-World Implementation: Advisory AI

**Challenge**: Nutzer stellen komplexe Fragen die mehrere Länder, Steuerregime und persönliche Faktoren berücksichtigen müssen.

**Ohne Pipeline**:
```
User: "Wo zahle ich als Freelancer mit 100k€ am wenigsten Steuern in Europa?"

KI: "Es gibt mehrere Optionen wie Portugal, Zypern, Malta..."
→ Oberflächlich, keine konkreten Zahlen, keine Empfehlung
```

**Mit Pipeline**:
```
User: "Wo zahle ich als Freelancer mit 100k€ am wenigsten Steuern in Europa?"

PLANNER:
├── Task 1: Top 5 steuerfreundliche EU-Länder für Freelancer identifizieren
├── Task 2: Für jedes Land konkrete Steuerberechnung
├── Task 3: Aufenthaltsbedingungen und Komplexität bewerten
└── Task 4: Ranking erstellen mit personalisierter Empfehlung

EXECUTOR:
├── Recherchiert jedes Land systematisch
├── Berechnet konkrete Steuerlast
├── Prüft Aufenthaltsbedingungen
└── Speichert alle Daten

SYNTHESIZER:
├── Erstellt Vergleichstabelle mit echten Zahlen
├── Rankt nach Gesamtbelastung
├── Gibt konkrete Empfehlung
└── Nennt Vor-/Nachteile und nächste Schritte

→ Fundierte, vollständige Antwort mit konkreten Zahlen
```

**Results**:
- **Vollständigkeit**: 100% der Frage-Aspekte abgedeckt
- **Konkretheit**: Echte Zahlen statt vage Aussagen
- **Nachvollziehbarkeit**: Jeder Schritt dokumentiert
- **Qualität**: Konsistent hohe Qualität bei jeder Anfrage

---

## Implementation Guide

### Prerequisites

- Multi-Agent Setup (oder sequentielle Prompt-Chains)
- Tool-System (Knowledge Base, Berechnungs-Tools, etc.)
- Optional: Context Storage für große Datenmengen

### Step-by-Step Implementation

**Phase 1: Planner Prompt erstellen**

```markdown
# Planner System Prompt

Du bist ein Research Planner. Deine Aufgabe ist es, komplexe Anfragen
in 1-5 konkrete Research-Tasks zu zerlegen.

REGELN:
- Erstelle ZIELE, keine Einzelschritte
- Jeder Task sollte ein eigenständiges Research-Ziel sein
- Maximal 5 Tasks pro Anfrage
- Tasks sollten parallel ausführbar sein wenn möglich

INPUT: User Query
OUTPUT: JSON mit Tasks

Beispiel:
{
  "tasks": [
    {"id": 1, "description": "..."},
    {"id": 2, "description": "..."}
  ]
}
```

**Phase 2: Executor Prompt erstellen**

```markdown
# Executor System Prompt

Du bist ein Research Executor. Du erhältst einen Task und führst ihn
systematisch aus.

REGELN:
- Identifiziere welche Tools/Quellen du brauchst
- Rufe Tools auf und sammle Daten
- Validiere ob Daten vollständig sind
- Wenn nicht vollständig: Weitere Tools aufrufen
- Maximal 5 Iterationen pro Task

VERFÜGBARE TOOLS:
- search_knowledge_base(query): Durchsucht interne Knowledge Base
- calculate_tax(country, income, type): Berechnet Steuerlast
- get_country_info(country, topic): Holt Länder-Infos

OUTPUT: Strukturierte Daten zum Task
```

**Phase 3: Synthesizer Prompt erstellen**

```markdown
# Synthesizer System Prompt

Du bist ein Research Synthesizer. Du erhältst gesammelte Daten und
erstellst eine strukturierte, fundierte Antwort.

REGELN:
- Nutze NUR die bereitgestellten Daten
- Erstelle klare Strukturen (Tabellen, Listen)
- Gib konkrete Empfehlungen mit Begründung
- Nenne immer nächste Schritte
- Keine Erfindungen oder Annahmen

INPUT: Gesammelte Daten aus allen Tasks
OUTPUT: Strukturierte Antwort für den User
```

**Phase 4: Pipeline verbinden**

```python
# Pseudocode für Pipeline

async def process_query(user_query):
    # Phase 1: Planning
    tasks = await planner.plan(user_query)

    # Phase 2: Execution (parallel)
    results = await asyncio.gather(*[
        executor.execute(task) for task in tasks
    ])

    # Phase 3: Synthesis
    answer = await synthesizer.synthesize(results, user_query)

    return answer
```

---

## Trade-offs

### Pros

- **Vollständigkeit**: Systematische Abdeckung aller Aspekte
  - Impact: 100% der Frage wird beantwortet
  - Example: Keine vergessenen Länder beim Steuervergleich

- **Qualität**: Fundierte statt oberflächliche Antworten
  - Impact: Konkrete Zahlen und Empfehlungen
  - Example: "16.000€ Steuern" statt "moderate Steuern"

- **Skalierbarkeit**: Funktioniert für einfache und komplexe Fragen
  - Impact: Ein System für alle Query-Typen

- **Nachvollziehbarkeit**: Jeder Schritt ist dokumentiert
  - Impact: Debugging und Qualitätskontrolle möglich

### Cons

- **Latenz**: Mehr Schritte = längere Antwortzeit
  - Impact: 2-3x länger als direkte Antwort
  - Mitigation: Parallel-Execution, Streaming-Output

- **Kosten**: Mehr LLM-Aufrufe
  - Impact: 3-5x mehr Token-Verbrauch
  - Mitigation: Nur für komplexe Queries nutzen

- **Komplexität**: Aufwändigere Implementierung
  - Impact: Mehr Code zu maintainen
  - Mitigation: Gute Abstraktion, Templates nutzen

---

## When to Use

### Use This Pattern When:

**YES**
- Fragen haben mehrere Aspekte/Teile
- Konkrete Daten/Zahlen werden benötigt
- Vergleiche zwischen Optionen gefragt sind
- Beratungsqualität wichtig ist
- Antworten müssen nachvollziehbar sein

**Ideal Conditions**:
- Beratungs-intensive Domains (Steuern, Finanzen, Legal)
- Multi-Faktoren-Entscheidungen
- Recherche-intensive Aufgaben

### Don't Use This Pattern When:

**NO**
- Einfache Faktenfragen ("Was ist die Hauptstadt von Portugal?")
- Kreative Aufgaben (Texte schreiben, Brainstorming)
- Schnelle Antworten wichtiger als Vollständigkeit
- Keine Tools/Datenquellen verfügbar

**Better Alternatives**:
- Für einfache Fragen: Direkter LLM-Call
- Für Kreatives: Single-Agent mit Kreativ-Prompt

---

## Variations

### Variation 1: Lite (2 Phasen)

**Difference**: Kein separater Synthesizer, Executor erstellt direkt Antwort

**Use when**: Einfachere Queries, weniger Latenz gewünscht

```
Query → Planner → Executor (inkl. Synthesis) → Answer
```

### Variation 2: With Validation (4 Phasen)

**Difference**: Zusätzlicher Validator prüft Ergebnisse

**Use when**: Hohe Qualitätsanforderungen, kritische Entscheidungen

```
Query → Planner → Executor → Validator → Synthesizer → Answer
```

### Variation 3: Interactive (mit User-Feedback)

**Difference**: User kann nach Planning die Tasks bestätigen/anpassen

**Use when**: User-Kontrolle wichtig, explorative Recherche

```
Query → Planner → [User Review] → Executor → Synthesizer → Answer
```

---

## Best Practices

### Do's

1. **Tasks als Ziele formulieren, nicht als Schritte**
   - Why: Gibt dem Executor Flexibilität
   - How: "Portugal analysieren" statt "Suche Portugal Steuern"

2. **Parallel execution wo möglich**
   - Why: Reduziert Latenz signifikant
   - How: Tasks ohne Abhängigkeiten parallel ausführen

3. **Context auf Disk speichern bei großen Datenmengen**
   - Why: Verhindert Token-Limit-Probleme
   - How: JSON-Files mit Query-ID als Ordner

### Don'ts

1. **Nicht für jede Frage nutzen**
   - Why: Overkill für einfache Fragen, verschwendet Ressourcen
   - Instead: Query-Complexity-Check vorschalten

2. **Nicht zu viele Tasks erstellen**
   - Why: Fragmentiert die Arbeit zu sehr
   - Instead: Max 5 Tasks, lieber breiter als tiefer

---

## Related Patterns

### Complementary Patterns

- **Parallel Agent Dispatch**: Parallele Ausführung der Tasks
- **ReAct Pattern**: Für Tool-intensive, explorative Aufgaben

### Alternative Patterns

- **Chain-of-Thought**: Für einfachere, lineare Aufgaben

---

## Further Reading

**Source Projects**:
- [Dexter](https://github.com/virattt/dexter) - Original implementation for Finance

---

**Pattern Confidence**: 90% (Based on Dexter Implementation + Domain Analysis)
**Last Updated**: 2024-12-09
