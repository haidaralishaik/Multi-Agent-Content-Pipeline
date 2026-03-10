"""Test instruction file loading"""
from pathlib import Path


def test_base_instructions_exist():
    """Verify base instructions file exists"""
    base_path = Path('instructions/base_instructions.md')
    assert base_path.exists(), "base_instructions.md not found!"
    print("[OK] Base instructions file exists")


def test_base_instructions_content():
    """Verify base instructions have required sections"""
    base_path = Path('instructions/base_instructions.md')
    content = base_path.read_text(encoding='utf-8')

    required_sections = [
        'Mission',
        'Core Principles',
        'Accuracy First',
        'Collaboration',
        'Output Format',
        'What NOT to Do'
    ]

    for section in required_sections:
        assert section in content, f"Missing section: {section}"
        print(f"[OK] Found section: {section}")

    print("\n[OK] Base instructions have all required sections!")


if __name__ == "__main__":
    test_base_instructions_exist()
    test_base_instructions_content()
    print("\n[DONE] Base instructions validation complete!")
