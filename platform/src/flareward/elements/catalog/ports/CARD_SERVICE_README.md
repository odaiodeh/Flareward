# Element Card System

## Overview

The Element Card system provides a **standardized way to describe elements** - their identity, capabilities, and skills. Cards are used for:

- **UI Display**: Show element details in resource views and blueprint editors
- **Node Context**: Provide adjacent node information at runtime
- **LLM Understanding**: Help agents understand available tools and capabilities

---

## Core Models

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                              ElementCard                                     │
├─────────────────────────────────────────────────────────────────────────────┤
│  uid: str              → Unique identifier                                   │
│  category: Enum        → NODE, TOOL, LLM, RETRIEVER, etc.                   │
│  type_key: str         → Element type (e.g., "a2a_agent", "openai_llm")     │
│  name: str             → User-defined display name                           │
│  description: str      → What this element does                              │
│  skills: List[Skill]   → Concrete actions (tools, operations)               │
│  capabilities: List[Capability] → Semantic abilities                        │
│  configuration: Dict   → Element config summary                              │
│  metadata: Any         → Step-specific metadata                              │
└─────────────────────────────────────────────────────────────────────────────┘

┌─────────────────────────────┐    ┌─────────────────────────────┐
│           Skill             │    │        Capability           │
├─────────────────────────────┤    ├─────────────────────────────┤
│  name: str                  │    │  name: str                  │
│  description: str           │    │  description: str           │
│  + extra fields (allow)     │    │  + extra fields (allow)     │
│    - id                     │    │    - value                  │
│    - examples               │    │    - (any A2A fields)       │
│    - tags                   │    │                             │
│    - inputModes             │    │                             │
│    - outputModes            │    │                             │
└─────────────────────────────┘    └─────────────────────────────┘
```

### Skill vs Capability

| Aspect | Skill | Capability |
|--------|-------|------------|
| What | Concrete action/tool | Semantic ability |
| Example | `git_status`, `send_slack_message` | `document_retrieval`, `code_analysis` |
| Source | Tool configs, MCP providers | Element spec, A2A agent card |

---

## Architecture

```
                                    DATA SOURCES
    ┌─────────────────────────────────────────────────────────────────────┐
    │                                                                     │
    │   BlueprintSpec          Resource              SessionRegistry      │
    │   (design-time)          (saved resources)     (runtime)            │
    │                                                                     │
    └─────────────────────────────────────────────────────────────────────┘
                │                      │                      │
                ▼                      ▼                      ▼
    ┌───────────────────┐  ┌───────────────────┐  ┌───────────────────┐
    │ BlueprintConfig   │  │ Dependency        │  │ SessionConfig     │
    │ Collector         │  │ Resolver          │  │ Collector         │
    │ (blueprints/)     │  │ (resources/)      │  │ (session/)        │
    └───────────────────┘  └───────────────────┘  └───────────────────┘
                │                      │                      │
                │    Extracts ElementConfigMeta from source   │
                │                      │                      │
                └──────────────────────┼──────────────────────┘
                                       │
                                       ▼
                        ┌──────────────────────────┐
                        │    ElementConfigMeta     │
                        │    (core/element_meta)   │
                        ├──────────────────────────┤
                        │  rid: str                │
                        │  category: Enum          │
                        │  type_key: str           │
                        │  name: str               │
                        │  config: BaseModel       │
                        │  dependency_rids: List   │
                        └──────────────────────────┘
                                       │
                                       │  List[ElementConfigMeta]
                                       ▼
                        ┌──────────────────────────┐
                        │   ElementCardService     │
                        │   (catalog/card_service) │
                        └──────────────────────────┘
                                       │
                                       │  1. Build dependency graph
                                       │  2. Topological sort
                                       │  3. Build cards in order
                                       ▼
                        ┌──────────────────────────┐
                        │   Dict[rid, ElementCard] │
                        └──────────────────────────┘
```

---

## Card Building Flow

```
                         ElementCardService.build_all_cards()
                                       │
                                       ▼
┌──────────────────────────────────────────────────────────────────────────────┐
│  STEP 1: Build Dependency Graph                                              │
│  ─────────────────────────────────────────────────────────────────────────── │
│                                                                              │
│    ElementConfigMeta[]  ──►  deps = {                                        │
│                                "agent_1": ["llm_1", "tool_1"],               │
│                                "tool_1": [],                                 │
│                                "llm_1": []                                   │
│                              }                                               │
│                                                                              │
│    Uses pre-computed dependency_rids from each ElementConfigMeta            │
└──────────────────────────────────────────────────────────────────────────────┘
                                       │
                                       ▼
