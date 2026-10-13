import json
from pipeline import run_pipeline

def test_good_with_traps():
    with open('samples/good_with_traps.txt', 'r') as f:
        note = f.read()
    with open('samples/expected.json', 'r') as f:
        expected = json.load(f)
    
    output, debug = run_pipeline(note)
    # Convert output to dict for comparison
    output_dict = output.model_dump()  # Pydantic v2
    
    # Check can_generate
    assert output_dict['can_generate'] == True, "Should be able to generate output for good note"
    
    # Check hero metric matches expected
    assert output_dict['hero_metric'] == expected['hero_metric'], f"Hero metric mismatch: expected {expected['hero_metric']}, got {output_dict['hero_metric']}"
    
    # Check that we have checklist items
    assert len(output_dict['checklist']) > 0, "Should have checklist items"
    
    print("Good note test passed!")
    print(f"Hero metric: {output_dict['hero_metric']}")
    print(f"Checklist items: {len(output_dict['checklist'])}")
    print(f"Red panel items: {len(output_dict['red_panel_items'])}")

def test_too_vague():
    with open('samples/too_vague.txt', 'r') as f:
        note = f.read()
    output, debug = run_pipeline(note)
    assert output.can_generate == False, "Should not be able to generate output for too vague note"
    assert output.refusal_reason is not None, "Should have a refusal reason"
    print("Too vague test passed!")
    print(f"Refusal reason: {output.refusal_reason}")

def main():
    print("Running tests...")
    print("-" * 50)
    test_good_with_traps()
    test_too_vague()
    print("-" * 50)
    print("All tests passed!")

if __name__ == '__main__':
    main()
