"""Theme Generator - Groups questions into actionable themes using LLM."""

import json
from typing import List, Dict, Any
from collections import defaultdict

from ..core.llm_client import LLMClient


class ThemeGenerator:
    """Generates themes from customer questions using LLM."""

    def __init__(self, llm_client: LLMClient, repository=None, auto_consolidate=True):
        """
        Initialize theme generator.

        Args:
            llm_client: LLM client for theme generation
            repository: Optional repository for database operations during batching
            auto_consolidate: Whether to automatically consolidate themes after generation (default: True)
        """
        self.llm_client = llm_client
        self.repository = repository
        self.auto_consolidate = auto_consolidate

    def generate_themes(
        self,
        questions: List[Dict[str, Any]],
        persona: str,
        num_themes: int = 6
    ) -> Dict[str, Any]:
        """
        Generate themes from a list of questions using batching for large sets.

        Args:
            questions: List of question dicts with 'question' and 'frequency' keys
            persona: Persona type (Decision Maker, Influencer, User)
            num_themes: Target number of themes to generate (default: 6)

        Returns:
            Dict with 'themes' list containing theme definitions and question assignments
        """
        if not questions:
            return {'themes': []}

        # Use batching for large question sets
        BATCH_SIZE = 50

        if len(questions) <= BATCH_SIZE:
            # Small set - process all at once
            existing_themes = None
            if self.repository:
                # Load existing themes from DB even for single batch
                existing_themes = self._load_existing_themes_from_db(persona)
                if existing_themes:
                    print(f"   📚 Loaded {len(existing_themes)} existing themes from database")

            result = self._generate_themes_single_batch(questions, persona, num_themes, existing_themes=existing_themes)

            # Store to DB if repository available
            if self.repository and result and result.get('themes'):
                self._store_themes_to_db(persona, result['themes'], is_incremental=bool(existing_themes))
                # Reload from DB to get accurate state
                final_themes = self._load_existing_themes_from_db(persona)

                # Run consolidation if needed
                if self.auto_consolidate and len(final_themes) > 10:
                    print(f"\n   🔄 Running automatic theme consolidation...")
                    final_themes = self._consolidate_themes(persona, final_themes)

                return {'themes': final_themes}

            return result
        else:
            # Large set - process in batches with DB updates
            return self._generate_themes_batched(questions, persona, num_themes, batch_size=BATCH_SIZE)

    def _generate_themes_batched(
        self,
        questions: List[Dict[str, Any]],
        persona: str,
        num_themes: int,
        batch_size: int
    ) -> Dict[str, Any]:
        """
        Generate themes in batches, maintaining consistency across batches.
        Stores themes to database after each batch and loads from DB for next batch.

        Args:
            questions: Full list of questions
            persona: Persona type
            num_themes: Target number of themes
            batch_size: Number of questions per batch

        Returns:
            Dict with all themes combined
        """
        if not self.repository:
            raise ValueError("Repository required for batched theme generation")

        total_batches = (len(questions) + batch_size - 1) // batch_size

        print(f"   ℹ️  Processing {len(questions)} questions in {total_batches} batches of {batch_size}")
        print(f"   ℹ️  Database will be updated after each batch")

        for batch_num in range(total_batches):
            start_idx = batch_num * batch_size
            end_idx = min(start_idx + batch_size, len(questions))
            batch_questions = questions[start_idx:end_idx]

            print(f"   → Batch {batch_num + 1}/{total_batches}: Processing questions {start_idx + 1}-{end_idx}...")

            # Load existing themes from database
            existing_themes = self._load_existing_themes_from_db(persona)
            if existing_themes:
                print(f"      📚 Loaded {len(existing_themes)} existing themes from database")

            # Generate themes for this batch
            batch_result = self._generate_themes_single_batch(
                batch_questions,
                persona,
                num_themes,
                existing_themes=existing_themes
            )

            if batch_result and batch_result.get('themes'):
                # Store themes to database immediately
                self._store_themes_to_db(persona, batch_result['themes'], is_incremental=True)

                # Reload to get accurate count
                all_themes = self._load_existing_themes_from_db(persona)
                print(f"      ✓ Batch complete. Total themes in DB: {len(all_themes)}")
            else:
                print(f"      ⚠️  Batch returned no themes")

        # Load final themes from database
        final_themes = self._load_existing_themes_from_db(persona)

        # Run consolidation to merge similar themes
        if self.auto_consolidate:
            print(f"\n   🔄 Running automatic theme consolidation...")
            consolidated_themes = self._consolidate_themes(persona, final_themes)
            return {'themes': consolidated_themes}
        else:
            return {'themes': final_themes}

    def _enrich_themes_with_call_ids(self, themes: List[Dict], original_questions: List[Dict]) -> List[Dict]:
        """
        Enrich LLM-generated themes with call_ids from original questions.

        LLM returns questions without call_ids, so we need to match them back
        to the original questions to restore the call_ids.

        Args:
            themes: Themes from LLM (questions lack call_ids)
            original_questions: Original questions with call_ids

        Returns:
            Themes with call_ids restored
        """
        # Build a map of normalized question -> call_ids
        question_to_call_ids = {}
        for q in original_questions:
            normalized = self.normalize_question(q['question'])
            question_to_call_ids[normalized] = q.get('call_ids', [])

        # Enrich each theme's questions
        for theme in themes:
            for q in theme.get('questions', []):
                q_text = q.get('question', '')
                normalized = self.normalize_question(q_text)

                # Restore call_ids from original questions
                if normalized in question_to_call_ids:
                    q['call_ids'] = question_to_call_ids[normalized]
                else:
                    q['call_ids'] = []

        return themes

    def _generate_themes_single_batch(
        self,
        questions: List[Dict[str, Any]],
        persona: str,
        num_themes: int,
        existing_themes: List[Dict] = None
    ) -> Dict[str, Any]:
        """
        Generate themes for a single batch of questions.

        Args:
            questions: Batch of questions (with call_ids)
            persona: Persona type
            num_themes: Target number of themes
            existing_themes: Previously generated themes (if any)

        Returns:
            Dict with themes for this batch
        """
        # Build prompt
        prompt = self._build_theme_generation_prompt(
            questions,
            persona,
            num_themes,
            existing_themes=existing_themes
        )

        # Call LLM
        try:
            response = self.llm_client.call_llm(prompt, max_tokens=8000)

            # Parse JSON response
            response = self._clean_json_response(response)

            # Try to parse JSON
            try:
                result = json.loads(response)
            except json.JSONDecodeError as e:
                # Try to fix common JSON errors
                print(f"      ⚠️  JSON parse error: {e}")
                print(f"         Attempting to fix...")

                # Try fixing truncated JSON
                response = self._attempt_json_repair(response)
                result = json.loads(response)
                print(f"         ✓ Repaired JSON successfully")

            # Enrich themes with call_ids from original questions
            if result.get('themes'):
                result['themes'] = self._enrich_themes_with_call_ids(result['themes'], questions)

            return result

        except json.JSONDecodeError as e:
            print(f"      ❌ Failed to parse JSON: {e}")
            print(f"         Response length: {len(response)} chars")
            return {'themes': []}
        except Exception as e:
            print(f"      ❌ Error: {e}")
            return {'themes': []}

    def _load_existing_themes_from_db(self, persona: str) -> List[Dict]:
        """
        Load existing themes for a persona from database.

        Args:
            persona: Persona type

        Returns:
            List of theme dicts with questions
        """
        if not self.repository:
            return []

        cursor = self.repository.conn.execute("""
            SELECT
                id,
                theme_name,
                theme_description,
                suggested_collateral
            FROM question_themes
            WHERE persona = ?
            ORDER BY question_count DESC
        """, (persona,))

        themes = []
        for row in cursor.fetchall():
            theme_id = row['id']

            # Load questions for this theme
            q_cursor = self.repository.conn.execute("""
                SELECT question_original, frequency, sample_call_ids
                FROM question_theme_assignments
                WHERE theme_id = ?
                ORDER BY frequency DESC
            """, (theme_id,))

            questions = []
            for q_row in q_cursor.fetchall():
                questions.append({
                    'question': q_row['question_original'],
                    'frequency': q_row['frequency'],
                    'call_ids': json.loads(q_row['sample_call_ids']) if q_row['sample_call_ids'] else []
                })

            try:
                suggested_collateral = json.loads(row['suggested_collateral']) if row['suggested_collateral'] else []
            except:
                suggested_collateral = []

            themes.append({
                'theme_name': row['theme_name'],
                'theme_description': row['theme_description'],
                'suggested_collateral': suggested_collateral,
                'questions': questions
            })

        return themes

    def _store_themes_to_db(self, persona: str, new_themes: List[Dict], is_incremental: bool = False):
        """
        Store themes to database, merging with existing themes.

        Args:
            persona: Persona type
            new_themes: List of new theme dicts from LLM
            is_incremental: If True, merge with existing themes; if False, replace all
        """
        if not self.repository:
            return

        if is_incremental:
            # Load existing themes and merge
            existing_themes = self._load_existing_themes_from_db(persona)
            merged_themes = self._merge_themes(existing_themes, new_themes)
        else:
            merged_themes = new_themes

        # Delete existing themes for this persona
        self.repository.conn.execute("""
            DELETE FROM question_themes WHERE persona = ?
        """, (persona,))

        # Insert merged themes
        for theme in merged_themes:
            theme_name = theme.get('theme_name', 'Untitled Theme')
            theme_description = theme.get('theme_description', '')
            suggested_collateral = json.dumps(theme.get('suggested_collateral', []))
            questions = theme.get('questions', [])

            # Insert theme
            cursor = self.repository.conn.execute("""
                INSERT INTO question_themes (
                    persona, theme_name, theme_description,
                    suggested_collateral, question_count, last_generated
                ) VALUES (?, ?, ?, ?, ?, datetime('now'))
            """, (persona, theme_name, theme_description, suggested_collateral, len(questions)))

            theme_id = cursor.lastrowid

            # Insert question assignments
            for q in questions:
                question_text = q.get('question', '')
                frequency = q.get('frequency', 1)
                call_ids = q.get('call_ids', [])

                normalized = self.normalize_question(question_text)
                sample_call_ids = json.dumps(call_ids[:5])  # Store up to 5 sample calls

                self.repository.conn.execute("""
                    INSERT INTO question_theme_assignments (
                        theme_id, question_normalized, question_original,
                        frequency, sample_call_ids
                    ) VALUES (?, ?, ?, ?, ?)
                """, (theme_id, normalized, question_text, frequency, sample_call_ids))

        self.repository.conn.commit()

    def _consolidate_themes(self, persona: str, themes: List[Dict]) -> List[Dict]:
        """
        Consolidate similar/duplicate themes using LLM.

        Args:
            persona: Persona type
            themes: List of themes to consolidate

        Returns:
            Consolidated list of themes
        """
        print(f"      [DEBUG] _consolidate_themes called with {len(themes)} themes")

        if len(themes) <= 10:
            print(f"      ℹ️  {len(themes)} themes - no consolidation needed")
            return themes

        print(f"      ℹ️  {len(themes)} themes found - identifying duplicates...")
        print(f"      [DEBUG] Building consolidation prompt...")

        # Build consolidation prompt
        consolidation_prompt = self._build_consolidation_prompt(themes, persona)
        print(f"      [DEBUG] Prompt built, calling LLM (max_tokens=4000)...")

        try:
            response = self.llm_client.call_llm(consolidation_prompt, max_tokens=4000)
            print(f"      [DEBUG] LLM returned response ({len(response)} chars)")
            response = self._clean_json_response(response)

            try:
                result = json.loads(response)
            except json.JSONDecodeError as e:
                print(f"      ⚠️  Failed to parse consolidation response: {e}")
                print(f"      ⏭️  Skipping consolidation, keeping original themes")
                return themes

            merge_groups = result.get('merge_groups', [])
            keep_separate = result.get('keep_separate', [])

            if not merge_groups and not keep_separate:
                print(f"      ⚠️  No consolidation instructions returned")
                return themes

            print(f"      ✓ Identified {len(merge_groups)} groups to merge")

            # Perform consolidation
            consolidated_themes = []
            processed_theme_names = set()

            # Process merge groups
            for group in merge_groups:
                theme_names_to_merge = group.get('themes_to_merge', [])
                new_name = group.get('consolidated_name', theme_names_to_merge[0])
                new_description = group.get('consolidated_description', '')

                # Find all themes in this group
                themes_to_merge = [t for t in themes if t['theme_name'] in theme_names_to_merge]

                if not themes_to_merge:
                    continue

                # Merge questions from all themes
                all_questions = []
                seen_questions = set()
                collateral_sets = []

                for theme in themes_to_merge:
                    for q in theme.get('questions', []):
                        q_text = q['question']
                        if q_text not in seen_questions:
                            all_questions.append(q)
                            seen_questions.add(q_text)

                    collateral = theme.get('suggested_collateral', [])
                    if collateral:
                        collateral_sets.extend(collateral)

                # Deduplicate collateral
                unique_collateral = list(dict.fromkeys(collateral_sets))[:3]

                consolidated_themes.append({
                    'theme_name': new_name,
                    'theme_description': new_description,
                    'suggested_collateral': unique_collateral,
                    'questions': all_questions
                })

                # Mark these themes as processed
                for name in theme_names_to_merge:
                    processed_theme_names.add(name)

                print(f"      → Merged {len(theme_names_to_merge)} themes into '{new_name}' ({len(all_questions)} questions)")

            # Add themes that should be kept separate
            for theme in themes:
                theme_name = theme['theme_name']
                if theme_name not in processed_theme_names:
                    consolidated_themes.append(theme)

            print(f"      ✅ Consolidation complete: {len(themes)} → {len(consolidated_themes)} themes")

            # Store consolidated themes back to database
            if self.repository and consolidated_themes:
                self._store_themes_to_db(persona, consolidated_themes, is_incremental=False)

            return consolidated_themes

        except Exception as e:
            print(f"      ❌ Consolidation failed: {e}")
            print(f"      ⏭️  Keeping original themes")
            return themes

    def _build_consolidation_prompt(self, themes: List[Dict], persona: str) -> str:
        """Build prompt for theme consolidation."""

        themes_str = ""
        for i, theme in enumerate(themes, 1):
            theme_name = theme.get('theme_name', 'Untitled')
            theme_desc = theme.get('theme_description', '')
            q_count = len(theme.get('questions', []))

            # Show 3 sample questions
            sample_questions = theme.get('questions', [])[:3]
            samples_str = "\n".join([f"      - {q['question'][:80]}" for q in sample_questions])

            themes_str += f"{i}. **{theme_name}** ({q_count} questions)\n"
            themes_str += f"   Description: {theme_desc}\n"
            if samples_str:
                themes_str += f"   Sample questions:\n{samples_str}\n"
            themes_str += "\n"

        prompt = f"""You are analyzing {len(themes)} question themes for {persona} stakeholders.

Your task: Identify which themes are duplicates or very similar and should be merged together.

CURRENT THEMES:
{themes_str}

INSTRUCTIONS:
1. Look for themes that cover the same topic (e.g., "Pricing & Licensing", "Enterprise Pricing Models", "Pricing Questions" are all about pricing)
2. Group similar themes together for merging
3. For each group, suggest a consolidated name and description
4. Keep themes separate if they cover truly different topics
5. Aim for 5-10 final themes total

OUTPUT FORMAT (JSON):
{{
  "merge_groups": [
    {{
      "themes_to_merge": ["Pricing & Licensing", "Enterprise Pricing Models", "Pricing Questions"],
      "consolidated_name": "Pricing & Licensing",
      "consolidated_description": "Questions about pricing models, volume discounts, licensing, and cost structures",
      "reason": "All three themes are about pricing and should be consolidated"
    }},
    {{
      "themes_to_merge": ["Security Compliance", "Data Security & Privacy"],
      "consolidated_name": "Security & Compliance",
      "consolidated_description": "Questions about security certifications, data handling, and regulatory compliance",
      "reason": "Both themes cover security topics"
    }}
  ],
  "keep_separate": [
    "Integration & APIs",
    "Product Roadmap",
    "Trial & POC Process"
  ]
}}

IMPORTANT:
- Only merge themes that are clearly about the same topic
- Don't merge themes just because they're vaguely related
- Each merge group should have 2+ themes
- All original theme names should appear in either merge_groups or keep_separate

Return ONLY valid JSON, no other text."""

        return prompt

    def _merge_themes(self, existing_themes: List[Dict], new_themes: List[Dict]) -> List[Dict]:
        """
        Merge new themes with existing themes.

        If a new theme has the same name as an existing theme, merge their questions.
        Otherwise, add as a new theme.

        Args:
            existing_themes: List of existing theme dicts
            new_themes: List of new theme dicts

        Returns:
            Merged list of themes
        """
        if not existing_themes:
            return new_themes

        # Create a map of existing themes by name
        theme_map = {}
        for theme in existing_themes:
            theme_name = theme['theme_name']
            theme_map[theme_name] = theme

        # Merge new themes
        for new_theme in new_themes:
            theme_name = new_theme['theme_name']

            if theme_name in theme_map:
                # Merge questions into existing theme
                existing_questions = theme_map[theme_name].get('questions', [])
                new_questions = new_theme.get('questions', [])

                # Avoid duplicates (by question text)
                existing_q_texts = {q['question'] for q in existing_questions}
                for q in new_questions:
                    if q['question'] not in existing_q_texts:
                        existing_questions.append(q)

                theme_map[theme_name]['questions'] = existing_questions
            else:
                # Add new theme
                theme_map[theme_name] = new_theme

        return list(theme_map.values())

    def _build_theme_generation_prompt(
        self,
        questions: List[Dict[str, Any]],
        persona: str,
        num_themes: int,
        existing_themes: List[Dict] = None
    ) -> str:
        """Build the prompt for theme generation."""

        # Format questions for prompt
        questions_str = ""
        for i, q in enumerate(questions, 1):
            freq = q.get('frequency', 1)
            question_text = q.get('question', '')
            questions_str += f"{i}. \"{question_text}\" (asked {freq}x)\n"

        # Format existing themes if provided
        existing_themes_str = ""
        if existing_themes:
            existing_themes_str = "\n\n" + "=" * 80 + "\n"
            existing_themes_str += "⚠️  EXISTING THEMES - ASSIGN TO THESE FIRST!\n"
            existing_themes_str += "=" * 80 + "\n\n"

            for i, theme in enumerate(existing_themes, 1):
                theme_name = theme.get('theme_name', 'Untitled')
                theme_desc = theme.get('theme_description', '')
                q_count = len(theme.get('questions', []))

                # Show sample questions from existing theme
                sample_questions = theme.get('questions', [])[:3]
                samples_str = ""
                if sample_questions:
                    samples_str = "\n   Sample questions in this theme:"
                    for q in sample_questions:
                        q_text = q.get('question', '')[:80]
                        samples_str += f"\n   - {q_text}"

                existing_themes_str += f"{i}. **{theme_name}**\n"
                existing_themes_str += f"   Description: {theme_desc}\n"
                existing_themes_str += f"   Current questions: {q_count}{samples_str}\n\n"

            existing_themes_str += """
🎯 CRITICAL INSTRUCTIONS - READ CAREFULLY:

1. **FIRST PRIORITY**: For EACH new question below, ask yourself:
   "Does this question fit into ANY of the existing themes above?"

2. If YES → ASSIGN to that existing theme (even if not a perfect match)

3. If NO → Only then create a NEW theme

4. **When to assign to existing theme:**
   - Question is about the same general topic (e.g., "per-user pricing" → "Pricing & Licensing")
   - Question is a variation of existing questions in that theme
   - When in doubt, prefer existing themes over creating new ones

5. **When to create NEW theme:**
   - Question is about a COMPLETELY DIFFERENT topic not covered by any existing theme
   - Example: If existing themes are about pricing, security, integrations, and the new question is about "analytics dashboards", create new theme

6. **DO NOT create narrow themes:**
   - ❌ BAD: "Per-User Pricing for Contractors" (too narrow)
   - ✅ GOOD: "Pricing & Licensing" (broad, covers all pricing questions)

""" + "=" * 80 + "\n\n"

        task_description = "Group these questions into themes" if not existing_themes else "Assign these questions to existing themes above, or create new themes if needed."

        prompt = f"""You are analyzing customer questions from sales calls with {persona} stakeholders.

Your task: {task_description} These themes will be used for creating sales collateral (battle cards, FAQs, one-pagers).{existing_themes_str}

QUESTIONS TO PROCESS (with frequency):
{questions_str}

INSTRUCTIONS:
1. {"Assign questions to existing themes when they fit, or create new themes for different topics" if existing_themes else f"Identify {num_themes} themes that naturally emerge from these questions"}
2. Each theme should be:
   - Specific enough to create targeted collateral for
   - Actionable (e.g., "Enterprise Pricing" not "Money Topics")
   - Broad enough to group related questions (avoid over-fragmentation)
3. Every question MUST be assigned to exactly one theme
4. For each theme, suggest 2-3 specific types of collateral

OUTPUT FORMAT (JSON):
{{
  "themes": [
    {{
      "theme_name": "Enterprise Pricing & Licensing",
      "theme_description": "Questions about pricing models, volume discounts, and licensing for large deployments",
      "questions": [
        {{
          "question": "What's your pricing model for enterprise deployments?",
          "frequency": 12
        }},
        {{
          "question": "Do you offer volume discounts?",
          "frequency": 8
        }}
      ],
      "suggested_collateral": [
        "Battle card: Enterprise Pricing Overview",
        "FAQ: Volume Licensing",
        "One-pager: ROI Calculator"
      ]
    }},
    {{
      "theme_name": "Security & Compliance",
      "theme_description": "Questions about security certifications, data handling, and regulatory compliance",
      "questions": [
        {{
          "question": "Do you have SOC 2 compliance?",
          "frequency": 15
        }}
      ],
      "suggested_collateral": [
        "Battle card: Security & Compliance",
        "One-pager: Security Architecture",
        "FAQ: Compliance Certifications"
      ]
    }}
  ]
}}


IMPORTANT:
- Every question must appear in exactly one theme
- Theme names should be 2-5 words, action-oriented
- {"Prefer assigning to existing themes when appropriate, but create new themes if questions don't fit" if existing_themes else "Collateral suggestions should be specific (e.g., \"SOC 2 Compliance FAQ\" not \"Security Doc\")"}
- Avoid creating overly narrow themes (e.g., "Per-User Pricing" → use broader "Pricing & Licensing")

Return ONLY valid JSON, no other text."""

        return prompt

    def _clean_json_response(self, response: str) -> str:
        """Clean up LLM response to extract JSON."""
        response = response.strip()

        # Remove markdown code blocks
        if response.startswith("```json"):
            response = response[7:]
        elif response.startswith("```"):
            response = response[3:]

        if response.endswith("```"):
            response = response[:-3]

        return response.strip()

    def _attempt_json_repair(self, response: str) -> str:
        """Attempt to repair malformed JSON."""
        # If JSON is truncated, try to close it
        if not response.rstrip().endswith('}'):
            # Count open braces
            open_braces = response.count('{')
            close_braces = response.count('}')

            if open_braces > close_braces:
                # Add missing closing braces
                missing = open_braces - close_braces
                response = response.rstrip()

                # Try to close arrays and objects gracefully
                if response.endswith(','):
                    response = response[:-1]  # Remove trailing comma

                # Close arrays
                open_brackets = response.count('[')
                close_brackets = response.count(']')
                if open_brackets > close_brackets:
                    response += ']' * (open_brackets - close_brackets)

                # Close objects
                response += '}' * missing

        return response

    def normalize_question(self, question: str) -> str:
        """Normalize question text for matching/deduping."""
        return question.lower().strip().rstrip('?').strip()
