"""Porta do relógio. Seção 6.2 do SDD.

Camada de portas. Os serviços, os controladores que precisam da hora, o `CircuitBreaker` e o
`GeminiChatProvider` pedem a hora a um `Clock`, em vez de chamar `datetime.now()`. Em produção
é o `SystemClock` (`app/adapters/clock.py`); os testes passam um relógio fixo e controlam o
tempo, por exemplo para vencer uma sessão de cadastro. O domínio nem isso usa: recebe `now`
como argumento.
"""

from datetime import datetime
from typing import Protocol


class Clock(Protocol):
    """Fonte da hora atual."""

    def now(self) -> datetime:
        """Hora atual com fuso. O `SystemClock` devolve UTC.

        As regras de janela e de retenção do domínio recusam um `datetime` sem fuso.
        """
        ...
