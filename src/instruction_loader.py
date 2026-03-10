"""
Instruction Loader - Loads and manages agent instruction files

This is the bridge between .md files and agent prompts!
"""

from pathlib import Path
from typing import Dict, Optional
import logging

logger = logging.getLogger(__name__)


class InstructionLoader:
    """
    Loads instruction files and combines them for agents

    Usage:
        loader = InstructionLoader()
        full_instructions = loader.get_full_instructions('researcher')
        # Returns: base_instructions.md + researcher_instructions.md combined
    """

    def __init__(self, instructions_dir: str = 'instructions'):
        """
        Initialize loader

        Args:
            instructions_dir: Path to instructions folder
        """
        self.instructions_dir = Path(instructions_dir)
        self._validate_directory()

        # Cache loaded instructions for performance
        self._cache: Dict[str, str] = {}

        # Load base instructions once (shared by all)
        self.base_instructions = self._load_base()
        logger.info("InstructionLoader initialized")

    def _validate_directory(self):
        """Ensure instructions directory exists"""
        if not self.instructions_dir.exists():
            raise FileNotFoundError(
                f"Instructions directory not found: {self.instructions_dir}"
            )

        # Check base instructions exist
        base_path = self.instructions_dir / 'base_instructions.md'
        if not base_path.exists():
            raise FileNotFoundError(
                f"Base instructions not found: {base_path}"
            )

    def _load_base(self) -> str:
        """
        Load base instructions (shared by all agents)

        Returns:
            Base instruction content
        """
        base_path = self.instructions_dir / 'base_instructions.md'

        try:
            with open(base_path, 'r', encoding='utf-8') as f:
                content = f.read()

            logger.info(f"Loaded base instructions ({len(content)} chars)")
            return content

        except Exception as e:
            logger.error(f"Failed to load base instructions: {e}")
            raise

    def load_specialty(self, role: str) -> str:
        """
        Load role-specific instructions

        Args:
            role: Agent role (researcher, writer, editor, fact_checker)

        Returns:
            Specialty instruction content

        Raises:
            FileNotFoundError: If specialty file doesn't exist
        """
        # Check cache first
        if role in self._cache:
            logger.debug(f"Using cached instructions for: {role}")
            return self._cache[role]

        specialty_path = self.instructions_dir / f'{role}_instructions.md'

        if not specialty_path.exists():
            raise FileNotFoundError(
                f"Specialty instructions not found for role '{role}': {specialty_path}"
            )

        try:
            with open(specialty_path, 'r', encoding='utf-8') as f:
                content = f.read()

            # Cache it
            self._cache[role] = content

            logger.info(f"Loaded {role} instructions ({len(content)} chars)")
            return content

        except Exception as e:
            logger.error(f"Failed to load {role} instructions: {e}")
            raise

    def get_full_instructions(self, role: str) -> str:
        """
        Get combined base + specialty instructions

        This is what actually gets passed to the agent as system prompt!

        Args:
            role: Agent role

        Returns:
            Combined instructions (base + specialty)
        """
        specialty = self.load_specialty(role)

        # Combine with clear separator
        combined = f"""{self.base_instructions}

---

# ROLE-SPECIFIC INSTRUCTIONS FOR: {role.upper()}

{specialty}"""

        logger.info(
            f"Combined instructions for {role}: "
            f"{len(self.base_instructions)} base + {len(specialty)} specialty = "
            f"{len(combined)} total chars"
        )

        return combined

    def list_available_roles(self) -> list[str]:
        """
        List all available agent roles

        Returns:
            List of role names
        """
        roles = []

        for filepath in self.instructions_dir.glob('*_instructions.md'):
            if filepath.stem != 'base_instructions':
                # Extract role name (remove '_instructions' suffix)
                role = filepath.stem.replace('_instructions', '')
                roles.append(role)

        return sorted(roles)

    def reload_instructions(self):
        """
        Clear cache and reload all instructions

        Useful when instructions are updated during development
        """
        self._cache.clear()
        self.base_instructions = self._load_base()
        logger.info("Instructions reloaded")


# Example usage
if __name__ == "__main__":
    loader = InstructionLoader()

    # List available roles
    print(f"Available roles: {loader.list_available_roles()}")

    # Load full instructions for researcher
    researcher_instructions = loader.get_full_instructions('researcher')
    print(f"\nResearcher instructions: {len(researcher_instructions)} characters")
    print(f"\nFirst 500 chars:\n{researcher_instructions[:500]}...")
