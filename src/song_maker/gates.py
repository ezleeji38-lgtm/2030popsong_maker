"""검증 게이트. Gate 1~6 검증 함수, Check/GateResult 모델."""

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field
from rich.console import Console

console = Console()


class Check(BaseModel):
    """개별 검증 항목."""

    name: str
    passed: bool
    blocking: bool = True
    message: str = ""


class GateResult(BaseModel):
    """Gate 검증 결과."""

    gate: str
    checks: list[Check]
    timestamp: datetime = Field(default_factory=datetime.now)

    @property
    def passed(self) -> bool:
        return all(c.passed for c in self.checks if c.blocking)

    @property
    def warnings(self) -> list[Check]:
        return [c for c in self.checks if not c.blocking and not c.passed]

    @property
    def failures(self) -> list[Check]:
        return [c for c in self.checks if c.blocking and not c.passed]

    def to_dict(self) -> dict[str, Any]:
        """meta.json 저장용 딕셔너리."""
        return {
            "passed": self.passed,
            "timestamp": self.timestamp.isoformat(),
            "checks": [c.model_dump() for c in self.checks],
            "warnings": [c.message for c in self.warnings],
            "failures": [c.message for c in self.failures],
        }


def run_gate(result: GateResult, stage_name: str) -> bool:
    """Gate 결과를 처리하고 통과 여부를 반환한다.

    - 비차단 경고: 메시지 출력 후 진행
    - 차단 실패: 메시지 출력 후 사용자 판단 요청
    """
    for warn in result.warnings:
        console.print(f"  [yellow][경고][/yellow] {warn.message}")

    if not result.passed:
        for fail in result.failures:
            console.print(f"  [red][실패][/red] {fail.message}")
        return _handle_failure(stage_name)

    console.print(f"  [green][통과][/green] {stage_name} 검증 완료")
    return True


def _handle_failure(stage_name: str) -> bool:
    """차단 실패 시 사용자에게 재시도/중단을 묻는다."""
    import typer

    action = typer.prompt(
        f"  {stage_name} 검증 실패. 재시도(r) / 중단(q)",
        default="q",
    )
    return action.lower() == "r"
