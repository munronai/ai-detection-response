"""AST Code & Syntax Context Parser for False-Positive Elimination."""

import ast
import re
import time
from typing import Any, Dict, List, Tuple
from app.domain.models import ASTAnalysisResult, SyntheticFixtureDetail

# Heuristic regex for extracting fenced code blocks from markdown prompts
CODE_BLOCK_PATTERN = re.compile(r"```([a-zA-Z0-9_\-\+]*)\n(.*?)```", re.DOTALL)

MOCK_FRAMEWORKS = {
    "unittest.mock",
    "pytest",
    "faker",
    "factory",
    "mock",
    "jest",
    "vitest",
    "sinon",
    "testify",
}

SYNTHETIC_PREFIXES = (
    "mock_",
    "fake_",
    "test_",
    "dummy_",
    "sample_",
    "temp_",
    "fixture_",
    "stub_",
    "synthetic_",
    "placeholder_",
)

SYNTHETIC_VALUE_PATTERNS = [
    re.compile(r"sk_test_[a-zA-Z0-9]+", re.IGNORECASE),
    re.compile(r"4[0-9]{3}[-\s]?[0-9]{4}[-\s]?[0-9]{4}[-\s]?[0-9]{4}"),  # Visa test cards
    re.compile(r"000-00-0000|123-45-6789|987-65-4321"),
    re.compile(r"fake[-_]token|dummy[-_]key|test[-_]secret|example\.com", re.IGNORECASE),
]


class PythonASTContextAuditor(ast.NodeVisitor):
    """Inspects Python Abstract Syntax Trees for test/mock scopes and synthetic identifiers."""

    def __init__(self):
        self.in_test_scope = False
        self.test_function_count = 0
        self.mock_imports: List[str] = []
        self.fixtures: List[SyntheticFixtureDetail] = []
        self.active_function_name = ""

    def visit_Import(self, node: ast.Import):
        for alias in node.names:
            base_mod = alias.name.split(".")[0]
            if alias.name in MOCK_FRAMEWORKS or base_mod in MOCK_FRAMEWORKS:
                self.mock_imports.append(alias.name)
        self.generic_visit(node)

    def visit_ImportFrom(self, node: ast.ImportFrom):
        if node.module:
            base_mod = node.module.split(".")[0]
            if node.module in MOCK_FRAMEWORKS or base_mod in MOCK_FRAMEWORKS:
                self.mock_imports.append(node.module)
        self.generic_visit(node)

    def visit_FunctionDef(self, node: ast.FunctionDef):
        is_test = node.name.startswith("test_") or node.name.endswith("_test") or any(
            (isinstance(d, ast.Name) and "fixture" in d.id.lower())
            or (isinstance(d, ast.Attribute) and "fixture" in d.attr.lower())
            for d in node.decorator_list
        )
        prev_scope = self.in_test_scope
        prev_fn = self.active_function_name
        if is_test:
            self.in_test_scope = True
            self.test_function_count += 1
            self.active_function_name = node.name

        self.generic_visit(node)

        self.in_test_scope = prev_scope
        self.active_function_name = prev_fn

    def visit_AsyncFunctionDef(self, node: ast.AsyncFunctionDef):
        is_test = node.name.startswith("test_") or node.name.endswith("_test")
        prev_scope = self.in_test_scope
        prev_fn = self.active_function_name
        if is_test:
            self.in_test_scope = True
            self.test_function_count += 1
            self.active_function_name = node.name

        self.generic_visit(node)

        self.in_test_scope = prev_scope
        self.active_function_name = prev_fn

    def visit_ClassDef(self, node: ast.ClassDef):
        is_test_class = node.name.startswith("Test") or node.name.endswith("Tests") or any(
            (isinstance(b, ast.Name) and "TestCase" in b.id) for b in node.bases
        )
        prev_scope = self.in_test_scope
        if is_test_class:
            self.in_test_scope = True

        self.generic_visit(node)
        self.in_test_scope = prev_scope

    def visit_Assign(self, node: ast.Assign):
        for target in node.targets:
            if isinstance(target, ast.Name):
                var_name = target.id
                var_lower = var_name.lower()

                # Check if variable name matches mock/fixture pattern
                is_mock_name = any(var_lower.startswith(p) for p in SYNTHETIC_PREFIXES)

                val_repr = ""
                is_mock_val = False
                if isinstance(node.value, ast.Constant):
                    val_repr = str(node.value.value)
                    for pat in SYNTHETIC_VALUE_PATTERNS:
                        if pat.search(val_repr):
                            is_mock_val = True
                            break

                if is_mock_name or (self.in_test_scope and (is_mock_val or "key" in var_lower or "token" in var_lower or "ssn" in var_lower)):
                    scope = "test_function" if self.in_test_scope else "mock_assignment"
                    self.fixtures.append(
                        SyntheticFixtureDetail(
                            identifier=var_name,
                            scope_type=scope,
                            value_snippet=val_repr[:24] + "..." if len(val_repr) > 24 else val_repr,
                            is_mock=True,
                        )
                    )
        self.generic_visit(node)