┌──────────────────────────────────────────────────────────────────────────────┐
│  STEP 2: Topological Sort                                                    │
│  ─────────────────────────────────────────────────────────────────────────── │
│                                                                              │
│    deps graph  ──►  ["tool_1", "llm_1", "agent_1"]                          │
│                                                                              │
│    Dependencies come BEFORE dependents (leaves first)                        │
└──────────────────────────────────────────────────────────────────────────────┘
                                       │
                                       ▼
┌──────────────────────────────────────────────────────────────────────────────┐
│  STEP 3: Build Cards In Order                                                │
│  ─────────────────────────────────────────────────────────────────────────── │
│                                                                              │
│    for rid in sorted_order:                                                  │
│        meta = config_map[rid]                                                │
│        dep_cards = {already built dependency cards}                          │
│        card = _build_single_card(meta, dep_cards)                            │
│        cards[rid] = card                                                     │
│                                                                              │
│    ┌─────────────────────────────────────────────────────────────────────┐   │
│    │  _build_single_card(meta, dep_cards)                                │   │
│    │                                                                     │   │
│    │    1. Get ElementSpec from registry                                 │   │
│    │    2. Create CardBuildInput with config + dep_cards                 │   │
│    │    3. Get CardBuilder from spec (or DefaultCardBuilder)             │   │
│    │    4. builder.build(input) → ElementCard                            │   │
│    └─────────────────────────────────────────────────────────────────────┘   │
└──────────────────────────────────────────────────────────────────────────────┘
```

---

## Card Builders (Strategy Pattern)

Each element type can have its own CardBuilder:

```
                            ┌─────────────────────┐
                            │    CardBuilder      │
                            │    (interface)      │
                            ├─────────────────────┤
                            │  build(input)       │
                            │    → ElementCard    │
                            └─────────────────────┘
                                      ▲
                                      │
         ┌────────────────────────────┼────────────────────────────┐
         │                            │                            │
┌─────────────────┐        ┌─────────────────┐        ┌─────────────────┐
│ DefaultCard     │        │ A2AAgentCard    │        │ McpProviderCard │
│ Builder         │        │ Builder         │        │ Builder         │
├─────────────────┤        ├─────────────────┤        ├─────────────────┤
│ Uses spec       │        │ Uses agent_card │        │ Extracts tool   │
│ metadata only   │        │ from remote A2A │        │ names as skills │
│                 │        │ agent           │        │                 │
└─────────────────┘        └─────────────────┘        └─────────────────┘


Example: A2AAgentCardBuilder
────────────────────────────

  ┌──────────────────────────────────────────────────────────────┐
  │  Input:                                                      │
  │    flareward.bootstrap.settings.agent_card = AgentCard(                            │
  │      name="OpenShift Assistant",                             │
  │      description="AI-powered assistant...",                  │
  │      skills=[AgentSkill(name="Install", ...)],               │
  │      capabilities=AgentCapabilities(streaming=True, ...)     │
  │    )                                                         │
  └──────────────────────────────────────────────────────────────┘
                               │
                               ▼
  ┌──────────────────────────────────────────────────────────────┐
  │  Output:                                                     │
  │    ElementCard(                                              │
  │      name="OpenShift Assistant",                             │
  │      description="AI-powered assistant...",                  │
  │      skills=[Skill(name="Install", examples=[...], ...)],    │
  │      capabilities=[Capability(name="streaming", value=True)] │
  │    )                                                         │
  └──────────────────────────────────────────────────────────────┘
```

---

## Dependency Resolution Example

```
Given elements:
  - CustomAgentNode (references: llm_1, tool_1, retriever_1)
  - LLM (no deps)
  - Tool (no deps)  
  - Retriever (no deps)

Step 1: Dependency Graph
────────────────────────
  agent_1 ──► [llm_1, tool_1, retriever_1]
  llm_1   ──► []
  tool_1  ──► []
  retriever_1 ──► []

Step 2: Topological Sort
────────────────────────
  [llm_1, tool_1, retriever_1, agent_1]  (leaves first)

