#!/usr/bin/env python3
"""Quick codebase analysis without visualization."""

import os
import ast
import json
from pathlib import Path
from typing import Dict, List
from collections import defaultdict
from dataclasses import dataclass, field

@dataclass
class FileMetrics:
    path: str
    lines_total: int = 0
    lines_code: int = 0
    lines_comments: int = 0
    lines_docstrings: int = 0
    lines_blank: int = 0
    functions: int = 0
    classes: int = 0
    imports: int = 0
    test_file: bool = False

@dataclass
class LayerMetrics:
    name: str
    files: List[FileMetrics] = field(default_factory=list)
    
    @property
    def total_files(self) -> int:
        return len(self.files)
    
    @property
    def total_lines(self) -> int:
        return sum(f.lines_total for f in self.files)
    
    @property
    def code_lines(self) -> int:
        return sum(f.lines_code for f in self.files)
    
    @property
    def comment_lines(self) -> int:
        return sum(f.lines_comments for f in self.files)
    
    @property
    def docstring_lines(self) -> int:
        return sum(f.lines_docstrings for f in self.files)
    
    @property
    def test_files(self) -> int:
        return sum(1 for f in self.files if f.test_file)
    
    @property
    def functions(self) -> int:
        return sum(f.functions for f in self.files)
    
    @property
    def classes(self) -> int:
        return sum(f.classes for f in self.files)

