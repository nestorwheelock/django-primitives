# django-questionnaires

Domain-agnostic questionnaire and survey primitives for Django.

## Features

- **Versioned questionnaire definitions** - Create, publish, and archive questionnaire templates
- **Multiple question types** - Yes/No, text, number, date, single choice, multi-choice
- **GenericFK respondents** - Link questionnaire instances to any model
- **Flag-based workflow** - Mark instances as flagged based on answer triggers
- **Clearance workflow** - Clear flagged instances with optional document attachments
- **Expiration support** - Define validity periods for questionnaire responses

## Installation

```bash
pip install django-questionnaires
```

Add to INSTALLED_APPS:

```python
INSTALLED_APPS = [
    ...
    'django_questionnaires',
]
```

## Quick Start

```python
from django_questionnaires.services import (
    create_definition,
    publish_definition,
    create_instance,
    submit_response,
)

# Create a questionnaire definition
definition = create_definition(
    slug="health-check",
    name="Health Questionnaire",
    description="Basic health screening",
    version="1.0.0",
    questions_data=[
        {
            "sequence": 1,
            "question_type": "yes_no",
            "question_text": "Do you have any allergies?",
            "is_required": True,
            "triggers_flag": True,
        },
    ],
    actor=user,
)

# Publish it
publish_definition(definition, actor=user)

# Create an instance for a respondent
instance = create_instance(
    definition_slug="health-check",
    respondent=patient,
    expires_in_days=30,
    actor=user,
)

# Submit responses
submit_response(
    instance=instance,
    answers={
        question.id: {"answer_bool": False}
    },
    actor=user,
)
```

## Models

### QuestionnaireDefinition

Versioned template for a questionnaire.

- `slug` - Unique identifier (among non-archived)
- `name` - Display name
- `version` - Semantic version string
- `status` - draft | published | archived
- `validity_days` - How long responses remain valid (null = forever)

### Question

Individual question within a definition.

- `question_type` - yes_no | text | number | date | choice | multi_choice
- `triggers_flag` - If True, certain answers flag the instance for review
- `choices` - JSON list for choice types
- `validation_rules` - JSON for min/max/regex constraints

### QuestionnaireInstance

An instance of a questionnaire sent to a respondent.

- `respondent` - GenericFK to any model
- `status` - pending | completed | flagged | cleared | expired
- `expires_at` - When the instance expires
- `cleared_by` - Who cleared a flagged instance

### Response

Individual answer to a question.

- Typed answer fields: `answer_bool`, `answer_text`, `answer_number`, `answer_date`, `answer_choices`
- `triggered_flag` - Whether this answer triggered a flag

## License

MIT