def extract_code_candidates(text: str) -> List[Tuple[str, str]]:
    """
    Extracts explicit code blocks (from markdown fences) or returns the entire text
    if it looks predominantly like source code.
    Returns list of (language, code_text).
    """
    matches = CODE_BLOCK_PATTERN.findall(text)
    if matches:
        return [(lang.strip() or "python", code.strip()) for lang, code in matches]

    # Heuristic: check if raw text looks like code (indentation, def/class/import/const/function keywords)
    code_indicators = ["def ", "class ", "import ", "from ", "const ", "let ", "function ", "return ", "assert "]
    if any(text.strip().startswith(ind) or f"\n{ind}" in text for ind in code_indicators):
        return [("python", text.strip())]

    return []


def parse_and_audit_code(prompt_text: str) -> ASTAnalysisResult:
    """
    Parses prompt text for code snippets and runs AST analysis to detect test fixtures
    and mock data that would cause false positives in traditional DLP / SLMs.
    """
    start_time = time.perf_counter()
    candidates = extract_code_candidates(prompt_text)

    if not candidates:
        return ASTAnalysisResult(
            has_code=False,
            ast_parsable=False,
            is_synthetic_test_fixture=False,
            confidence_penalty=1.0,
            analysis_time_ms=(time.perf_counter() - start_time) * 1000,
            reason="Natural language text (no code detected)",
        )

    primary_lang, primary_code = candidates[0]
    auditor = PythonASTContextAuditor()

    try:
        tree = ast.parse(primary_code)
        auditor.visit(tree)

        has_fixtures = len(auditor.fixtures) > 0
        in_test_env = auditor.in_test_scope or auditor.test_function_count > 0 or len(auditor.mock_imports) > 0

        # High confidence that code is a synthetic fixture / mock
        is_synthetic = (has_fixtures and in_test_env) or (auditor.test_function_count > 0 and has_fixtures)

        # 95% discount on risk if AST confirms synthetic test fixture
        penalty = 0.05 if is_synthetic else 1.0
        reason_msg = (
            f"AST verified synthetic test fixture: {len(auditor.fixtures)} mock var(s) inside {auditor.test_function_count} test fn(s)"
            if is_synthetic
            else f"AST parsed code ({primary_lang}): prod/application logic"
        )

        return ASTAnalysisResult(
            has_code=True,
            language=primary_lang,
            ast_parsable=True,
            is_synthetic_test_fixture=is_synthetic,
            test_function_count=auditor.test_function_count,
            mock_frameworks=list(set(auditor.mock_imports)),
            fixtures=auditor.fixtures,
            confidence_penalty=penalty,
            analysis_time_ms=(time.perf_counter() - start_time) * 1000,
            reason=reason_msg,
        )

    except SyntaxError:
        # Non-Python code (e.g. JS, TS, Go) or snippet fragment fallback
        is_test_scope = bool(re.search(r"\b(describe|it|test|expect|assert)\s*\(", primary_code))
        is_mock_import = bool(re.search(r"['\"](@testing-library|jest|vitest|sinon|supertest)['\"]", primary_code))
        has_mock_var = any(re.search(rf"\b{p}[a-zA-Z0-9_]*\b", primary_code) for p in SYNTHETIC_PREFIXES)

        is_synthetic = (is_test_scope and (is_mock_import or has_mock_var))
        penalty = 0.05 if is_synthetic else 1.0

        return ASTAnalysisResult(
            has_code=True,
            language=primary_lang,
            ast_parsable=False,
            is_synthetic_test_fixture=is_synthetic,
            test_function_count=1 if is_test_scope else 0,
            mock_frameworks=["js_test_framework"] if is_mock_import else [],
            fixtures=[],
            confidence_penalty=penalty,
            analysis_time_ms=(time.perf_counter() - start_time) * 1000,
            reason="Regex grammar approximation: " + ("Synthetic test scope" if is_synthetic else "Unparsed code snippet"),
        )
