# FACE STITCHER
# This module takes care of stitching 2 faces together once their UVs are all set
from mathutils import Vector, Matrix
from math import radians, sin, cos

from .geometryutils import segments_intersect, segments_intersection_point
from .utils import _almost_equal, _almost_equal_vectors
from .xface import XFace


class StitchingError(Exception):
    pass


def stitch(xface: XFace, near: XFace, near_island_faces: [XFace]):
    common_edges = xface.get_common_edges(near)
    if not common_edges:
        raise StitchingError("These two faces do not have common edges")

    common_edge = common_edges.pop()
    if not _same_uv_edge_length(xface, common_edge[0], near, common_edge[1]):
        raise StitchingError("The UV edges of the shared edge of these 2 faces do not have the same size")

    rotation = _get_rotation_to_be_aligned(near.get_uv_edge(common_edge[1]).copy(),
                                           xface.get_uv_edge(common_edge[0]).copy())
    if rotation is None:
        raise StitchingError("There is no rotation in which these 2 UV edges are aligned")

    simulated_points = []
    for i in range(xface.get_face_length()):
        simulated_points.append(_rotate_around(xface.get_uv(i).copy(), Vector((0.0, 0.0)), radians(rotation)))
        if xface.is_inverted_against(near):
            simulated_points[i] = _rotate_around(simulated_points[i], Vector((0.0, 0.0)), radians(180.0))

    stitching_diff = Vector((0.0, 0.0))
    common_vertices = xface.get_common_vertices(near)
    for common_pair in common_vertices:
        if common_pair[0] == common_edge[0]:
            stitching_diff = near.get_uv(common_pair[1]) - simulated_points[common_edge[0]]
            break

    for i in range(xface.get_face_length()):
        simulated_points[i] = simulated_points[i] + stitching_diff

    for island_face in near_island_faces:
        if _faces_overlap_in_uv(simulated_points, island_face):
            raise StitchingError("Stitching to this face would overlap to existing faces")

    for i in range(xface.get_face_length()):
        xface.update_uv(i, simulated_points[i])


def stitch_by_vertex(xface: XFace, near: XFace, near_island_faces: [XFace]):
    if xface.get_common_edges(near):
        raise StitchingError("These two faces have a common edge they should not be stitched by vertex")

    common_vertices = xface.get_common_vertices(near)
    if not common_vertices:
        raise StitchingError("These two faces do not have a common edge nor common vertices")

    stitching_diff = near.get_uv(common_vertices[0][1]) - xface.get_uv(common_vertices[0][0])
    simulated_points = []
    for i in range(xface.get_face_length()):
        simulated_points.append(xface.get_uv(i) + stitching_diff)

    for island_face in near_island_faces:
        if _faces_overlap_in_uv(simulated_points, island_face):
            raise StitchingError("Stitching to this face would overlap to existing faces")

    for i in range(xface.get_face_length()):
        xface.update_uv(i, simulated_points[i])
    return


def _same_uv_edge_length(xface: XFace, edge_index: int, other: XFace, other_edge_index: int):
    edge = xface.get_uv_edge(edge_index)
    other_edge = other.get_uv_edge(other_edge_index)
    return _almost_equal(edge.length, other_edge.length)


def _get_rotation_to_be_aligned(vector_to_check: Vector, vector_to_rotate: Vector):
    check_vector = vector_to_check.normalized().freeze()
    for i in range(4):
        rotation = 90.0 * i
        rotation_matrix = Matrix.Rotation(radians(rotation), 2, 'Z')
        rotated_vector = vector_to_rotate.copy()
        rotated_vector.rotate(rotation_matrix)
        rotated_vector = rotated_vector.normalized().freeze()
        if _almost_equal_vectors(check_vector, rotated_vector) or _almost_equal_vectors(check_vector, -rotated_vector):
            return rotation
    return None


def _rotate_around(point_to_rotate, point_around, angle_radians):
    ptr = point_to_rotate.copy()
    pa = point_around.copy()

    s = sin(angle_radians)
    c = cos(angle_radians)

    ptr = ptr - pa

    x_new = ptr.x * c - ptr.y * s
    y_new = ptr.x * s + ptr.y * c

    ptr.x = x_new
    ptr.y = y_new

    ptr = ptr + pa

    return ptr


def _faces_overlap_in_uv(simulated_points: [Vector], xface: XFace) -> bool:
    return _are_the_same_points(simulated_points, xface.get_all_uvs()) \
           or _any_edges_intersect(simulated_points, xface.get_all_uvs()) \
           or _any_point_inside(simulated_points, xface.get_all_uvs()) \
           or _any_point_inside(xface.get_all_uvs(), simulated_points)


