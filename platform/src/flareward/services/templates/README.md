# Templates Module

The Templates module provides reusable blueprint templates with placeholder support.
Users can select a template, fill in required fields, and get a fully configured
blueprint with resources saved to their account.

## Core Concept

```
┌─────────────────────────────────────────────────────────────────────────────┐
│  TEMPLATE = BlueprintDraft + PlaceholderMeta + Metadata                     │
│                                                                             │
│  ┌─────────────────────────────────────────────────────────────────────┐    │
│  │  BlueprintDraft (always valid!)                                     │    │
│  │  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐                  │    │
│  │  │ nodes       │  │ llms        │  │ plan        │                  │    │
│  │  │ conditions  │  │ retrievers  │  │ ...         │                  │    │
│  │  │ ...         │  │ tools       │  │             │                  │    │
│  │  └─────────────┘  └─────────────┘  └─────────────┘                  │    │
│  │                                                                     │    │
│  │  Placeholder fields have default/dummy values that pass validation  │    │
│  │  Example: api_key = "PLACEHOLDER_API_KEY"                           │    │
│  └─────────────────────────────────────────────────────────────────────┘    │
│                                                                             │
│  ┌─────────────────────────────────────────────────────────────────────┐    │
│  │  PlaceholderMeta                                                    │    │
│  │  Points to which fields need user input:                            │    │
│  │    - llms.google_gemini.api_key (required)                          │    │
│  │    - nodes.orchestrator.system_prompt (optional)                    │    │
│  └─────────────────────────────────────────────────────────────────────┘    │
│                                                                             │
│  ┌─────────────────────────────────────────────────────────────────────┐    │
│  │  TemplateMetadata                                                   │    │
│  │  author, tags, version, category, is_public, etc.                   │    │
│  └─────────────────────────────────────────────────────────────────────┘    │
└─────────────────────────────────────────────────────────────────────────────┘
```

## High-Level Flow

```
┌──────────────┐    ┌──────────────┐    ┌──────────────┐    ┌──────────────┐
│  1. Browse   │───▶│  2. Preview  │───▶│  3. Fill     │───▶│  4. Create   │
│  Templates   │    │  & Schema    │    │  Inputs      │    │  Blueprint   │
└──────────────┘    └──────────────┘    └──────────────┘    └──────────────┘
       │                   │                   │                   │
       ▼                   ▼                   ▼                   ▼
 list_templates()   get_input_schema()    validate_input()   materialize()
                                                                   │
                                                                   ▼
                                                    ┌──────────────────────┐
                                                    │  Blueprint + $refs   │
                                                    │  Resources saved     │
                                                    └──────────────────────┘
```

## Directory Structure

```
templates/
├── README.md              # This file
├── __init__.py            # Package exports
├── service.py             # TemplateService (public facade)
├── errors.py              # All error models
│
├── models/                # Data models
│   ├── __init__.py
│   └── template.py        # Template, PlaceholderMeta, TemplateSummary, etc.
│
├── repository/            # Persistence layer
│   ├── __init__.py
│   ├── repository.py      # Abstract TemplateRepository
│   └── mongo_repository.py
│
├── schema/                # Input schema generation
│   ├── __init__.py
│   └── analyzer.py        # PlaceholderAnalyzer
│
└── instantiation/         # Template instantiation & materialization
    ├── README.md          # Detailed instantiation docs
    ├── __init__.py
    ├── models.py          # Data models for instantiation
    ├── instantiator.py    # TemplateInstantiator
    └── materializer.py    # ResourceMaterializer
```

## Key Classes

### TemplateService (service.py)
Public facade for all template operations.

```
┌─────────────────────────────────────────────────────────────────────────────┐
│  TemplateService                                                            │
├─────────────────────────────────────────────────────────────────────────────┤
│  Dependencies (injected):                                                   │
│    - TemplateRepository    → Template persistence                           │
│    - ElementRegistry       → Element schema lookups                         │
│    - BlueprintService      → Save instantiated blueprints                   │
│    - ResourcesService      → Save instantiated resources                    │
├─────────────────────────────────────────────────────────────────────────────┤
│  CRUD:                                                                      │
│    create_template()      → Create new template                             │
│    get_template()         → Get by ID                                       │
│    update_template()      → Update existing                                 │
│    delete_template()      → Delete template                                 │
│    list_templates()       → List with filtering                             │
├─────────────────────────────────────────────────────────────────────────────┤
│  Schema:                                                                    │
│    get_input_schema()     → JSON Schema for UI form                         │
│    validate_input()       → Validate user input                             │
├─────────────────────────────────────────────────────────────────────────────┤
│  Instantiation:                                                             │
│    instantiate()          → Merge input → BlueprintDraft                    │
│    materialize()          → Full flow: input → saved blueprint + resources  │
└─────────────────────────────────────────────────────────────────────────────┘
```

### PlaceholderAnalyzer (schema/analyzer.py)
Creates Pydantic models from placeholder metadata for input validation.

```
Template + PlaceholderMeta
         │
         ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│  PlaceholderAnalyzer.create_input_model()                                   │
│                                                                             │
│  1. Iterate PlaceholderMeta.categories                                      │
│  2. For each placeholder field:                                             │
│     - Find resource in draft                                                │
│     - Get config schema from ElementRegistry                                │
│     - Extract (annotation, FieldInfo) from original schema                  │
│  3. Build nested Pydantic model:                                            │
│                                                                             │
│     class TemplateInput(BaseModel):                                         │
│         llms: LlmsInput                                                     │
│                                                                             │
│     class LlmsInput(BaseModel):                                             │
│         google_gemini: GoogleGeminiInput                                    │
│                                                                             │
│     class GoogleGeminiInput(BaseModel):                                     │
│         api_key: str = Field(...)                                           │
└─────────────────────────────────────────────────────────────────────────────┘
         │
         ▼
   JSON Schema (for UI)
   Validation (for API)
```

