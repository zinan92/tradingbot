"""
Flake8 plugin to enforce hexagonal architecture rules.

Prevents illegal imports across architectural layers.
"""

import ast
from typing import Any, Generator, Tuple, Type
from pathlib import Path


class HexagonalArchitectureChecker:
    """
    Flake8 plugin to enforce hexagonal architecture boundaries.
    
    Rules:
    - HEX001: Domain layer cannot import from infrastructure or application
    - HEX002: Application layer cannot import from infrastructure
    - HEX003: Use port interfaces instead of concrete implementations
    """
    
    name = "flake8-hexagonal"
    version = "1.0.0"
    
    # Error messages
    HEX001 = "HEX001 Domain layer cannot import from {}"
    HEX002 = "HEX002 Application layer cannot import from infrastructure: {}"
    HEX003 = "HEX003 Use port interface instead of concrete implementation: {}"
    
    def __init__(self, tree: ast.AST, filename: str):
        self.tree = tree
        self.filename = Path(filename)
        self.errors: list[tuple[int, int, str, Type[Any]]] = []
    
    def run(self) -> Generator[Tuple[int, int, str, Type[Any]], None, None]:
        """Run the checker and yield errors."""
        # Determine current layer
        current_layer = self._get_layer(self.filename)
        
        if current_layer in ["domain", "application"]:
            # Check imports
            visitor = ImportVisitor(current_layer, self.filename)
            visitor.visit(self.tree)
            
            for error in visitor.errors:
                yield error
    
    def _get_layer(self, filepath: Path) -> str:
        """Determine which layer a file belongs to."""
        parts = filepath.parts
        
        if "domain" in parts:
            return "domain"
        elif "application" in parts:
            return "application"
        elif "infrastructure" in parts:
            return "infrastructure"
        else:
            return "other"


class ImportVisitor(ast.NodeVisitor):
    """AST visitor to check imports."""
    
    def __init__(self, current_layer: str, filename: Path):
        self.current_layer = current_layer
        self.filename = filename
        self.errors: list[tuple[int, int, str, Type[Any]]] = []
        
        # Allowed imports for each layer
        self.allowed_imports = {
            "domain": [
                "src.domain",
                "typing",
                "abc",
                "dataclasses",
                "datetime",
                "decimal",
                "enum",
                "uuid",
                # Standard library is allowed
            ],
            "application": [
                "src.domain",
                "src.application",
                "typing",
                "abc",
                "dataclasses",
                "datetime",
                "decimal",
                # Standard library is allowed
            ]
        }
        
        # Concrete implementations that should use ports
        self.concrete_implementations = {
            "BacktestEngine": "BacktestPort",
            "DataAdapter": "MarketDataPort",
            "BinanceClient": "BrokerPort",
            "BinanceFuturesBroker": "BrokerPort",
            "DatabaseManager": "DatabasePort",
            "WebSocketManager": "WebSocketPort",
            "InMemoryEventBus": "EventBusPort",
            "BacktestRepository": "BacktestRepositoryPort",
            "get_registry": "StrategyRegistryPort",
        }
    
    def visit_Import(self, node: ast.Import) -> None:
        """Check import statements."""
        for alias in node.names:
            self._check_import(alias.name, node.lineno, node.col_offset)
    
    def visit_ImportFrom(self, node: ast.ImportFrom) -> None:
        """Check from...import statements."""
        if node.module:
            module = node.module
            
            # Check module itself
            self._check_import(module, node.lineno, node.col_offset)
            
            # Check imported names for concrete implementations
            for alias in node.names:
                imported_name = alias.name
                if imported_name in self.concrete_implementations:
                    port_name = self.concrete_implementations[imported_name]
                    self.errors.append((
                        node.lineno,
                        node.col_offset,
                        f"HEX003 Use port interface '{port_name}' instead of concrete implementation '{imported_name}'",
                        HexagonalArchitectureChecker
                    ))
    
    def _check_import(self, module_name: str, lineno: int, col_offset: int) -> None:
        """Check if an import is allowed."""
        # Skip relative imports and standard library
        if not module_name or not module_name.startswith("src"):
            return
        
        # Domain layer checks
        if self.current_layer == "domain":
            if "infrastructure" in module_name:
                self.errors.append((
                    lineno,
                    col_offset,
                    f"HEX001 Domain layer cannot import from infrastructure: {module_name}",
                    HexagonalArchitectureChecker
                ))
            elif "application" in module_name:
                self.errors.append((
                    lineno,
                    col_offset,
                    f"HEX001 Domain layer cannot import from application: {module_name}",
                    HexagonalArchitectureChecker
                ))
        
        # Application layer checks
        elif self.current_layer == "application":
            if "infrastructure" in module_name:
                # Check if it's importing from ports (allowed)
                if "ports" not in self.filename.parts:
                    self.errors.append((
                        lineno,
                        col_offset,
                        f"HEX002 Application layer cannot import from infrastructure: {module_name}",
                        HexagonalArchitectureChecker
                    ))


def check_hexagonal_architecture(
    physical_line: str,
    filename: str,
    lines: list[str],
    line_number: int
) -> Generator[Tuple[int, str], None, None]:
    """
    Alternative entry point for simpler line-based checking.
    
    This is for compatibility with older flake8 versions.
    """
    filepath = Path(filename)
    current_layer = _get_layer_simple(filepath)
    
    if current_layer in ["domain", "application"]:
        # Check for infrastructure imports
        if "from src.infrastructure" in physical_line:
            if current_layer == "domain":
                yield (0, "HEX001 Domain layer cannot import from infrastructure")
            elif current_layer == "application":
                yield (0, "HEX002 Application layer cannot import from infrastructure")
        
        # Check for concrete implementations
        for impl, port in {
            "BacktestEngine": "BacktestPort",
            "BinanceClient": "BrokerPort",
            "DatabaseManager": "DatabasePort",
        }.items():
            if impl in physical_line and "import" in physical_line:
                yield (0, f"HEX003 Use {port} instead of {impl}")


def _get_layer_simple(filepath: Path) -> str:
    """Simple layer detection."""
    parts = str(filepath).split("/")
    if "domain" in parts:
        return "domain"
    elif "application" in parts:
        return "application"
    return "other"


# Flake8 entry point
check_hexagonal_architecture.name = "hexagonal"
check_hexagonal_architecture.version = "1.0.0"