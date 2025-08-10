#!/usr/bin/env python3
"""
Comprehensive codebase analysis tool for code review.
Generates metrics, hierarchy diagrams, and quality insights.
"""

import os
import ast
import json
import re
from pathlib import Path
from typing import Dict, List, Tuple, Any
from collections import defaultdict, Counter
from dataclasses import dataclass, field
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
from matplotlib.patches import Rectangle
import numpy as np

@dataclass
class FileMetrics:
    """Metrics for a single file."""
    path: str
    lines_total: int = 0
    lines_code: int = 0
    lines_comments: int = 0
    lines_docstrings: int = 0
    lines_blank: int = 0
    functions: int = 0
    classes: int = 0
    imports: int = 0
    complexity: int = 0
    test_file: bool = False

@dataclass
class LayerMetrics:
    """Metrics for an architectural layer."""
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

class CodebaseAnalyzer:
    """Analyzes Python codebase for metrics and quality."""
    
    def __init__(self, root_path: str):
        self.root_path = Path(root_path)
        self.metrics: Dict[str, LayerMetrics] = {}
        self.file_metrics: List[FileMetrics] = []
        self.exclude_dirs = {
            'venv', '__pycache__', '.git', '.pytest_cache', 
            'node_modules', '.mypy_cache', 'htmlcov', 'dist',
            'build', '.eggs', '*.egg-info'
        }
        
    def analyze(self):
        """Run complete analysis."""
        print("🔍 Analyzing codebase...")
        self._collect_metrics()
        self._categorize_by_layer()
        self._generate_report()
        self._create_visualizations()
        
    def _collect_metrics(self):
        """Collect metrics for all Python files."""
        for py_file in self._find_python_files():
            metrics = self._analyze_file(py_file)
            if metrics:
                self.file_metrics.append(metrics)
                
    def _find_python_files(self) -> List[Path]:
        """Find all Python files excluding certain directories."""
        files = []
        for path in self.root_path.rglob("*.py"):
            # Skip excluded directories
            if any(excluded in str(path) for excluded in self.exclude_dirs):
                continue
            files.append(path)
        return files
    
    def _analyze_file(self, file_path: Path) -> FileMetrics:
        """Analyze a single Python file."""
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()
                lines = content.splitlines()
                
            metrics = FileMetrics(
                path=str(file_path.relative_to(self.root_path)),
                lines_total=len(lines),
                test_file='test' in file_path.name.lower()
            )
            
            # Parse AST for detailed metrics
            try:
                tree = ast.parse(content)
                self._analyze_ast(tree, metrics)
            except SyntaxError:
                pass
            
            # Analyze lines
            in_docstring = False
            docstring_quotes = None
            
            for line in lines:
                stripped = line.strip()
                
                # Blank lines
                if not stripped:
                    metrics.lines_blank += 1
                    continue
                
                # Docstrings
                if not in_docstring and (stripped.startswith('"""') or stripped.startswith("'''")):
                    in_docstring = True
                    docstring_quotes = '"""' if stripped.startswith('"""') else "'''"
                    metrics.lines_docstrings += 1
                    if stripped.endswith(docstring_quotes) and len(stripped) > 3:
                        in_docstring = False
                elif in_docstring:
                    metrics.lines_docstrings += 1
                    if docstring_quotes in stripped:
                        in_docstring = False
                # Comments
                elif stripped.startswith('#'):
                    metrics.lines_comments += 1
                # Code
                else:
                    metrics.lines_code += 1
                    
            return metrics
            
        except Exception as e:
            print(f"Error analyzing {file_path}: {e}")
            return None
    
    def _analyze_ast(self, tree: ast.AST, metrics: FileMetrics):
        """Analyze AST for functions, classes, and complexity."""
        for node in ast.walk(tree):
            if isinstance(node, ast.FunctionDef):
                metrics.functions += 1
                metrics.complexity += self._calculate_complexity(node)
            elif isinstance(node, ast.ClassDef):
                metrics.classes += 1
            elif isinstance(node, (ast.Import, ast.ImportFrom)):
                metrics.imports += 1
    
    def _calculate_complexity(self, node: ast.AST) -> int:
        """Calculate cyclomatic complexity of a function."""
        complexity = 1
        for child in ast.walk(node):
            if isinstance(child, (ast.If, ast.While, ast.For, ast.ExceptHandler)):
                complexity += 1
            elif isinstance(child, ast.BoolOp):
                complexity += len(child.values) - 1
        return complexity
    
    def _categorize_by_layer(self):
        """Categorize files by architectural layer."""
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
        
        for file_metric in self.file_metrics:
            path = file_metric.path.lower()
            
            if 'test' in path:
                layers['tests'].files.append(file_metric)
            elif 'src/domain' in path:
                layers['domain'].files.append(file_metric)
            elif 'src/application' in path:
                layers['application'].files.append(file_metric)
            elif 'src/infrastructure' in path:
                layers['infrastructure'].files.append(file_metric)
            elif 'src/api' in path:
                layers['api'].files.append(file_metric)
            elif 'scripts/' in path:
                layers['scripts'].files.append(file_metric)
            elif 'web/' in path:
                layers['web'].files.append(file_metric)
            else:
                layers['other'].files.append(file_metric)
        
        self.metrics = layers
    
    def _generate_report(self):
        """Generate comprehensive metrics report."""
        print("\n" + "="*80)
        print("📊 CODEBASE METRICS REPORT")
        print("="*80)
        
        # Overall statistics
        total_files = len(self.file_metrics)
        total_lines = sum(f.lines_total for f in self.file_metrics)
        total_code = sum(f.lines_code for f in self.file_metrics)
        total_comments = sum(f.lines_comments for f in self.file_metrics)
        total_docstrings = sum(f.lines_docstrings for f in self.file_metrics)
        total_blank = sum(f.lines_blank for f in self.file_metrics)
        total_tests = sum(1 for f in self.file_metrics if f.test_file)
        total_functions = sum(f.functions for f in self.file_metrics)
        total_classes = sum(f.classes for f in self.file_metrics)
        
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
        
        # Comment ratio
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
        
        # Layer breakdown
        print(f"\n🏗️  ARCHITECTURAL LAYERS")
        print(f"{'─'*60}")
        print(f"{'Layer':<20} {'Files':>8} {'Lines':>10} {'Code':>10} {'Tests':>8}")
        print(f"{'─'*60}")
        
        for name, layer in sorted(self.metrics.items()):
            if layer.total_files > 0:
                print(f"{layer.name:<20} {layer.total_files:>8} {layer.total_lines:>10,} "
                      f"{layer.code_lines:>10,} {layer.test_files:>8}")
        
        # Code quality indicators
        print(f"\n🎯 CODE QUALITY INDICATORS")
        print(f"{'─'*40}")
        
        # Average file size
        avg_lines = total_lines / total_files if total_files > 0 else 0
        print(f"Avg Lines/File:     {avg_lines:.0f}")
        if avg_lines > 500:
            print("   ⚠️  Consider breaking down large files")
        elif avg_lines > 300:
            print("   ⚡ Some files might be too large")
        else:
            print("   ✅ Good file size distribution")
        
        # Functions per file
        avg_functions = total_functions / total_files if total_files > 0 else 0
        print(f"Avg Functions/File: {avg_functions:.1f}")
        
        # Test coverage estimation
        test_ratio = total_tests / (total_files - total_tests) * 100 if (total_files - total_tests) > 0 else 0
        print(f"\n🧪 Test Coverage Estimation")
        print(f"{'─'*40}")
        print(f"Test File Ratio:    {test_ratio:.1f}%")
        if test_ratio < 30:
            print("   ⚠️  Low test coverage")
        elif test_ratio < 60:
            print("   ⚡ Moderate test coverage")
        else:
            print("   ✅ Good test coverage")
        
        # Top 10 largest files
        print(f"\n📁 TOP 10 LARGEST FILES")
        print(f"{'─'*60}")
        print(f"{'File':<40} {'Lines':>10} {'Type':>10}")
        print(f"{'─'*60}")
        
        sorted_files = sorted(self.file_metrics, key=lambda x: x.lines_total, reverse=True)[:10]
        for f in sorted_files:
            file_type = "Test" if f.test_file else "Code"
            short_path = f.path if len(f.path) <= 40 else "..." + f.path[-37:]
            print(f"{short_path:<40} {f.lines_total:>10,} {file_type:>10}")
        
        # Complex files (high cyclomatic complexity)
        complex_files = sorted(
            [f for f in self.file_metrics if f.complexity > 10],
            key=lambda x: x.complexity,
            reverse=True
        )[:5]
        
        if complex_files:
            print(f"\n⚠️  HIGH COMPLEXITY FILES")
            print(f"{'─'*60}")
            print(f"{'File':<40} {'Complexity':>15}")
            print(f"{'─'*60}")
            for f in complex_files:
                short_path = f.path if len(f.path) <= 40 else "..." + f.path[-37:]
                print(f"{short_path:<40} {f.complexity:>15}")
    
    def _create_visualizations(self):
        """Create visual diagrams of the codebase."""
        fig = plt.figure(figsize=(20, 12))
        fig.suptitle('Trading Bot v2 - Codebase Analysis', fontsize=16, fontweight='bold')
        
        # 1. Layer Distribution (Pie Chart)
        ax1 = plt.subplot(2, 3, 1)
        layer_sizes = []
        layer_labels = []
        colors = []
        color_map = {
            'Domain': '#FF6B6B',
            'Application': '#4ECDC4',
            'Infrastructure': '#45B7D1',
            'API': '#96CEB4',
            'Tests': '#FFEAA7',
            'Scripts': '#DDA0DD',
            'Web': '#98D8C8',
            'Other': '#C0C0C0'
        }
        
        for name, layer in self.metrics.items():
            if layer.total_lines > 0:
                layer_sizes.append(layer.total_lines)
                layer_labels.append(f"{layer.name}\n({layer.total_files} files)")
                colors.append(color_map.get(layer.name, '#C0C0C0'))
        
        if layer_sizes:
            ax1.pie(layer_sizes, labels=layer_labels, colors=colors, autopct='%1.1f%%', startangle=90)
            ax1.set_title('Code Distribution by Layer (Lines)', fontweight='bold')
        
        # 2. Code vs Documentation (Stacked Bar)
        ax2 = plt.subplot(2, 3, 2)
        layers = []
        code_lines = []
        doc_lines = []
        test_lines = []
        
        for name, layer in sorted(self.metrics.items()):
            if layer.total_files > 0:
                layers.append(layer.name)
                code_lines.append(layer.code_lines)
                doc_lines.append(layer.comment_lines + layer.docstring_lines)
                test_lines.append(sum(f.lines_code for f in layer.files if f.test_file))
        
        if layers:
            x = np.arange(len(layers))
            width = 0.6
            
            p1 = ax2.bar(x, code_lines, width, label='Code', color='#3498db')
            p2 = ax2.bar(x, doc_lines, width, bottom=code_lines, label='Docs', color='#2ecc71')
            
            ax2.set_ylabel('Lines of Code')
            ax2.set_title('Code vs Documentation by Layer', fontweight='bold')
            ax2.set_xticks(x)
            ax2.set_xticklabels(layers, rotation=45, ha='right')
            ax2.legend()
            ax2.grid(axis='y', alpha=0.3)
        
        # 3. Hexagonal Architecture Diagram
        ax3 = plt.subplot(2, 3, 3)
        ax3.set_xlim(0, 10)
        ax3.set_ylim(0, 10)
        ax3.axis('off')
        ax3.set_title('Hexagonal Architecture', fontweight='bold')
        
        # Draw hexagon layers
        domain_hex = plt.Circle((5, 5), 1.5, color='#FF6B6B', alpha=0.7)
        app_hex = plt.Circle((5, 5), 2.5, color='#4ECDC4', alpha=0.5)
        infra_hex = plt.Circle((5, 5), 3.5, color='#45B7D1', alpha=0.3)
        
        ax3.add_patch(infra_hex)
        ax3.add_patch(app_hex)
        ax3.add_patch(domain_hex)
        
        ax3.text(5, 5, 'Domain\nCore', ha='center', va='center', fontweight='bold', fontsize=10)
        ax3.text(5, 3, 'Application\nUse Cases', ha='center', va='center', fontsize=9)
        ax3.text(5, 1.5, 'Infrastructure\nAdapters', ha='center', va='center', fontsize=9)
        
        # Add port indicators
        port_positions = [(7, 5), (3, 5), (5, 7), (5, 3), (6.5, 6.5), (3.5, 3.5)]
        for x, y in port_positions:
            ax3.plot(x, y, 'o', color='#e74c3c', markersize=8)
        ax3.text(8, 5, 'Ports', ha='left', va='center', fontsize=8)
        
        # 4. File Size Distribution (Histogram)
        ax4 = plt.subplot(2, 3, 4)
        file_sizes = [f.lines_total for f in self.file_metrics if not f.test_file]
        
        if file_sizes:
            ax4.hist(file_sizes, bins=30, color='#9b59b6', alpha=0.7, edgecolor='black')
            ax4.axvline(np.mean(file_sizes), color='red', linestyle='--', label=f'Mean: {np.mean(file_sizes):.0f}')
            ax4.axvline(np.median(file_sizes), color='green', linestyle='--', label=f'Median: {np.median(file_sizes):.0f}')
            ax4.set_xlabel('Lines per File')
            ax4.set_ylabel('Number of Files')
            ax4.set_title('File Size Distribution', fontweight='bold')
            ax4.legend()
            ax4.grid(axis='y', alpha=0.3)
        
        # 5. Test Coverage Heatmap
        ax5 = plt.subplot(2, 3, 5)
        ax5.set_title('Module Coverage Heatmap', fontweight='bold')
        
        # Create coverage matrix
        modules = []
        coverage_data = []
        
        for name, layer in sorted(self.metrics.items()):
            if layer.total_files > 0 and name != 'Other':
                modules.append(layer.name)
                test_ratio = (layer.test_files / layer.total_files * 100) if layer.total_files > 0 else 0
                doc_ratio = ((layer.comment_lines + layer.docstring_lines) / layer.code_lines * 100) if layer.code_lines > 0 else 0
                coverage_data.append([test_ratio, doc_ratio])
        
        if coverage_data:
            im = ax5.imshow(np.array(coverage_data).T, cmap='RdYlGn', aspect='auto', vmin=0, vmax=100)
            ax5.set_xticks(np.arange(len(modules)))
            ax5.set_yticks(np.arange(2))
            ax5.set_xticklabels(modules, rotation=45, ha='right')
            ax5.set_yticklabels(['Test Coverage', 'Doc Coverage'])
            
            # Add text annotations
            for i in range(len(modules)):
                for j in range(2):
                    text = ax5.text(i, j, f'{coverage_data[i][j]:.0f}%',
                                   ha="center", va="center", color="black", fontsize=9)
            
            plt.colorbar(im, ax=ax5)
        
        # 6. Complexity Analysis
        ax6 = plt.subplot(2, 3, 6)
        complexity_ranges = {'Low (1-5)': 0, 'Medium (6-10)': 0, 'High (11-20)': 0, 'Very High (>20)': 0}
        
        for f in self.file_metrics:
            if f.complexity <= 5:
                complexity_ranges['Low (1-5)'] += 1
            elif f.complexity <= 10:
                complexity_ranges['Medium (6-10)'] += 1
            elif f.complexity <= 20:
                complexity_ranges['High (11-20)'] += 1
            else:
                complexity_ranges['Very High (>20)'] += 1
        
        if any(complexity_ranges.values()):
            colors = ['#2ecc71', '#f39c12', '#e67e22', '#e74c3c']
            ax6.bar(complexity_ranges.keys(), complexity_ranges.values(), color=colors)
            ax6.set_ylabel('Number of Functions')
            ax6.set_title('Cyclomatic Complexity Distribution', fontweight='bold')
            ax6.set_xticklabels(complexity_ranges.keys(), rotation=45, ha='right')
            ax6.grid(axis='y', alpha=0.3)
        
        plt.tight_layout()
        plt.savefig('codebase_analysis.png', dpi=150, bbox_inches='tight')
        print("\n📊 Visualizations saved to 'codebase_analysis.png'")
        plt.show()
        
        # Create hierarchy diagram
        self._create_hierarchy_diagram()
    
    def _create_hierarchy_diagram(self):
        """Create a code hierarchy diagram."""
        fig, ax = plt.subplots(figsize=(16, 10))
        ax.set_xlim(0, 100)
        ax.set_ylim(0, 100)
        ax.axis('off')
        fig.suptitle('Trading Bot v2 - Module Hierarchy', fontsize=16, fontweight='bold')
        
        # Define hierarchy structure
        hierarchy = {
            'src': {
                'y': 85, 'width': 80, 'height': 10,
                'children': {
                    'domain': {
                        'y': 70, 'x': 10, 'width': 20, 'height': 8,
                        'items': ['entities', 'value_objects', 'events', 'ports']
                    },
                    'application': {
                        'y': 70, 'x': 35, 'width': 20, 'height': 8,
                        'items': ['commands', 'queries', 'services', 'use_cases']
                    },
                    'infrastructure': {
                        'y': 70, 'x': 60, 'width': 20, 'height': 8,
                        'items': ['database', 'exchange', 'monitoring', 'adapters']
                    }
                }
            },
            'tests': {
                'y': 50, 'width': 80, 'height': 10,
                'children': {
                    'unit': {'y': 35, 'x': 10, 'width': 15, 'height': 8},
                    'integration': {'y': 35, 'x': 30, 'width': 15, 'height': 8},
                    'e2e': {'y': 35, 'x': 50, 'width': 15, 'height': 8},
                    'property': {'y': 35, 'x': 70, 'width': 15, 'height': 8}
                }
            },
            'api': {
                'y': 20, 'width': 35, 'height': 8,
                'items': ['FastAPI', 'WebSocket', 'REST endpoints']
            },
            'web': {
                'y': 20, 'x': 45, 'width': 35, 'height': 8,
                'items': ['React Dashboard', 'Real-time Updates', 'Charts']
            }
        }
        
        # Draw main modules
        colors = {
            'src': '#3498db',
            'domain': '#e74c3c',
            'application': '#2ecc71',
            'infrastructure': '#f39c12',
            'tests': '#9b59b6',
            'api': '#1abc9c',
            'web': '#34495e'
        }
        
        # Draw src
        rect = Rectangle((10, hierarchy['src']['y']), 
                        hierarchy['src']['width'], 
                        hierarchy['src']['height'],
                        facecolor=colors['src'], alpha=0.3, edgecolor='black', linewidth=2)
        ax.add_patch(rect)
        ax.text(50, hierarchy['src']['y'] + 5, 'Source Code', 
               ha='center', va='center', fontsize=12, fontweight='bold')
        
        # Draw src children
        for name, child in hierarchy['src']['children'].items():
            rect = Rectangle((child['x'], child['y']), 
                           child['width'], child['height'],
                           facecolor=colors[name], alpha=0.5, edgecolor='black', linewidth=1)
            ax.add_patch(rect)
            ax.text(child['x'] + child['width']/2, child['y'] + child['height']/2 + 2, 
                   name.capitalize(), ha='center', va='center', fontsize=10, fontweight='bold')
            
            # Add items
            if 'items' in child:
                for i, item in enumerate(child['items']):
                    ax.text(child['x'] + child['width']/2, child['y'] - 2 - i*2, 
                           f"• {item}", ha='center', va='top', fontsize=8)
        
        # Draw tests
        rect = Rectangle((10, hierarchy['tests']['y']), 
                        hierarchy['tests']['width'], 
                        hierarchy['tests']['height'],
                        facecolor=colors['tests'], alpha=0.3, edgecolor='black', linewidth=2)
        ax.add_patch(rect)
        ax.text(50, hierarchy['tests']['y'] + 5, 'Test Suite', 
               ha='center', va='center', fontsize=12, fontweight='bold')
        
        # Draw test types
        for name, child in hierarchy['tests']['children'].items():
            rect = Rectangle((child['x'], child['y']), 
                           child['width'], child['height'],
                           facecolor=colors['tests'], alpha=0.5, edgecolor='black', linewidth=1)
            ax.add_patch(rect)
            ax.text(child['x'] + child['width']/2, child['y'] + child['height']/2, 
                   name.capitalize(), ha='center', va='center', fontsize=9)
        
        # Draw API and Web
        for module in ['api', 'web']:
            mod = hierarchy[module]
            x = mod.get('x', 10 if module == 'api' else 45)
            rect = Rectangle((x, mod['y']), 
                           mod['width'], mod['height'],
                           facecolor=colors[module], alpha=0.4, edgecolor='black', linewidth=2)
            ax.add_patch(rect)
            ax.text(x + mod['width']/2, mod['y'] + mod['height']/2 + 2, 
                   module.upper(), ha='center', va='center', fontsize=11, fontweight='bold')
            
            # Add items
            if 'items' in mod:
                for i, item in enumerate(mod['items']):
                    ax.text(x + mod['width']/2, mod['y'] - 1 - i*1.5, 
                           f"• {item}", ha='center', va='top', fontsize=8)
        
        # Add arrows showing dependencies
        # Domain -> Application
        ax.annotate('', xy=(35, 74), xytext=(30, 74),
                   arrowprops=dict(arrowstyle='->', lw=2, color='gray'))
        # Application -> Infrastructure
        ax.annotate('', xy=(60, 74), xytext=(55, 74),
                   arrowprops=dict(arrowstyle='->', lw=2, color='gray'))
        # Infrastructure -> API
        ax.annotate('', xy=(27, 28), xytext=(70, 70),
                   arrowprops=dict(arrowstyle='->', lw=2, color='gray', alpha=0.5))
        # API -> Web
        ax.annotate('', xy=(45, 24), xytext=(45, 24),
                   arrowprops=dict(arrowstyle='<->', lw=2, color='gray'))
        
        # Add legend
        ax.text(5, 5, 'Legend:', fontsize=10, fontweight='bold')
        ax.text(5, 3, '→ Dependencies', fontsize=9)
        ax.text(5, 1, '▢ Modules', fontsize=9)
        
        plt.savefig('code_hierarchy.png', dpi=150, bbox_inches='tight')
        print("📊 Hierarchy diagram saved to 'code_hierarchy.png'")
        plt.show()

def main():
    """Run the analysis."""
    analyzer = CodebaseAnalyzer('.')
    analyzer.analyze()
    
    # Generate summary JSON
    summary = {
        'total_files': len(analyzer.file_metrics),
        'total_lines': sum(f.lines_total for f in analyzer.file_metrics),
        'code_lines': sum(f.lines_code for f in analyzer.file_metrics),
        'comment_lines': sum(f.lines_comments for f in analyzer.file_metrics),
        'docstring_lines': sum(f.lines_docstrings for f in analyzer.file_metrics),
        'test_files': sum(1 for f in analyzer.file_metrics if f.test_file),
        'functions': sum(f.functions for f in analyzer.file_metrics),
        'classes': sum(f.classes for f in analyzer.file_metrics),
        'layers': {
            name: {
                'files': layer.total_files,
                'lines': layer.total_lines,
                'code': layer.code_lines,
                'tests': layer.test_files
            }
            for name, layer in analyzer.metrics.items()
        }
    }
    
    with open('codebase_metrics.json', 'w') as f:
        json.dump(summary, f, indent=2)
    
    print("\n📋 Metrics saved to 'codebase_metrics.json'")
    print("="*80)

if __name__ == '__main__':
    main()