"""
Memory Templates System for MemCore

Provides pre-defined templates for common memory types:
- Meeting notes
- Project specifications
- Bug reports
- Feature requests
- Research notes
- Code snippets
- Book/article summaries
"""
from typing import Dict, Any, List, Optional
from dataclasses import dataclass
from datetime import datetime


@dataclass
class MemoryTemplate:
    """Template definition for a memory type."""
    name: str
    description: str
    default_quadrants: List[str]
    default_tags: List[str]
    suggested_importance: float
    content_schema: Dict[str, Any]  # Field definitions
    template_prompt: str  # LLM prompt for extraction


class MemoryTemplateManager:
    """
    Manages memory templates for structured capture.

    Provides consistent formats for common memory types,
    making it easier to capture structured information.
    """

    TEMPLATES: Dict[str, MemoryTemplate] = {
        "meeting_notes": MemoryTemplate(
            name="Meeting Notes",
            description="Capture key points from meetings",
            default_quadrants=["personal"],
            default_tags=["meeting", "notes"],
            suggested_importance=0.7,
            content_schema={
                "participants": "List of people present",
                "topic": "Main topic/agenda",
                "key_points": "Key discussion points",
                "decisions": "Decisions made",
                "action_items": "Action items with owners",
                "follow_up": "Follow-up items"
            },
            template_prompt="""Extract meeting notes in this format:
Participants: [list]
Topic: [topic]

Key Points:
- [point 1]
- [point 2]

Decisions:
- [decision 1]

Action Items:
- [ ] [task] - @[owner]

Follow-up: [details]"""
        ),

        "project_spec": MemoryTemplate(
            name="Project Specification",
            description="Document project requirements and specifications",
            default_quadrants=["coding"],
            default_tags=["project", "spec", "requirements"],
            suggested_importance=0.9,
            content_schema={
                "project_name": "Name of the project",
                "overview": "Brief description",
                "goals": "Project goals/objectives",
                "requirements": "Technical requirements",
                "timeline": "Key milestones",
                "resources": "Required resources",
                "notes": "Additional notes"
            },
            template_prompt="""Extract project specification:
# [Project Name]

## Overview
[brief description]

## Goals
- [goal 1]
- [goal 2]

## Requirements
- [requirement 1]
- [requirement 2]

## Timeline
- [milestone]: [date]

## Resources
- [resource]

## Notes
[additional notes]"""
        ),

        "bug_report": MemoryTemplate(
            name="Bug Report",
            description="Document software bugs and issues",
            default_quadrants=["coding"],
            default_tags=["bug", "issue"],
            suggested_importance=0.8,
            content_schema={
                "title": "Brief bug description",
                "severity": "Critical/High/Medium/Low",
                "description": "Detailed description",
                "steps_to_reproduce": "Steps to reproduce",
                "expected_behavior": "What should happen",
                "actual_behavior": "What actually happens",
                "environment": "Environment details",
                "workaround": "Any known workaround"
            },
            template_prompt="""Extract bug report:
## [Title]

**Severity:** [Critical/High/Medium/Low]

### Description
[detailed description]

### Steps to Reproduce
1. [step 1]
2. [step 2]

### Expected Behavior
[what should happen]

### Actual Behavior
[what actually happens]

### Environment
- OS: [os]
- Version: [version]

### Workaround
[workaround if any]"""
        ),

        "feature_request": MemoryTemplate(
            name="Feature Request",
            description="Document feature ideas and requests",
            default_quadrants=["coding", "personal"],
            default_tags=["feature", "idea", "enhancement"],
            suggested_importance=0.6,
            content_schema={
                "title": "Feature title",
                "problem": "Problem this solves",
                "solution": "Proposed solution",
                "benefits": "Expected benefits",
                "considerations": "Implementation considerations",
                "priority": "Priority level"
            },
            template_prompt="""Extract feature request:
## [Title]

### Problem
[what problem does this solve]

### Proposed Solution
[description of feature]

### Benefits
- [benefit 1]
- [benefit 2]

### Considerations
- [consideration 1]

### Priority
[High/Medium/Low]"""
        ),

        "research_notes": MemoryTemplate(
            name="Research Notes",
            description="Capture research findings and insights",
            default_quadrants=["research"],
            default_tags=["research", "notes"],
            suggested_importance=0.75,
            content_schema={
                "topic": "Research topic",
                "sources": "Information sources",
                "key_findings": "Main findings",
                "insights": "Personal insights",
                "questions": "Remaining questions",
                "next_steps": "Next research steps"
            },
            template_prompt="""Extract research notes:
# Research: [Topic]

## Sources
- [source 1]
- [source 2]

## Key Findings
- [finding 1]
- [finding 2]

## Insights
[personal insights]

## Questions
- [question 1]

## Next Steps
- [next step 1]"""
        ),

        "code_snippet": MemoryTemplate(
            name="Code Snippet",
            description="Store useful code snippets and examples",
            default_quadrants=["coding"],
            default_tags=["code", "snippet"],
            suggested_importance=0.65,
            content_schema={
                "language": "Programming language",
                "description": "What this code does",
                "code": "The code snippet",
                "usage": "How to use it",
                "notes": "Additional notes"
            },
            template_prompt="""Extract code snippet:
## [Description]

**Language:** [language]

```[language]
[code]
```

### Usage
[how to use this code]

### Notes
[additional notes]"""
        ),

        "book_summary": MemoryTemplate(
            name="Book/Article Summary",
            description="Summarize books, articles, or papers",
            default_quadrants=["research", "personal"],
            default_tags=["reading", "summary"],
            suggested_importance=0.7,
            content_schema={
                "title": "Title of work",
                "author": "Author(s)",
                "type": "Book/Article/Paper",
                "key_points": "Main points/takeaways",
                "quotes": "Notable quotes",
                "personal_take": "Personal thoughts",
                "rating": "Personal rating"
            },
            template_prompt="""Extract book/article summary:
# [Title]

**Author:** [author]
**Type:** [Book/Article/Paper]

## Key Points
- [point 1]
- [point 2]

## Notable Quotes
> [quote 1]

## Personal Take
[your thoughts]

## Rating: [X/10]"""
        ),

        "learning_log": MemoryTemplate(
            name="Learning Log",
            description="Track what you've learned",
            default_quadrants=["personal", "research"],
            default_tags=["learning", "growth"],
            suggested_importance=0.6,
            content_schema={
                "topic": "What was learned",
                "context": "Where/How you learned it",
                "details": "What you learned",
                "application": "How you'll apply it",
                "related": "Related topics"
            },
            template_prompt="""Extract learning log:
## Learned: [Topic]

**Context:** [where/how]

### What I Learned
[details]

### Application
[how I'll use this]

### Related Topics
- [related 1]"""
        ),

        "decision_log": MemoryTemplate(
            name="Decision Log",
            description="Document important decisions and rationale",
            default_quadrants=["personal"],
            default_tags=["decision", "rationale"],
            suggested_importance=0.8,
            content_schema={
                "decision": "The decision made",
                "context": "Decision context",
                "options": "Options considered",
                "rationale": "Why this choice",
                "tradeoffs": "Trade-offs involved",
                "outcome": "Expected outcome"
            },
            template_prompt="""Extract decision log:
## Decision: [Decision]

**Context:** [background]

### Options Considered
- Option A: [description]
- Option B: [description]

### Rationale
[why this choice]

### Trade-offs
- [trade-off 1]

### Expected Outcome
[outcome]"""
        ),

        "ai_instruction": MemoryTemplate(
            name="AI Instruction",
            description="Capture instructions for AI assistants",
            default_quadrants=["ai_instructions"],
            default_tags=["ai", "instruction"],
            suggested_importance=0.95,
            content_schema={
                "instruction": "The instruction/rule",
                "context": "When this applies",
                "priority": "Priority level",
                "examples": "Examples if applicable"
            },
            template_prompt="""Extract AI instruction:
## Instruction
[instruction text]

**Applies When:** [context]
**Priority:** [High/Medium/Low]

### Examples
- Input: [example input]
  Output: [expected output]"""
        )
    }

    def __init__(self):
        pass

    def list_templates(self) -> List[Dict[str, Any]]:
        """List all available templates."""
        return [
            {
                "id": key,
                "name": template.name,
                "description": template.description,
                "default_quadrants": template.default_quadrants,
                "default_tags": template.default_tags,
                "suggested_importance": template.suggested_importance
            }
            for key, template in self.TEMPLATES.items()
        ]

    def get_template(self, template_id: str) -> Optional[MemoryTemplate]:
        """Get a specific template by ID."""
        return self.TEMPLATES.get(template_id)

    def apply_template(
        self,
        template_id: str,
        content: str,
        llm=None
    ) -> Dict[str, Any]:
        """
        Apply a template to raw content.

        If llm is provided, uses the template prompt to restructure content.
        Otherwise, returns template metadata for manual formatting.
        """
        template = self.get_template(template_id)
        if not template:
            return {"error": f"Template not found: {template_id}"}

        result = {
            "template_id": template_id,
            "template_name": template.name,
            "default_quadrants": template.default_quadrants,
            "default_tags": template.default_tags,
            "suggested_importance": template.suggested_importance,
            "content_schema": template.content_schema,
            "formatted_content": None
        }

        # If LLM available, use it to format content
        if llm:
            # This would be async in practice
            result["formatted_content"] = f"[Formatted using {template.name} template]\n\n{content}"

        return result

    def suggest_template(self, content: str) -> List[Dict[str, Any]]:
        """Suggest templates based on content analysis."""
        suggestions = []
        content_lower = content.lower()

        # Simple keyword matching for suggestions
        indicators = {
            "meeting_notes": ["meeting", "discussed", "participants", "action items"],
            "project_spec": ["project", "requirements", "specification", "goals"],
            "bug_report": ["bug", "error", "issue", "crash", "reproduce"],
            "feature_request": ["feature", "request", "would be nice", "enhancement"],
            "research_notes": ["research", "study", "found that", "according to"],
            "code_snippet": ["code", "function", "class", "def ", "import ", "```"],
            "book_summary": ["book", "author", "chapter", "read", "summary"],
            "learning_log": ["learned", "tutorial", "course", "studied"],
            "decision_log": ["decided", "decision", "chose", "option", "trade-off"],
            "ai_instruction": ["always", "never", "should", "prefer", "instruction"]
        }

        for template_id, keywords in indicators.items():
            score = sum(1 for kw in keywords if kw in content_lower)
            if score > 0:
                template = self.TEMPLATES[template_id]
                suggestions.append({
                    "template_id": template_id,
                    "name": template.name,
                    "match_score": score,
                    "description": template.description
                })

        # Sort by match score
        suggestions.sort(key=lambda x: x["match_score"], reverse=True)
        return suggestions[:3]  # Top 3 suggestions

    def create_from_template(
        self,
        template_id: str,
        filled_fields: Dict[str, str],
        custom_tags: Optional[List[str]] = None
    ) -> Dict[str, Any]:
        """
        Create a memory from a template with filled fields.

        Args:
            template_id: The template to use
            filled_fields: Dictionary of field values
            custom_tags: Additional tags to include

        Returns:
            Memory data ready to be saved
        """
        template = self.get_template(template_id)
        if not template:
            return {"error": f"Template not found: {template_id}"}

        # Build content from fields
        content_parts = []
        for field, description in template.content_schema.items():
            value = filled_fields.get(field, "")
            if value:
                content_parts.append(f"## {field.replace('_', ' ').title()}\n{value}\n")

        content = "\n".join(content_parts)

        # Build summary
        summary = filled_fields.get(
            "title",
            filled_fields.get("topic", f"{template.name} - {datetime.now().strftime('%Y-%m-%d')}")
        )

        # Merge tags
        tags = list(template.default_tags)
        if custom_tags:
            tags.extend(custom_tags)
        tags = list(set(tags))  # Remove duplicates

        return {
            "summary": summary,
            "content": content,
            "quadrants": template.default_quadrants,
            "tags": tags,
            "importance": template.suggested_importance,
            "type": "raw"
        }
