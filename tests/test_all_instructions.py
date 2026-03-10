"""Test all instruction files"""
from pathlib import Path


def test_all_instruction_files_exist():
    """Verify all instruction files exist"""
    instruction_files = [
        'base_instructions.md',
        'researcher_instructions.md',
        'writer_instructions.md',
        'editor_instructions.md',
        'fact_checker_instructions.md'
    ]

    instructions_dir = Path('instructions')

    for filename in instruction_files:
        filepath = instructions_dir / filename
        assert filepath.exists(), f"{filename} not found!"
        print(f"[OK] Found: {filename}")

    print("\n[OK] All instruction files present!")


def test_instruction_file_sizes():
    """Verify instruction files have substantial content"""
    instructions_dir = Path('instructions')

    for filepath in instructions_dir.glob('*.md'):
        content = filepath.read_text(encoding='utf-8')
        word_count = len(content.split())

        assert word_count > 100, f"{filepath.name} seems too short ({word_count} words)"
        print(f"[OK] {filepath.name}: {word_count} words")

    print("\n[OK] All instruction files have substantial content!")


if __name__ == "__main__":
    test_all_instruction_files_exist()
    test_instruction_file_sizes()
    print("\n[DONE] All instruction files validated!")
