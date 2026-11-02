"""Architectural safety regression; native tests also deny foreign services."""
import ast
from pathlib import Path


def test_no_output_mapping_dispatch_client_or_button_platform():
    folder = Path(__file__).resolve().parents[1] / 'custom_components' / 'uninus_nutriculture'
    assert not (folder/'button.py').exists()
    assert not (folder/'switch.py').exists()
    for path in folder.glob('*.py'):
        tree = ast.parse(path.read_text(encoding='utf-8'))
        for node in ast.walk(tree):
            if isinstance(node,ast.Attribute):
                assert node.attr not in {'async_call','call_service','publish','async_publish'} or (node.attr == 'publish' and isinstance(node.value,ast.Name) and node.value.id == 'self')
            if isinstance(node,(ast.Import,ast.ImportFrom)):
                names = [x.name for x in node.names] + [getattr(node,'module','') or '']
                assert not any('mqtt' in name.lower() for name in names)
