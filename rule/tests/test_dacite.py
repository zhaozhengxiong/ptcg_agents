from dataclasses import dataclass

from rule.dacite import from_dict


@dataclass
class Child:
    value: int


@dataclass
class Parent:
    name: str
    child: Child
    values: list[int]


def test_from_dict_builds_nested_dataclasses() -> None:
    payload = {"name": "test", "child": {"value": 5}, "values": [1, 2, 3]}

    instance = from_dict(Parent, payload)

    assert instance == Parent(name="test", child=Child(value=5), values=[1, 2, 3])
