import json
from pathlib import Path
from pprint import pprint

path = Path(r"data\evaluation\representative_sample\finding_sample_annotations.json")

data = json.loads(path.read_text(encoding="utf-8"))

results = []


def walk(value):
    if isinstance(value, dict):
        if value.get("sample_index") == 53:
            results.append(value)

        for child in value.values():
            walk(child)

    elif isinstance(value, list):
        for child in value:
            walk(child)


walk(data)

pprint(results)
