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
