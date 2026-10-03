import math
from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class Vec:
    """Vector 2D inmutable."""

    x: float
    y: float

    def __add__(self, other: "Vec") -> "Vec":
        return Vec(self.x + other.x, self.y + other.y)

    def __sub__(self, other: "Vec") -> "Vec":
        return Vec(self.x - other.x, self.y - other.y)

    def __mul__(self, k: float) -> "Vec":
        return Vec(self.x * k, self.y * k)

    def __neg__(self) -> "Vec":
        return Vec(-self.x, -self.y)

    # Producto punto: positivo si apuntan para el mismo lado, 0 si son
    # perpendiculares, negativo si apuntan para lados opuestos.
    def dot(self, other: "Vec") -> float:
        return self.x * other.x + self.y * other.y

    def length(self) -> float:
        return math.hypot(self.x, self.y)

    def normalized(self) -> "Vec":
        """Vector de largo 1 en la misma dirección. El vector nulo queda nulo."""
        n = self.length()
        if n == 0:
            return ZERO
        return Vec(self.x / n, self.y / n)

    def perpendicular(self) -> "Vec":
        """Rotado 90° en sentido antihorario."""
        return Vec(-self.y, self.x)


ZERO = Vec(0.0, 0.0)

#Con esto limitamos el valor entre un maximo y un minimo.
def clamp(value: float, low: float, high: float) -> float:
    return max(low, min(high, value))
