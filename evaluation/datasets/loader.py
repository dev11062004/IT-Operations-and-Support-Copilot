"""Dataset loading and validation models for production RAG and IT Support evaluation."""

import json
from pathlib import Path
from typing import Any, List, Optional, Union
import pandas as pd
from pydantic import BaseModel, Field


class BenchmarkItem(BaseModel):
    """A single evaluation benchmark test case for RAG policies."""
    id: str = Field(..., description="Unique test case identifier (e.g. BENCH-001)")
    question: str = Field(..., description="The query submitted to the RAG agent")
    expected_answer: Optional[str] = Field("", description="Ground truth reference answer")
    relevant_documents: List[str] = Field(
        default_factory=list,
        description="List of document filenames required to answer the question"
    )
    relevant_chunks: List[str] = Field(
        default_factory=list,
        description="Key chunk identifiers or content markers containing the ground truth facts"
    )
    category: str = Field(
        "General Policy",
        description="Domain category (e.g., Annual Leave, IT Security, Expenses, Remote Working, Sustainability)"
    )
    difficulty: str = Field(
        "easy",
        description="Complexity rating: 'easy' (single fact), 'medium' (multi-sentence), 'hard' (multi-hop / comparative)"
    )
    is_refusal_expected: bool = Field(
        False,
        description="True if the question asks for policy content absent from corpus (expects refusal standard)"
    )
    is_out_of_domain: bool = Field(
        False,
        description="True if the question is completely outside corporate policy domain"
    )
    metadata: dict[str, Any] = Field(
        default_factory=dict,
        description="Optional additional context or annotations"
    )


class ITBenchmarkItem(BaseModel):
    """A single evaluation benchmark test case for IT Support workflows."""
    id: str = Field(..., description="Unique IT test case identifier (e.g. IT-001)")
    question: str = Field(..., description="The employee or technician IT support query")
    intent: Optional[str] = Field(None, description="Expected classified IT intent enum")
    category: str = Field("OTHER", description="Expected IT Category (NETWORK, ACCESS, etc.)")
    expected_documents: List[str] = Field(
        default_factory=list,
        description="List of policy / runbook source documents expected to be retrieved"
    )
    expected_runbook: Optional[str] = Field(
        None,
        description="Expected runbook ID to be triggered (e.g. RB-NET-VPN-001)"
    )
    expected_tools: List[str] = Field(
        default_factory=list,
        description="Expected MCP diagnostic or operational tools invoked"
    )
    expected_ticket_type: Optional[str] = Field(
        None,
        description="Expected ticket category or None if self-served without ticket"
    )
    expected_escalation: bool = Field(
        False,
        description="True if scenario is expected to escalate to human technician or Tier 2/3"
    )
    expected_outcome: Optional[str] = Field(
        "answered",
        description="Expected operational outcome (e.g. answered, runbook_completed, escalated, ticket_created, refusal)"
    )
    is_refusal_expected: bool = Field(
        False,
        description="True if refusal / deflection standard is expected"
    )
    is_out_of_domain: bool = Field(
        False,
        description="True if query is completely outside enterprise IT domain"
    )
    requires_approval: bool = Field(
        False,
        description="True if action is high-risk requiring admin approval"
    )
    expected_risk_level: Optional[str] = Field(
        "low",
        description="Expected risk classification (low, medium, high, critical, critical_unauthorized)"
    )
    metadata: dict[str, Any] = Field(
        default_factory=dict,
        description="Optional additional scenario context"
    )


