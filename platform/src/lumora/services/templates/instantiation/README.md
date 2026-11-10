# Instantiation Module

This module handles the instantiation and materialization of templates.

**Instantiation**: Merging user input into a template draft → BlueprintDraft
**Materialization**: Saving resources to user's account and creating $ref entries

## Directory Structure

```
instantiation/
├── README.md           # This file
├── __init__.py         # Package exports
├── models.py           # Data models (CollectedResource, Results)
├── instantiator.py     # TemplateInstantiator class
└── materializer.py     # ResourceMaterializer class
```

## Flow Overview

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                         INSTANTIATION FLOW                                  │
└─────────────────────────────────────────────────────────────────────────────┘

       Template                    User Input
          │                            │
          ▼                            ▼
┌─────────────────┐           ┌─────────────────┐
│  BlueprintDraft │           │ {"llms": {...}, │
│  (with defaults)│           │  "nodes": {...}}│
└────────┬────────┘           └────────┬────────┘
         │                             │
         └──────────────┬──────────────┘
                        ▼
          ┌─────────────────────────┐
          │  TemplateInstantiator   │
          │  .instantiate()         │
          │                         │
          │  1. Deep copy draft     │
          │  2. Merge user values   │
          │  3. Collect filled list │
          └────────────┬────────────┘
                       ▼
          ┌─────────────────────────┐
          │  InstantiationResult    │
          │  - blueprint (merged)   │
          │  - filled_fields        │
          └────────────┬────────────┘
                       ▼
          ┌─────────────────────────┐
          │  ResourceMaterializer   │
          │  .materialize()         │
          │                         │
          │  1. Collect inline      │
          │  2. Remap refs          │
          │  3. Save to DB          │
          │  4. Build $ref draft    │
          └────────────┬────────────┘
                       ▼
          ┌─────────────────────────┐
          │  MaterializationResult  │
          │  - blueprint_draft      │
          │  - resource_ids         │
          │  - id_mapping           │
          └─────────────────────────┘
```

---

## TemplateInstantiator

Merges user input into a template's placeholder fields.

### Design

```
┌─────────────────────────────────────────────────────────────────────────────┐
│  TemplateInstantiator                                                       │
├─────────────────────────────────────────────────────────────────────────────┤
│  RESPONSIBILITY: Merge user input into template placeholders                │
│                                                                             │
│  INPUT:                                                                     │
│    - Template (with draft + placeholders)                                   │
│    - user_input: Dict[str, Any]                                             │
│                                                                             │
│  OUTPUT:                                                                    │
│    - InstantiationResult (blueprint + metadata)                             │
│                                                                             │
│  ERRORS:                                                                    │
│    - MergeError (missing required fields, resource not found)               │
└─────────────────────────────────────────────────────────────────────────────┘
```

### Flow

```
instantiate(template, user_input)
          │
          ▼
┌─────────────────────────────────────────┐
│  1. _copy_draft()                       │
│     Deep clone to avoid mutating        │
│     original template                   │
└────────────────┬────────────────────────┘
                 ▼
┌─────────────────────────────────────────┐
│  2. _merge_placeholders()               │
│     For each category:                  │
│       For each resource:                │
│         For each placeholder field:     │
│           - If value in input → set it  │
│           - If required & missing → err │
└────────────────┬────────────────────────┘
                 ▼
┌─────────────────────────────────────────┐
│  3. _collect_filled_fields()            │
│     Track which fields were filled      │
│     → ["llms.gemini.api_key", ...]      │
└────────────────┬────────────────────────┘
                 ▼
┌─────────────────────────────────────────┐
│  RETURN InstantiationResult             │
│    - blueprint: merged draft            │
│    - template_id: source template       │
│    - filled_fields: what was filled     │
└─────────────────────────────────────────┘
```

### Key Methods

| Method | Purpose |
|--------|---------|
| `instantiate()` | Main entry point |
| `_copy_draft()` | Deep clone draft |
| `_merge_placeholders()` | Merge all values |
| `_merge_resource_fields()` | Merge single resource |
| `_set_field()` | Set value at field path |
| `_find_resource()` | Find resource by rid |
| `_collect_filled_fields()` | Track filled fields |

---

## ResourceMaterializer

Saves inline blueprint resources to the database and creates $ref entries.

### Design

```
┌─────────────────────────────────────────────────────────────────────────────┐
│  ResourceMaterializer                                                       │
├─────────────────────────────────────────────────────────────────────────────┤
│  RESPONSIBILITY: Convert inline resources → saved resources + $ref draft   │
│                                                                             │
│  INPUT:                                                                     │
│    - BlueprintDraft (with inline configs)                                   │
│    - user_id: str                                                           │
│                                                                             │
│  OUTPUT:                                                                    │
│    - MaterializationResult (draft with $refs + resource IDs)                │
│                                                                             │
│  DEPENDENCIES:                                                              │
│    - ResourcesService (for saving)                                          │
│                                                                             │
│  ROLLBACK:                                                                  │
│    - If anything fails, delete all saved resources                          │
└─────────────────────────────────────────────────────────────────────────────┘
```

### 4-Step Flow

```
materialize(draft, user_id)
          │
          ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│  STEP 1: COLLECT INLINE RESOURCES                                           │
