"""Persona Classifier - Classify participants by role/persona."""


class PersonaClassifier:
    """Classifies participants into personas based on job titles."""

    # Persona types
    DECISION_MAKER = "Decision Maker"
    INFLUENCER = "Influencer"
    USER = "User"

    @staticmethod
    def classify(title: str) -> str:
        """
        Classify a participant's title into a persona.

        Classification hierarchy (checked in order):
        1. Decision Maker: VPs, SVPs, CTO, EVP, Chief titles
        2. Influencer: Directors, Managers, Heads, Principals, Distinguished, Leads
        3. User: Engineers, Developers (including Senior/Staff)
        4. Default: User (for unknown/empty titles)

        Args:
            title: Job title string

        Returns:
            Persona name: "Decision Maker", "Influencer", or "User"
        """
        if not title or not title.strip():
            return PersonaClassifier.USER

        title_lower = title.lower()

        # ====================================================================
        # Early check for Director to avoid conflicts with "Chief Director"
        # ====================================================================
        if 'director' in title_lower and 'chief' not in title_lower:
            return PersonaClassifier.INFLUENCER

        # ====================================================================
        # DECISION MAKERS (Priority 1 - highest)
        # ====================================================================
        # Check specific patterns first to avoid partial matches
        dm_patterns = [
            'cto',
            'chief technology officer',
            'chief information officer',
            'chief',  # Chief Architect, Chief Engineer, etc.
            'vp ',  # Space after to avoid matching "svp" prematurely
            'vice president',
            'svp',
            'senior vice president',
            'evp',
            'executive vice president',
        ]

        for pattern in dm_patterns:
            if pattern in title_lower:
                return PersonaClassifier.DECISION_MAKER

        # ====================================================================
        # INFLUENCERS (Priority 2)
        # ====================================================================
        # Check more specific patterns first (e.g., "senior manager" before "manager")
        inf_patterns = [
            'director',
            'senior manager',
            'sr. manager',
            'sr manager',
            'manager',  # Check after "senior manager"
            'head of',
            'head ',  # "Head of Engineering", "Engineering Head"
            'principal',  # Principal Engineer, Principal Architect
            'distinguished',  # Distinguished Engineer
            'tech lead',
            'technical lead',
            'engineering lead',
            'team lead',
            ' lead',  # Space before to catch "Platform Lead", etc.
        ]

        for pattern in inf_patterns:
            if pattern in title_lower:
                return PersonaClassifier.INFLUENCER

        # ====================================================================
        # USERS (Priority 3)
        # ====================================================================
        # Engineers, Developers (including Senior, Staff, etc.)
        user_patterns = [
            'software engineer',
            'software developer',
            'developer',
            'engineer',  # Catches Senior/Staff/Software Engineer
            'programmer',
            'architect',  # Solutions Architect, Staff Architect (for now)
        ]

        for pattern in user_patterns:
            if pattern in title_lower:
                return PersonaClassifier.USER

        # ====================================================================
        # DEFAULT
        # ====================================================================
        return PersonaClassifier.USER

    @staticmethod
    def get_persona_icon(persona: str) -> str:
        """Get Font Awesome icon class for persona."""
        if persona == PersonaClassifier.DECISION_MAKER:
            return "fa-user-tie"
        elif persona == PersonaClassifier.INFLUENCER:
            return "fa-handshake"
        elif persona == PersonaClassifier.USER:
            return "fa-code"
        else:
            return "fa-user"

    @staticmethod
    def get_persona_color(persona: str) -> str:
        """Get color hex code for persona."""
        if persona == PersonaClassifier.DECISION_MAKER:
            return "#3498db"  # Blue
        elif persona == PersonaClassifier.INFLUENCER:
            return "#2ecc71"  # Green
        elif persona == PersonaClassifier.USER:
            return "#e67e22"  # Orange
        else:
            return "#95a5a6"  # Gray


# Test cases (for verification)
if __name__ == "__main__":
    test_cases = [
        # Decision Makers
        ("VP Engineering", "Decision Maker"),
        ("SVP of Technology", "Decision Maker"),
        ("Vice President, Product", "Decision Maker"),
        ("CTO", "Decision Maker"),
        ("Chief Architect", "Decision Maker"),
        ("Chief Engineer", "Decision Maker"),
        ("EVP Technology", "Decision Maker"),

        # Influencers
        ("Director of Engineering", "Influencer"),
        ("Senior Manager, DevOps", "Influencer"),
        ("Sr. Manager", "Influencer"),
        ("Engineering Manager", "Influencer"),
        ("Head of Platform", "Influencer"),
        ("Principal Engineer", "Influencer"),
        ("Distinguished Engineer", "Influencer"),
        ("Tech Lead", "Influencer"),
        ("Engineering Lead", "Influencer"),

        # Users
        ("Software Engineer", "User"),
        ("Senior Software Engineer", "User"),
        ("Staff Engineer", "User"),
        ("Developer", "User"),
        ("Senior Developer", "User"),
        ("Software Developer", "User"),
        ("Solutions Architect", "User"),
        ("Staff Architect", "User"),

        # Edge cases
        ("", "User"),  # Empty
        ("Consultant", "User"),  # Unknown
        ("Analyst", "User"),  # Unknown
    ]

    print("Testing PersonaClassifier...\n")
    passed = 0
    failed = 0

    for title, expected in test_cases:
        result = PersonaClassifier.classify(title)
        status = "✓" if result == expected else "✗"
        if result == expected:
            passed += 1
        else:
            failed += 1
        print(f"{status} '{title}' → {result} (expected: {expected})")

    print(f"\n{passed} passed, {failed} failed")
