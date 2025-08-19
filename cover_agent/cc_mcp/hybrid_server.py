"""
Hybrid Cover Agent MCP Server

This server provides Cover Agent's analysis capabilities while allowing
Cursor's internal model to handle test generation.
"""

import asyncio
import json
import os
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

# Add the project root to the path to import cover_agent modules
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

try:
    import mcp
    from mcp.server import FastMCP
    from mcp.types import TextContent, ImageContent
except ImportError:
    print("❌ MCP library not found. Please install it with: pip install mcp")
    sys.exit(1)

from cover_agent.lsp_logic.utils.utils_context import (
    initialize_language_server,
    find_test_file_context,
    analyze_context,
)
from cover_agent.lsp_logic.multilspy import LanguageServer
from cover_agent.lsp_logic.multilspy.multilspy_config import Language
from cover_agent.coverage_processor import CoverageProcessor
from cover_agent.settings.config_schema import CoverageType
from cover_agent.custom_logger import CustomLogger


class HybridCoverAgentMCPServer:
    """Hybrid MCP Server that combines Cover Agent analysis with Cursor's model"""
    
    def __init__(self):
        self.lsp_server: Optional[LanguageServer] = None
        self.project_root: Optional[str] = None
        self.project_language: str = "python"
        self.server = FastMCP("hybrid-cover-agent-mcp")
        self.logger = CustomLogger.get_logger(__name__, generate_log_files=False)
        
        # Language extension mapping
        self.language_extensions = {
            '.py': Language.PYTHON,
            '.java': Language.JAVA,
            '.js': Language.JAVASCRIPT,
            '.ts': Language.TYPESCRIPT,
            '.cs': Language.CSHARP,
            '.rs': Language.RUST,
            '.cpp': Language.CSHARP,  # Using C# LSP for C++ as fallback
            '.cc': Language.CSHARP,
            '.cxx': Language.CSHARP,
            '.c': Language.CSHARP,
            '.h': Language.CSHARP,
            '.hpp': Language.CSHARP,
        }
        
        # Test framework mapping by language
        self.test_frameworks = {
            Language.PYTHON: {'command': 'python -m pytest', 'coverage': '--cov'},
            Language.JAVA: {'command': 'mvn test', 'coverage': ''},
            Language.JAVASCRIPT: {'command': 'npm test', 'coverage': '--coverage'},
            Language.TYPESCRIPT: {'command': 'npm test', 'coverage': '--coverage'},
            Language.CSHARP: {'command': 'dotnet test', 'coverage': '--collect:"XPlat Code Coverage"'},
            Language.RUST: {'command': 'cargo test', 'coverage': ''},
        }
        
        # Register tools using decorators
        self._register_tools()
        
    def _register_tools(self):
        """Register tools using decorators"""
        print("🚀 Registering Hybrid Cover Agent MCP tools...")
        
        # Register tools using decorators
        self.server.tool(
            name="analyze_code_context",
            description="Analyze code context using LSP and provide detailed insights for test generation"
        )(self.analyze_code_context)
        
        self.server.tool(
            name="get_coverage_gaps",
            description="Get detailed coverage gaps and uncovered lines for test generation"
        )(self.get_coverage_gaps)
        
        self.server.tool(
            name="analyze_test_structure",
            description="Analyze existing test structure and identify improvement opportunities"
        )(self.analyze_test_structure)
        
        self.server.tool(
            name="get_test_generation_context",
            description="Get comprehensive context for test generation including code structure, coverage gaps, and existing tests"
        )(self.get_test_generation_context)
        
        self.server.tool(
            name="validate_test_coverage",
            description="Validate test coverage after test generation and provide improvement suggestions"
        )(self.validate_test_coverage)
        
        self.server.tool(
            name="auto_generate_tests_for_coverage",
            description="Automatically generate tests to improve coverage to target percentage"
        )(self.auto_generate_tests_for_coverage)
        
        print("✅ Hybrid MCP tools registered successfully")
    
    def _detect_language(self, file_path: str) -> Language:
        """Detect programming language from file extension."""
        file_ext = Path(file_path).suffix.lower()
        detected_language = self.language_extensions.get(file_ext, Language.PYTHON)
        print(f"🔍 Detected language: {detected_language} for file: {file_path}")
        return detected_language
    
    def _get_language_specific_patterns(self, language: Language) -> Dict[str, str]:
        """Get language-specific patterns for code analysis."""
        patterns = {
            Language.PYTHON: {
                'class': r'class\s+(\w+)',
                'function': r'def\s+(\w+)',
                'import': r'(import\s+\w+|from\s+\w+\s+import)',
            },
            Language.JAVA: {
                'class': r'(public\s+|private\s+|protected\s+)?class\s+(\w+)',
                'function': r'(public\s+|private\s+|protected\s+|static\s+)*\w+\s+(\w+)\s*\(',
                'import': r'import\s+[\w\.]+',
            },
            Language.JAVASCRIPT: {
                'class': r'class\s+(\w+)',
                'function': r'(function\s+(\w+)|(\w+)\s*:\s*function|(\w+)\s*=\s*function)',
                'import': r'(import\s+.*from|require\s*\()',
            },
            Language.TYPESCRIPT: {
                'class': r'(export\s+)?class\s+(\w+)',
                'function': r'(function\s+(\w+)|(\w+)\s*:\s*\([^)]*\)\s*=>|(\w+)\s*=\s*\([^)]*\)\s*=>)',
                'import': r'(import\s+.*from|require\s*\()',
            },
            Language.CSHARP: {
                'class': r'(public\s+|private\s+|internal\s+)?class\s+(\w+)',
                'function': r'(public\s+|private\s+|protected\s+|internal\s+|static\s+)*\w+\s+(\w+)\s*\(',
                'import': r'using\s+[\w\.]+',
            },
            Language.RUST: {
                'class': r'(pub\s+)?struct\s+(\w+)',
                'function': r'(pub\s+)?fn\s+(\w+)',
                'import': r'use\s+[\w:]+',
            }
        }
        return patterns.get(language, patterns[Language.PYTHON])
    
    def _get_cpp_patterns(self) -> Dict[str, str]:
        """Get C++ specific patterns for code analysis."""
        return {
            'class': r'class\s+(\w+)',
            'function': r'(\w+)\s+(\w+)\s*\(',
            'import': r'#include\s+[<\"][^>\"]*[>\"]',
        }
        
    async def analyze_code_context(self, source_file: str, project_root: str) -> str:
        """Analyze code context using LSP and provide detailed insights."""
        try:
            print(f"🔍 Analyzing code context for {source_file}")
            
            # Detect programming language
            detected_language = self._detect_language(source_file)
            self.project_language = str(detected_language)
            
            # Initialize LSP server if not already done
            if not self.lsp_server or self.project_root != project_root:
                args = type('Args', (), {
                    'project_root': project_root,
                    'project_language': self.project_language
                })()
                try:
                    self.lsp_server = await initialize_language_server(args)
                    self.project_root = project_root
                except Exception as e:
                    print(f"⚠️ LSP initialization failed: {e}. Continuing with basic analysis.")
                    self.lsp_server = None
            else:
                # Create args object for existing project
                args = type('Args', (), {
                    'project_root': project_root,
                    'project_language': self.project_language
                })()
            
            # Get context files (only if LSP is available)
            context_files = []
            if self.lsp_server:
                try:
                    context_files = await find_test_file_context(args, self.lsp_server, source_file)
                except Exception as e:
                    print(f"⚠️ Context file search failed: {e}")
            
            # Read source file content
            with open(source_file, 'r') as f:
                source_content = f.read()
            
            # Analyze file structure with language-specific patterns
            file_analysis = self._analyze_file_structure_multilang(source_content, source_file, detected_language)
            
            result = {
                "source_file": source_file,
                "context_files": [str(f) for f in context_files],
                "file_analysis": file_analysis,
                "project_root": project_root,
                "language": self.project_language,
                "status": "success",
                "suggestions": self._generate_context_suggestions(file_analysis, context_files)
            }
            return json.dumps(result, indent=2)
            
        except Exception as e:
            print(f"❌ Error in code context analysis: {e}")
            error_result = {
                "status": "error",
                "error": str(e)
            }
            return json.dumps(error_result, indent=2)
    
    async def get_coverage_gaps(self, source_file: str, test_file: str, project_root: str) -> str:
        """Get detailed coverage gaps and uncovered lines."""
        try:
            print(f"📊 Analyzing coverage gaps for {source_file}")
            
            # Detect language and get appropriate test command
            detected_language = self._detect_language(source_file)
            test_framework = self.test_frameworks.get(detected_language, self.test_frameworks[Language.PYTHON])
            
            # Generate language-specific test command
            coverage_report_path = os.path.join(project_root, "coverage.xml")
            
            if detected_language == Language.PYTHON:
                python_executable = sys.executable
                test_command = f"cd {project_root} && {python_executable} -m pytest {test_file} --cov=. --cov-report=xml --cov-report=term"
            elif detected_language == Language.JAVA:
                test_command = f"cd {project_root} && mvn test jacoco:report"
                coverage_report_path = os.path.join(project_root, "target/site/jacoco/jacoco.xml")
            elif detected_language in [Language.JAVASCRIPT, Language.TYPESCRIPT]:
                test_command = f"cd {project_root} && npm test -- --coverage --coverageReporters=lcov"
                coverage_report_path = os.path.join(project_root, "coverage/lcov.info")
            elif detected_language == Language.CSHARP:
                test_command = f"cd {project_root} && dotnet test --collect:\"XPlat Code Coverage\""
                coverage_report_path = os.path.join(project_root, "TestResults/*/coverage.cobertura.xml")
            elif detected_language == Language.RUST:
                test_command = f"cd {project_root} && cargo test"
                coverage_report_path = os.path.join(project_root, "target/coverage/coverage.xml")
            else:
                # Fallback to Python
                python_executable = sys.executable
                test_command = f"cd {project_root} && {python_executable} -m pytest {test_file} --cov=. --cov-report=xml --cov-report=term"
            
            # Execute test command
            import subprocess
            result = subprocess.run(test_command, shell=True, capture_output=True, text=True)
            
            if result.returncode != 0:
                error_result = {
                    "status": "error",
                    "error": f"Test execution failed: {result.stderr}"
                }
                return json.dumps(error_result, indent=2)
            
            # Process coverage report
            if os.path.exists(coverage_report_path):
                coverage_processor = CoverageProcessor(
                    file_path=coverage_report_path,
                    src_file_path=source_file,
                    coverage_type=CoverageType.XML,
                    logger=self.logger,
                    generate_log_files=False
                )
                
                # Get coverage data
                covered_lines, uncovered_lines, coverage_percentage = coverage_processor.parse_coverage_report()
                
                # Analyze uncovered lines
                uncovered_analysis = self._analyze_uncovered_lines(source_file, uncovered_lines)
                
                result = {
                    "coverage_percentage": coverage_percentage,
                    "covered_lines": covered_lines,
                    "uncovered_lines": uncovered_lines,
                    "uncovered_analysis": uncovered_analysis,
                    "source_file": source_file,
                    "test_file": test_file,
                    "status": "success",
                    "suggestions": self._generate_coverage_suggestions(uncovered_analysis, coverage_percentage)
                }
                return json.dumps(result, indent=2)
            else:
                error_result = {
                    "status": "error",
                    "error": "Coverage report not generated"
                }
                return json.dumps(error_result, indent=2)
                
        except Exception as e:
            print(f"❌ Error in coverage gap analysis: {e}")
            error_result = {
                "status": "error",
                "error": str(e)
            }
            return json.dumps(error_result, indent=2)
    
    async def analyze_test_structure(self, test_file: str, project_root: str) -> str:
        """Analyze existing test structure and identify improvement opportunities."""
        try:
            print(f"🔬 Analyzing test structure for {test_file}")
            
            if not os.path.exists(test_file):
                error_result = {
                    "status": "error",
                    "error": f"Test file {test_file} does not exist"
                }
                return json.dumps(error_result, indent=2)
            
            # Read test file
            with open(test_file, 'r') as f:
                test_content = f.read()
            
            # Analyze test structure
            test_analysis = self._analyze_test_structure(test_content, test_file)
            
            # Find source file
            source_file = self._find_source_file_for_test(test_file, project_root)
            
            result = {
                "test_file": test_file,
                "source_file": source_file,
                "test_analysis": test_analysis,
                "project_root": project_root,
                "status": "success",
                "suggestions": self._generate_test_structure_suggestions(test_analysis)
            }
            return json.dumps(result, indent=2)
            
        except Exception as e:
            print(f"❌ Error in test structure analysis: {e}")
            error_result = {
                "status": "error",
                "error": str(e)
            }
            return json.dumps(error_result, indent=2)
    
    async def get_test_generation_context(self, source_file: str, test_file: str, project_root: str) -> str:
        """Get comprehensive context for test generation."""
        try:
            print(f"🎯 Getting comprehensive test generation context for {source_file}")
            
            # Get all context information
            code_context_str = await self.analyze_code_context(source_file, project_root)
            coverage_gaps_str = await self.get_coverage_gaps(source_file, test_file, project_root)
            test_structure_str = await self.analyze_test_structure(test_file, project_root)
            
            # Parse JSON strings to dictionaries
            code_context = json.loads(code_context_str)
            coverage_gaps = json.loads(coverage_gaps_str)
            test_structure = json.loads(test_structure_str)
            
            # Combine all context
            comprehensive_context = {
                "code_context": code_context,
                "coverage_gaps": coverage_gaps,
                "test_structure": test_structure,
                "generation_guidance": self._generate_test_generation_guidance(
                    code_context, coverage_gaps, test_structure
                ),
                "status": "success"
            }
            
            return json.dumps(comprehensive_context, indent=2)
            
        except Exception as e:
            print(f"❌ Error in test generation context: {e}")
            error_result = {
                "status": "error",
                "error": str(e)
            }
            return json.dumps(error_result, indent=2)
    
    async def validate_test_coverage(self, source_file: str, test_file: str, project_root: str) -> str:
        """Validate test coverage and provide improvement suggestions."""
        try:
            print(f"✅ Validating test coverage for {source_file}")
            
            # Get current coverage
            coverage_gaps_str = await self.get_coverage_gaps(source_file, test_file, project_root)
            coverage_gaps = json.loads(coverage_gaps_str)
            
            if coverage_gaps["status"] == "error":
                return coverage_gaps_str
            
            # Analyze test quality
            test_quality = self._analyze_test_quality(test_file, source_file)
            
            result = {
                "coverage_analysis": coverage_gaps,
                "test_quality": test_quality,
                "improvement_suggestions": self._generate_improvement_suggestions(
                    coverage_gaps, test_quality
                ),
                "status": "success"
            }
            return json.dumps(result, indent=2)
            
        except Exception as e:
            print(f"❌ Error in test coverage validation: {e}")
            error_result = {
                "status": "error",
                "error": str(e)
            }
            return json.dumps(error_result, indent=2)
    
    async def auto_generate_tests_for_coverage(self, source_file: str, test_file: str, project_root: str, target_coverage: float = 90.0) -> str:
        """Automatically generate tests to improve coverage to target percentage."""
        try:
            print(f"🎯 Auto-generating tests to reach {target_coverage}% coverage for {source_file}")
            
            # Get current coverage
            coverage_gaps_str = await self.get_coverage_gaps(source_file, test_file, project_root)
            coverage_gaps = json.loads(coverage_gaps_str)
            
            if coverage_gaps["status"] == "error":
                return coverage_gaps_str
            
            current_coverage = coverage_gaps.get("coverage_percentage", 0)
            print(f"📊 Current coverage: {current_coverage}%, Target: {target_coverage}%")
            
            if current_coverage >= target_coverage:
                result = {
                    "status": "success",
                    "message": f"Target coverage {target_coverage}% already achieved (current: {current_coverage}%)",
                    "current_coverage": current_coverage,
                    "target_coverage": target_coverage,
                    "improvement": 0
                }
                return json.dumps(result, indent=2)
            
            # Get uncovered lines that need testing
            uncovered_lines = coverage_gaps.get("uncovered_lines", [])
            uncovered_analysis = coverage_gaps.get("uncovered_analysis", {})
            
            # Generate test suggestions
            test_suggestions = self._generate_test_suggestions_for_coverage(
                source_file, uncovered_lines, uncovered_analysis, current_coverage, target_coverage
            )
            
            # Create comprehensive test generation prompt
            test_generation_prompt = self._create_test_generation_prompt(
                source_file, test_file, uncovered_lines, test_suggestions
            )
            
            result = {
                "status": "success",
                "current_coverage": current_coverage,
                "target_coverage": target_coverage,
                "coverage_gap": target_coverage - current_coverage,
                "uncovered_lines_count": len(uncovered_lines),
                "test_suggestions": test_suggestions,
                "test_generation_prompt": test_generation_prompt,
                "message": f"Generated test suggestions to improve coverage from {current_coverage}% to {target_coverage}%"
            }
            
            return json.dumps(result, indent=2)
            
        except Exception as e:
            print(f"❌ Error in auto test generation: {e}")
            error_result = {
                "status": "error",
                "error": str(e)
            }
            return json.dumps(error_result, indent=2)
    
    def _generate_test_suggestions_for_coverage(self, source_file: str, uncovered_lines: List[int], 
                                              uncovered_analysis: Dict, current_coverage: float, 
                                              target_coverage: float) -> List[str]:
        """Generate specific test suggestions for uncovered lines."""
        suggestions = []
        
        # Priority 1: Test critical uncovered lines
        critical_lines = uncovered_analysis.get("critical_lines", [])
        for line in critical_lines[:5]:  # Focus on top 5 critical lines
            suggestions.append(f"Test line {line['line']}: {line['content']}")
        
        # Priority 2: Test uncovered functions
        uncovered_functions = uncovered_analysis.get("uncovered_functions", [])
        for func in uncovered_functions:
            suggestions.append(f"Add test for function: {func['name']}")
        
        # Priority 3: Test uncovered classes
        uncovered_classes = uncovered_analysis.get("uncovered_classes", [])
        for cls in uncovered_classes:
            suggestions.append(f"Add test for class: {cls['name']}")
        
        # Priority 4: Edge cases and error conditions
        suggestions.append("Add tests for edge cases and error conditions")
        suggestions.append("Add tests for boundary conditions")
        
        return suggestions
    
    def _create_test_generation_prompt(self, source_file: str, test_file: str, 
                                     uncovered_lines: List[int], test_suggestions: List[str]) -> str:
        """Create a comprehensive prompt for test generation."""
        # Detect language and provide language-specific guidance
        detected_language = self._detect_language(source_file)
        
        # Check if it's a C++ file
        file_ext = Path(source_file).suffix.lower()
        is_cpp_file = file_ext in ['.cpp', '.cc', '.cxx', '.c', '.h', '.hpp']
        
        language_guidance = {
            Language.PYTHON: {
                'framework': 'pytest',
                'imports': 'import pytest\nfrom unittest.mock import Mock, patch',
                'test_prefix': 'test_',
                'assertions': 'assert statements',
                'mocking': 'unittest.mock or pytest-mock'
            },
            Language.JAVA: {
                'framework': 'JUnit 5',
                'imports': 'import org.junit.jupiter.api.Test;\nimport static org.junit.jupiter.api.Assertions.*;',
                'test_prefix': '@Test',
                'assertions': 'assertEquals, assertTrue, assertThrows',
                'mocking': 'Mockito'
            },
            Language.JAVASCRIPT: {
                'framework': 'Jest',
                'imports': "import { test, expect, jest } from '@jest/globals';",
                'test_prefix': 'test(',
                'assertions': 'expect().toBe(), expect().toThrow()',
                'mocking': 'jest.mock() and jest.fn()'
            },
            Language.TYPESCRIPT: {
                'framework': 'Jest with TypeScript',
                'imports': "import { test, expect, jest } from '@jest/globals';",
                'test_prefix': 'test(',
                'assertions': 'expect().toBe(), expect().toThrow()',
                'mocking': 'jest.mock() and jest.fn()'
            },
            Language.CSHARP: {
                'framework': 'xUnit',
                'imports': 'using Xunit;\nusing Moq;',
                'test_prefix': '[Fact]',
                'assertions': 'Assert.Equal, Assert.True, Assert.Throws',
                'mocking': 'Moq framework'
            },
            Language.RUST: {
                'framework': 'Rust built-in test framework',
                'imports': '#[cfg(test)]\nuse super::*;',
                'test_prefix': '#[test]',
                'assertions': 'assert_eq!, assert!, panic!',
                'mocking': 'mockall crate'
            }
        }
        
        if is_cpp_file:
            lang_info = {
                'framework': 'Google Test (gtest)',
                'imports': '#include <gtest/gtest.h>\n#include <gmock/gmock.h>',
                'test_prefix': 'TEST(',
                'assertions': 'EXPECT_EQ, EXPECT_TRUE, EXPECT_THROW',
                'mocking': 'Google Mock (gmock)'
            }
            detected_language = "cpp"
        else:
            lang_info = language_guidance.get(detected_language, language_guidance[Language.PYTHON])
        
        prompt = f"""
# Test Generation Task ({detected_language.upper()})

## Source File: {source_file}
## Test File: {test_file}
## Language: {detected_language}
## Test Framework: {lang_info['framework']}

## Current Test Coverage Issues:
- Uncovered lines: {len(uncovered_lines)} lines
- Focus areas: {', '.join(test_suggestions[:3])}

## Language-Specific Requirements:
- Framework: {lang_info['framework']}
- Imports: {lang_info['imports']}
- Test prefix: {lang_info['test_prefix']}
- Assertions: {lang_info['assertions']}
- Mocking: {lang_info['mocking']}

## General Requirements:
1. Generate comprehensive test cases to cover the uncovered lines
2. Focus on critical functionality and edge cases
3. Ensure tests are well-structured and maintainable
4. Use appropriate mocking and test fixtures
5. Follow {lang_info['framework']} best practices

## Test Generation Guidelines:
- Test both happy path and error scenarios
- Include boundary condition tests
- Mock external dependencies appropriately
- Use descriptive test names
- Add proper assertions and error messages
- Follow {detected_language} coding conventions

Please generate the test code that addresses these coverage gaps using {lang_info['framework']}.
"""
        return prompt
    
    def _analyze_file_structure_multilang(self, content: str, file_path: str, language: Language) -> Dict[str, Any]:
        """Analyze file structure using language-specific patterns."""
        # Check if it's a C++ file
        file_ext = Path(file_path).suffix.lower()
        is_cpp_file = file_ext in ['.cpp', '.cc', '.cxx', '.c', '.h', '.hpp']
        
        if is_cpp_file:
            patterns = self._get_cpp_patterns()
            detected_language = "cpp"
        else:
            patterns = self._get_language_specific_patterns(language)
            detected_language = str(language)
        
        lines = content.split('\n')
        
        # Find classes, functions, imports using language-specific patterns
        classes = []
        functions = []
        imports = []
        
        import re
        
        for i, line in enumerate(lines, 1):
            stripped = line.strip()
            
            # Find imports
            if re.search(patterns['import'], stripped):
                imports.append({"line": i, "content": stripped})
            
            # Find class definitions
            class_match = re.search(patterns['class'], stripped)
            if class_match:
                class_name = class_match.group(-1) if class_match.groups() else "Unknown"
                classes.append({"line": i, "name": class_name, "content": stripped})
            
            # Find function definitions
            func_match = re.search(patterns['function'], stripped)
            if func_match:
                func_name = func_match.group(-1) if func_match.groups() else "Unknown"
                functions.append({"line": i, "name": func_name, "content": stripped})
        
        return {
            "total_lines": len(lines),
            "classes": classes,
            "functions": functions,
            "imports": imports,
            "file_type": Path(file_path).suffix,
            "language": detected_language
        }
    
    def _analyze_file_structure(self, content: str, file_path: str) -> Dict[str, Any]:
        """Analyze the structure of a source file."""
        lines = content.split('\n')
        
        # Find classes, functions, imports
        classes = []
        functions = []
        imports = []
        
        for i, line in enumerate(lines, 1):
            stripped = line.strip()
            
            # Find imports
            if stripped.startswith(('import ', 'from ')):
                imports.append({"line": i, "content": stripped})
            
            # Find class definitions
            elif stripped.startswith('class ') and ':' in stripped:
                class_name = stripped.split('class ')[1].split('(')[0].split(':')[0].strip()
                classes.append({"line": i, "name": class_name, "content": stripped})
            
            # Find function definitions
            elif stripped.startswith('def ') and ':' in stripped:
                func_name = stripped.split('def ')[1].split('(')[0].strip()
                functions.append({"line": i, "name": func_name, "content": stripped})
        
        return {
            "total_lines": len(lines),
            "classes": classes,
            "functions": functions,
            "imports": imports,
            "file_type": Path(file_path).suffix
        }
    
    def _analyze_uncovered_lines(self, source_file: str, uncovered_lines: List[int]) -> Dict[str, Any]:
        """Analyze uncovered lines to understand what needs testing."""
        try:
            with open(source_file, 'r') as f:
                lines = f.readlines()
            
            uncovered_content = []
            for line_num in uncovered_lines:
                if 0 < line_num <= len(lines):
                    line_content = lines[line_num - 1].strip()
                    if line_content and not line_content.startswith('#'):
                        uncovered_content.append({
                            "line": line_num,
                            "content": line_content
                        })
            
            return {
                "uncovered_lines": uncovered_content,
                "total_uncovered": len(uncovered_lines),
                "critical_lines": [line for line in uncovered_content if self._is_critical_line(line["content"])]
            }
        except Exception as e:
            return {"error": str(e)}
    
    def _analyze_test_structure(self, test_content: str, test_file: str) -> Dict[str, Any]:
        """Analyze the structure of existing tests."""
        lines = test_content.split('\n')
        
        test_classes = []
        test_functions = []
        
        for i, line in enumerate(lines, 1):
            stripped = line.strip()
            
            # Find test classes
            if stripped.startswith('class ') and 'Test' in stripped and ':' in stripped:
                class_name = stripped.split('class ')[1].split('(')[0].split(':')[0].strip()
                test_classes.append({"line": i, "name": class_name})
            
            # Find test functions
            elif stripped.startswith('def test_') and ':' in stripped:
                func_name = stripped.split('def ')[1].split('(')[0].strip()
                test_functions.append({"line": i, "name": func_name})
        
        return {
            "test_classes": test_classes,
            "test_functions": test_functions,
            "total_tests": len(test_functions),
            "file_type": Path(test_file).suffix
        }
    
    def _find_source_file_for_test(self, test_file: str, project_root: str) -> Optional[str]:
        """Find the source file corresponding to a test file."""
        test_path = Path(test_file)
        test_name = test_path.stem
        
        # Common patterns
        possible_names = [
            test_name.replace('test_', ''),
            test_name.replace('test_', '').replace('Test', ''),
            test_name.replace('Test', '')
        ]
        
        # Look for source files
        for name in possible_names:
            for ext in ['.py', '.js', '.ts', '.java']:
                source_file = test_path.parent.parent / f"{name}{ext}"
                if source_file.exists():
                    return str(source_file)
        
        return None
    
    def _is_critical_line(self, line_content: str) -> bool:
        """Determine if a line is critical for testing."""
        critical_patterns = [
            'if __name__ == "__main__"',
            'raise ',
            'return ',
            'assert ',
            'except ',
            'finally:',
            'with ',
            'def ',
            'class '
        ]
        
        return any(pattern in line_content for pattern in critical_patterns)
    
    def _analyze_test_quality(self, test_file: str, source_file: str) -> Dict[str, Any]:
        """Analyze the quality of existing tests."""
        try:
            with open(test_file, 'r') as f:
                test_content = f.read()
            
            # Basic quality metrics
            lines = test_content.split('\n')
            total_lines = len(lines)
            comment_lines = len([line for line in lines if line.strip().startswith('#')])
            empty_lines = len([line for line in lines if not line.strip()])
            code_lines = total_lines - comment_lines - empty_lines
            
            return {
                "total_lines": total_lines,
                "code_lines": code_lines,
                "comment_lines": comment_lines,
                "empty_lines": empty_lines,
                "test_density": code_lines / total_lines if total_lines > 0 else 0
            }
        except Exception as e:
            return {"error": str(e)}
    
    def _generate_context_suggestions(self, file_analysis: Dict, context_files: List) -> List[str]:
        """Generate suggestions based on code context analysis."""
        suggestions = []
        
        if file_analysis["classes"]:
            suggestions.append(f"Found {len(file_analysis['classes'])} classes that need testing")
        
        if file_analysis["functions"]:
            suggestions.append(f"Found {len(file_analysis['functions'])} functions that need testing")
        
        if context_files:
            suggestions.append(f"Found {len(context_files)} related files for context")
        
        return suggestions
    
    def _generate_coverage_suggestions(self, uncovered_analysis: Dict, coverage_percentage: float) -> List[str]:
        """Generate suggestions based on coverage analysis."""
        suggestions = []
        
        if coverage_percentage < 80:
            suggestions.append(f"Coverage is low ({coverage_percentage:.1f}%). Focus on critical uncovered lines.")
        
        if uncovered_analysis.get("critical_lines"):
            suggestions.append(f"Found {len(uncovered_analysis['critical_lines'])} critical uncovered lines")
        
        return suggestions
    
    def _generate_test_structure_suggestions(self, test_analysis: Dict) -> List[str]:
        """Generate suggestions based on test structure analysis."""
        suggestions = []
        
        if test_analysis["total_tests"] < 3:
            suggestions.append("Very few tests found. Consider adding more comprehensive test cases.")
        
        return suggestions
    
    def _generate_test_generation_guidance(self, code_context: Dict, coverage_gaps: Dict, test_structure: Dict) -> Dict[str, Any]:
        """Generate guidance for test generation."""
        guidance = {
            "focus_areas": [],
            "test_priorities": [],
            "suggested_approaches": []
        }
        
        # Focus on uncovered lines
        if coverage_gaps.get("status") == "success":
            uncovered = coverage_gaps.get("uncovered_analysis", {})
            if uncovered.get("critical_lines"):
                guidance["focus_areas"].extend([f"Line {line['line']}: {line['content']}" for line in uncovered["critical_lines"]])
        
        # Prioritize classes and functions
        if code_context.get("status") == "success":
            file_analysis = code_context.get("file_analysis", {})
            if file_analysis.get("classes"):
                guidance["test_priorities"].extend([f"Test class: {cls['name']}" for cls in file_analysis["classes"]])
            if file_analysis.get("functions"):
                guidance["test_priorities"].extend([f"Test function: {func['name']}" for func in file_analysis["functions"]])
        
        return guidance
    
    def _generate_improvement_suggestions(self, coverage_gaps: Dict, test_quality: Dict) -> List[str]:
        """Generate improvement suggestions."""
        suggestions = []
        
        if coverage_gaps.get("status") == "success":
            coverage_percentage = coverage_gaps.get("coverage_percentage", 0)
            if coverage_percentage < 90:
                suggestions.append(f"Increase coverage from {coverage_percentage:.1f}% to 90%+")
        
        if test_quality.get("test_density", 0) < 0.7:
            suggestions.append("Improve test density by adding more test cases")
        
        return suggestions
    
    async def run(self):
        """Run the MCP server"""
        print("🚀 Starting Hybrid Cover Agent MCP Server...")
        await self.server.run_stdio_async()


async def main():
    """Main function to run the hybrid MCP server"""
    server = HybridCoverAgentMCPServer()
    await server.run()


if __name__ == "__main__":
    asyncio.run(main())
