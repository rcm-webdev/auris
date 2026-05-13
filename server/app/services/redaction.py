from presidio_analyzer import AnalyzerEngine
from presidio_anonymizer import AnonymizerEngine
from presidio_anonymizer.entities import OperatorConfig

_analyzer = AnalyzerEngine()
_anonymizer = AnonymizerEngine()
_replace_op = {"DEFAULT": OperatorConfig("replace", {"new_value": "[REDACTED]"})}


def redact(raw_text: str) -> str:
    """Detect PHI entities with Presidio and replace all with [REDACTED].

    PHI boundary: raw_text must be discarded by the caller immediately after
    this function returns. It must never be stored, logged, or passed elsewhere.
    """
    results = _analyzer.analyze(text=raw_text, language="en")
    anonymized = _anonymizer.anonymize(
        text=raw_text,
        analyzer_results=results,
        operators=_replace_op,
    )
    return anonymized.text