class BenchmarkDataset(BaseModel):
    """Container for a versioned evaluation benchmark dataset."""
    name: str = Field("Policy RAG Benchmark", description="Human-readable benchmark name")
    version: str = Field("v1.0", description="Semantic dataset version string")
    description: str = Field("", description="Overview of dataset scope and composition")
    items: List[BenchmarkItem] = Field(default_factory=list, description="List of benchmark items")

    def __len__(self) -> int:
        return len(self.items)

    def __iter__(self):
        return iter(self.items)

    def __getitem__(self, idx: int) -> BenchmarkItem:
        return self.items[idx]

    def to_dataframe(self) -> pd.DataFrame:
        """Convert benchmark items to a pandas DataFrame."""
        records = []
        for item in self.items:
            records.append({
                "id": item.id,
                "question": item.question,
                "expected_answer": item.expected_answer,
                "relevant_documents": item.relevant_documents,
                "relevant_chunks": item.relevant_chunks,
                "category": item.category,
                "difficulty": item.difficulty,
                "is_refusal_expected": item.is_refusal_expected,
                "is_out_of_domain": item.is_out_of_domain,
            })
        return pd.DataFrame(records)

    def filter_by_category(self, category: str) -> "BenchmarkDataset":
        """Filter dataset by domain category."""
        filtered = [item for item in self.items if item.category.lower() == category.lower()]
        return BenchmarkDataset(
            name=f"{self.name} - {category}",
            version=self.version,
            description=f"Filtered category '{category}' from version {self.version}",
            items=filtered
        )

    def filter_by_difficulty(self, difficulty: str) -> "BenchmarkDataset":
        """Filter dataset by difficulty level."""
        filtered = [item for item in self.items if item.difficulty.lower() == difficulty.lower()]
        return BenchmarkDataset(
            name=f"{self.name} - {difficulty}",
            version=self.version,
            description=f"Filtered difficulty '{difficulty}' from version {self.version}",
            items=filtered
        )

    def save_json(self, path: Union[str, Path]) -> None:
        """Serialize benchmark dataset to JSON file."""
        target = Path(path)
        target.parent.mkdir(parents=True, exist_ok=True)
        with open(target, "w", encoding="utf-8") as f:
            json.dump(self.model_dump(), f, indent=2, ensure_ascii=False)


class ITBenchmarkDataset(BaseModel):
    """Container for versioned IT Support benchmark dataset."""
    name: str = Field("IT Operations & Support Benchmark", description="Human-readable benchmark name")
    version: str = Field("v1.0", description="Semantic dataset version string")
    description: str = Field("", description="Overview of dataset scope and composition")
    items: List[ITBenchmarkItem] = Field(default_factory=list, description="List of IT benchmark items")

    def __len__(self) -> int:
        return len(self.items)

    def __iter__(self):
        return iter(self.items)

    def __getitem__(self, idx: int) -> ITBenchmarkItem:
        return self.items[idx]

    def to_dataframe(self) -> pd.DataFrame:
        """Convert IT benchmark items to a pandas DataFrame."""
        records = []
        for item in self.items:
            records.append({
                "id": item.id,
                "question": item.question,
                "intent": item.intent,
                "category": item.category,
                "expected_documents": item.expected_documents,
                "expected_runbook": item.expected_runbook,
                "expected_tools": item.expected_tools,
                "expected_ticket_type": item.expected_ticket_type,
                "expected_escalation": item.expected_escalation,
                "expected_outcome": item.expected_outcome,
                "is_refusal_expected": item.is_refusal_expected,
                "is_out_of_domain": item.is_out_of_domain,
                "requires_approval": item.requires_approval,
                "expected_risk_level": item.expected_risk_level,
            })
        return pd.DataFrame(records)

    def filter_by_category(self, category: str) -> "ITBenchmarkDataset":
        """Filter dataset by IT domain category."""
        filtered = [item for item in self.items if item.category.lower() == category.lower()]
        return ITBenchmarkDataset(
            name=f"{self.name} - {category}",
            version=self.version,
            description=f"Filtered category '{category}' from version {self.version}",
            items=filtered
        )

    def filter_by_intent(self, intent: str) -> "ITBenchmarkDataset":
        """Filter dataset by IT intent."""
        filtered = [item for item in self.items if item.intent and item.intent.lower() == intent.lower()]
        return ITBenchmarkDataset(
            name=f"{self.name} - {intent}",
            version=self.version,
            description=f"Filtered intent '{intent}' from version {self.version}",
            items=filtered
        )

    def save_json(self, path: Union[str, Path]) -> None:
        """Serialize benchmark dataset to JSON file."""
        target = Path(path)
        target.parent.mkdir(parents=True, exist_ok=True)
        with open(target, "w", encoding="utf-8") as f:
            json.dump(self.model_dump(), f, indent=2, ensure_ascii=False)