Step 3: Build In Order
──────────────────────
  1. Build llm_1 card        → cards["llm_1"]
  2. Build tool_1 card       → cards["tool_1"]  
  3. Build retriever_1 card  → cards["retriever_1"]
  4. Build agent_1 card with dependency_cards = {
       "llm_1": cards["llm_1"],
       "tool_1": cards["tool_1"],
       "retriever_1": cards["retriever_1"]
     }
     
     → Agent card can now compose skills/capabilities from its deps!
```

---

## RTGraphPlan Integration

At runtime, `RTGraphPlan` builds element cards for all elements in the session:

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                              RTGraphPlan                                     │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│   __init__(logical_plan, session_registry, element_registry)                │
│       │                                                                     │
│       ├──► _build_all_cards()                                               │
│       │        │                                                            │
│       │        │  ┌─────────────────────────────────────┐                   │
│       │        └─►│  SessionConfigCollector.collect()   │                   │
│       │           │  → List[ElementConfigMeta]          │                   │
│       │           └─────────────────────────────────────┘                   │
│       │                          │                                          │
│       │                          ▼                                          │
│       │           ┌─────────────────────────────────────┐                   │
│       │           │  ElementCardService.build_all_cards │                   │
│       │           │  → Dict[rid, ElementCard]           │                   │
│       │           └─────────────────────────────────────┘                   │
│       │                          │                                          │
│       │                          ▼                                          │
│       │               self._cards = {...}                                   │
│       │                                                                     │
│       └──► _build_runtime_steps()                                           │
│                │                                                            │
│                │  For each step:                                            │
│                │    - Get cards for adjacent nodes                          │
│                │    - Build StepContext with AdjacentNodes                  │
│                │    - Inject context into node function                     │
│                │                                                            │
│                ▼                                                            │
│   ┌─────────────────────────────────────────────────────────────────────┐   │
│   │  StepContext                                                        │   │
│   │    uid: str                                                         │   │
│   │    adjacent_nodes: AdjacentNodes  ◄── Contains ElementCards         │   │
│   │    branches: Dict[str, str]                                         │   │
│   │    topology: TopologyInfo                                           │   │
│   └─────────────────────────────────────────────────────────────────────┘   │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## File Structure

```
catalog/
├── card_service.py          # ElementCardService - main orchestrator
├── element_registry.py      # Registry of all element specs
└── CARD_SERVICE_README.md   # This file

elements/common/card/
├── models/
│   ├── card.py              # ElementCard, Skill, Capability
│   └── input.py             # CardBuildInput, SpecMetadata
├── interface.py             # CardBuilder interface
└── default.py               # DefaultCardBuilder

core/
└── element_meta.py          # ElementConfigMeta (universal input DTO)

Collectors (prepare ElementConfigMeta from different sources):
├── blueprints/collector.py  # BlueprintConfigCollector
├── resources/resolver.py    # DependencyResolver  
└── session/collector.py     # SessionConfigCollector

Element-specific builders:
├── elements/nodes/a2a_agent/card_builder.py
├── elements/providers/mcp/card_builder.py
└── ... (other custom builders)
```

---

## Usage Examples

### Building cards from a blueprint:

```python
from blueprints.collector import BlueprintConfigCollector
from catalog.card_service import ElementCardService

collector = BlueprintConfigCollector()
card_service = ElementCardService(element_registry)

# Collect configs from blueprint
configs = collector.collect(blueprint_spec)

# Build all cards
cards = card_service.build_all_cards(configs)

for rid, card in cards.items():
    print(card)
```

### Building cards at runtime (RTGraphPlan):

```python
from graph.rt_graph_plan import RTGraphPlan

rt_plan = RTGraphPlan(logical_plan, session_registry, element_registry)

# Cards are automatically built during construction
# Access via rt_plan._cards or through step contexts
```

---

## Key Design Decisions

1. **Universal Input (ElementConfigMeta)**: The card service is agnostic to data sources. Callers adapt their data into `ElementConfigMeta`.

2. **Pre-computed Dependencies**: Dependencies are extracted by collectors using `RefWalker`, not by the card service. This keeps the service focused.

3. **Strategy Pattern for Builders**: Each element type can customize how its card is built via `card_builder_cls` on its spec.

4. **Dependency Order**: Cards are built in topological order so parent elements can access their dependency cards.

5. **Extra Fields Preserved**: `Skill` and `Capability` use `extra='allow'` to capture all data from external sources (like A2A AgentCard).