def _are_the_same_points(points_a: [Vector], points_b: [Vector]) -> bool:
    if len(points_a) != len(points_b):
        return False
    for point_a in points_a:
        any_match = any(_almost_equal_vectors(point_a, point_b) for point_b in points_b)
        if not any_match:
            return False
    return True


def _any_edges_intersect(points_a: [Vector], points_b: [Vector]) -> bool:
    if _get_leftmost_point_in(points_a).x > _get_rightmost_point_in(points_b).x:
        return False

    if _get_leftmost_point_in(points_b).x > _get_rightmost_point_in(points_a).x:
        return False

    if _get_botmost_point_in(points_a).y > _get_topmost_point_in(points_b).y:
        return False

    if _get_botmost_point_in(points_b).y > _get_topmost_point_in(points_a).y:
        return False

    for i in range(len(points_a)):
        curr_point_a = points_a[i]
        next_point_a = points_a[(i + 1) % (len(points_a))]
        for j in range(len(points_b)):
            curr_point_b = points_a[i]
            next_point_b = points_a[(i + 1) % (len(points_a))]
            if not _is_the_same_segment(curr_point_a, next_point_a, curr_point_b, next_point_b) and \
                    segments_intersect(curr_point_a, next_point_a, curr_point_b, next_point_b):
                return True
    return False


def _is_the_same_segment(p1: Vector, q1: Vector, p2: Vector, q2: Vector):
    return (_almost_equal_vectors(p1, p2) and _almost_equal_vectors(q1, q2)) or \
           (_almost_equal_vectors(p1, q2) and _almost_equal_vectors(p2, q1))


# Returns true if all of the points in A are inside the polygon formed by the points in B
def _all_points_inside(points_a: [Vector], points_b: [Vector]) -> bool:
    max_x = _get_rightmost_point_in(points_a + points_b).x + 1
    for i in range(len(points_a)):
        intersections = set()

        curr_point = points_a[i]
        if any(_almost_equal_vectors(curr_point, point_b) for point_b in points_b):
            continue

        next_point = Vector((max_x, curr_point.y))
        for j in range(len(points_b)):
            curr_point_b = points_b[j]
            next_point_b = points_b[(j + 1) % (len(points_b))]
            if segments_intersect(curr_point, next_point, curr_point_b, next_point_b):
                intersections.add(segments_intersection_point(curr_point, next_point, curr_point_b, next_point_b)
                                  .freeze())
        if len(intersections) % 2 == 0:
            return False
    return True


def _get_rightmost_point_in(points: [Vector]) -> Vector:
    point = points[0]
    for i in range(len(points)):
        if points[i].x > point.x or _almost_equal(points[i].x, point.x):
            point = points[i]
    return point


def _get_leftmost_point_in(points: [Vector]) -> Vector:
    point = points[0]
    for i in range(len(points)):
        if points[i].x < point.x or _almost_equal(points[i].x, point.x):
            point = points[i]
    return point


def _get_topmost_point_in(points: [Vector]) -> Vector:
    point = points[0]
    for i in range(len(points)):
        if points[i].y > point.y or _almost_equal(points[i].y, point.y):
            point = points[i]
    return point


def _get_botmost_point_in(points: [Vector]) -> Vector:
    point = points[0]
    for i in range(len(points)):
        if points[i].y < point.y or _almost_equal(points[i].y, point.y):
            point = points[i]
    return point


def _any_point_inside(points_a: [Vector], points_b: [Vector]) -> bool:
    for point_a in points_a:
        if not any(_almost_equal_vectors(point_a, point_b) for point_b in points_b) \
                and _get_winding_number(point_a, points_b):
            return True
    return False


def _get_winding_number(point: Vector, points: [Vector]):
    winding_number = 0
    for i in range(len(points)):
        curr_point = points[i]
        next_point = points[(i + 1) % len(points)]
        if curr_point.y < point.y or _almost_equal(curr_point.y, point.y):
            if next_point.y > point.y and not _almost_equal(next_point.y, point.y):
                is_left = _is_at_left(curr_point, next_point, point)
                if not _almost_equal(is_left, 0.0) and is_left > 0:
                    winding_number += 1
        else:
            if next_point.y < point.y or _almost_equal(next_point.y, point.y):
                is_left = _is_at_left(curr_point, next_point, point)
                if not _almost_equal(is_left, 0.0) and is_left < 0:
                    winding_number -= 1
    return winding_number


# _is_at_left: Tests if a point is Left|On|Right of an infinite line.
#    Input:  three points p0, p1, and p2
#    Return: >0 for p2 left of the line through p0 and p1
#            =0 for p2 on the line
#            <0 for p2 right of the line
def _is_at_left(p0: Vector, p1: Vector, p2: Vector):
    return ((p1.x - p0.x) * (p2.y - p0.y)) - ((p2.x - p0.x) * (p1.y - p0.y))