def get_default_dataset_path(version: str = "v1") -> Path:
    """Resolve default path for a named benchmark version."""
    datasets_dir = Path(__file__).parent
    candidates = [
        datasets_dir / f"{version}_policy_benchmark.json",
        datasets_dir / f"{version}_it_support_benchmark.json",
        datasets_dir / f"{version}.json",
    ]
    for c in candidates:
        if c.exists():
            return c
    return datasets_dir / "v1_policy_benchmark.json"


def load_benchmark_dataset(version_or_path: Union[str, Path] = "v1") -> Union[BenchmarkDataset, ITBenchmarkDataset]:
    """Load and validate a versioned benchmark dataset from file or version tag.

    Args:
        version_or_path: Version identifier (e.g. 'v1', 'v1_it') or direct filesystem Path to JSON.

    Returns:
        Validated BenchmarkDataset or ITBenchmarkDataset instance.
    """
    path = Path(version_or_path)
    if not path.exists() or path.is_dir():
        path = get_default_dataset_path(str(version_or_path))

    if not path.exists():
        raise FileNotFoundError(f"Benchmark dataset file not found at: {path}")

    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)

    # Automatically detect if dataset is an IT Support benchmark
    items = data.get("items", [])
    if items and ("expected_runbook" in items[0] or "intent" in items[0] or "expected_ticket_type" in items[0]):
        return ITBenchmarkDataset.model_validate(data)

    return BenchmarkDataset.model_validate(data)


def load_it_benchmark_dataset(version_or_path: Union[str, Path] = "v1_it_support_benchmark.json") -> ITBenchmarkDataset:
    """Explicit loader for IT Support benchmark datasets."""
    path = Path(version_or_path)
    if not path.exists() or path.is_dir():
        datasets_dir = Path(__file__).parent
        candidates = [
            datasets_dir / f"{version_or_path}",
            datasets_dir / f"{version_or_path}.json",
            datasets_dir / f"{version_or_path}_it_support_benchmark.json",
        ]
        found = False
        for c in candidates:
            if c.exists() and not c.is_dir():
                path = c
                found = True
                break
        if not found and str(version_or_path) in ("v1", "default", "v1_it", "v1_it_support_benchmark.json"):
            path = datasets_dir / "v1_it_support_benchmark.json"

    if not path.exists():
        raise FileNotFoundError(f"IT benchmark dataset not found at: {path}")

    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)

    return ITBenchmarkDataset.model_validate(data)



def convert_excel_to_benchmark(excel_path: Path, output_json: Path, version: str = "v1.0") -> BenchmarkDataset:
    """Convert legacy expected_behaviour.xlsx to strongly typed versioned BenchmarkDataset."""
    df = pd.read_excel(excel_path, sheet_name="Sheet1")
    items: List[BenchmarkItem] = []

    category_map = {
        "Annual Leave": "Annual Leave",
        "IT Security": "IT Security",
        "Expenses": "Expenses",
        "Remote Working": "Remote Working",
        "Sustainability": "Sustainability",
    }

    for idx, row in df.iterrows():
        source_raw = str(row["source"]) if pd.notna(row.get("source")) else ""
        source_clean = source_raw.replace("\u2013", "-").replace("\u2014", "-").strip()

        # Derive category
        cat = "General Policy"
        for key in category_map:
            if key.lower() in source_clean.lower():
                cat = key
                break

        item = BenchmarkItem(
            id=f"BENCH-{idx + 1:03d}",
            question=str(row["question"]).strip(),
            expected_answer=str(row["reference"]).strip(),
            relevant_documents=[source_clean] if source_clean else [],
            relevant_chunks=[f"{source_clean}_chunk"],
            category=cat,
            difficulty="easy",
            is_refusal_expected=False,
            is_out_of_domain=False,
        )
        items.append(item)

    dataset = BenchmarkDataset(
        name="Company XYZ Policy Benchmark",
        version=version,
        description="Converted canonical benchmark derived from expected_behaviour.xlsx",
        items=items
    )
    dataset.save_json(output_json)
    return dataset
