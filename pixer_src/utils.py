from mathutils import Vector


def sign(number: float):
    if number == 0:
        return 0
    else:
        return int(number/abs(number))


def equals_sign(vector_a: Vector, vector_b: Vector) -> bool:
    for i in range(3):
        if sign(vector_a[i]) != sign(vector_b[i]):
            return False
    return True


def _almost_equal_vectors(vector_a: Vector, vector_b: Vector) -> bool:
    return _almost_equal(vector_a.x, vector_b.x) and _almost_equal(vector_a.y, vector_b.y)


def _almost_equal(a: float, b: float, difference: float = 10 ** -6) -> bool:
    return abs(a - b) < difference