│  ┌───────────────────────────────────────────────────────────────────────┐  │
│  │  For each category (nodes, llms, tools, ...):                         │  │
│  │    For each BlueprintResource:                                        │  │
│  │      If _should_save() → add to collected list                        │  │
│  │                                                                       │  │
│  │  _should_save():                                                      │  │
│  │    - config is not None (has inline config)                           │  │
│  │    - rid is not external ($ref:...)                                   │  │
│  │    - type is not system (user_question_node, final_answer_node)       │  │
│  │                                                                       │  │
│  │  CollectedResource:                                                   │  │
│  │    template_rid: "orchestrator"        (original ID)                  │  │
│  │    final_rid: "a1b2c3d4..."           (generated UUID)                │  │
│  │    category: ResourceCategory.NODE                                    │  │
│  │    bp_resource: BlueprintResource      (with typed config)            │  │
│  └───────────────────────────────────────────────────────────────────────┘  │
│                                                                             │
│  → collected: List[CollectedResource]                                       │
│  → id_mapping: {template_rid → final_rid}                                   │
└─────────────────────────────────────────────────────────────────────────────┘
          │
          ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│  STEP 2: REMAP REFS IN CONFIGS                                              │
│  ┌───────────────────────────────────────────────────────────────────────┐  │
│  │  For each collected resource:                                         │  │
│  │    RefRemapper.remap(config, prefixed_mapping)                        │  │
│  │                                                                       │  │
│  │  prefixed_mapping:                                                    │  │
│  │    {"llm_ref" → "$ref:a1b2c3d4..."}  (using Ref.make_external)        │  │
│  │                                                                       │  │
│  │  Before:                                                              │  │
│  │    node.config.llm = LLMRef("google_gemini")                          │  │
│  │                                                                       │  │
│  │  After:                                                               │  │
│  │    node.config.llm = LLMRef("$ref:a1b2c3d4...")                       │  │
│  └───────────────────────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────────────────────┘
          │
          ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│  STEP 3: SAVE RESOURCES                                                     │
│  ┌───────────────────────────────────────────────────────────────────────┐  │
│  │  For each collected resource:                                         │  │
│  │    1. Convert BlueprintResource → Resource                            │  │
│  │       - rid: final_rid                                                │  │
│  │       - user_id: user_id                                              │  │
│  │       - category: category.value                                      │  │
│  │       - type: bp_resource.type                                        │  │
│  │       - name: "{type}_{unique_suffix}"                                │  │
│  │       - cfg_dict: lumora.bootstrap.settings.model_dump()                                 │  │
│  │                                                                       │  │
│  │    2. ResourcesService.save_resource(resource)                        │  │
│  │                                                                       │  │
│  │    3. Track saved_rids for rollback                                   │  │
│  │                                                                       │  │
│  │  ON ERROR:                                                            │  │
│  │    _rollback(saved_rids) → Delete all saved resources                 │  │
│  └───────────────────────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────────────────────┘
          │
          ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│  STEP 4: BUILD FINAL DRAFT                                                  │
│  ┌───────────────────────────────────────────────────────────────────────┐  │
│  │  Create new BlueprintDraft:                                           │  │
│  │                                                                       │  │
│  │  nodes/conditions: _remap_entries()                                   │  │
│  │    - Saved resource → BlueprintResource(rid=$ref:final_rid)           │  │
│  │    - System node    → Keep as-is (with inline config)                 │  │
│  │                                                                       │  │
│  │  llms/retrievers/tools/providers: []                                  │  │
│  │    - Empty! (embedded in saved node configs)                          │  │
│  │                                                                       │  │
│  │  plan: _remap_plan()                                                  │  │
│  │    - Update step.node refs to final_rids                              │  │
│  │    - Update step.exit_condition refs                                  │  │
│  └───────────────────────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────────────────────┘
          │
          ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│  RETURN MaterializationResult                                               │
