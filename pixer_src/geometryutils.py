# GEOMETRY UTILS
# Some helper functions
from mathutils import Vector
from .utils import sign, _almost_equal


# Returns true if the segment 'p1q1' and 'p2q2' intersect
def segments_intersect(p1, q1, p2, q2):
    # Find the 4 orientations required for the general and special cases
    o1 = _orientation(p1, q1, p2)
    o2 = _orientation(p1, q1, q2)
    o3 = _orientation(p2, q2, p1)
    o4 = _orientation(p2, q2, q1)

    # General case
    if not _almost_equal(o1, o2) and not _almost_equal(o3, o4):
        return True

    # Special Cases
    # p1 , q1 and p2 are colinear and p2 lies on segment p1q1
    if _almost_equal(o1, 0.0) and _on_segment(p1, p2, q1):
        return True

    # p1 , q1 and q2 are colinear and q2 lies on segment p1q1
    if _almost_equal(o2, 0.0) and _on_segment(p1, q2, q1):
        return True

    # p2 , q2 and p1 are colinear and p1 lies on segment p2q2
    if _almost_equal(o3, 0.0) and _on_segment(p2, p1, q2):
        return True

    # p2 , q2 and q1 are colinear and q1 lies on segment p2q2
    if _almost_equal(o4, 0.0) and _on_segment(p2, q1, q2):
        return True

    # If none of the cases
    return False


# Given three colinear points p, q, r, the function checks if point q lies on line segment 'pr'
# Credits to www.geeksforgeeks.com
def _on_segment(p: Vector, q: Vector, r: Vector):
    if (q.x < max(p.x, r.x) or _almost_equal(q.x, max(p.x, r.x))) and \
            (q.x > min(p.x, r.x) or _almost_equal(q.x, min(p.x, r.x))) and \
            (q.y < max(p.y, r.y) or _almost_equal(q.y, max(p.y, r.y))) and \
            (q.y > min(p.y, r.y) or _almost_equal(q.y, min(p.y, r.y))):
        return True
    return False


# Returns the orientation of an ordered triplet (p,q,r)
# 1 : Clockwise points
# 0 : Colinear points
# -1 : Counterclockwise
# Credits to www.geeksforgeeks.com
def _orientation(p: Vector, q: Vector, r: Vector):
    return sign((float(q.y - p.y) * (r.x - q.x)) - (float(q.x - p.x) * (r.y - q.y)))


def segments_intersection_point(p1, q1, p2, q2):
    a1, b1, c1 = _get_line_parameters(p1, q1)
    a2, b2, c2 = _get_line_parameters(p2, q2)
    det = (a1 * b2) - (a2 * b1)
    if _almost_equal(det, 0.0):
        return Vector(((b2 * c1 - b1 * c2) / det, (a1 * c2 - a2 * c1) / det))
    else:
        return None


def _get_line_parameters(p1: Vector, q1: Vector):
    a = q1.y - p1.y
    b = p1.x - q1.x
    c = a * p1.x + b * p1.y
    return a, b, c