class QuickAnalyzer:
    def __init__(self):
        self.root_path = Path('.')
        self.metrics: Dict[str, LayerMetrics] = {}
        self.file_metrics: List[FileMetrics] = []
        self.exclude_dirs = {
            'venv', '__pycache__', '.git', 'node_modules', 
            '.mypy_cache', 'htmlcov', 'dist', 'build'
        }
        
    def analyze(self):
        print("🔍 Analyzing codebase...")
        for py_file in self._find_python_files():
            metrics = self._analyze_file(py_file)
            if metrics:
                self.file_metrics.append(metrics)
        self._categorize_by_layer()
        self._print_report()
        
    def _find_python_files(self):
        files = []
        for path in self.root_path.rglob("*.py"):
            if not any(excluded in str(path) for excluded in self.exclude_dirs):
                files.append(path)
        return files
    
    def _analyze_file(self, file_path: Path) -> FileMetrics:
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()
                lines = content.splitlines()
                
            metrics = FileMetrics(
                path=str(file_path.relative_to(self.root_path)),
                lines_total=len(lines),
                test_file='test' in file_path.name.lower()
            )
            
            try:
                tree = ast.parse(content)
                for node in ast.walk(tree):
                    if isinstance(node, ast.FunctionDef):
                        metrics.functions += 1
                    elif isinstance(node, ast.ClassDef):
                        metrics.classes += 1
                    elif isinstance(node, (ast.Import, ast.ImportFrom)):
                        metrics.imports += 1
            except:
                pass
            
            in_docstring = False
            for line in lines:
                stripped = line.strip()
                if not stripped:
                    metrics.lines_blank += 1
                elif stripped.startswith('#'):
                    metrics.lines_comments += 1
                elif '"""' in stripped or "'''" in stripped:
                    metrics.lines_docstrings += 1
                    in_docstring = not in_docstring
                elif in_docstring:
                    metrics.lines_docstrings += 1
                else:
                    metrics.lines_code += 1
                    
            return metrics
        except:
            return None
    
    def _categorize_by_layer(self):
        layers = {
            'domain': LayerMetrics('Domain'),
            'application': LayerMetrics('Application'),
            'infrastructure': LayerMetrics('Infrastructure'),
            'api': LayerMetrics('API'),
            'tests': LayerMetrics('Tests'),
            'scripts': LayerMetrics('Scripts'),
            'web': LayerMetrics('Web'),
            'other': LayerMetrics('Other')
        }
        
        for fm in self.file_metrics:
            path = fm.path.lower()
            if 'test' in path:
                layers['tests'].files.append(fm)
            elif 'src/domain' in path:
                layers['domain'].files.append(fm)
            elif 'src/application' in path:
                layers['application'].files.append(fm)
            elif 'src/infrastructure' in path:
                layers['infrastructure'].files.append(fm)
            elif 'src/api' in path:
                layers['api'].files.append(fm)
            elif 'scripts/' in path:
                layers['scripts'].files.append(fm)
            elif 'web/' in path:
                layers['web'].files.append(fm)
            else:
                layers['other'].files.append(fm)
        
        self.metrics = layers
    
    def _print_report(self):
        total_files = len(self.file_metrics)
        total_lines = sum(f.lines_total for f in self.file_metrics)
        total_code = sum(f.lines_code for f in self.file_metrics)
        total_comments = sum(f.lines_comments for f in self.file_metrics)
        total_docstrings = sum(f.lines_docstrings for f in self.file_metrics)
        total_blank = sum(f.lines_blank for f in self.file_metrics)
        total_tests = sum(1 for f in self.file_metrics if f.test_file)
        total_functions = sum(f.functions for f in self.file_metrics)
        total_classes = sum(f.classes for f in self.file_metrics)
        
        print("\n" + "="*80)
        print("📊 CODEBASE METRICS REPORT")
        print("="*80)
        
        print(f"\n📈 OVERALL STATISTICS")
        print(f"{'─'*40}")
        print(f"Total Files:        {total_files:,}")
        print(f"Total Lines:        {total_lines:,}")
        print(f"├─ Code:            {total_code:,} ({total_code/total_lines*100:.1f}%)")
        print(f"├─ Comments:        {total_comments:,} ({total_comments/total_lines*100:.1f}%)")
        print(f"├─ Docstrings:      {total_docstrings:,} ({total_docstrings/total_lines*100:.1f}%)")
        print(f"└─ Blank:           {total_blank:,} ({total_blank/total_lines*100:.1f}%)")
        print(f"\nTest Files:         {total_tests:,} ({total_tests/total_files*100:.1f}%)")
        print(f"Functions:          {total_functions:,}")
        print(f"Classes:            {total_classes:,}")
        
        documentation_lines = total_comments + total_docstrings
        if total_code > 0:
            comment_ratio = documentation_lines / total_code * 100
            print(f"\n📝 Documentation Ratio: {comment_ratio:.1f}%")
            if comment_ratio < 10:
                print("   ⚠️  Low documentation coverage")
            elif comment_ratio < 20:
                print("   ⚡ Moderate documentation")
            else:
                print("   ✅ Good documentation coverage")
        
        print(f"\n🏗️  ARCHITECTURAL LAYERS")
        print(f"{'─'*70}")
        print(f"{'Layer':<20} {'Files':>8} {'Lines':>10} {'Code':>10} {'Tests':>8} {'Classes':>8}")
        print(f"{'─'*70}")
        
        for name, layer in sorted(self.metrics.items()):
            if layer.total_files > 0:
                print(f"{layer.name:<20} {layer.total_files:>8} {layer.total_lines:>10,} "
                      f"{layer.code_lines:>10,} {layer.test_files:>8} {layer.classes:>8}")
        
        print(f"\n🧪 TEST COVERAGE ANALYSIS")
        print(f"{'─'*40}")
        test_ratio = total_tests / (total_files - total_tests) * 100 if (total_files - total_tests) > 0 else 0
        print(f"Test File Ratio:    {test_ratio:.1f}%")
        
        # Count test types
        unit_tests = sum(1 for f in self.file_metrics if 'unit' in f.path.lower())
        integration_tests = sum(1 for f in self.file_metrics if 'integration' in f.path.lower())
        e2e_tests = sum(1 for f in self.file_metrics if 'e2e' in f.path.lower())
        property_tests = sum(1 for f in self.file_metrics if 'property' in f.path.lower())
        
        print(f"\nTest Types:")
        print(f"├─ Unit Tests:        {unit_tests}")
        print(f"├─ Integration Tests: {integration_tests}")
        print(f"├─ E2E Tests:         {e2e_tests}")
        print(f"└─ Property Tests:    {property_tests}")
        
        print(f"\n📁 TOP 10 LARGEST FILES")
        print(f"{'─'*70}")
        print(f"{'File':<50} {'Lines':>10} {'Type':>10}")
        print(f"{'─'*70}")
        
        sorted_files = sorted(self.file_metrics, key=lambda x: x.lines_total, reverse=True)[:10]
        for f in sorted_files:
            file_type = "Test" if f.test_file else "Code"
            short_path = f.path if len(f.path) <= 50 else "..." + f.path[-47:]
            print(f"{short_path:<50} {f.lines_total:>10,} {file_type:>10}")
        
        # Save summary
        summary = {
            'total_files': total_files,
            'total_lines': total_lines,
            'code_lines': total_code,
            'comment_lines': total_comments,
            'docstring_lines': total_docstrings,
            'test_files': total_tests,
            'functions': total_functions,
            'classes': total_classes,
            'documentation_ratio': documentation_lines / total_code * 100 if total_code > 0 else 0,
            'test_ratio': test_ratio,
            'layers': {
                name: {
                    'files': layer.total_files,
                    'lines': layer.total_lines,
                    'code': layer.code_lines,
                    'tests': layer.test_files,
                    'classes': layer.classes,
                    'functions': layer.functions
                }
                for name, layer in self.metrics.items()
                if layer.total_files > 0
            }
        }
        
        with open('codebase_metrics.json', 'w') as f:
            json.dump(summary, f, indent=2)
        
        print(f"\n📋 Detailed metrics saved to 'codebase_metrics.json'")
        print("="*80)

if __name__ == '__main__':
    analyzer = QuickAnalyzer()
    analyzer.analyze()