│    - blueprint_draft: final draft with $refs                                │
│    - resource_ids: ["a1b2c3d4...", "e5f6g7h8...", ...]                      │
│    - id_mapping: {"orchestrator" → "a1b2c3d4...", ...}                      │
└─────────────────────────────────────────────────────────────────────────────┘
```

### Before/After Example

```
BEFORE (template draft with inline configs):
┌─────────────────────────────────────────────────────────────────────────────┐
│  BlueprintDraft:                                                            │
│    nodes:                                                                   │
│      - rid: "orchestrator", type: "orchestrator_node"                       │
│        config: {llm: LLMRef("google_gemini"), system_prompt: "..."}         │
│      - rid: "user_question", type: "user_question_node"                     │
│        config: {...}   ← System node                                        │
│    llms:                                                                    │
│      - rid: "google_gemini", type: "google_genai"                           │
│        config: {api_key: "sk-...", model: "gemini-1.5-pro"}                 │
│    plan:                                                                    │
│      - node: NodeRef("orchestrator")                                        │
│      - node: NodeRef("user_question")                                       │
└─────────────────────────────────────────────────────────────────────────────┘

AFTER (materialized draft with $refs):
┌─────────────────────────────────────────────────────────────────────────────┐
│  BlueprintDraft:                                                            │
│    nodes:                                                                   │
│      - rid: NodeRef("$ref:abc123")      ← Saved orchestrator                │
│      - rid: "user_question", ...        ← System node (kept inline)         │
│    llms: []                             ← Empty (embedded in orchestrator)  │
│    plan:                                                                    │
│      - node: NodeRef("abc123")          ← Updated to final_rid              │
│      - node: NodeRef("user_question")   ← System node unchanged             │
└─────────────────────────────────────────────────────────────────────────────┘

SAVED RESOURCES (in database):
┌─────────────────────────────────────────────────────────────────────────────┐
│  Resource: rid="abc123"                                                     │
│    user_id: "user-456"                                                      │
│    category: "nodes"                                                        │
│    type: "orchestrator_node"                                                │
│    name: "orchestrator_node_7f8a9b2c"                                       │
│    cfg_dict: {llm: "$ref:def456", system_prompt: "..."}                     │
│                                                                             │
│  Resource: rid="def456"                                                     │
│    user_id: "user-456"                                                      │
│    category: "llms"                                                         │
│    type: "google_genai"                                                     │
│    name: "google_genai_7f8a9b2c"                                            │
│    cfg_dict: {api_key: "sk-...", model: "gemini-1.5-pro"}                   │
└─────────────────────────────────────────────────────────────────────────────┘
```

### Key Methods

| Method | Purpose |
|--------|---------|
| `materialize()` | Main entry point |
| `_collect_inline_resources()` | Find resources to save |
| `_should_save()` | Predicate: should this resource be saved? |
| `_remap_configs()` | Update Ref objects in configs |
| `_save_resources()` | Save to database |
| `_rollback()` | Delete on failure |
| `_build_final_draft()` | Build draft with $refs |
| `_remap_entries()` | Replace saved with $ref |
| `_remap_plan()` | Update plan refs |

---

## Data Models (models.py)

```python
class CollectedResource(NamedTuple):
    """Internal: A resource collected for saving."""

    template_rid: str  # Original ID in template ("orchestrator")
    final_rid: str  # Generated UUID for database
    category: ResourceCategory  # nodes, llms, etc.
    bp_resource: BlueprintResource  # The actual resource with typed config


class InstantiationResult(BaseModel):
    """Result of TemplateInstantiator.instantiate()"""

    blueprint: BlueprintDraft  # Merged draft
    template_id: str  # Source template
    filled_fields: List[str]  # Fields that were filled

    @property
    def field_count(self) -> int:
        return len(self.filled_fields)


class MaterializationResult(BaseModel):
    """Result of ResourceMaterializer.materialize()"""

    blueprint_draft: BlueprintDraft  # Final draft with $refs
    resource_ids: List[str]  # Saved resource IDs
    id_mapping: Dict[str, str]  # template_rid → final_rid
```

---

## SOLID Principles

| Principle | Implementation |
|-----------|----------------|
| **S**RP | Instantiator merges, Materializer saves |
| **O**CP | Works with any ResourceCategory via enum |
| **L**SP | - |
| **I**SP | Separate result models for each operation |
| **D**IP | Depends on ResourcesService abstraction |

## Error Handling

- **MergeError**: From instantiator when required fields missing
- **MaterializationError**: From materializer when save fails
- **Rollback**: On any failure, saved resources are deleted

## Key Dependencies

```
┌─────────────────────────────────────────────────────────────────────────────┐
│  RefRemapper (core/ref/remapper.py)                                         │
│    - Walks object graph and remaps Ref objects                              │
│    - Uses Ref.make_external() for clean $ref: formatting                    │
│                                                                             │
│  Ref (core/ref/models.py)                                                   │
│    - ref.to_external(rid) → Creates $ref entry                              │
│    - Ref.make_external(rid) → Returns "$ref:rid" string                     │
│                                                                             │
│  ResourcesService (resources/service.py)                                    │
│    - save_resource(resource) → Persist to database                          │
│    - delete(rid) → Remove for rollback                                      │
└─────────────────────────────────────────────────────────────────────────────┘
```
