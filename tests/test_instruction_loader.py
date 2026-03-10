"""Test instruction loader"""
from src.instruction_loader import InstructionLoader


def test_loader_initialization():
    """Test loader can be created"""
    loader = InstructionLoader()
    assert loader.base_instructions is not None
    assert len(loader.base_instructions) > 0
    print("[OK] Loader initialized successfully")


def test_load_specialty():
    """Test loading specialty instructions"""
    loader = InstructionLoader()

    roles = ['researcher', 'writer', 'editor', 'fact_checker']

    for role in roles:
        specialty = loader.load_specialty(role)
        assert specialty is not None
        assert len(specialty) > 100
        print(f"[OK] Loaded {role} instructions: {len(specialty)} chars")


def test_combined_instructions():
    """Test getting full combined instructions"""
    loader = InstructionLoader()

    full = loader.get_full_instructions('researcher')

    # Should contain both base and specialty content
    assert 'Core Agent Instructions' in full
    assert 'Researcher Agent' in full
    assert len(full) > len(loader.base_instructions)

    print(f"[OK] Combined instructions: {len(full)} chars")
    print(f"   Base: {len(loader.base_instructions)} chars")
    print(f"   Combined total: {len(full)} chars")


def test_list_roles():
    """Test listing available roles"""
    loader = InstructionLoader()

    roles = loader.list_available_roles()

    expected = ['editor', 'fact_checker', 'researcher', 'writer']
    assert roles == expected

    print(f"[OK] Found roles: {roles}")


def test_caching():
    """Test instruction caching"""
    loader = InstructionLoader()

    # Load twice
    first = loader.load_specialty('researcher')
    second = loader.load_specialty('researcher')

    # Should be identical (from cache)
    assert first == second
    assert 'researcher' in loader._cache

    print("[OK] Caching works")


if __name__ == "__main__":
    test_loader_initialization()
    test_load_specialty()
    test_combined_instructions()
    test_list_roles()
    test_caching()
    print("\n[DONE] Instruction loader tests passed!")
