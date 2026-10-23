class EngineError(Exception):
    """Error base del motor de cálculo."""


class MissingRuleError(EngineError):
    """No hay regla vigente para el concepto/fecha pedidos. Nunca se usa un valor por defecto."""


class MissingDataError(EngineError):
    """Falta un dato de entrada necesario para calcular."""


class RuleSetError(EngineError):
    """El RuleSet no es publicable (sin fuente, vigencias solapadas, valores inválidos)."""