## Materialization Flow

The main entry point: `TemplateService.materialize()`

```
┌─────────────────────────────────────────────────────────────────────────────┐
│  materialize(template_id, user_id, user_input)                              │
└─────────────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│  Step 1: INSTANTIATE                                                        │
│  ┌─────────────────────────────────────────────────────────────────────┐    │
│  │  TemplateInstantiator.instantiate(template, user_input)             │    │
│  │    - Copy draft (deep clone)                                        │    │
│  │    - Merge user values into placeholder fields                      │    │
│  │    → Returns InstantiationResult with BlueprintDraft                │    │
│  └─────────────────────────────────────────────────────────────────────┘    │
└─────────────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│  Step 2: VALIDATE                                                           │
│  ┌─────────────────────────────────────────────────────────────────────┐    │
│  │  BlueprintService.validate_draft(blueprint)                         │    │
│  │    - Validate all element configs against schemas                   │    │
│  └─────────────────────────────────────────────────────────────────────┘    │
└─────────────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│  Step 3: MATERIALIZE                                                        │
│  ┌─────────────────────────────────────────────────────────────────────┐    │
│  │  ResourceMaterializer.materialize(draft, user_id)                   │    │
│  │    - Save inline resources to user's account                        │    │
│  │    - Replace inline configs with $ref entries                       │    │
│  │    → Returns MaterializationResult with final BlueprintDraft        │    │
│  └─────────────────────────────────────────────────────────────────────┘    │
└─────────────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│  Step 4: SAVE BLUEPRINT                                                     │
│  ┌─────────────────────────────────────────────────────────────────────┐    │
│  │  BlueprintService.save_draft(user_id, draft)                        │    │
│  │    - Save blueprint with $ref references                            │    │
│  │    - Link to source template in metadata                            │    │
│  └─────────────────────────────────────────────────────────────────────┘    │
└─────────────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│  RESULT                                                                     │
│  ┌─────────────────────────────────────────────────────────────────────┐    │
│  │  MaterializeResult:                                                 │    │
│  │    - blueprint_id: "bp-12345"                                       │    │
│  │    - template_id: "tpl-67890"                                       │    │
│  │    - resource_ids: ["res-aaa", "res-bbb", ...]                      │    │
│  │    - fields_filled: 3                                               │    │
│  └─────────────────────────────────────────────────────────────────────┘    │
└─────────────────────────────────────────────────────────────────────────────┘
```

## Data Models

### Template Structure

```python
Template:
├── template_id: str
├── draft: BlueprintDraft          # Valid blueprint with placeholder defaults
├── placeholders: PlaceholderMeta  # Points to fields needing input
├── metadata: TemplateMetadata     # Catalog info (author, tags, etc.)
├── created_at: datetime
└── updated_at: datetime

PlaceholderMeta:
└── categories: List[CategoryPlaceholders]
    └── category: ResourceCategory (nodes, llms, etc.)
    └── resources: List[ResourcePlaceholders]
        └── rid: str
        └── placeholders: List[PlaceholderPointer]
            └── field_path: str    # e.g., "api_key", "flareward.bootstrap.settings.model"
            └── required: bool
            └── label: str         # Human-readable label
            └── hint: str          # Help text
```

### Result Models

```python
InstantiationResult:
├── blueprint: BlueprintDraft      # Merged draft
├── template_id: str
└── filled_fields: List[str]       # Fields that were filled

MaterializationResult:
├── blueprint_draft: BlueprintDraft  # Final draft with $refs
├── resource_ids: List[str]          # Saved resource IDs
└── id_mapping: Dict[str, str]       # template_rid → final_rid

MaterializeResult (from service):
├── blueprint_id: str              # Saved blueprint ID
├── template_id: str
├── resource_ids: List[str]
├── fields_filled: int
├── resources_created: int
└── name: str
```

## Error Handling

All errors are defined in `errors.py`:

```
TemplateNotFoundError     → Template doesn't exist
TemplateSaveError         → Failed to save template
InstantiationError        → Instantiation failed (missing fields, etc.)
MergeError                → Failed to merge input into draft
MaterializationError      → Failed to save resources
```

## SOLID Principles

| Principle | Implementation |
|-----------|----------------|
| **S**RP | Each class has one responsibility |
| **O**CP | New element types work without code changes |
| **L**SP | All repositories implement same interface |
| **I**SP | TemplateSummary for read-only projections |
| **D**IP | Dependencies injected, abstractions used |

## Usage Example

```python
# Initialize
service = TemplateService(
    repository=MongoTemplateRepository(db),
    element_registry=element_registry,
    blueprint_service=blueprint_service,
    resources_service=resources_service,
)

# Get input schema for UI form
schema = service.get_input_schema("template-123")

# Validate user input
result = service.validate_input("template-123", user_input)
if not result.is_valid:
    return {"errors": result.errors}

# Create blueprint + resources
result = service.materialize(
    template_id="template-123",
    user_id="user-456",
    user_input={"llms": {"gemini": {"api_key": "..."}}},
)

# Result contains:
# - result.blueprint_id: The saved blueprint
# - result.resource_ids: All saved resources
```
